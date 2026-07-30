# 05. goroutine-channel 관계 그래프

## 목표

`sender → channel → receiver` 통신 구조를 그래프로 표현해, 어떤 고루틴이 어떤 채널을 매개로 연결되는지 보이게 한다.

완료 조건: dump 시 DOT 형식의 edge 목록이 출력되고, 샘플 producer/consumer에서 sender와 receiver가 같은 채널 노드로 연결된다.

## 선행 조건

- [01_channel_id.md](01_channel_id.md)
- [02_event_collect.md](02_event_collect.md)

## 수정 대상 파일

- `/Users/jiseunglyeol/code/go/src/runtime/chantrace.go` (edge 집계와 DOT dump)
- 이벤트 스키마 확장 시 `/Users/jiseunglyeol/code/go/src/runtime/chan.go`의 handoff 경로

## 수정사항

관계 그래프는 “한 번의 send가 특정 receiver를 깨운 경우”를 가장 정확히 표현한다. 버퍼를 경유하면 sender와 receiver가 시간상 분리되므로, v1에서는 다음 규칙을 쓴다.

| 경로 | edge 규칙 |
|---|---|
| unbuffered 또는 waiting handoff (`send`/`recv` 헬퍼) | `G_sender -> C_id`, `C_id -> G_receiver`를 한 쌍으로 기록 |
| buffered 경유 | `G -> C` (send), `C -> G` (recv)를 각각 독립 edge로 기록 |
| close | 그래프 edge에 넣지 않음 (선택적으로 `close` 노드 annotation) |

### 1) edge 레코드와 테이블

```go
const chantraceEdgeSlots = 2048

type chanEdgeKind uint8

const (
	chanEdgeSend chanEdgeKind = iota // G -> C
	chanEdgeRecv                     // C -> G
)

type chanEdge struct {
	kind   chanEdgeKind
	goid   uint64
	chanID uint64
	count  uint64
	used   bool
}

var chantraceEdges [chantraceEdgeSlots]chanEdge

func chantraceEdgeSlot(kind chanEdgeKind, goid, chanID uint64) int {
	h := goid ^ (chanID << 1) ^ uint64(kind)*0x9e3779b97f4a7c15
	return int(h % uint64(chantraceEdgeSlots))
}

func chantraceNoteEdge(kind chanEdgeKind, goid, chanID uint64) {
	if goid == 0 || chanID == 0 {
		return
	}
	idx := chantraceEdgeSlot(kind, goid, chanID)
	e := &chantraceEdges[idx]
	if e.used && (e.kind != kind || e.goid != goid || e.chanID != chanID) {
		return // collision drop for v1
	}
	if !e.used {
		e.used = true
		e.kind = kind
		e.goid = goid
		e.chanID = chanID
	}
	e.count++
}
```

### 2) handoff에서 peer goid 기록 (정확도 향상)

`chanEvent`에 peer를 넣으려면 필드를 하나 추가한다.

```go
type chanEvent struct {
	kind      chanEventKind
	_         [3]byte
	chanID    uint64
	goid      uint64
	peerGoid  uint64 // handoff peer; 0 if unknown
	ts        int64
	qcount    uint32
	dataqsiz  uint32
	blockedNS int64
}
```

`send` 헬퍼 (`chan.go`)는 waiting receiver의 `sg.g.goid`를 안다.

```go
func send(c *hchan, sg *sudog, ep unsafe.Pointer, unlockf func(), skip int) {
	// ... copy value ...
	gp := sg.g
	peer := gp.goid
	id := c.id
	qc := c.qcount
	ds := c.dataqsiz
	unlockf()
	gp.param = unsafe.Pointer(sg)
	sg.success = true
	if sg.releasetime != 0 {
		sg.releasetime = cputicks()
	}
	goready(gp, skip+1)

	if chantraceEnabled() {
		chantraceRecord(chanEvent{
			kind:     chanEvSend,
			chanID:   id,
			goid:     chantraceGoid(),
			peerGoid: peer,
			qcount:   uint32(qc),
			dataqsiz: uint32(ds),
		})
	}
}
```

주의: 가이드 02에서 `chansend`의 `send(...)` 호출 직후에 이미 send 이벤트를 넣었다면, 중복을 피하기 위해 그 호출부 기록은 제거하고 `send`/`recv` 헬퍼 쪽으로 옮긴다. 버퍼 enqueue 경로의 이벤트는 `chansend`/`chanrecv`에 남긴다.

`recv` 헬퍼도 대칭으로 `peerGoid = sg.g.goid`를 넣는다.

### 3) dump 시 edge 재구성

```go
func chantraceDumpGraph() {
	for i := range chantraceEdges {
		chantraceEdges[i] = chanEdge{}
	}
	n := chantraceRingPos.Load()
	start := uint64(0)
	if n > uint64(chantraceRingSize) {
		start = n - uint64(chantraceRingSize)
	}
	for i := start; i < n; i++ {
		ev := chantraceRing[i%uint64(chantraceRingSize)]
		switch ev.kind {
		case chanEvSend:
			chantraceNoteEdge(chanEdgeSend, ev.goid, ev.chanID)
			if ev.peerGoid != 0 {
				chantraceNoteEdge(chanEdgeRecv, ev.peerGoid, ev.chanID)
			}
		case chanEvRecv:
			chantraceNoteEdge(chanEdgeRecv, ev.goid, ev.chanID)
			if ev.peerGoid != 0 {
				chantraceNoteEdge(chanEdgeSend, ev.peerGoid, ev.chanID)
			}
		}
	}

	print("digraph chantrace {\n")
	for i := range chantraceEdges {
		e := &chantraceEdges[i]
		if !e.used {
			continue
		}
		switch e.kind {
		case chanEdgeSend:
			print("  G", e.goid, " -> C", e.chanID, " [label=\"send x", e.count, "\"];\n")
		case chanEdgeRecv:
			print("  C", e.chanID, " -> G", e.goid, " [label=\"recv x", e.count, "\"];\n")
		}
	}
	print("}\n")
}
```

`chantraceDump()` 끝에서 `chantraceDumpGraph()`를 호출한다.

### 4) 이벤트 중복 정리 체크리스트

`chansend` 정리:

1. `recvq` handoff: `send()` 내부에서만 기록
2. buffer enqueue: `chansend`에서 기록 (`peerGoid=0`)
3. block wake: `chansend` wake 경로에서 기록 (`peerGoid=0`, `blockedNS` 포함)

`chanrecv`도 대칭으로 맞춘다.

## 검증 방법

`/Users/jiseunglyeol/code/chan-tracer-test/main.go`에 둔다.

```go
package main

import "sync"

func main() {
	ch := make(chan int)
	var wg sync.WaitGroup
	wg.Add(2)
	go func() {
		defer wg.Done()
		ch <- 42
	}()
	go func() {
		defer wg.Done()
		<-ch
	}()
	wg.Wait()
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

DOT를 그림으로 보려면 dump의 `digraph` 블록만 파일로 저장한 뒤 Graphviz로 렌더링한다.

```bash
# digraph 부분만 추출했다고 가정
dot -Tpng /tmp/chan05.dot -o /tmp/chan05.png
```

## 기대 결과

```text
digraph chantrace {
  G2 -> C1 [label="send x1"];
  C1 -> G3 [label="recv x1"];
}
```

`G` 번호는 스케줄링에 따라 달라질 수 있으나, 하나의 `C1`을 사이에 두고 send와 recv가 마주보면 성공이다.

buffered 샘플:

```go
ch := make(chan int, 1)
ch <- 1  // G1 -> C1
<-ch     // C1 -> G1
```

```text
digraph chantrace {
  G1 -> C1 [label="send x1"];
  C1 -> G1 [label="recv x1"];
}
```

## 주의사항

- runtime hot path에서 문자열 보간이나 heap `map`을 쓰지 않는다. dump 시에만 edge 테이블을 채운다.
- handoff 기록을 `send`/`recv`로 옮기면 가이드 02의 호출부 기록과 중복될 수 있다. 반드시 한쪽으로 통일한다.
- `select`로 여러 채널을 기다리는 경우 peer 관계는 그대로 handoff에만 정확하다. select 메타데이터는 비범위다.
- DOT label의 따옴표와 공백은 `print`로 직접 출력한다. JSON을 쓰지 않는다.
- 검증 샘플은 `/Users/jiseunglyeol/code/chan-tracer-test/main.go`에 두고, 런타임 수정 후 `make.bash`로 툴체인을 다시 만든 뒤 `go run .`으로 실행한다.
