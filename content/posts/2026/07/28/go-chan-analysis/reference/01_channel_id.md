# 01. 모든 channel에 ID 부여

## 목표

채널 생성 시점에 고유 ID를 부여해, 이후 send/recv/close 이벤트를 같은 채널로 연결할 수 있게 한다.

완료 조건: `make(chan)` 경로에서 `hchan.id`가 할당되고, 추적 모드가 켜져 있으면 create 로그에 `id`가 출력된다.

## 선행 조건

없음. 이 단계에서 `chantrace.go` 골격과 모드 스위치를 함께 만든다.

## 수정 대상 파일

- `/Users/jiseunglyeol/code/go/src/runtime/chan.go` (`hchan`, `makechan`)
- `/Users/jiseunglyeol/code/go/src/runtime/chantrace.go` (신규)
- `/Users/jiseunglyeol/code/go/src/runtime/proc.go` (`schedinit`에서 `chantraceInit` 호출)

## 수정사항

### 1) 신규 `chantrace.go` 골격

환경변수 `GOCHANTRACE`로 모드를 고른다. 기본값은 `off`다.


| 값            | 의미                     |
| ------------ | ---------------------- |
| `off` 또는 미설정 | 기록하지 않음                |
| `on`         | 모든 이벤트 기록              |
| `sample`     | N번째 이벤트만 기록 (기본 N=100) |


```go
// Copyright 2026 The Go Authors. All rights reserved.
// Use of this source code is governed by a BSD-style
// license that can be found in the LICENSE file.

package runtime

import (
	"internal/runtime/atomic"
)

const (
	chantraceModeOff = iota
	chantraceModeOn
	chantraceModeSample

	chantraceRingSize   = 1 << 16 // 65536 events
	chantraceSampleEvery = 100
)

type chanEventKind uint8

const (
	chanEvCreate chanEventKind = iota
	chanEvSend
	chanEvRecv
	chanEvClose
)

// chanEvent is a fixed-size record. Hot path must not allocate or serialize JSON.
type chanEvent struct {
	kind      chanEventKind
	_         [3]byte
	chanID    uint64
	goid      uint64
	ts        int64 // nanotime()
	qcount    uint32
	dataqsiz  uint32
	blockedNS int64
}

var (
	chantraceMode     uint32 // atomic
	chantraceNextID   atomic.Uint64
	chantraceSeq      atomic.Uint64
	chantraceRing     [chantraceRingSize]chanEvent
	chantraceRingPos  atomic.Uint64
	chantraceInitDone atomic.Uint32
)

func chantraceInit() {
	if chantraceInitDone.Load() != 0 {
		return
	}
	mode := chantraceModeOff
	switch gogetenv("GOCHANTRACE") {
	case "on", "1":
		mode = chantraceModeOn
	case "sample":
		mode = chantraceModeSample
	}
	atomic.Store(&chantraceMode, uint32(mode))
	chantraceInitDone.Store(1)
}

//go:nosplit
func chantraceEnabled() bool {
	return atomic.Load(&chantraceMode) != chantraceModeOff
}

//go:nosplit
func chantraceShouldSample() bool {
	m := atomic.Load(&chantraceMode)
	if m == chantraceModeOff {
		return false
	}
	if m == chantraceModeOn {
		return true
	}
	// sample
	n := chantraceSeq.Add(1)
	return n%uint64(chantraceSampleEvery) == 0
}

//go:nosplit
func chantraceRecord(ev chanEvent) {
	if !chantraceShouldSample() {
		return
	}
	if ev.ts == 0 {
		ev.ts = nanotime()
	}
	pos := chantraceRingPos.Add(1) - 1
	chantraceRing[pos%uint64(chantraceRingSize)] = ev
}

func chantraceDump() {
	if !chantraceEnabled() {
		return
	}
	n := chantraceRingPos.Load()
	start := uint64(0)
	if n > uint64(chantraceRingSize) {
		start = n - uint64(chantraceRingSize)
	}
	print("chantrace dump begin n=", n, "\n")
	for i := start; i < n; i++ {
		ev := chantraceRing[i%uint64(chantraceRingSize)]
		switch ev.kind {
		case chanEvCreate:
			print("chan create id=", ev.chanID, " cap=", ev.dataqsiz, " goid=", ev.goid, "\n")
		case chanEvSend:
			print("chan send id=", ev.chanID, " goid=", ev.goid, " q=", ev.qcount, "/", ev.dataqsiz, " blocked_ns=", ev.blockedNS, "\n")
		case chanEvRecv:
			print("chan recv id=", ev.chanID, " goid=", ev.goid, " q=", ev.qcount, "/", ev.dataqsiz, " blocked_ns=", ev.blockedNS, "\n")
		case chanEvClose:
			print("chan close id=", ev.chanID, " goid=", ev.goid, "\n")
		}
	}
	print("chantrace dump end\n")
}
```

초기화 호출 위치는 `schedinit` 근처(`parseRuntimeDebugVars` / `GOMAXPROCS` 파싱과 같은 구간)에 `chantraceInit()` 한 줄을 추가한다.

파일: `/Users/jiseunglyeol/code/go/src/runtime/proc.go`의 `schedinit` 안.

```go
	parseRuntimeDebugVars(gogetenv("GODEBUG"))
	chantraceInit()
```



### 2) `hchan`에 ID 필드 추가

파일: `chan.go`의 `hchan` 구조체. `bubble` 다음에 `id`를 둔다. `id`는 생성 후 불변이므로 `lock` 보호 대상이 아니다.

Before:

```go
type hchan struct {
	qcount   uint
	dataqsiz uint
	buf      unsafe.Pointer
	elemsize uint16
	closed   uint32
	timer    *timer
	elemtype *_type
	sendx    uint
	recvx    uint
	recvq    waitq
	sendq    waitq
	bubble   *synctestBubble

	lock mutex
}
```

After:

```go
type hchan struct {
	qcount   uint
	dataqsiz uint
	buf      unsafe.Pointer
	elemsize uint16
	closed   uint32
	timer    *timer
	elemtype *_type
	sendx    uint
	recvx    uint
	recvq    waitq
	sendq    waitq
	bubble   *synctestBubble
	id       uint64 // chantrace channel ID; 0 if tracing never assigned

	lock mutex
}
```

`hchanSize`는 `unsafe.Sizeof(hchan{})`로 계산되므로 필드 추가만으로 할당 크기가 따라간다.

### 3) `makechan`에서 ID 할당과 create 기록

`lockInit(&c.lock, lockRankHchan)` 이후, `return c` 직전에 삽입한다.

```go
	lockInit(&c.lock, lockRankHchan)

	c.id = chantraceNextID.Add(1)
	if chantraceEnabled() {
		gp := getg()
		if gp.m.curg != nil {
			gp = gp.m.curg
		}
		chantraceRecord(chanEvent{
			kind:     chanEvCreate,
			chanID:   c.id,
			goid:     gp.goid,
			dataqsiz: uint32(c.dataqsiz),
			qcount:   0,
		})
	}

	if debugChan {
		print("makechan: chan=", c, "; elemsize=", elem.Size_, "; dataqsiz=", size, "\n")
	}
	return c
```



## 검증 방법

샘플은 `/Users/jiseunglyeol/code/chan-tracer-test/main.go`에 둔다.

```go
package main

func main() {
	ch := make(chan int, 2)
	_ = ch
}
```

`bin/go`가 없으면(또는 `chan.go` / `chantrace.go` / `proc.go`를 바꾼 뒤에는) 먼저 커스텀 툴체인을 빌드한다. clone만 한 상태에서는 `/Users/jiseunglyeol/code/go/bin/go`가 없다.

```bash
cd /Users/jiseunglyeol/code/go/src
./make.bash
/Users/jiseunglyeol/code/go/bin/go version
```

그다음 커스텀 `go`로 `main.go`를 실행한다.

```bash
cd /Users/jiseunglyeol/code/chan-tracer-test
export GOTOOLCHAIN=local
GOCHANTRACE=on /Users/jiseunglyeol/code/go/bin/go run .
```

이 단계에서는 create 기록이 ring에만 들어가므로, 확인을 위해 잠깐 `makechan` 안에서 `print("chan create id=", c.id, "\n")`를 넣거나 `chantraceDump()`를 프로세스 종료 경로에 연결해도 된다. dump 연결은 가이드 02에서 정리한다.

## 기대 결과

```text
chan create id=1 cap=2 goid=1
```

같은 프로세스에서 채널을 두 번 만들면 `id`가 증가한다 (`1`, `2`, ...).

`GOCHANTRACE`가 꺼져 있어도 `c.id`는 할당된다. 기록만 생략한다. 이렇게 하면 이후 단계에서 모드를 켜도 ID 체계가 동일하다.

## 주의사항

- hot path에서 `fmt`, JSON, 파일 I/O, `make`/`append`를 쓰지 않는다.
- `hchan.lock`을 잡은 상태에서 다른 G를 ready하지 않는 기존 규칙을 지킨다. create 기록은 lock 초기화 후, 아직 lock을 잡지 않은 상태에서 수행한다.
- `timer` 채널과 `synctest` bubble 필드는 건드리지 않는다. ID만 추가한다.
- `select` 전용 경로는 1차 비범위다.
- `id`를 `lock`보다 앞에 두면 패딩이 달라질 수 있다. 동작에는 문제 없으나, race detector가 쓰는 `raceaddr()`(`c` 시작 주소의 오프셋) 의미는 그대로이므로 `qcount` 위치는 유지하는 편이 안전하다. 이 가이드는 `bubble` 뒤에 `id`를 두는 방식을 택한다.



## 후기

GOTOOLCHAIN로 내가 만든 고툴체인으로 돌게금 고정하고
지금 테스트를 위해 채널 생성시 로그를 찍으면 다음처럼 3개가 나옴, 샘플코드는 채널 하나만 생성하는데 
```go
chan create id=1
chan create id=2
chan create id=3
```

### 샘플은 채널 1개인데 create가 3번인 이유

`makechan`은 사용자 `make(chan ...)`뿐 아니라 런타임 내부 `make`도 모두 탄다. 임시 `print`를 `chantraceEnabled()` 밖에 두면 그 경로가 전부 출력된다.


| id  | 출처                    | 위치                                 |
| --- | --------------------- | ---------------------------------- |
| 1   | GC 활성화 동기화            | `runtime/mgc.go` `gcenable()`      |
| 2   | package init / cgo 조율 | `runtime/proc.go` `main_init_done` |
| 3   | 검증 샘플                 | `chan-tracer-test/main.go`         |


런타임이 채널을 쓰는 이유: 고루틴끼리 “준비됐다 / 끝났다”를 안전하게 맞추려면 대기·깨우기 수단이 필요하고, Go에서는 그 수단이 채널이다. 사용자 코드와 같은 추상화를 런타임도 쓴다.

`gcenable()`: background sweeper와 scavenger를 띄운 뒤, 둘 다 기동 신호를 보낼 때까지 main이 기다린다. cap=2인 이유다.

```go
// runtime/mgc.go
func gcenable() {
	c := make(chan int, 2)
	go bgsweep(c)
	go bgscavenge(c)
	<-c
	<-c
	memstats.enablegc = true
}
```

`main_init_done`: package init이 끝나기 전에 cgo callback 등이 끼어들지 않도록 알리는 신호다. init이 끝나면 `close(main_init_done)`한다.

```go
// runtime/proc.go
main_init_done = make(chan bool)
// ... doInit ...
close(main_init_done)
```

사용자 샘플:

```go
// chan-tracer-test/main.go
ch := make(chan int, 2)
```



### 실행에 쓰는 환경변수

`GOTOOLCHAIN`은 공식 Go 툴체인의 버전 선택 스위치다. `local`이면 `go` 바이너리가 속한 트리(여기서는 `/Users/jiseunglyeol/code/go`)만 쓰고, 네트워크로 다른 버전을 받아 전환하지 않는다. 커스텀 포크를 쓸 때 시스템/원격 툴체인으로 새지 않게 막는다.

`GOCHANTRACE`는 이 프로젝트에서 `chantrace.go`가 읽는 관측 모드 스위치다. 공식 Go에는 없다.


| 값           | 의미                                  |
| ----------- | ----------------------------------- |
| 미설정 / `off` | ring에 이벤트를 쓰지 않음. `hchan.id` 할당은 유지 |
| `on`        | 모든 create/send/recv/close를 기록       |
| `sample`    | N번째마다 기록 (기본 N=100)                 |


둘의 층이 다르다. `GOTOOLCHAIN`은 “어느 `go`로 빌드·실행할지”, `GOCHANTRACE`는 “그 바이너리의 런타임이 채널을 추적할지”다.

```bash
export GOTOOLCHAIN=local
GOCHANTRACE=on /Users/jiseunglyeol/code/go/bin/go run .
```

