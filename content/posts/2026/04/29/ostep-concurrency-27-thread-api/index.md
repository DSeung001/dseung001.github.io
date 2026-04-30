---
title: "Operating Systems: Three Easy Pieces - Thread API"
date: 2026-04-29T00:00:00+09:00
categories: [ "Memo", "Digging", "OSTEP" ]
tags: [ "OSTEP", "Operating Systems", "Thread", "Thread API", "Synchronization" ]
draft: false
description: "OSTEP Concurrency 27강 Thread API 정리"
keywords: [ "OSTEP", "Concurrency", "Thread", "Thread API", "Synchronization", "Process" ]
author: "DSeung001"
lastmod: 2026-04-29T00:00:00+09:00
---
교재에서는 `c`의 `POSIX`을 기반으로 진행되고 있고 `Python`을 공부 중이므로 `Python`의 `threading`로 해당 글을 진행합니다.
`threading` 모듈은 OS의 저수준 스레딩 기능 위에 구축된 객체 지향 API로 `Unix` 계얼에서는 `POSIX Thread(pthreads)` 라이브러리를 기반으로 동작합니다.

# Thread Creation
파이썬에서는 `threading.Thread` 객체를 만들어 스레드를 생성합니다. 핵심은 "어떤 함수를 어떤 인자로 실행할지"를 스레드 객체에 넘기고, `start()`로 실행을 시작하는 흐름입니다.

```python
import threading

def worker(name, count):
    for i in range(count):
        print(f"[{threading.current_thread().name}] {name}: {i}")

# target: 새 스레드에서 실행할 함수
# args: target 함수에 전달할 인자 튜플
t1 = threading.Thread(target=worker, args=("A", 3), name="Thread-A")
t2 = threading.Thread(target=worker, args=("B", 3), name="Thread-B")

t1.start()
t2.start()
```

`threading.Thread(...)` 호출은 내부적으로 `Thread.__init__(...)` 인자와 매핑이 되죠죠
```python
   def __init__(self, group=None, target=None, name=None,
                 args=(), kwargs=None, *, daemon=None, context=None):
```

- `group`: 예약된 인자(현재는 `None`만 사용)
- `target`: 새 스레드가 시작되면 실행할 함수
- `name`: 디버깅/로그용 스레드 이름
- `args`: `target`에 전달할 위치 인자 튜플
- `kwargs`: `target`에 전달할 키워드 인자 딕셔너리
- `daemon`: 메인 스레드 종료 시 함께 종료할 데몬 스레드 여부
- `context`: 실행 컨텍스트 전달용 인자(버전에 따라 지원 여부가 다를 수 있음)

스레드를 생성하면 같은 프로세스 주소 공간을 공유하지만, 각 스레드는 자신만의 호출 스택을 가지고 독립적으로 실행됩니다.

# Thread Completion
스레드를 만든 뒤 완료까지 기다리려면 `join()`을 호출해야 합니다. 즉, 메인 스레드(또는 호출한 스레드)는 대상 스레드가 끝날 때까지 대기합니다.
파이썬 시그니처는 다음과 같습니다.

```python
def join(self, timeout=None):
```

- `timeout`: 최대 대기 시간(초)입니다. `None`이면 종료될 때까지 계속 기다립니다.
- 반환값: `join()` 자체는 값을 반환하지 않고 단지 종료까지 기다리는 동기화만 담당합니다.

```python
import threading
import time

def worker(name, delay):
    print(f"{name}: start")
    time.sleep(delay)
    print(f"{name}: end")

t1 = threading.Thread(target=worker, args=("T1", 1))
t2 = threading.Thread(target=worker, args=("T2", 2))

t1.start()
t2.start()

# 두 스레드가 끝날 때까지 대기
t1.join()
t2.join()
print("main: all threads completed")
```

OSTEP의 `pthread_join(thread, value_ptr)`와 비교하면 중요한 차이가 있습니다.  
`pthread_join()`은 스레드의 반환값 포인터를 받을 수 있지만, `threading.Thread.join()`은 반환값을 직접 전달하지 않습니다. 
스레드의 각 결과가 필요하면 아래 방식 중 하나를 사용합니다.

- 공유 객체(예: 리스트/딕셔너리)에 결과 저장 + 락으로 보호
- `queue.Queue`에 결과 넣기
- `concurrent.futures.ThreadPoolExecutor`로 `Future.result()` 사용

`Python`에서 `thread`를 돌릴 때 주의할 부분이 있습니다.
- 스레드를 만들자마자 즉시 `join()`하면 겹쳐 실행할 구간이 거의 없어 사실상 순차 실행과 비슷해집니다. 특히 `CPython`에서는 `GIL` 때문에 CPU-bound 작업의 병렬 이득이 원래 제한적이라, 이런 패턴은 효과가 더 줄어듭니다.
- 장시간 실행되는 서버/워커 모델은 스레드를 요청마다 생성,즉시 종료하지 않고 오래 유지해 계속 작업을 처리하므로, 매 작업마다 `join()`으로 기다리는 구조를 쓰지 않는 경우가 많습니다(보통 프로그램 종료 시점에만 정리).
- `join()`은 완료 대기 도구일 뿐, 경쟁 조건을 막아주지는 않습니다, 하지만 병렬 작업에서는 여러 스레드의 계산이 끝난 뒤 다음 단계로 넘어가기 위한 동기화 지점(간단한 barrier)으로 자주 사용됩니다.

# Locks
스레드 생성과 Join을 제외하고 스레드 라이브러리에서 중요한 함수는 임계 구역에 대한 상호 배제를 제공하는 함수들입니다.

원문(pthreads)의 핵심을 `Python threading`에 대입하면 `pthread_mutex_lock/unlock`은 `Lock.acquire()/release()` 또는 `with lock:`에 대응합니다.

아래 코드의 의도는 원문과 같습니다.
- 락이 비어 있으면 즉시 획득하고 임계 구역에 진입
- 다른 스레드가 락을 잡고 있으면 획득할 때까지 대기
- 락을 획득한 스레드만 해제해야 함
```python
import threading

lock = threading.Lock()
counter = 0

def worker():
    global counter
    for _ in range(100000):
        # acquire + release를 안전하게 보장
        # lock을 획득해야만 counter += 1 로직 실행
        with lock:
            counter += 1
```

**Lock.acquire()/release()**
스레드가 `acquire()`를 호출하면 해당 스레드는 락을 획득(잠금)하여 다른 스레드의 접근을 차단하며, 작업 후 `release()`로 락을 해제해야 다른 스레드가 진입할 수 있습니다.

```python
def acquire(self, blocking=True, timeout=-1):
```

- `lock.acquire(blocking=False)`
  - 락이 비어 있으면 즉시 획득하고 `True`를 반환
  - 이미 다른 스레드가 락을 잡고 있으면 기다리지 않고 즉시 `False`를 반환
  - 기다리지 않고 시도를 할 수 있어, 실패 시 다른 작업을 하거나 나중에 재시도할 때 유용

- `lock.acquire(timeout=...)`
  - 락을 최대 지정 시간(초)까지만 대기
  - 시간 안에 획득하면 `True`, 시간 초과 시 `False`를 반환
  - 무한 대기를 피하고, 잠금 획득 실패 시 대체 경로를 두고 싶은 경우에 유용

위 인자들로 다음과 같이 구현이 됩니다.
```python
if lock.acquire(blocking=False):
    try:
        # 즉시 락 획득에 성공한 경우만 수행
        pass
    finally:
        lock.release()

# 최대 0.5초만 기다린 뒤 포기
if lock.acquire(timeout=0.5):
    try:
        pass
    finally:
        lock.release()
```

원문처럼 `trylock/timedlock` 스타일을 남용하면 코드 복잡도가 커질 수 있지만 교착 상태 회피나 무한 대기 방지가 필요한 상황에서는 중요합니다.

# Condition Variables
조건 변수(`threading.Condition`)는 <u>한 스레드가 상태 변화를 기다리고, 다른 스레드가 그 변화를 알리는(signal) 구조</u>를 구현할 때 사용되며 데이터 전달 없이 상태 변화만 알립니다. Python 런타임은 조건 변수 관련 기능을 OS 동기화 기능을 래핑해서 제공합니다. 코드에서는 `Condition` API를 쓰고, 내부에서는 `sleep/wakeup + lock` 조합이 처리됩니다.

원문의 `pthread_cond_wait/ pthread_cond_signal`은 Python에서 다음과 같이 매칭되죠.
- `pthread_cond_wait(cond, mutex)` = `cond.wait()`
- `pthread_cond_signal(cond)` = `cond.notify()` (여러 개 깨우려면 `cond.notify_all()`)

핵심은 `c`의 `POSIX`와 동일합니다. 

1. 조건 변수는 락과 함께 사용됩니다.
2. `wait()`는 락을 잡은 상태에서 호출합니다.
3. `wait()`는 내부적으로 잠들 때 락을 놓고, 깨어난 뒤 다시 락을 잡고 복귀합니다.
4. 깨어났다고 `ready` 같은 조건식이 바로 참이라는 보장은 없습니다(가짜 깨움, 다른 스레드의 간섭 등). 그래서 `if`가 아니라 `while`로 조건을 재검사합니다.

```python
import threading
import time

cond = threading.Condition()
ready = False

def waiter():
    global ready
    with cond:  # lock 획득
        while not ready:
            cond.wait()  # 잠들었다 깨어날 때 락을 다시 잡은 뒤 복귀, 그래도 ready가 거짓이면 반복 대기
        print("waiter: 조건 충족, 작업 진행")

def signaler():
    global ready
    time.sleep(0.05)  # waiter가 cond.wait()에 들어갈 시간 대기
    with cond:  # 상태 변경 + notify는 같은 lock 구역에서
        ready = True
        cond.notify()  # 대기 중 하나 깨우기

if __name__ == "__main__":
    t_wait = threading.Thread(target=waiter, name="waiter")
    t_sig = threading.Thread(target=signaler, name="signaler")
    t_wait.start()
    t_sig.start()
    t_wait.join()
    t_sig.join()
    print("main: 모든 스레드 종료")
```

위처럼 `ready` 수정과 `notify()`를 같은 임계 구역에서 수행해야 `race condition`을 줄일 수 있습니다.
단순 flag 스핀(`while not ready: pass`)으로 대기하는 방식은 CPU를 계속 차지하므로 `cond.wait()`로 CPU를 낭비하지 않고 대기하는 편이 낫습니다. 또한 타이밍 버그(비결정적인 동작) 등이 생길 수 있습니다.

# Compiling and Running
OSTEP 소스 코드에 대한 컴파일 실행법입니다. 
[https://github.com/remzi-arpacidusseau/ostep-code()]https://github.com/remzi-arpacidusseau/ostep-code) 여기서 코드를 확인할 수 있지만, 이 글은 `Python`을 기준으로 진행했기 때문에 이 부분은 패스하겠습니다. (코드의 내용은 비슷한 방향으로 진행했습니다.)

# Summary
스레드 생성, 잠금, 상호 배제, 조건 변수, 신호 및 대기 등 동시성 라이브러리의 기본을 소개했습니다.
더 많이 알고 싶고 더 저수준까지 알고 싶다면 `Linux` 등에서 `man -k pthread`로 인터페이스를 이루는 100개가 넘는 API를 확인할 수 있습니다.
스레드와 관련해 어려운 부분은 API가 아니라, 동시성 프로그램을 구축하는 과정 속의 복잡한 논리임을 생각하며 이 글을 마칩니다. 

## Thread API 가이드라인

- 스레드 간 잠금·신호 기능은 최대한 단순해야 합니다. 복잡해지면 스레드 상호작용 버그로 이어집니다.
- 스레드 간 상호작용은 최소화하세요. 각 상호작용은 신중하게 설계하고, 검증된 방식으로만 구성해야 합니다.
- 잠금과 조건 변수는 반드시 초기화하세요. 그렇지 않으면 간헐적으로 버그가 납니다.
- 반환 코드를 확인하세요.(`C`/Unix 프로그래밍 관례 기준.)
- 스레드에 인자를 넘기거나 값을 돌려줄 때는 각별히 주의하세요. 특히 스택에 올린 지역 변수에 대한 참조를 넘기는 경우는 거의 항상 잘못된 패턴입니다.
- 스레드마다 호출 스택이 따로 있으므로, 값을 공유하려면 힙이나 다른 스레드에서도 접근 가능한 저장 위치를 써야 합니다.
- Linux의 pthread 매뉴얼은 매우 유용합니다.(`Python`은 [공식 문서](https://docs.python.org/ko/3/library/threading.html)를 참고하세요.)


## WSL, man -k pthread
Windows의 `WSL`에서 `man -k pthread`로 찾아본 결과, 이 환경에선 페이지 단위로 74개가 잡혔습니다(원문이 말하는 “100개 이상”은 배포판·`man` 인덱스 범위에 따라 달라질 수 있습니다).

- `pthread_attr_*`: 생성 옵션(스택·detach·스케줄·시그널 마스크·affinity) → `pthread_create` 연동
- `pthread_create`/`join`/`detach`/`exit`: 생성·종료 동기화·detach·종료
- `pthread_cancel`/`pthread_cleanup_*`/`pthread_testcancel`: 취소·청소 스택·취소 지점 테스트
- `pthread_getsched*`/`pthread_setsched*`: 스케줄 정책·우선순위(유효 범위: OS/권한)
- `*_affinity*_np`: 논리 CPU 관련
- `pthread_kill`/`pthread_sigmask`/`pthread_sigqueue`: 스레드별 시그널·블록 마스크·큐잉(+데이터)
- `pthread_mutex*`/`mutexattr_*`: 뮤텍스 + 속성(pshared, robust 등)
- `pthread_rwlockattr_*`: rwlock **속성**, 아래에 `pthread_rwlock_*`는 없음
- `pthread_spin_*`: 스핀락
- 세마포어(`sem_*` 등): `pthread_*` 검색 범위 밖이라 위 목록에 잘 안 끼는 경우 많음
- `pthread_yield`(계열): 스레드 락 양보 힌트(동작 보장은 약함)

터미널 원문은 다음과 같습니다.

```bash
root@DESKTOP-7DV25NI:~# man -k pthread
pthread_attr_destroy (3) - initialize and destroy thread attributes object
pthread_attr_getaffinity_np (3) - set/get CPU affinity attribute in thread attributes object
pthread_attr_getdetachstate (3) - set/get detach state attribute in thread attributes object
pthread_attr_getguardsize (3) - set/get guard size attribute in thread attributes object
pthread_attr_getinheritsched (3) - set/get inherit-scheduler attribute in thread attributes object
pthread_attr_getschedparam (3) - set/get scheduling parameter attributes in thread attributes object
pthread_attr_getschedpolicy (3) - set/get scheduling policy attribute in thread attributes object
pthread_attr_getscope (3) - set/get contention scope attribute in thread attributes object
pthread_attr_getsigmask_np (3) - set/get signal mask attribute in thread attributes object
pthread_attr_getstack (3) - set/get stack attributes in thread attributes object
pthread_attr_getstackaddr (3) - set/get stack address attribute in thread attributes object
pthread_attr_getstacksize (3) - set/get stack size attribute in thread attributes object
pthread_attr_init (3) - initialize and destroy thread attributes object
pthread_attr_setaffinity_np (3) - set/get CPU affinity attribute in thread attributes object
pthread_attr_setdetachstate (3) - set/get detach state attribute in thread attributes object
pthread_attr_setguardsize (3) - set/get guard size attribute in thread attributes object
pthread_attr_setinheritsched (3) - set/get inherit-scheduler attribute in thread attributes object
pthread_attr_setschedparam (3) - set/get scheduling parameter attributes in thread attributes object
pthread_attr_setschedpolicy (3) - set/get scheduling policy attribute in thread attributes object
pthread_attr_setscope (3) - set/get contention scope attribute in thread attributes object
pthread_attr_setsigmask_np (3) - set/get signal mask attribute in thread attributes object
pthread_attr_setstack (3) - set/get stack attributes in thread attributes object
pthread_attr_setstackaddr (3) - set/get stack address attribute in thread attributes object
pthread_attr_setstacksize (3) - set/get stack size attribute in thread attributes object
pthread_cancel (3)   - send a cancellation request to a thread
pthread_cleanup_pop (3) - push and pop thread cancellation clean-up handlers
pthread_cleanup_pop_restore_np (3) - push and pop thread cancellation clean-up handlers while saving cancelability type
pthread_cleanup_push (3) - push and pop thread cancellation clean-up handlers
pthread_cleanup_push_defer_np (3) - push and pop thread cancellation clean-up handlers while saving cancelability type
pthread_create (3)   - create a new thread
pthread_detach (3)   - detach a thread
pthread_equal (3)    - compare thread IDs
pthread_exit (3)     - terminate calling thread
pthread_getaffinity_np (3) - set/get CPU affinity of a thread
pthread_getattr_default_np (3) - get or set default thread-creation attributes
pthread_getattr_np (3) - get attributes of created thread
pthread_getconcurrency (3) - set/get the concurrency level
pthread_getcpuclockid (3) - retrieve ID of a threads CPU time clock
pthread_getname_np (3) - set/get the name of a thread
pthread_getschedparam (3) - set/get scheduling policy and parameters of a thread
pthread_join (3)     - join with a terminated thread
pthread_kill (3)     - send a signal to a thread
pthread_kill_other_threads_np (3) - terminate all other threads in process
pthread_mutex_consistent (3) - make a robust mutex consistent
pthread_mutex_consistent_np (3) - make a robust mutex consistent
pthread_mutexattr_getpshared (3) - get/set process-shared mutex attribute
pthread_mutexattr_getrobust (3) - get and set the robustness attribute of a mutex attributes object
pthread_mutexattr_getrobust_np (3) - get and set the robustness attribute of a mutex attributes object
pthread_mutexattr_setpshared (3) - get/set process-shared mutex attribute
pthread_mutexattr_setrobust (3) - get and set the robustness attribute of a mutex attributes object
pthread_mutexattr_setrobust_np (3) - get and set the robustness attribute of a mutex attributes object
pthread_rwlockattr_getkind_np (3) - set/get the read-write lock kind of the thread read-write lock attribute object
pthread_rwlockattr_setkind_np (3) - set/get the read-write lock kind of the thread read-write lock attribute object
pthread_self (3)     - obtain ID of the calling thread
pthread_setaffinity_np (3) - set/get CPU affinity of a thread
pthread_setattr_default_np (3) - get or set default thread-creation attributes
pthread_setcancelstate (3) - set cancelability state and type
pthread_setcanceltype (3) - set cancelability state and type
pthread_setconcurrency (3) - set/get the concurrency level
pthread_setname_np (3) - set/get the name of a thread
pthread_setschedparam (3) - set/get scheduling policy and parameters of a thread
pthread_setschedprio (3) - set scheduling priority of a thread
pthread_sigmask (3)  - examine and change mask of blocked signals
pthread_sigqueue (3) - queue a signal and data to a thread
pthread_spin_destroy (3) - initialize or destroy a spin lock
pthread_spin_init (3) - initialize or destroy a spin lock
pthread_spin_lock (3) - lock and unlock a spin lock
pthread_spin_trylock (3) - lock and unlock a spin lock
pthread_spin_unlock (3) - lock and unlock a spin lock
pthread_testcancel (3) - request delivery of any pending cancellation request
pthread_timedjoin_np (3) - try to join with a terminated thread
pthread_tryjoin_np (3) - try to join with a terminated thread
pthread_yield (3)    - yield the processor
pthreads (7)         - POSIX threads
```

추가로 세마포어도 하면
```bash
root@DESKTOP-7DV25NI:~# man -k sem
apt-patterns (7)     - Syntax and semantics of apt search patterns
as (1)               - the portable GNU assembler.
bsd_signal (3)       - signal handling with BSD semantics
gpgparsemail (1)     - Parse a mail message into an annotated format
sem_close (3)        - close a named semaphore
sem_destroy (3)      - destroy an unnamed semaphore
sem_getvalue (3)     - get the value of a semaphore
sem_init (3)         - initialize an unnamed semaphore
sem_open (3)         - initialize and open a named semaphore
sem_overview (7)     - overview of POSIX semaphores
sem_post (3)         - unlock a semaphore
sem_timedwait (3)    - lock a semaphore
sem_trywait (3)      - lock a semaphore
sem_unlink (3)       - remove a named semaphore
sem_wait (3)         - lock a semaphore
semanage.conf (5)    - global configuration file for the SELinux Management library
semctl (2)           - System V semaphore control operations
semget (2)           - get a System V semaphore set identifier
semop (2)            - System V semaphore operations
semtimedop (2)       - System V semaphore operations
sigisemptyset (3)    - POSIX signal set operations
smartpqi (4)         - Microsemi Smart Family SCSI driver
sysv_signal (3)      - signal handling with System V semantics
x86_64-linux-gnu-as (1) - the portable GNU assembler.
```