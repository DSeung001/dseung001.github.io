# 03. blocking time 측정

## 목표

send와 receive가 `gopark`로 대기한 구간의 시작과 종료 시각을 기록해, 채널 병목 시간을 나노초 단위로 계산한다.

완료 조건: block된 경로의 이벤트에 `blocked_ns > 0`이 채워지고, 버퍼/직접 전달로 즉시 끝난 경로는 `blocked_ns=0`이다.

## 선행 조건

- [01_channel_id.md](01_channel_id.md)
- [02_event_collect.md](02_event_collect.md)

## 수정 대상 파일

- `/Users/jiseunglyeol/code/go/src/runtime/chan.go` (`chansend`, `chanrecv`의 park/unpark 구간)
- `/Users/jiseunglyeol/code/go/src/runtime/chantrace.go` (필요 시 헬퍼 시그니처만 확인)

## 수정사항

기존 런타임은 `blockprofilerate > 0`일 때 `cputicks()`로 block profile을 남긴다. chantrace는 이와 별도로 `nanotime()`을 쓴다. block profile 설정과 무관하게 추적 모드만으로 동작해야 한다.

### 1) `chansend` block 경로

대상 구간: 버퍼가 가득 차서 `gopark`하는 부분 (대략 `c.sendq.enqueue` 전후).

Before (핵심만):

```go
	gp := getg()
	mysg := acquireSudog()
	mysg.releasetime = 0
	if t0 != 0 {
		mysg.releasetime = -1
	}
	// ... enqueue ...
	gopark(chanparkcommit, unsafe.Pointer(&c.lock), reason, traceBlockChanSend, 2)
	// ... wakeup ...
	if mysg.releasetime > 0 {
		blockevent(mysg.releasetime-t0, 2)
	}
	mysg.c.set(nil)
	releaseSudog(mysg)
	if closed {
		// panic
	}
	chantraceRecordOp(chanEvSend, c, 0)
	return true
```

After:

```go
	gp := getg()
	mysg := acquireSudog()
	mysg.releasetime = 0
	if t0 != 0 {
		mysg.releasetime = -1
	}
	// ... enqueue, parkingOnChan ...

	var blockStart int64
	if chantraceEnabled() {
		blockStart = nanotime()
	}
	gopark(chanparkcommit, unsafe.Pointer(&c.lock), reason, traceBlockChanSend, 2)

	// someone woke us up.
	// ... waiting list checks ...
	var blockedNS int64
	if blockStart != 0 {
		blockedNS = nanotime() - blockStart
		if blockedNS < 0 {
			blockedNS = 0
		}
	}
	if mysg.releasetime > 0 {
		blockevent(mysg.releasetime-t0, 2)
	}
	mysg.c.set(nil)
	releaseSudog(mysg)
	if closed {
		if c.closed == 0 {
			throw("chansend: spurious wakeup")
		}
		panic(plainError("send on closed channel"))
	}
	if chantraceEnabled() {
		chantraceRecord(chanEvent{
			kind:      chanEvSend,
			chanID:    c.id,
			goid:      chantraceGoid(),
			qcount:    uint32(c.qcount),
			dataqsiz:  uint32(c.dataqsiz),
			blockedNS: blockedNS,
		})
	}
	return true
```

즉시 완료 경로(A: direct send, B: buffer enqueue)는 가이드 02대로 `blockedNS: 0`을 유지한다.

### 2) `chanrecv` block 경로

대상 구간: 버퍼가 비어 `gopark`하는 부분.

```go
	var blockStart int64
	if chantraceEnabled() {
		blockStart = nanotime()
	}
	gopark(chanparkcommit, unsafe.Pointer(&c.lock), reason, traceBlockChanRecv, 2)

	// someone woke us up
	// ... mysg checks, timer unblock ...
	var blockedNS int64
	if blockStart != 0 {
		blockedNS = nanotime() - blockStart
		if blockedNS < 0 {
			blockedNS = 0
		}
	}
	if mysg.releasetime > 0 {
		blockevent(mysg.releasetime-t0, 2)
	}
	success := mysg.success
	gp.param = nil
	mysg.c.set(nil)
	releaseSudog(mysg)
	if chantraceEnabled() {
		chantraceRecord(chanEvent{
			kind:      chanEvRecv,
			chanID:    c.id,
			goid:      chantraceGoid(),
			qcount:    uint32(c.qcount),
			dataqsiz:  uint32(c.dataqsiz),
			blockedNS: blockedNS,
		})
	}
	return true, success
```

가이드 02에서 이미 `chantraceRecordOp(chanEvRecv, c, 0)`를 넣었다면 `blockedNS`를 넘기도록 교체한다.

### 3) dump 출력 형식

가이드 01의 dump는 이미 `blocked_ns=`를 출력한다. 추가 수정은 필요 없다.

집계를 보강하려면 `chantraceDump` 끝에 채널별 합계를 넣을 수 있다.

```go
	// optional summary after event list
	// per-chan blocked send/recv totals accumulated while scanning the ring
	print("chantrace block summary id=", id, " send_block_ns=", sendSum, " recv_block_ns=", recvSum, "\n")
```

고정 크기 배열(예: 최근 4096개 채널 ID 버킷)만 쓰고, `map`은 쓰지 않는다. runtime에서 일반 `map` 할당은 가능하지만 hot path 밖이어도 단순 배열 스캔이 안전하다.

## 검증 방법

의도적으로 block을 만든다. `/Users/jiseunglyeol/code/chan-tracer-test/main.go`에 둔다.

```go
package main

import "time"

func main() {
	ch := make(chan int) // unbuffered
	go func() {
		time.Sleep(50 * time.Millisecond)
		ch <- 1
	}()
	<-ch
}
```

런타임 수정 후 툴체인을 다시 빌드한 뒤 실행한다.

```bash
cd /Users/jiseunglyeol/code/go/src
./make.bash

cd /Users/jiseunglyeol/code/chan-tracer-test
export GOTOOLCHAIN=local
GOCHANTRACE=on /Users/jiseunglyeol/code/go/bin/go run .
```

대조군(즉시 완료)도 같은 `main.go`로 바꿔 다시 빌드한다.

```go
package main

func main() {
	ch := make(chan int, 1)
	ch <- 1
	<-ch
}
```

## 기대 결과

block 샘플:

```text
chan create id=1 cap=0 goid=1
chan send id=1 goid=2 q=0/0 blocked_ns=0
chan recv id=1 goid=1 q=0/0 blocked_ns=51234567
```

또는 send가 먼저 block된 구조에서는 send 쪽에 큰 `blocked_ns`가 붙는다. 절대값은 스케줄링에 따라 달라지며, `time.Sleep(50ms)` 근처면 대략 `4e7`~`6e7`ns 수준이면 충분하다.

즉시 완료 샘플:

```text
chan send id=1 goid=1 q=1/1 blocked_ns=0
chan recv id=1 goid=1 q=0/1 blocked_ns=0
```

## 주의사항

- `nanotime()`은 `gopark` 직전과 wake 직후에만 호출한다. lock을 잡은 채 긴 계산을 하지 않는다.
- `blockStart`는 스택 지역 변수로 둔다. `sudog`에 필드를 추가하지 않는다. sudog 레이아웃 변경은 파급이 크다.
- 기존 `cputicks`/`blockevent` 경로는 그대로 둔다. chantrace가 block profile을 대체하지 않는다.
- closed channel로 wake되어 panic하는 send는 이벤트에 `blockedNS`를 남겨도 되고, panic 전이라 생략해도 된다. 이 가이드는 panic 경로에서는 기록하지 않는다.
- synctest bubble 채널도 같은 계측을 타지만, bubble 전용 시각 모델은 다루지 않는다.
