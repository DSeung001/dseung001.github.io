---
title: "Operating Systems: Three Easy Pieces - Semaphores"
date: 2026-05-05T00:00:00+09:00
categories: [ "Memo", "Digging", "OSTEP" ]
tags: [ "OSTEP", "Operating Systems", "Concurrency", "Semaphore", "Synchronization" ]
draft: false
description: "OSTEP Concurrency 31강 Semaphores 정리"
keywords: [ "OSTEP", "Concurrency", "Semaphore", "Synchronization", "Thread", "Lock" ]
author: "DSeung001"
lastmod: 2026-05-05T00:00:00+09:00
---

동시성 문제를 해결하기 위해 `cv`, `lock`을 추가했죠. 이제는 다익스트리아가 도입한 세마포어에 대해 알아봅시다.

세마포어의 핵심은 다음과 같습니다
- 원자적 정수 변수: 세마포어 값은 중단 없이 한 번에 변경되어야 합니다.
- 카운팅 기능: 0 또는 1만 갖는 바이너리 세마포어(뮤텍스와 유사)와 0 이상의 정수 값을 가지는 카운팅 세마포어가 있습니다.
- 동기화: 자원이 없으면 프로세스는 대기(block)하고, 자원이 생기면 깹니다

세마포은 동시성을 관리하는 논리적 제어장치 또는 충돌을 방지하는 메커니즘입니다.

# Semaphores: A Definition
세마포어는 두 개의 루틴을 조작할 수 있는 정수 값을 가진 객체입니다.
초기 값이 동작을 결정하기 때문에 다른 루틴을 호출하여 상호작용이 생기기 전에 초기화가 필요합니다.

OSTEP에서 나오는 세마포어 연산은 `init`, `wait`, `post` 세 가지인데,
파이썬에서는 `threading.Semaphore`(또는 `threading.BoundedSemaphore`)로 거의 그대로 대응시킬 수 있습니다.
이 둘의 차이는 초기화 때 선언한 `value`를 초과해서 카운터가 증가하는 것을 막아주는지 여부입니다. 
`BoundedSemaphore`는 초과 `release()`를 에러로 잡아주기 때문이죠.


```python
import threading

# 세마포어 초기화
sem = threading.Semaphore(value=1)

# wait():
# 세마포어 값을 감소시키고, 0이면 블록
# blocking 여부와 timeout 설정 가능
sem.acquire()

# post():
# 세마포어 값을 증가시키고, 대기 중인 스레드를 깨움
# (Python 3.9+) n으로 한 번에 여러 번 release 가능: sem.release(n=...)
sem.release()

# 사용 예시
sem.acquire()
try:
    # critical section
    pass
finally:
    sem.release()

# 초기값을 넘는 release를 제한하려면 BoundedSemaphore 사용
bounded = threading.BoundedSemaphore(value=1)
```

사용법은 다음과 같습니다.

- **`init(value)`**: `threading.Semaphore(value)`로 생성합니다. `value`는 스레드가 동시에 접근할 수 있는 개수이며, `mutex`처럼 사용 시 보통 `1`로 설정합니다.
- **`wait()`**: `sem.acquire()`입니다. 값이 0이면 다른 스레드가 `release()`할 때까지 대기(블록) 합니다.
  - 논블로킹으로 시도만 하고 싶으면 `sem.acquire(blocking=False)`를 씁니다. 성공하면 `True`, 실패하면 `False`입니다.
  - 타임아웃을 주려면 `sem.acquire(timeout=초)`를 씁니다. 성공하면 `True`, 타임아웃이면 `False`입니다.
- **`post()`**: `sem.release()`입니다. 값을 증가시키고, 기다리는 스레드가 있으면 하나를 깨웁니다. (Python 3.9+에서는 `sem.release(n=...)`로 여러 번 release할 수도 있습니다.)

# Binary Semaphores (Locks)
이진 세마포어는 `lock`의 잠금 상태와 잠기지 않은 상태도 표현할 수 있습니다.
매우 간단한 방식으로 구현이 가능하죠.

아래는 이진 세마포어를 통한 `lock`의 흐름을 표로 정리한 것입니다.

| Val | Thread 0 | Thread 0 state | Thread 1 | Thread 1 state |
|---:|---|---|---|---|
| 1 |  | Run |  | Ready |
| 1 | call `sem_wait()` | Run |  | Ready |
| 0 | `sem_wait()` returns | Run |  | Ready |
| 0 | (crit sect begin) | Run |  | Ready |
| 0 | Interrupt; Switch→T1 | Ready |  | Run |
| 0 |  | Ready | call `sem_wait()` | Run |
| -1 |  | Ready | decr sem | Run |
| -1 |  | Ready | (sem<0)→sleep | Sleep |
| -1 | Switch→T0 | Run |  | Sleep |
| -1 | (crit sect end) | Run |  | Sleep |
| -1 | call `sem_post()` | Run |  | Sleep |
| 0 | incr sem | Run |  | Sleep |
| 0 | wake(T1) | Run |  | Ready |
| 0 | `sem_post()` returns | Run |  | Ready |
| 0 | Interrupt; Switch→T1 | Ready |  | Run |
| 0 |  | Ready | `sem_wait()` returns | Run |
| 0 |  | Ready | (crit sect) | Run |
| 0 |  | Ready | call `sem_post()` | Run |
| 1 |  | Ready | `sem_post()` returns | Run |

위 표에서 `Val`이 -1로 내려가는 행은, 대기 중인 스레드 수까지 한 정수 값에 합산해 적는 Dijkstra 스타일 세마포어 정의를 보여주려는 것입니다.

파이썬의 `threading.Semaphore`는 일반적으로 문서/코드 수준에서 보기 쉽게 남아 있는 허용(퍼밋) 카운터와 `Condition` 기반 대기 큐로 동작을 이해하도록 설계되어 있습니다.
실제 구현은 내부 정수 카운터를 조정하면서, 허용이 남아 있지 않으면 `Condition.wait()`로 대기 스레드를 큐에 넣는 방식입니다.

```python
import threading

class BinarySemaphoreLock:
    def __init__(self):
        self._sem = threading.Semaphore(value=1)  # init(1)

    def acquire(self, blocking=True, timeout=None) -> bool:
        return self._sem.acquire(blocking=blocking, timeout=timeout)  # sem_wait()

    def release(self, n=1) -> None:
        self._sem.release(n=n)  # sem_post()

    # `with:` 진입 시 파이썬이 `__enter__`를 호출합니다.
    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.release()
        return False

if __name__ == "__main__":
    lock = BinarySemaphoreLock()

    # 이벤트로 흐름 순서 고정
    t0_in_cs = threading.Event()
    t1_attempt_wait = threading.Event()

    def t0():
        lock.acquire()          # sem_wait()/acquire 진입 후 임계구역 진입
        t0_in_cs.set()          # (crit sect begin)
        t1_attempt_wait.wait()  # T1이 sem_wait() 시도 라인까지 올 때까지 유지
        lock.release()          # sem_post()/release가 대기 중인 스레드를 깨움

    def t1():
        t0_in_cs.wait()         # T0이 CS에 들어간 이후에 실행
        t1_attempt_wait.set()
        lock.acquire()          # 가용 퍼밋이 없어서 블록 → T0가 release 후 진행
        lock.release()

    th0 = threading.Thread(target=t0, name="T0")
    th1 = threading.Thread(target=t1, name="T1")
    th0.start(); th1.start()
    th0.join(); th1.join()
```

# Semaphores For Ordering
세마포어로 두 작업 간 선행 관계(어떤 이벤트가 발생한 이후에만 특정 코드가 진행)를 표현하기 좋은 도구입니다. (OSTEP에서는 이를 세마포어의 ordering(정렬) 용법으로 소개합니다).

한쪽은 이벤트가 오기 전까지 `wait()`/`P()`로 멈춰 있고, 다른 쪽이 이벤트를 만들었다는 사실을 `post()`/`V()`로 한 번 알립니다(파이썬에서는 `Semaphore.release()`). 핵심은 처음부터 일어났다고 가정하면 안 되는 일을 `wait`/`post`의 짝으로 강제하는 것입니다.

실무적으로는 상태가 복잡해지면 `Condition` 변수가 더 읽기 쉬운 경우도 많지만, 세마포어는 `cv` + `wait`/`post`(또는 `acquire`/`release`)만으로 간단히 관계를 나타낼 수 있어 조금 더 쓰기 편리하죠.

지난 `cv` 글에서 적었던 부모 스레드는 자식 스레드가 종료되어야 완료되는 케이스를 세마포어로 정의해봅시다.
```bash
parent: begin
child
parent: end
```
파이썬으로 매핑하면 `sem = threading.Semaphore(0)` 뒤에 부모에서 `sem.acquire()`, 자식 끝에서 `sem.release()` 정도가 됩니다(이전 챕터의 `join()`과 같은 목적이라고 보면 됩니다).

---
`Lock`을 하기 위해 바이너리 세마포어에서는 `1`로 초기화를 했습니다.
두번째는 스레드의 순서 정렬을 위해 `0`으로 설정했죠

이들을 토대로 알 수 있는 세마포어의 초기화에 대한 일반적인 규칙은, 초기화 직후 바로 제공할 수 있는 자원의 수를 고려하는 것 입니다.
`lock`은 바로 시작할 때 제공하므로 `1`이고 정렬은 자식이라는 선행 작업이 있어야하므로 `0`인거죠.
---

# The Producer/Consumer (Bounded Buffer) Problem
세마포어로 유한 버퍼 문제에서도 요긴하게 쓸 수 있습니다. 세마포어의 개념 자체가 유한 버퍼 문제와 매우 닮아 있기 때문이죠.
처음에는 두 개의 세마포어 `empty`, `full`을 도입해 문제에 접근해 봅니다.

이 예제에서는 생산자는 넣을 빈 칸이 생기기를(`wait(empty)`) 기다리고, 소비자는 꺼낼 데이터가 생기기를(`wait(full)`) 기다립니다. (`MAX = 1` 가정)

```python
import threading

MAX = 1
loops = 10

buffer = [0] * MAX
fill = 0
use = 0

empty = threading.Semaphore(MAX)  # 빈 칸이 MAX개(처음엔 버퍼가 비어 있음)
full = threading.Semaphore(0)  # 채워진 칸이 0개(아직 꺼낼 값 없음)

def put(value: int) -> None:
    global fill
    buffer[fill] = value
    fill = (fill + 1) % MAX

def get() -> int:
    global use
    tmp = buffer[use]
    use = (use + 1) % MAX
    return tmp

def producer() -> None:
    for i in range(loops):
        empty.acquire()  # wait(empty)
        put(i)
        full.release()  # post(full)
    empty.acquire()
    put(-1)
    full.release()

def consumer() -> None:
    tmp = 0
    while tmp != -1:
        full.acquire()  # wait(full)
        tmp = get()
        empty.release()  # post(empty)
        if tmp == -1:
            break
        print(tmp, end=" ")

tp = threading.Thread(target=producer)
tc = threading.Thread(target=consumer)
tp.start()
tc.start()
tp.join()
tc.join()
```
위 코드에서 생산자가 `put`한 뒤 `full.release()`(`post(full)`)를 하면, 대기 중이던 소비자가 깨어나 `get()`으로 소비합니다.
소비자가 `empty.release()`(`post(empty)`)로 빈 칸을 돌려주면, 막혀 있던 생산자가 다시 `empty.acquire()`로 넣을 수 있고, 이 과정이 반복됩니다.
이 코드에 동시성으로 더 많은 스레드를 넣어도 잘 작동되게 해보죠 그러기 위해 세마포어로 임계구역을 한 번 더 보호해줍시다.
아래와 같이 `producer`와 `consumer`를 수정해봅시다.
```python
# 이전 블록의 loops, empty, full, put, get 정의가 있다고 가정
# 앞선 예와 동일하게 empty / full 은 그대로 두고,
# 버퍼 연산만 감싸는 뮤텍스(이진 세마포어). 초깃값은 반드시 1.
mutex = threading.Semaphore(1)


def producer() -> None:
    for i in range(loops):
        empty.acquire() # wait(empty)
        mutex.acquire()
        put(i)
        mutex.release()
        full.release() # post(full)
    empty.acquire()
    put(-1)
    full.release()

def consumer() -> None:
    tmp = 0
    while tmp != -1:
        full.acquire() # wait(full)
        mutex.acquire()
        tmp = get()
        mutex.release()
        empty.release() # post(empty)
        if tmp == -1:
            break
        print(tmp, end=" ")
```

위 코드는 정상적으로 동작합니다.
하지만 아래 코드는 `lock` 순서 때문에 교착에 가깝게 멈출 수 있으며, 환경에 따라 `Process finished with exit code -1`처럼 강제 종료된 것처럼 보일 수도 있습니다.
```python
def producer() -> None:
    for i in range(loops):
        mutex.acquire()
        empty.acquire() # wait(empty)
        put(i)
        full.release() # post(full)
        mutex.release()
    empty.acquire()
    put(-1)
    full.release()

def consumer() -> None:
    tmp = 0
    while tmp != -1:
        mutex.acquire()
        full.acquire() # wait(full)
        tmp = get()
        empty.release() # post(empty)
        mutex.release()
        if tmp == -1:
            break
        print(tmp, end=" ")
```
차이점은 `mutex.acquire()`를 `empty`/`full`보다 먼저 잡았느냐입니다. 한 스레드가 `mutex`를 획득한 뒤 실행이 인터리빙되어 다른 스레드가 돌면, 다른 스레드도 `mutex`에서 막히게되고 그로인해 `empty` 또는 `full`을 기다리는 쪽에서는 신호가 오지 않아 서로의 진행을 기다리는 형태가 될 수 있습니다.
그래서 이 패턴에서는 `mutex`가 `put`/`get`(버퍼 연산) 주변만 감싸고, 카운팅 세마포어인 `empty`/`full`은 그 바깥에서 잡는 편이 안전합니다

여기서 해결책은 다음과 같습니다.
- 항상 같은 순서로 `acquire`/`release`를 짝 지을 것
- `lock`의 범위는 임계 구역만으로 제한할 것

# Reader-Writer Locks
고전적인 문제로, 서로 다른 데이터 구조 접근이 서로 다른 종류의 락을 요구할 수 있습니다.
예를 들어 동시에 공유하는 리스트에서는 삽입(쓰기)은 한 번에 하나의 작업만 수행되어야 하지만, 읽기는 많은 스레드가 동시에 해도 괜찮을 때가 있습니다.
쓰기 작업은 읽기 작업이 전부 종료된 뒤에만 실행될 수 있어야 합니다.
그런 패턴을 지원하기 위해 만든 특별한 락이 `reader-writer lock`입니다.

OSTEP에서 보여 주는 reader-writer 락(이진 세마포어 두 개 + `readers` 카운터)과 같은 구조를 파이썬에서는 `threading.Semaphore`로 그대로 옮길 수 있습니다(`sem_wait`/`sem_post`는 각각 `acquire`/`release`).

```python
import threading


class RwLock:
    """reader-writer lock: lock은 readers 카운터 보호, writelock은 writer 배타 + reader가 획득."""

    def __init__(self) -> None:
        self.readers = 0
        self.lock = threading.Semaphore(1)
        self.writelock = threading.Semaphore(1)

    def rwlock_acquire_readlock(self) -> None:
        self.lock.acquire()
        self.readers += 1
        # 리더가 생기는 순간 쓰기 쪽과 충돌을 막기 위해 writelock을 받음
        if self.readers == 1:
            self.writelock.acquire()
        self.lock.release()

    def rwlock_release_readlock(self) -> None:
        self.lock.acquire()
        self.readers -= 1
        # 마지막 리더만 writelock을 반환해 쓰기 스레드 진입을 허용
        if self.readers == 0:
            self.writelock.release()
        self.lock.release()

    def rwlock_acquire_writelock(self) -> None:
        self.writelock.acquire()

    def rwlock_release_writelock(self) -> None:
        self.writelock.release()

```
위 코드는 `reader-writer lock`의 전형적인 조건들을 충족합니다.
- 읽기는 여러 스레드가 동시에 존재 가능
- 쓰기는 활성화된 읽기 스레드가 없을 때만 가능

# The Dining Philosophers
다익스트리아(Dijkstra) 선생님이 남긴 유명한 문제로 철학자들의 저녁식사 문제가 있습니다.
이는 흥미롭지만, 실제 유용성은 낮습니다. 그래도 명성 때문에 다룬다고 하는군요.

이 문제의 설정은 다음과 같습니다. 5명의 철학자가 테이블 주위에 앉아 있다고 가정합니다.
각 철학자 사이에는 하나의 포크가 있으며 (그러므로 총 5개) 철학자들이 생각할 때 포크가 필요하지 않은 시간과 필요한 시간이 있습니다.
필요한 시간에는 오른쪽/왼쪽 총 2개의 포크가 필요하며, 이 포크에 대한 경쟁과 그로 인해 발생하는 동기화 문제를 다룹니다.

그러므로 주요 과제는 철학자가 교착상태 없이 굶지 않는 루틴을 작성하는 겁니다.

```python
import threading

N = 5
forks = [threading.Semaphore(1) for _ in range(N)]


def left(p: int) -> int:
    return p


def right(p: int) -> int:
    return (p + 1) % N


def get_forks(p: int) -> None:
    forks[left(p)].acquire()
    forks[right(p)].acquire()


def put_forks(p: int) -> None:
    forks[left(p)].release()
    forks[right(p)].release()
```

이 코드가 교착상태가 되는 이유는 의존성 사이클이 생길 수 있기 때문입니다.

모든 철학자가 동시에 `get_forks()`에 들어가서 왼쪽 포크를 먼저 잡고(acquire 성공) 곧바로 오른쪽 포크를 기다리면(acquire 블록) 다음 상태가 되는데
- 철학자 0: 포크 0을 쥠, 포크 1을 기다림
- 철학자 1: 포크 1을 쥠, 포크 2를 기다림
- ...
- 철학자 4: 포크 4를 쥠, 포크 0을 기다림

이렇게 되면 각자가 하나를 쥔 채 다른 하나를 기다리는 `hold-and-wait` 상태가 만들어집니다.
기다림이 `0 → 1 → 2 → 3 → 4 → 0`으로 이어지는 `circular wait(원형 대기)`가 성립해서 아무도 진행하지 못하는 데드락 상태가 됩니다.
참고로 라이브락은 서로 양보/재시도하며 계속 실행은 되지만 진전이 없는 경우를 말합니다. 여기처럼 자원을 쥔 채로 멈춰 서는 건 데드락에 가깝죠.

이 상태를 해결하는 가장 간단한 방법은 `원형 대기(circular wait)`가 성립하지 않도록, 적어도 한 명의 포크를 잡는 순서를 바꾸는 것입니다.
모두가 `left → right` 순서로만 잡을 때는 원이 닫히지만, 한 명이라도 `right → left`로 잡으면 대기 방향이 한 군데에서 꺾여서 `0 → 1 → 2 → 3 → 4 → 0` 같은 사이클이 만들어지지 않습니다.

```python
def get_forks(p: int) -> None:
    # 한 명(여기서는 4번)만 반대로 잡아 원형 대기를 깨뜨린다
    if p == 4:
        forks[right(p)].acquire()
        forks[left(p)].acquire()
    else:
        forks[left(p)].acquire()
        forks[right(p)].acquire()
```
이렇게 바꾸면 4번 철학자는 먼저 오른쪽(포크 0)을 잡으려 하기 때문에, 각자 왼쪽 포크를 하나씩 쥔 채 오른쪽을 기다리는 형태가 더 이상 동시에 성립하지 않습니다.

즉, 한 가지 가능한 흐름은 다음과 같습니다(철학자: P0–P4, 포크: fork0–fork4).

- P0: fork0을 잡고 fork1을 기다림
- P1: fork1을 잡고 fork2를 기다림
- P2: fork2를 잡고 fork3을 기다림
- P3: fork3을 잡고 fork4를 기다림
- P4: fork0을 먼저 잡으려 하지만, 이미 P0가 잡고 있어 대기함

이 상태에서는 fork4가 아직 비어 있으므로 P3는 fork4를 얻어 식사를 진행할 수 있습니다. 이렇게 되면 `hold-and-wait`이 부분적으로는 생길 수 있어도, 원형 대기가 닫히지 않아 데드락으로 고착되지 않습니다.

이 문제가 실제 유용성이 낮다는 부분에 공감이 가는군요.
현실에서는 보통 포크를 left/right로 따로 다루기보다, 더 큰 단위의 락으로 임계구역을 직렬화해서 `hold-and-wait`/데드락 가능성을 줄이는 쪽이 실용적일 때가 많겠네요.(대신 병렬성은 떨어집니다).

# Thread Throttling
너무 많은 스레드가 동시에 작업을 수행해 시스템이 느려질 때, 너무 많다의 기준(최대 동시 실행 개수)을 정해 동시성을 제한할 수 있습니다. 세마포어를 활용해 이런 제한을 두는 접근을 `Throttling`이라고 부릅니다.

좀 더 구체적인 예로, 수백 개의 스레드가 어떤 문제를 병렬로 처리한다고 가정해 봅시다. 그중 특정 코드 구간이 실행될 때 매우 많은 메모리를 할당받는 상황이 있을 수 있습니다.
이 부분을 메모리 집약적 영역(`memory-intensive region`)이라 부르겠습니다.
모든 스레드가 동시에 이 영역에 들어가면 머신의 물리 메모리 한계를 초과할 수 있고, 그 결과 스레싱(디스크로 페이지 스와핑이 발생)으로 전체 계산이 느려집니다.

이 문제를 해결하려면 메모리 집약적 영역에 동시에 들어갈 수 있는 최대 개수로 세마포어를 초기화한 뒤, 해당 영역의 앞/뒤에 `wait/post`(파이썬에서는 `acquire/release`)를 배치하면 됩니다. 그러면 세마포어가 그 코드 구간에 동시에 존재하는 스레드 수를 자연스럽게 제한해 줍니다.

# How To Implement Semaphores
마지막으로 저레벨 `synchronization primitives`를 이용해 세마포어를 간단하게 만들어봅니다.
이 코드는 Dijkstra의 정의와 달리, 세마포어 값이 음수일 때 대기 중인 스레드 수를 반영하는 불변식을 유지하지 않습니다.
대신 값은 0보다 낮아지지 않도록 구현합니다. 이렇게 하는 편이 더 단순하고, 리눅스 구현과도 일치합니다(파이썬 내부 구현과도 비슷한 방향입니다).

파이썬으로 같은 아이디어(카운터 + 조건변수 + 락)로 옮기면 다음과 같습니다.
`threading.Condition()`을 사용시, 내부에 락을 포함하고 있어서서 `with cond:`로 `lock` 획득과 해제를 함께 처리할 수 있습니다.

```python
import threading

class Zemaphore:
    def __init__(self, value: int):
        self._value = value
        self._cond = threading.Condition()  # 내부에 카운터 Lock

    def wait(self) -> None:
        with self._cond:
            while self._value <= 0:
                self._cond.wait()
            self._value -= 1

    def post(self) -> None:
        with self._cond:
            self._value += 1
            self._cond.notify(1)
```

세마포어를 cv로 만드는 것은 그냥 공유 카운터 하나 두고, 그 값으로 `wait/post`하면 되는 것으로 보이지만 아래 조건들을 충족해야 합니다.
- 카운터 검사와 감소(`value > 0` 확인 후 `value--`)는 원자적으로 진행해야 합니다. 락이 없다면 동시에 통과해 카운터가 꼬입니다.
- `wakeup` 손실 문제를 피해야 합니다. 카운터 값을 체크 후(0) → 잠들 준비하는 사이에 다른 스레드가 `post()`로 깨웠는데 아직 스레드가 자지 않는다면, 신호가 사라져 영원히 잠들 수 있습니다. 그래서 `cv`는 반드시 같은 락을 잡은 상태에서 조건을 검사하고, `wait()`가 `lock`을 풀고 잠드는 동작이 원자적으로 이어져야 합니다.
- `spurious wakeup` 때문에 `if`가 아니라 `while`로 조건을 다시 검사해야 합니다.
- 여러 대기자가 있을 때 `notify(1)`로 하나만 깨울지, `notify_all()`로 다 깨운 뒤 경쟁시키는지 같은 정책과 공정성 문제가 남습니다.

# Summary
세마포어는 동시 프로그램을 만들 때 유용하게 쓰이는 기능입니다.
그래서 일부 프로그래머는 단순함과 유용성 때문에 `lock`과 `cv`를 피하고 세마포어만 사용하기도 하죠.

결과적으로 세마포어를 잠금(`lock`)과 조건 변수(`condition variable`)의 일반화로 볼 수 있지만, 세마포어 위에 조건 변수를 구현하는 일이 어렵다는 점을 고려하면 이 일반화는 생각만큼 일반적이지는 않습니다.