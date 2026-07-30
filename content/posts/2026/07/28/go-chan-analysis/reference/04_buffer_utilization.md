# 04. 채널 buffer 사용률 측정

## 목표

`qcount / dataqsiz`를 바탕으로 채널별 현재, 평균, 최대 버퍼 점유율을 계산한다.

완료 조건: dump 시 buffered 채널에 `util cur/avg/max`가 출력되고, unbuffered(`dataqsiz==0`)는 `n/a`로 표시된다.

## 선행 조건

- [01_channel_id.md](01_channel_id.md)
- [02_event_collect.md](02_event_collect.md)
- [03_blocking_time.md](03_blocking_time.md)는 필수는 아니지만, 같은 dump 경로를 쓰므로 함께 두는 것을 권장한다.

## 수정 대상 파일

- `/Users/jiseunglyeol/code/go/src/runtime/chantrace.go` (집계와 dump)
- `/Users/jiseunglyeol/code/go/src/runtime/chan.go` (이벤트에 `qcount`/`dataqsiz`가 이미 들어가는지 확인)

## 수정사항

가이드 02에서 send/recv 이벤트에 이미 `qcount`와 `dataqsiz`를 넣고 있다. 이 단계의 핵심은 dump 시점 집계다. hot path에는 합계 갱신을 넣지 않는 것을 기본으로 한다.

### 1) 집계용 고정 테이블

`chantrace.go`에 채널별 요약 슬롯을 둔다. ID 공간이 커질 수 있으므로 “최근 관측된 채널”만 담는 고정 배열을 쓴다.

```go
const chantraceStatSlots = 1024

type chanUtilStat struct {
	id      uint64
	cap     uint32
	samples uint64
	sumQ    uint64
	maxQ    uint32
	lastQ   uint32
	used    bool
}

var chantraceStats [chantraceStatSlots]chanUtilStat

func chantraceStatIndex(id uint64) int {
	// simple open addressing; dump-time only is also fine
	return int(id % uint64(chantraceStatSlots))
}

func chantraceNoteUtil(id uint64, qcount, dataqsiz uint32) {
	if dataqsiz == 0 || id == 0 {
		return
	}
	idx := chantraceStatIndex(id)
	st := &chantraceStats[idx]
	if st.used && st.id != id {
		// collision: keep existing; acceptable for v1
		return
	}
	if !st.used {
		st.used = true
		st.id = id
		st.cap = dataqsiz
	}
	st.samples++
	st.sumQ += uint64(qcount)
	st.lastQ = qcount
	if qcount > st.maxQ {
		st.maxQ = qcount
	}
}
```

### 2) 집계 호출 시점 선택

두 가지 중 하나를 고른다. 이 가이드는 A를 기본으로 한다.

#### A) dump 시 ring을 다시 스캔 (권장)

hot path 변화 없음. `chantraceDump` 시작 시 stats를 초기화하고 이벤트를 스캔한다.

```go
func chantraceDump() {
	if !chantraceEnabled() {
		return
	}
	for i := range chantraceStats {
		chantraceStats[i] = chanUtilStat{}
	}

	n := chantraceRingPos.Load()
	start := uint64(0)
	if n > uint64(chantraceRingSize) {
		start = n - uint64(chantraceRingSize)
	}
	print("chantrace dump begin n=", n, "\n")
	for i := start; i < n; i++ {
		ev := chantraceRing[i%uint64(chantraceRingSize)]
		// existing per-event print ...
		switch ev.kind {
		case chanEvSend, chanEvRecv, chanEvCreate, chanEvClose:
			chantraceNoteUtil(ev.chanID, ev.qcount, ev.dataqsiz)
		}
	}
	print("chantrace util summary\n")
	for i := range chantraceStats {
		st := &chantraceStats[i]
		if !st.used || st.cap == 0 {
			continue
		}
		avgNum := st.sumQ
		avgDen := st.samples
		if avgDen == 0 {
			continue
		}
		// print as fixed-point *100 for percent without float fmt
		curPct := (uint64(st.lastQ) * 100) / uint64(st.cap)
		avgPct := (avgNum * 100) / (avgDen * uint64(st.cap))
		maxPct := (uint64(st.maxQ) * 100) / uint64(st.cap)
		print("chan id=", st.id, " util cur=", curPct, "% avg=", avgPct, "% max=", maxPct, "%",
			" q=", st.lastQ, "/", st.cap, "\n")
	}

	// unbuffered channels seen in ring
	for i := start; i < n; i++ {
		ev := chantraceRing[i%uint64(chantraceRingSize)]
		if ev.dataqsiz == 0 && ev.chanID != 0 && ev.kind == chanEvCreate {
			print("chan id=", ev.chanID, " util n/a (unbuffered)\n")
		}
	}
	print("chantrace dump end\n")
}
```

#### B) hot path에서 즉시 갱신

`chantraceRecord` 끝에서 `chantraceNoteUtil`을 호출한다. 구현은 단순하지만 경쟁과 충돌 처리가 생기고, 기획서의 “hot path는 가볍게” 원칙에 덜 맞다. v1에서는 A를 사용한다.

### 3) create 이벤트의 capacity

가이드 01 create 기록에 `dataqsiz`를 넣고 `qcount=0`으로 둔다. util 요약에서 create만 있는 채널도 `cap`을 알 수 있다.

send/recv 직후 `qcount`는 “연산 반영 후” 값을 넣는 것을 일관되게 유지한다.

| 연산 | 기록할 qcount |
|---|---|
| buffer send 성공 | 증가 후 값 |
| buffer recv 성공 | 감소 후 값 |
| direct send/recv (대기자 handoff) | unlock 전 스냅샷 (보통 0에 가까움) |
| create | 0 |
| close | 당시 qcount |

### 4) 퍼센트 출력 대안

소수 둘째 자리까지 필요하면 정수 스케일만 쓴다.

```go
// cur = lastQ/cap -> print cur_x10000 so 5000 means 0.50
curX10000 := (uint64(st.lastQ) * 10000) / uint64(st.cap)
print("chan id=", st.id, " util cur=", curX10000/100, ".", (curX10000/10)%10, (curX10000%10),
	" avg=...", " max=...", "\n")
```

기대 결과 예시 형식은 `cur=0.50` 형태를 목표로 한다.

## 검증 방법

`/Users/jiseunglyeol/code/chan-tracer-test/main.go`에 둔다.

```go
package main

func main() {
	ch := make(chan int, 4)
	ch <- 1
	ch <- 2
	<-ch
	// qcount should be 1 / 4 at last recv after send×2 recv×1
	close(ch)

	u := make(chan int) // unbuffered
	close(u)
}
```

더 명확한 점유율 확인도 같은 `main.go`로 바꿔 다시 빌드한다.

```go
package main

func main() {
	ch := make(chan int, 2)
	ch <- 1
	ch <- 2 // full: 2/2
	<-ch     // 1/2
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

## 기대 결과

```text
chantrace dump begin n=...
chan create id=1 cap=2 goid=1
chan send id=1 goid=1 q=1/2 blocked_ns=0
chan send id=1 goid=1 q=2/2 blocked_ns=0
chan recv id=1 goid=1 q=1/2 blocked_ns=0
chantrace util summary
chan id=1 util cur=0.50 avg=0.66 max=1.00 q=1/2
chan id=2 util n/a (unbuffered)
chantrace dump end
```

`avg`는 ring에 남은 send/recv/create 샘플의 산술 평균이다. ring이 wrap되면 최근 창만 반영된다.

## 주의사항

- `dataqsiz == 0`으로 나누지 않는다. unbuffered는 항상 `n/a`다.
- float 포맷팅 패키지를 runtime에 끌어들이지 않는다. 정수 연산으로 비율을 만든다.
- util 집계는 dump 시에만 수행한다. send/recv hot path에 통계 lock을 추가하지 않는다.
- 슬롯 충돌 시 일부 채널이 요약에서 빠질 수 있다. v1 한계로 문서화하고, 필요하면 슬롯 수를 늘다.
- timer channel도 `dataqsiz > 0`이면 수치상 집계될 수 있다. 1차에서는 필터하지 않아도 되지만, `c.timer != nil` create를 건너뛰는 옵션을 나중에 넣을 수 있다.
