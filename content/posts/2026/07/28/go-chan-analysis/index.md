---
title: "Go Chan 분석"
date: 2026-07-28T00:00:00+09:00
categories: [ "Golang" ]
tags: [ "Go", "Channel", "Chan", "동시성" ]
draft: true
description: "Go Chan 분석해서 만들어보기"
keywords: [ "Golang", "Channel", "Chan", "동시성", "goroutine" ]
author: "DSeung001"
lastmod: 2026-07-28T00:00:00+09:00
---

# 개요
이 글의 목표는 Go의 채널 개념을 토대로 언버퍼/버퍼의 차이, GMP, 이벤트 루프의 차이도 보며
최종적으로 직접 채널을 만들어 볼 예정입니다.

# Go Chan
Go를 처음 배웠을 때 가장 재밌으며 난해했던 개념이 채널이었습니다.
처음 들었을 때는 TV 채널 같은 걸까 하며 의문이 들었죠.

> Go에서 채널은 고루틴(Goroutine) 간에 데이터를 주고받고 실행을 동기화하기 위한 파이프로, 통신/차단/동기화 등을 할 수 있습니다.

## Effective Go에서 말하는 채널
Go 공식 문서 [Effective Go - Channels](https://go.dev/doc/effective_go#channels)를 기준으로 채널의 사용법을 다음처럼 정리할 수 있습니다.

### make로 만든 참조값

`map`과 마찬가지로 `make`로 만들며 반환값은 밑바닥 자료구조를 가리키는 참조처럼 동작합니다.
이때 버퍼 크기를 주는 걸로 `unbuffered/buffered`로 채널을 구분해 사용할 수 있습니다.

```go
ci := make(chan int)            // unbuffered channel of integers
cj := make(chan int, 0)         // unbuffered channel of integers
cs := make(chan *os.File, 100)  // buffered channel of pointers to Files
```

### unbuffered
unbuffered 채널은 값 교환(communication)과 동기화(synchronization)를 한 번에 묶어 주는 역할로 쓰이며, 주로 어느 정도 시간이 소요되는 백그라운드 작업이 끝났을 때 신호로 사용될 수 있습니다.
- 채널이 비어 있으면 receiver는 받을 데이터가 생길 때까지 block합니다. (buffered도 동일)
- unbuffered이면 sender는 receiver가 값을 받을 때까지 block합니다.
```go
c := make(chan int)  // Allocate a channel.
// Start the sort in a goroutine; when it completes, signal on the channel.
go func() {
    list.Sort()
    c <- 1  // Send a signal; value does not matter.
}()
doSomethingForAWhile()
<-c   // Wait for sort to finish; discard sent value.
```

### buffered
버퍼가 생기면 sender는 receiver를 직접 기다리지 않아도 됩니다.
빈 칸이 있으면 값을 버퍼에 복사하는 시점에 send가 끝나고, 버퍼가 가득 차면 receiver가 값을 꺼낼 때까지 기다립니다.
Effective Go는 이 점을 이용해 buffered channel을 세마포어처럼 쓸 수 있다고 설명합니다.
> 세마포어: 여러 프로세스나 스레드가 공유 자원에 동시에 접근하는 것을 조절하는 정수 변수 기반의 동기화 신호 장치 (접근 통제)

아래처럼 채널을 만들어 한 번에 처리할 수 있는 개수를 제한하는 로직에서, 그 개수 제한을 세마포어 개념으로 처리할 수 있습니다.
`MaxOutstanding`는 동시 `process` 수 상한이고, `Serve`가 만드는 고루틴 수 자체는 막지 않습니다.
1. Serve: 요청이 오면 `go handle(req)`로 고루틴을 바로 띄웁니다. 여기에는 세마포어가 없습니다.
2. handle: `sem <- 1`에서 버퍼 칸 하나를 채웁니다.
    - 아직 채워진 칸이 `MaxOutstanding` 미만이면 바로 `process`로 들어갑니다.
    - 이미 `MaxOutstanding`개가 차 있으면, 누군가 `<-sem`으로 칸을 비울 때까지 block합니다.
    - `process`가 끝나면 `<-sem`으로 칸을 비워, 막혀 있던 다른 handle이 진행할 수 있습니다.

```go
var sem = make(chan int, MaxOutstanding)

func handle(r *Request) {
    sem <- 1    // Wait for active queue to drain.
    process(r)  // May take a long time.
    <-sem       // Done; enable next request to run.
}

func Serve(queue chan *Request) {
    for {
        req := <-queue
        go handle(req)  // Don't wait for handle to finish.
    }
}
```

여기까지가 우리가 Go를 다루며 느낄 수 있는 `Chan`의 사용법이었습니다.
이제는 런타임 단을 Go 코드로 파악해 봅시다. 실제 런타임을 Go 코드로 볼 수 있으니 이를 토대로 파악해 봅시다.
예전에는 상당 부분이 C 였지만 1.4 이후로 런타임을 Go로 바꿔서 1.23 기준으로는 `src/runtime`에 `.c` 파일이 없습니다. 대신에 컨텍스트 스위칭 같은 아주 낮은 층의 어셈블리는 `.s`로 존재하죠.

## Chan이 하는 일 (send / recv / buffer / park)
### hchan: 채널의 실제 구조
### makechan: 버퍼와 락 초기화
### chansend / chanrecv의 세 갈래
#### 상대가 대기 중이면 직접 전달 (sendDirect / recvDirect)
#### 버퍼에 자리가 있으면 원형 큐에 enqueue
#### 둘 다 안 되면 sudog 대기열 진입 후 park
### sudog / gopark / goready: 대기와 깨우기
### closechan: 대기자 일괄 깨우기

## 고루틴 스케줄링과의 관계 (GMP)
### park 후 P가 다른 G를 실행
### goready 후 runnable로 복귀
### 이벤트 루프 비유와 차이 (OSTEP 33강)

# 직접 만들기
## 목표 범위
## 구현과 검증