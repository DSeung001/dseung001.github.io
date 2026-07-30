# 07. 공식 Go와 benchmark 비교

## 목표

추적 비활성, 전체 추적, 샘플링 모드에서 실행 시간과 메모리 오버헤드를 공식 Go와 커스텀 Go로 비교해 수치로 남긴다.

완료 조건: 동일 벤치 바이너리를 세 모드와 두 툴체인 조합으로 돌려, 시간(ns/op)과 할당(B/op, allocs/op) 비교표를 채울 수 있다.

## 선행 조건

- [01_channel_id.md](01_channel_id.md) ~ [04_buffer_utilization.md](04_buffer_utilization.md)까지 적용된 커스텀 툴체인
- 시스템 Go `go1.26.5`와 커스텀 Go 경로 분리 (기획서 6절)

## 수정 대상 파일

이 단계는 런타임 기능 추가보다 측정 절차가 중심이다.

- 벤치 코드: `/Users/jiseunglyeol/code/chan-tracer-test/chantrace_bench_test.go` (생성 권장)
- 선택 런타임 조정: dump가 `exit`마다 돌면 벤치 결과를 오염시키므로, 벤치 중에는 dump를 끄거나 `GOCHANTRACE_DUMP=0` 가드를 둔다

### dump 가드 (권장 런타임 소패치)

`chantrace.go`:

```go
var chantraceDumpOnExit uint32 // 1 = dump on exit

func chantraceInit() {
	// ... existing GOCHANTRACE parse ...
	if gogetenv("GOCHANTRACE_DUMP") == "0" {
		atomic.Store(&chantraceDumpOnExit, 0)
	} else if chantraceEnabled() {
		atomic.Store(&chantraceDumpOnExit, 1)
	}
}

func chantraceMaybeDumpOnExit() {
	if atomic.Load(&chantraceDumpOnExit) != 0 {
		chantraceDump()
	}
}
```

exit 훅에서는 `chantraceDump()` 대신 `chantraceMaybeDumpOnExit()`를 호출한다.

## 수정사항

### 1) 벤치 샘플

`/Users/jiseunglyeol/code/chan-tracer-test/chantrace_bench_test.go`:

```go
package chanbench

import "testing"

func BenchmarkUnbufferedPingPong(b *testing.B) {
	ch := make(chan int)
	go func() {
		for x := range ch {
			ch <- x
		}
	}()
	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		ch <- i
		<-ch
	}
	b.StopTimer()
	close(ch)
}

func BenchmarkBufferedSendRecv(b *testing.B) {
	ch := make(chan int, 64)
	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		ch <- i
		<-ch
	}
}

func BenchmarkFanOutFanIn(b *testing.B) {
	const workers = 4
	in := make(chan int, workers)
	out := make(chan int, workers)
	for w := 0; w < workers; w++ {
		go func() {
			for x := range in {
				out <- x * 2
			}
		}()
	}
	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		in <- i
		<-out
	}
	b.StopTimer()
	close(in)
}
```

### 2) 실행 매트릭스

툴체인:

| 이름 | 경로 |
|---|---|
| 시스템 Go | `~/sdk/go1.26.5/bin/go` 또는 `go` (버전이 go1.26.5인지 확인) |
| 커스텀 Go | `/Users/jiseunglyeol/code/go/bin/go` |

모드 (커스텀만 의미 있음. 시스템 Go는 추적 코드가 없으므로 baseline):

| 모드 | 환경변수 |
|---|---|
| off | `GOCHANTRACE=off GOCHANTRACE_DUMP=0` |
| on | `GOCHANTRACE=on GOCHANTRACE_DUMP=0` |
| sample | `GOCHANTRACE=sample GOCHANTRACE_DUMP=0` |

명령 예시:

`/Users/jiseunglyeol/code/go/bin/go`가 없으면 먼저 툴체인을 빌드한다.

```bash
cd /Users/jiseunglyeol/code/go/src
./make.bash
/Users/jiseunglyeol/code/go/bin/go version

cd /Users/jiseunglyeol/code/chan-tracer-test

# 시스템 Go baseline
go version
go test -bench='BenchmarkUnbufferedPingPong|BenchmarkBufferedSendRecv|BenchmarkFanOutFanIn' \
  -benchmem -count=5 . | tee /tmp/bench_system.txt

# 커스텀 Go — off
export GOTOOLCHAIN=local
GOCHANTRACE=off GOCHANTRACE_DUMP=0 \
  /Users/jiseunglyeol/code/go/bin/go test -bench='BenchmarkUnbufferedPingPong|BenchmarkBufferedSendRecv|BenchmarkFanOutFanIn' \
  -benchmem -count=5 . | tee /tmp/bench_custom_off.txt

# 커스텀 Go — on
GOCHANTRACE=on GOCHANTRACE_DUMP=0 \
  /Users/jiseunglyeol/code/go/bin/go test -bench='BenchmarkUnbufferedPingPong|BenchmarkBufferedSendRecv|BenchmarkFanOutFanIn' \
  -benchmem -count=5 . | tee /tmp/bench_custom_on.txt

# 커스텀 Go — sample
GOCHANTRACE=sample GOCHANTRACE_DUMP=0 \
  /Users/jiseunglyeol/code/go/bin/go test -bench='BenchmarkUnbufferedPingPong|BenchmarkBufferedSendRecv|BenchmarkFanOutFanIn' \
  -benchmem -count=5 . | tee /tmp/bench_custom_sample.txt
```

`benchstat`가 있으면 분산을 줄여 비교한다.

```bash
benchstat /tmp/bench_system.txt /tmp/bench_custom_off.txt
benchstat /tmp/bench_custom_off.txt /tmp/bench_custom_on.txt
benchstat /tmp/bench_custom_off.txt /tmp/bench_custom_sample.txt
```

### 3) 비교표 템플릿

측정 후 아래 표를 채운다.

#### UnbufferedPingPong

| 구성 | ns/op | B/op | allocs/op | vs system | vs custom off |
|---|---:|---:|---:|---:|---:|
| system Go |  |  |  | 0% |  |
| custom off |  |  |  |  | 0% |
| custom sample |  |  |  |  |  |
| custom on |  |  |  |  |  |

#### BufferedSendRecv

| 구성 | ns/op | B/op | allocs/op | vs system | vs custom off |
|---|---:|---:|---:|---:|---:|
| system Go |  |  |  | 0% |  |
| custom off |  |  |  |  | 0% |
| custom sample |  |  |  |  |  |
| custom on |  |  |  |  |  |

#### FanOutFanIn

| 구성 | ns/op | B/op | allocs/op | vs system | vs custom off |
|---|---:|---:|---:|---:|---:|
| system Go |  |  |  | 0% |  |
| custom off |  |  |  |  | 0% |
| custom sample |  |  |  |  |  |
| custom on |  |  |  |  |  |

오버헤드 계산:

```text
vs custom off (%) = (mode_ns - off_ns) / off_ns * 100
vs system (%)     = (mode_ns - system_ns) / system_ns * 100
```

### 4) 해석 가이드

- `custom off`가 `system`보다 뚜렷이 느리면 ID 할당이나 빈 분기 비용이다. `chantraceEnabled()` 체크가 hot path에 과도한지 확인한다.
- `on`이 `sample`보다 훨씬 느린 것이 정상이다. ring 기록 비용이다.
- `B/op`가 모드에 따라 크게 늘면 hot path에서 할당이 생긴 것이다. 즉시 수정 대상이다.
- dump를 켠 채 벤치하면 I/O가 섞이므로 `GOCHANTRACE_DUMP=0`을 강제한다.

## 검증 방법

1. `cd /Users/jiseunglyeol/code/go/src && ./make.bash`로 커스텀 툴체인을 빌드하고 `bin/go` 존재를 확인한다.
2. 위 매트릭스를 `-count=5` 이상으로 실행한다.
3. `benchstat` 또는 중앙값으로 표를 채운다.
4. `custom off` 대비 `on` 오버헤드가 재현 가능한지 한 번 더 반복한다.

분리 원칙 재확인:

```bash
# PATH에 커스텀 bin을 넣지 않는다
which go
go version   # system

GOTOOLCHAIN=local /Users/jiseunglyeol/code/go/bin/go version  # custom
```

## 기대 결과

예시(가상 수치, 형태만 참고):

```text
UnbufferedPingPong
  system:        120 ns/op
  custom off:    125 ns/op   (+4% vs system)
  custom sample: 140 ns/op   (+12% vs off)
  custom on:     210 ns/op   (+68% vs off)
```

실제 숫자는 CPU와 패치 내용에 따라 달라진다. 완료 기준은 “수치가 비어 있지 않고, 동일 명령으로 다시 얻을 수 있는 것”이다.

## 주의사항

- 전역 `PATH`/`GOROOT`를 바꾸지 않는다. 명령마다 커스텀 `go` 경로를 명시한다.
- `GOTOOLCHAIN=local`로 공식 툴체인 자동 전환을 막는다.
- 벤치 중 관계 그래프/wait graph dump를 돌리지 않는다.
- 시스템 Go에는 `GOCHANTRACE`가 없으므로, 시스템 결과는 항상 baseline 한 줄이다 취급한다.
- 1차 범위에서 `select` 특화 벤치는 넣지 않아도 된다. 필요하면 M5 문서화 단계에서 추가한다.
