---
title: "Operating Systems: Three Easy Pieces - Locks"
date: 2026-04-30T00:00:00+09:00
categories: [ "Memo", "Digging", "OSTEP" ]
tags: [ "OSTEP", "Operating Systems", "Concurrency", "Lock", "Synchronization", "Mutex" ]
draft: false
description: "OSTEP Concurrency 28강 Locks 정리"
keywords: [ "OSTEP", "Concurrency", "Lock", "Mutex", "Spin lock", "Synchronization", "Critical section" ]
author: "DSeung001"
lastmod: 2026-04-30T00:00:00+09:00
---
동시성 프로그래밍에서 일련의 명령을 원자적으로 실행하고 싶지만, 단일 또는 멀티 프로세스에서 멀티 스레드 환경을 도입시 프로세서에서의 인터럽트가 발생하기 때문에 그렇게 할 수 없죠, 그래서 이장에서 `Lock`을 도입하여 문제를 해결합니다.

해당 글에서도 `c`가 아닌 `python`으로 코드를 적습니다.(컨샙이나 이해부분을 위해 OSTEP를 보는 것이죠)
하지만 포인터 개념이 필요한 경우 `c` 코드를 참고합니다.

# Locks: The Basic Idea
`Lock`의 기본 아이디어를 간단한 예제로 살펴보겠습니다. 잔고를 업데이트하는 코드입니다. 다음 명령어를 여러 스레드가 동시에 수행하면 스레드 컨텍스트 스위칭 타이밍에 따라 레이스 컨디션이 발생할 수 있습니다. (한 줄로 보여도 내부적으로는 값 읽기, 계산, 할당이 이뤄지는 복합적인 명령이기 때문입니다.)
```bash
balance = balance + 1;
```
여기에 `Lock`을 적용합니다. `Lock`은 특정 시점에 잠금 해제(사용 가능) 상태이거나, 획득됨(잠금 보유) 상태를 가집니다. 따라서 어떤 스레드가 `Lock`을 획득하면 그 스레드만 임계 구역에 들어갈 수 있습니다.
어떤 스레드가 `Lock`을 보유 중인지, 획득 순서가 어떻게 되는지는 내부 큐로 관리되지만 일반적으로 사용자가 직접 알 수는 없습니다.
```bash
lock_t mutex; // some globally-allocated lock ’mutex’

lock(&mutex);
balance = balance + 1;
unlock(&mutex);
```

`lock()`과 `unlock()`의 의미는 간단합니다.
`lock()`을 호출하면 잠금을 획득하려고 시도하고, 다른 스레드가 이미 보유 중이라면 대기합니다. 잠금을 획득하면 임계 구역에 진입합니다. 즉 다른 스레드가 `Lock`을 가지고 있으면 `lock()`은 바로 반환되지 않습니다.
`unlock()`은 잠금을 해제해 다른 스레드가 `lock()`을 통해 잠금을 획득할 수 있게 만듭니다.

`Lock`은 프로그래머에게 스케줄링에 대한 최소한의 제어를 제공합니다. 일반적으로 스레드는 프로그래머가 생성하지만, 실제 스케줄링은 OS가 결정합니다.

이 덕분에 특정 코드 구간에서는 단 하나의 스레드만 활성화되도록 보장할 수 있고, 스케줄링의 비결정성을 어느 정도 통제 가능한 형태로 다룰 수 있습니다.

# Pthread Locks

`pthread_mutex_t mutex = PTHREAD_MUTEX_INITIALIZER;`에 대응되는 파이썬 선언은 다음과 같습니다.

```python
import threading

mutex = threading.Lock()
```

임계 구역 코드는 아래처럼 작성할 수 있습니다.

```python
with mutex:
    balance += 1
```
서로 다른 임계 구역(값/데이터 구조)을 위해 각각 다른 `Lock`을 생성할 수 있습니다. 임계 구역에 접근할 때 하나의 큰 `Lock`만 사용하는 것이 아니라, 서로 다른 데이터와 구조를 보호하기 위해 여러 `Lock`을 나누어 사용하는 것이 일반적입니다. 이를 통해 많은 스레드가 동시에 서로 다른 `Lock`을 사용할 수 있습니다.

# Building A Lock
`Lock`에 대한 컨셉은 어느 정도 이해하셨을 겁니다.
그러면 `Lock`을 어떻게 만드는지, 어떤 HW 자원과 지원이 필요한지에 대해 이야기해보겠습니다.

`Lock`을 만들기 위해서는 하드웨어와 OS의 도움이 필요합니다. 수년 동안 `Computer Architecture` 영역에는 여러 하드웨어 저수준 요소가 추가되었습니다.
이러한 명령어 자체의 상세 내용은 `Computer Architecture` 주제이므로 여기서는 넘어가고, 우리는 잠금과 상호 배제 메커니즘을 만들기 위해 이를 어떻게 사용하는지에 집중합니다.
또한 OS가 어떻게 관여해 전체 그림을 완성하고, 더 정교한 라이브러리를 구축할 수 있게 하는지도 살펴봅니다.

# Evaluating Locks
`Lock`을 설계할 때는 기능이 올바르게 동작하는지 평가해야 합니다.
- 잠금의 기본 목표인 상호 배제를 제공해, 여러 스레드가 동시에 임계 구역에 들어가지 못하게 하는지
- 잠금이 해제되었을 때 대기 중인 스레드가 획득 기회를 얻는지(특정 스레드가 기아 상태에 빠지지 않는지)
- 잠금 사용으로 인한 추가 비용(오버헤드)이 어느 정도인지
    - 경쟁이 없는 경우(단일 스레드)에도 불필요한 오버헤드가 큰지
    - 여러 스레드가 단일 CPU에서 잠금을 두고 경쟁할 때 성능이 얼마나 유지되는지

위 지표로 다양한 시나리오를 평가하면 `Lock`의 특성을 더 명확히 이해할 수 있습니다.

# Controlling Interrupts
상호 배제를 제공하기 위한 초기 접근 중 하나는 임계 구역 진입 전 인터럽트를 비활성화하는 것입니다.
이 방식은 주로 단일 프로세서 시스템에서 의미가 있습니다.

이 기능은 사용자 수준의 파이썬 코드에서 직접 제공되지 않습니다. CPU 인터럽트 제어는 커널/특권 모드와 밀접한 기능이며, C(커널 코드)에서는 다음처럼 표현할 수 있습니다.
```c
void lock() {
    DisableInterrupts();
}
void unlock() {
    EnableInterrupts();
}
```
단일 프로세서에서는 임계 구역에 들어가기 전에 인터럽트를 끄면(하드웨어 명령 사용) 실행 중 코드가 중단되지 않으므로, 해당 구간의 원자성을 보장하기 쉽습니다.
이 접근의 장점은 단순성입니다. 중단 없이 코드가 실행되므로 구현이 직관적입니다.
하지만 단점도 큽니다.
- 이 방법은 인터럽트 비활성화를 호출한 주체를 신뢰할 수 있어야 합니다. 악의적으로 오래 점유하면 OS가 제어권을 되찾지 못할 수 있습니다.
- 다중 프로세서에서는 한 CPU에서 인터럽트를 꺼도 다른 CPU의 실행은 계속됩니다. 따라서 동일 임계 구역에 대한 동시 접근을 막지 못합니다.
- 인터럽트를 오래 비활성화하면 시스템 응답성이 크게 떨어지고, 장치 처리 지연 등 심각한 문제를 유발할 수 있습니다.

이러한 이유로 인터럽트 비활성화는 상호 배제의 일반 해법이 아니라 제한된 맥락에서만 사용됩니다. 예를 들어 OS 커널은 매우 짧은 구간에서 인터럽트 마스킹을 사용해 커널 내부 자료구조 접근의 원자성을 보장합니다.

참고로 파이썬의 `signal.pthread_sigmask()`는 이름이 비슷하지만, 하드웨어 인터럽트 마스킹과는 다른 개념입니다. 이것은 스레드 단위로 POSIX 시그널 전달을 차단/해제하는 API입니다.

```python
import signal

# 현재 스레드에서 Ctrl+C(SIGINT) 전달을 잠시 차단
old_mask = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGINT})
try:
    # 민감한 구간(예: 중간 상태를 만들 수 있는 짧은 코드)
    critical_step()
finally:
    # 이전 마스크 복구
    signal.pthread_sigmask(signal.SIG_SETMASK, old_mask)
```

즉 파이썬의 시그널 마스킹은 특정 시그널 받지 못하게 하는 기능입니다.

# A Failed Attempt: Just Using Loads/Stores
인터럽트 기반 접근을 넘어가려면 CPU 하드웨어와 그 위에서 제공하는 원자적 명령어를 활용해 잠금 시스템을 구축해야 합니다.

단일 플래그 변수로 간단한 `Lock`을 구현해보면, 단순한 load/store만으로는 충분하지 않다는 점을 확인할 수 있습니다.

```text
초기 상태: flag = 0

Thread 1: if (flag == 0)   // true 확인
          ... 컨텍스트 스위칭 ...
Thread 2: if (flag == 0)   // 여전히 true 확인
Thread 2: flag = 1         // Lock 획득했다고 판단
          ... 컨텍스트 스위칭 ...
Thread 1: flag = 1         // Thread 1도 Lock 획득했다고 판단
```

위와 같이 검사(check)와 갱신(set) 사이가 교차(interleaving)되면 두 스레드가 모두 임계 구역에 들어갈 수 있습니다.
- 정확성 문제: 상호 배제가 깨집니다.
- 원인: `flag` 검사와 갱신이 하나의 원자적 연산이 아니기 때문입니다.

기본 요구사항인 상호 배제를 구현하지 못했을 뿐만 아니라, `flag` 값을 반복문으로 계속 확인하는 `spin-waiting`이 발생해 CPU 리소스를 낭비하게 됩니다.

# Building Working Spin Locks with Test-And-Set
인터럽트를 비활성화하는 방법과 단순 플래그 방식이 모두 한계를 보이자, 시스템 설계자들은 `Lock` 구현을 위해 하드웨어 지원을 도입했습니다. `test-and-set` 같은 원자적 명령은 1960년대 초기 다중 프로세서 시스템에서 중요해졌고, 오늘날에도 보편적으로 사용됩니다.

가장 간단한 하드웨어 지원은 `test-and-set`(또는 `atomic exchange`)입니다. 핵심은 <u>읽기(test)와 쓰기(set)를 하나의 원자적 연산으로 수행</u>한다는 점입니다.

다음 코드는 의사코드(pseudocode)로 다음 3줄로 컴파일하는게 아닌 CPU의 원자 명령어나 컴파일러 `intrinsic`로 처리합니다.
```c
// 이전 값을 반환하고 포인터가 가리키는 값을 업데이트(플래그 값)
int TestAndSet(int *old_ptr, int new) {
        int old = *old_ptr; // fetch old value at old_ptr
        *old_ptr = new;     // store ’new’ into old_ptr
        return old;         // return the old value
}
```

위 코드의 의미는 다음과 같습니다.
- `old_ptr`가 가리키는 현재 값을 읽어 `old`에 저장합니다.
- 같은 원자적 연산 안에서 해당 메모리에 `new`를 기록합니다.
- 이전 값(`old`)을 반환하므로, 호출자는 "내가 잠금을 획득했는지"를 판단할 수 있습니다.

사용법은 보통 아래와 같습니다.

```c
typedef struct __lock_t {
    int flag; // 0: unlocked, 1: locked
} lock_t;

void init(lock_t *lock) {
    lock->flag = 0;
}

void lock(lock_t *lock) {
    // 이전 값이 1이면 이미 누군가 보유 중이므로 계속 회전(spin)
    // lock->flag가 1인 상태에서 TestAndSet(&lock->flag, 1)을 호출하면 1을 반환
    // lock->flag가 0인 상태에서 호출하면 0을 반환하고, 동시에 flag를 1로 설정
    while (TestAndSet(&lock->flag, 1) == 1)
        ; // spin
}

void unlock(lock_t *lock) {
    lock->flag = 0;
}
```

`TestAndSet(&lock->flag, 1)`의 반환값이 `0`이면 잠금을 처음 획득한 것이고, `1`이면 이미 잠겨 있다는 뜻입니다.
파이썬에서는 CPU의 `test-and-set` 명령을 직접 호출하기 어렵습니다.

잠시 동안은 하드웨어 지원 없이 알고리즘만으로 잠금 기능을 구현하는 시도도 있었지만, 결국 하드웨어 지원 방식이 더 깔끔하고 실용적이라는 흐름이 강해졌습니다.
```c
// 이런 느낌으로 구현했습니다.
int flag[2];
int turn;
void init() {
    // indicate you intend to hold the lock w/ ’flag’
    flag[0] = flag[1] = 0;
    // whose turn is it? (thread 0 or 1)
    turn = 0;
}
void lock() {
    // ’self’ is the thread ID of caller
    flag[self] = 1;
    // make it other thread’s turn
    // 스레드가 2개라는 가정
    turn = 1 - self;
    while ((flag[1-self] == 1) && (turn == 1 - self))
        ; // spin-wait while it’s not your turn
}
void unlock() {
    // simply undo your intent
    flag[self] = 0;
}
```

다시 본론으로 돌아와 `TestAndSet` 기반 코드를 보면 두 가지 시나리오를 생각해볼 수 있습니다.
- 처음에는 `flag`가 0이므로 스핀 없이 자원을 획득할 수 있습니다. 하지만 곧바로 `flag`가 1이 되므로, 다음 스레드는 스핀 상태로 대기하며 자원을 획득한 스레드가 `unlock`할 때까지 기다리게 됩니다.
- 또 다른 시나리오로, 첫 스레드가 `flag`를 1로 바꾼 직후 다른 스레드로 컨텍스트 스위칭이 일어날 수 있습니다. 이때 두 번째 스레드가 `TestAndSet`를 실행해도 1을 반환받기 때문에 대기 상태가 됩니다.

`flag` 검사(Test)와 변경(Set)을 원자적으로 수행하므로, 검사-갱신 사이의 경쟁 조건을 막을 수 있습니다.
여기서는 `lock`이 해제될 때까지 스핀하므로, 회전 중인 스레드는 CPU 자원을 양보하지 않습니다.

# Evaluating Spin Locks
스핀 대기는 `Lock` 평가 기준 중 공정성 측면에서 불리할 수 있습니다.
스핀 중인 스레드는 CPU를 계속 사용하므로 스케줄링 상황에 따라 오래 기다릴 수 있고, 경우에 따라 기아(starvation)가 발생할 가능성도 있습니다.

또한 성능 측면에서도 단일 CPU에서는 오버헤드가 크게 느껴질 수 있습니다. `Lock`을 보유한 스레드가 임계 구역에 있는 동안 나머지 `N - 1`개 스레드는 `Lock` 획득을 시도하며 계속 스핀합니다.

이 지점에서 `Compare-And-Swap`(CAS)이 유용합니다. CAS는 "값이 기대한 상태일 때만 변경"을 원자적으로 수행하므로, 검사와 갱신 사이의 경쟁 조건을 줄일 수 있습니다.
- `test-and-set`은 시도할 때마다 쓰기를 유발할 수 있지만, CAS는 비교에 실패하면 값을 바꾸지 않습니다.
- 따라서 경쟁이 심한 상황에서 불필요한 메모리 쓰기와 캐시 무효화를 줄이는 데 도움이 됩니다.
- 결과적으로 다중 CPU 환경에서 더 나은 확장성을 기대할 수 있습니다.

다음 코드도 의사코드인 점은 참고
```c
int CompareAndSwap(int *ptr, int expected, int new) {
    int original = *ptr;
    if (original == expected)
        *ptr = new;
    return original;
}
```

# Compare-And-Swap
`Compare-And-Swap`의 아이디어는 `ptr`로 지정된 주소의 값이 `expected`와 같은지 비교하고, 같다면 `ptr`이 가리키는 메모리 값을 `new`로 바꾸는 것입니다.
그렇지 않다면 값은 그대로 유지됩니다. 두 경우 모두 해당 메모리 위치의 원래 값을 반환하므로, 호출한 코드가 성공/실패 여부를 판단할 수 있습니다.

`compare-and-swap` 명령어는 `test-and-set`와 유사한 방식으로 `Lock`을 구축할 수 있습니다.
```c
void lock(lock_t *lock) {
        // ptr, expected, new
        while (CompareAndSwap(&lock->flag, 0, 1) == 1)
            ; // spin
}
```
위 코드의 나머지 동작은 `test-and-set` 기반 스핀락과 유사합니다.

# Load-Linked and Store-Conditional
**Load-Linked**
일반적인 로드(load)처럼 메모리 값을 읽어 레지스터에 저장합니다. 동시에 해당 주소(또는 예약 단위)에 대한 예약(reservation)을 설정합니다.

**Store-Conditional**
`Load-Linked` 이후 해당 예약 구간에 다른 쓰기가 없을 때만 저장(store)에 성공합니다. 성공하면 `ptr`을 `value`로 갱신하고 성공 값(보통 1)을 반환합니다. 실패하면 `ptr`은 변경하지 않고 실패 값(보통 0)을 반환합니다.

다음 `LL`/`SC` 코드는 의사코드이며, 실제 구현에서는 하드웨어가 원자성을 보장한다고 보면 됩니다.
```c
int LoadLinked(int *ptr) {
    return *ptr;
}

int StoreConditional(int *ptr, int value) {
    if (no update to *ptr since LL to this addr) {
        *ptr = value;
        return 1;
    } else {
        return 0; // failed to update
    }
}

void lock(lock_t *lock) {
    while (1) {
        while (LoadLinked(&lock->flag) == 1)
            ; // flag가 1이면 spin
        if (StoreConditional(&lock->flag, 1) == 1)
            return; // SC가 성공해야만 리턴, 아니면 반복
    }
}

void unlock(lock_t *lock) {
    lock->flag = 0;
}
```
플래그가 0이어서 두 개의 스레드가 각각 로드와 저장을 시도할 때, 처음에는 둘 다 `LL`에서 0을 반환받아 `SC`에 진입할 수 있습니다. 하지만 `SC`에 먼저 도착한 스레드만 `Lock`을 획득하고, 나중에 도착한 스레드는 중간 저장이 발생했기 때문에 재시도 처리됩니다.

위 코드는 다음처럼 더 짧게 표현할 수도 있습니다.
```c
void lock(lock_t *lock) {
        while (LoadLinked(&lock->flag) ||
              !StoreConditional(&lock->flag, 1))
            ; // spin
}
```
위 코드는 `LL`로 읽은 `flag` 값이 0이고, `LL` 이후 업데이트가 없어 `SC`가 성공(1 반환)할 때만 `while`문의 조건을 어겨 빠져나옵니다.
만약 하나라도 조건을 만족하지 못하면 계속 스핀합니다.
즉 `LL` 값이 1이거나, `SC`가 0을 반환하면 다시 대기(spin) 상태로 반복합니다.

# Fetch-And-Add
마지막 `hardware primitive`로 `Fetch-And-Add`가 있습니다. 특정 주소의 이전 값을 반환하면서 값을 원자적으로 증가시킵니다.

다음은 의사코드입니다.
```c
int FetchAndAdd(int *ptr){
    int old = *ptr;
    *ptr = old + 1;
    return old;
}
```
이 `hardware primitive`는 티켓 락(ticket lock) 구현에 사용되며, 스레드 진행 보장 측면에서 유리합니다.
예를 들어 `TestAndSet` 기반 스핀락은 스케줄링 상황에 따라 특정 스레드가 오래 대기할 수 있지만, 티켓 락은 도착 순서대로 진입 기회를 제공합니다.

핵심 아이디어는 간단합니다.
- `ticket`: 새로 들어오는 스레드가 번호표를 뽑는 카운터
- `turn`: 현재 임계 구역에 들어갈 수 있는 번호
- 각 스레드는 `myturn = FetchAndAdd(&ticket)`으로 자신의 번호를 받고, `turn == myturn`이 될 때까지 대기합니다.

```c
typedef struct __lock_t {
    int ticket;
    int turn;
} lock_t;

void init(lock_t *lock) {
    lock->ticket = 0;
    lock->turn = 0;
}

void lock(lock_t *lock) {
    int myturn = FetchAndAdd(&lock->ticket); // 내 번호표
    while (lock->turn != myturn)
        ; // 내 차례가 올 때까지 spin
}

void unlock(lock_t *lock) {
    lock->turn = lock->turn + 1; // 다음 번호 깨우기
}
```
위 코드의 시나리오는 2개의 스레드가 있고 각각 A,B라 칭할 때 A가 먼저 `Lock`을 점유하면 `FetchAndAdd`로 인해 A의 티켓은 1이되고 `myturn`은 0이 됩니다.
아래는 두 스레드(A, B) 시나리오입니다.
- 초기값은 `ticket = 0`, `turn = 0`입니다.
- A가 먼저 `lock()`을 호출하면 `myturn = 0`을 받고, `ticket`은 1이 됩니다. 이때 `turn == myturn`이므로 A가 임계 구역에 진입합니다.
- B가 이어서 `lock()`을 호출하면 `myturn = 1`을 받고, `ticket`은 2가 됩니다. 현재 `turn`은 0이므로 B는 `while`에서 대기합니다.
- A가 `unlock()`을 호출하면 `turn`이 1로 증가합니다.
- 이제 B의 `myturn`(1)과 `turn`(1)이 같아지므로 B가 임계 구역에 진입합니다.

이 방식은 번호표 순서대로 진입하므로 공정성과 진행 보장 측면에서 유리합니다.

# Too Much Spinning: What Now
# A Simple Approach: Just Yield, Baby
# Using Queues: Sleeping Instead Of Spinning
# Different OS, Different Support
# Two-Phase Locks
# Summary