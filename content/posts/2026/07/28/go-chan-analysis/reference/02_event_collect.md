# 02. send / recv / close 이벤트 수집

## 목표

어떤 goroutine이 어느 채널에 send, receive, close를 수행했는지 고정 크기 이벤트로 기록한다.

완료 조건: 동일 `chanID`로 create/send/recv/close가 ring에 남고, dump 시 시간순으로 출력된다.

## 선행 조건

- [01_channel_id.md](01_channel_id.md) 완료 (`hchan.id`, `chantrace.go` 골격, `chantraceRecord`)

## 수정 대상 파일

- `/Users/jiseunglyeol/code/go/src/runtime/chan.go` (`chansend`, `chanrecv`, `closechan`)
- `/Users/jiseunglyeol/code/go/src/runtime/chantrace.go` (dump 연결용 헬퍼 보강)
- `/Users/jiseunglyeol/code/go/src/runtime/proc.go` (프로세스 종료 시 dump 호출, 선택)

## 수정사항

### 1) 기록 헬퍼 추가 (`chantrace.go`)

가이드 01의 `chantraceRecord`를 그대로 쓰고, 호출부에서 반복을 줄이려면 아래 헬퍼를 추가한다.

```go
//go:nosplit
func chantraceGoid() uint64 {
	gp := getg()
	if gp.m != nil && gp.m.curg != nil {
		gp = gp.m.curg
	}
	return gp.goid
}

//go:nosplit
func chantraceRecordOp(kind chanEventKind, c *hchan, blockedNS int64) {
	if c == nil || !chantraceEnabled() {
		return
	}
	chantraceRecord(chanEvent{
		kind:      kind,
		chanID:    c.id,
		goid:      chantraceGoid(),
		qcount:    uint32(c.qcount),
		dataqsiz:  uint32(c.dataqsiz),
		blockedNS: blockedNS,
	})
}
```

`qcount`를 읽을 때는 가능하면 `c.lock`을 이미 잡은 분기에서 호출한다. unlock 이후에는 값이 바뀌어 있어도 “완료 직후 스냅샷”으로 취급한다.

### 2) `chansend`에 send 이벤트 삽입

파일: `chan.go` / `chansend`.

기록 위치는 “전송이 실제로 끝난 시점”이다. block 대기 시간(`blockedNS`)은 가이드 03에서 채우므로, 지금은 `0`을 넘긴다.

#### (A) waiting receiver에게 직접 전달

`send(c, sg, ep, ...)` 호출 직후, `return true` 전:

```go
	if sg := c.recvq.dequeue(); sg != nil {
		send(c, sg, ep, func() { unlock(&c.lock) }, 3)
		chantraceRecordOp(chanEvSend, c, 0)
		return true
	}
```

참고: `send`가 이미 unlock한다. unlock 뒤 `c.qcount`는 대략적 스냅샷이다. 더 정확한 값을 원하면 `send` 호출 전에 `qc := c.qcount`를 캡처해 헬퍼에 넘기도록 시그니처를 확장한다.

권장(캡처형):

```go
	if sg := c.recvq.dequeue(); sg != nil {
		qc := c.qcount
		ds := c.dataqsiz
		id := c.id
		send(c, sg, ep, func() { unlock(&c.lock) }, 3)
		if chantraceEnabled() {
			chantraceRecord(chanEvent{
				kind:     chanEvSend,
				chanID:   id,
				goid:     chantraceGoid(),
				qcount:   uint32(qc),
				dataqsiz: uint32(ds),
			})
		}
		return true
	}
```



#### (B) 버퍼에 enqueue

```go
	if c.qcount < c.dataqsiz {
		qp := chanbuf(c, c.sendx)
		// ... typedmemmove, sendx++, qcount++ ...
		if chantraceEnabled() {
			chantraceRecord(chanEvent{
				kind:     chanEvSend,
				chanID:   c.id,
				goid:     chantraceGoid(),
				qcount:   uint32(c.qcount),
				dataqsiz: uint32(c.dataqsiz),
			})
		}
		unlock(&c.lock)
		return true
	}
```



#### (C) block 후 wake

`releaseSudog` 직전, 성공 반환 경로:

```go
	mysg.c.set(nil)
	releaseSudog(mysg)
	if closed {
		// panic path: send on closed channel
		// ...
	}
	chantraceRecordOp(chanEvSend, c, 0) // blockedNS는 03에서 교체
	return true
```

non-blocking 실패(`return false`)와 `send on closed channel` panic 경로는 1차에서 기록하지 않아도 된다. 필요하면 이후 `chanEvSendFail`을 추가한다.

### 3) `chanrecv`에 recv 이벤트 삽입



#### (A) waiting sender에서 수신

```go
		if sg := c.sendq.dequeue(); sg != nil {
			qc := c.qcount
			ds := c.dataqsiz
			id := c.id
			recv(c, sg, ep, func() { unlock(&c.lock) }, 3)
			if chantraceEnabled() {
				chantraceRecord(chanEvent{
					kind:     chanEvRecv,
					chanID:   id,
					goid:     chantraceGoid(),
					qcount:   uint32(qc),
					dataqsiz: uint32(ds),
				})
			}
			return true, true
		}
```



#### (B) 버퍼에서 수신

```go
	if c.qcount > 0 {
		// ... typedmemmove, recvx++, qcount-- ...
		if chantraceEnabled() {
			chantraceRecord(chanEvent{
				kind:     chanEvRecv,
				chanID:   c.id,
				goid:     chantraceGoid(),
				qcount:   uint32(c.qcount),
				dataqsiz: uint32(c.dataqsiz),
			})
		}
		unlock(&c.lock)
		return true, true
	}
```



#### (C) closed empty 수신

```go
		if c.qcount == 0 {
			if raceenabled {
				raceacquire(c.raceaddr())
			}
			id := c.id
			ds := c.dataqsiz
			unlock(&c.lock)
			if ep != nil {
				typedmemclr(c.elemtype, ep)
			}
			if chantraceEnabled() {
				chantraceRecord(chanEvent{
					kind:     chanEvRecv,
					chanID:   id,
					goid:     chantraceGoid(),
					qcount:   0,
					dataqsiz: uint32(ds),
				})
			}
			return true, false
		}
```



#### (D) block 후 wake

```go
	success := mysg.success
	gp.param = nil
	mysg.c.set(nil)
	releaseSudog(mysg)
	chantraceRecordOp(chanEvRecv, c, 0)
	return true, success
```



### 4) `closechan`에 close 이벤트 삽입

`c.closed = 1` 직후, waiter를 깨우기 전에 기록한다. 이 시점에는 아직 `c.lock`을 잡고 있다.

```go
	c.closed = 1
	if chantraceEnabled() {
		chantraceRecord(chanEvent{
			kind:     chanEvClose,
			chanID:   c.id,
			goid:     chantraceGoid(),
			qcount:   uint32(c.qcount),
			dataqsiz: uint32(c.dataqsiz),
		})
	}
```


## 후기
gmp관계를 코드랑 합쳐서 설명하는게 필요할듯
chansend/chanrecv에 다양하 이벤트를 기록했는데 
블로그에서 분석한걸 토대로 합치는 작업이 필요해 보임
지금은 채널이 사용된거에 대해 로그를 남기는 코드를 연결했음 