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

위 표에서 `Val`이 -1로 내려가는 행은, 대기 중인 스레드 수까지 한 정수 값에 합산해 적는 **Dijkstra 스타일 세마포어 정의**를 보여주려는 것입니다.
파이썬의 `threading.Semaphore`는 보통 사람이 편하게 이해하기 쉽게 **남아 있는 허용치 카운터 + `Condition` 기반 대기 큐**로 모델링하고, OSTEP 표의 음수 `Val`처럼 카운터에 대기까지 합산하는 형태는 공개적으로 보여주진 않습니다.
파이썬의 구현체 안에서 내부 정수로 카운터를 조정하고, 남은 허용치가 없으면 `Condition.wait()`로 대기 스레드를 큐에 넣는 방식을 쓰죠.

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
        lock.acquire()          # 퍼밋이 없어서 블록 → T0가 release 후 진행
        lock.release()

    th0 = threading.Thread(target=t0, name="T0")
    th1 = threading.Thread(target=t1, name="T1")
    th0.start(); th1.start()
    th0.join(); th1.join()
```



# Semaphores For Ordering
# The Producer/Consumer (Bounded Buffer) Problem
# Reader-Writer Locks
# The Dining Philosophers
# Thread Throttling
# How To Implement Semaphores
# Summary