# 06. deadlock wait graph 출력

## 목표

deadlock이 감지됐을 때, 각 goroutine이 어떤 채널의 send 또는 receive를 기다리는지 연결해 원인을 설명한다.

완료 조건: `checkdead`가 `fatal("all goroutines are asleep - deadlock!")`를 내기 직전에 wait graph 요약이 출력된다.

## 선행 조건

- [01_channel_id.md](01_channel_id.md) (`hchan.id`)
- [02_event_collect.md](02_event_collect.md) 권장 (평소 이벤트와 대조)

## 수정 대상 파일

- `/Users/jiseunglyeol/code/go/src/runtime/proc.go` (`checkdead`)
- `/Users/jiseunglyeol/code/go/src/runtime/chantrace.go` (wait graph 출력 헬퍼)
- 필요 시 `/Users/jiseunglyeol/code/go/src/runtime/runtime2.go` (필드 접근 확인만, 수정 최소)

## 수정사항

### 1) wait graph 헬퍼 (`chantrace.go`)

```go
func chantraceDumpWaitGraph() {
	print("chantrace wait graph begin\n")
	forEachG(func(gp *g) {
		if isSystemGoroutine(gp, false) {
			return
		}
		status := readgstatus(gp) &^ _Gscan
		if status != _Gwaiting && status != _Gpreempted {
			return
		}
		reason := gp.waitreason
		if reason != waitReasonChanSend &&
			reason != waitReasonChanReceive &&
			reason != waitReasonSynctestChanSend &&
			reason != waitReasonSynctestChanReceive {
			return
		}
		sg := gp.waiting
		if sg == nil {
			print("  G", gp.goid, " waits chan op reason=", reason, " (no sudog)\n")
			return
		}
		c := sg.c.get()
		var id uint64
		var cap uint32
		var q uint32
		dir := "recv"
		if reason == waitReasonChanSend || reason == waitReasonSynctestChanSend {
			dir = "send"
		}
		if c != nil {
			id = c.id
			cap = uint32(c.dataqsiz)
			q = uint32(c.qcount)
		}
		print("  G", gp.goid, " waits ", dir, " on chan=", id, " q=", q, "/", cap, "\n")
		if c != nil {
			// show who else is queued on the same channel (best-effort, no lock)
			print("    channel sendq/recvq heads may contend; id=", id, "\n")
		}
	})
	print("chantrace wait graph end\n")
}
```

`waitReasonSynctestChanSend` / `waitReasonSynctestChanReceive` 상수 이름은 `runtime2.go`에 정의된 실제 식별자를 확인한 뒤 맞춘다. 이름이 다르면 해당 파일의 문자열 테이블을 기준으로 고친다.

`sg.c.get()`는 `maybeTraceableChan` API다. go1.26.5 워크스페이스 기준으로 이 접근자를 사용한다.

### 2) `checkdead`에 호출 삽입

파일: `proc.go`의 `checkdead` 끝부분.

Before:

```go
	unlock(&sched.lock) // unlock so that GODEBUG=scheddetail=1 doesn't hang
	fatal("all goroutines are asleep - deadlock!")
}
```

After:

```go
	unlock(&sched.lock) // unlock so that GODEBUG=scheddetail=1 doesn't hang
	if chantraceEnabled() {
		chantraceDumpWaitGraph()
		chantraceDump() // optional: recent events for context
	} else {
		// still useful on custom toolchain even when tracing mode is off,
		// because hchan.id is always assigned in guide 01.
		chantraceDumpWaitGraph()
	}
	fatal("all goroutines are asleep - deadlock!")
}
```

기본안: deadlock 경로에서는 `GOCHANTRACE`와 무관하게 wait graph를 출력한다. ID는 가이드 01에서 항상 할당되기 때문이다. 이벤트 dump만 모드를 따른다.

`forEachG` / `readgstatus` / `isSystemGoroutine`는 이미 `checkdead`가 쓰는 심볼이므로 import 추가는 없다.

### 3) 채널 대기열 요약 (선택, 권장)

같은 채널에 send 대기와 recv 대기가 동시에 쌓인 비정상 상태는 기존 invariant상 거의 없지만, “모두 send만 대기” 같은 전형적인 deadlock은 아래처럼 채널 단위로 묶으면 읽기 쉽다.

```go
func chantraceDumpWaitGraph() {
	print("chantrace wait graph begin\n")
	print("digraph chanwait {\n")
	forEachG(func(gp *g) {
		// ... same filters ...
		c := sg.c.get()
		if c == nil {
			return
		}
		if reason == waitReasonChanSend || reason == waitReasonSynctestChanSend {
			print("  G", gp.goid, " -> C", c.id, " [label=\"wait send\"];\n")
		} else {
			print("  C", c.id, " -> G", gp.goid, " [label=\"wait recv\"];\n")
		}
	})
	print("}\n")
	print("chantrace wait graph end\n")
}
```

텍스트 목록과 DOT 중 하나만 출력해도 된다. 이 가이드는 텍스트 목록을 필수, DOT를 선택으로 둔다.

### 4) lock 규칙

`checkdead`는 진입 시 `sched.lock`을 잡은 상태다. 기존 코드는 `fatal` 전에 `unlock(&sched.lock)`을 수행한다. wait graph 출력은 unlock 이후에 둔다. 채널 `hchan.lock`은 잡지 않는다. deadlock 순간에는 세상이 멈춘 상태에 가깝지만, lock 순서 문제를 피하기 위해 best-effort 읽기만 한다.

## 검증 방법

의도적 deadlock 샘플을 `/Users/jiseunglyeol/code/chan-tracer-test/main.go`에 둔다.

```go
package main

func main() {
	ch := make(chan int)
	go func() {
		ch <- 1 // waits forever for receiver
	}()
	ch <- 2 // main also waits forever for receiver
}
```

또는 상호 대기(같은 `main.go`로 교체):

```go
package main

func main() {
	a := make(chan int)
	b := make(chan int)
	go func() {
		<-a
		b <- 1
	}()
	<-b
	a <- 1
}
```

런타임 수정 후 툴체인을 다시 빌드한 뒤 실행한다.

```bash
cd /Users/jiseunglyeol/code/go/src
./make.bash

cd /Users/jiseunglyeol/code/chan-tracer-test
export GOTOOLCHAIN=local
GOCHANTRACE=on /Users/jiseunglyeol/code/go/bin/go run .
# expect non-zero exit after deadlock message
```

## 기대 결과

첫 번째 샘플 기준 예시:

```text
chantrace wait graph begin
  G1 waits send on chan=1 q=0/0
  G2 waits send on chan=1 q=0/0
chantrace wait graph end
fatal error: all goroutines are asleep - deadlock!
```

상호 대기 샘플:

```text
chantrace wait graph begin
  G1 waits recv on chan=2 q=0/0
  G2 waits recv on chan=1 q=0/0
chantrace wait graph end
```

가이드 05의 관계 그래프와 달리, 여기서의 화살표는 “통신 완료”가 아니라 “대기 중”이다.

## 주의사항

- `fatal` 메시지 자체는 유지한다. wait graph는 부가 정보다.
- `gp.waiting`이 select 중이면 sudog 리스트일 수 있다. 1차에서는 `gp.waiting` 헤드의 채널만 출력한다. 전체 select case 순회는 비범위다.
- timer / time.Sleep만으로 막힌 경우는 채널 wait reason이 아니므로 이 그래프에 안 나온다. 기존 deadlock 감지 동작은 그대로다.
- `c.id == 0`이면 가이드 01이 빠졌거나 오래된 채널이다. 그 경우 포인터 주소 출력은 하지 않고 `chan=0`으로 둔다.
- race detector 빌드와 동시 검증은 나중 단계로 미룬다.
