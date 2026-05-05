---
title: "Operating Systems: Three Easy Pieces - Condition Variables"
date: 2026-05-04T00:00:00+09:00
categories: [ "Memo", "Digging", "OSTEP" ]
tags: [ "OSTEP", "Operating Systems", "Concurrency", "Condition variable", "Synchronization"]
draft: false
description: "OSTEP Concurrency 30강 Condition Variables 정리"
keywords: [ "OSTEP", "Concurrency", "Condition variable", "cv", "Monitor", "Synchronization" ]
author: "DSeung001"
lastmod: 2026-05-04T00:00:00+09:00
---

아쉽게도 `lock`만으로는 동시 프로그램을 구축하는 데 제약이 있습니다.<br/>
특히 스레드가 실행을 계속하기 전에 조건이 참인지 확인을 하고 싶어하는 경우가 많은 데, 이를 해결할 때 부족한점이 보이죠.

예를 들어 부모 스레드는 자식 스레드가 완료되었는 지 여부를 확인하고 싶을 수 있죠.(이를 join으로 부르기도 합니다.)

```python
import threading

def child():
    print("child")
    # XXX how to indicate we are done?

def main():
    print("parent: begin")
    t = threading.Thread(target=child)
    t.start()
    # XXX how to wait for child?
    print("parent: end")


if __name__ == "__main__":
    main()
```

위 코드는 실행하면 아래처럼 부모가 먼저 끝날 수 있습니다.

```text
parent: begin
parent: end
child
```

원하는 순서는 자식이 끝난 뒤 부모가 마무리하는 것입니다.

```bash
parent: begin
child
parent: end
```

파이썬이라면 `t.join()` 한 줄이 이 경우의 정석입니다. <br/>
교재에서 스핀에서 `condition variable`으로 이어지는 구성인 이유는 조건이 참이 될 때까지 기다린다는 더 일반적인 문제를 단계적으로 보여 주기 위해서입니다.

여기서 `lock`만으로 부족할까라는 생각이 들 수 있는데 `lock`은 어디까지가 상호배제로 교착을 막는 쪽이고, `cv`처럼 조건이 맞을 떄까지 `cpu`를 반환하고 대기하는 건 별도의 메커니즘입니다.

`lock`으로만 구현하려면 아래처럼 공유 플래그를 두고 스핀으로 `done`이 될 때까지 도는 방식입니다. 동작은 맞출 수 있지만 CPU 사이클을 허비합니다.
```python
import threading

# 스레드 간에 공유되는 “완료” 플래그
done = [0]

def child():
    print("child")
    done[0] = 1

def main():
    print("parent: begin")
    t = threading.Thread(target=child)
    t.start()
    while done[0] == 0:
        pass  # spin
    print("parent: end")


if __name__ == "__main__":
    main()
```
# Definition and Routines
조건이 충족될 때까지 기다리기 위해 스레드는 `cv`(condition variable)를 사용할 수 있습니다. `cv`는 스레드가 실행 상태이지만 원하는 상태가 아닐 때, 조건이 충족될 때까지 대기열에 넣는 큐입니다.
다른 스레드가 상태를 바꿔 (`cv`에 신호를 보내) 대기 중인 스레드 중 하나를 깨우면 다시 진행할 수 있도록 합니다.

이 아이디어는 `Dijkstra`의 `private semaphores`의 사용으로 올라가며, 유사한 아이디어들을 `Hoare`가 모니터에 대한 작업에서 `cv(condition variable)`로 명명했습니다.
- **세마포어(semaphores)**: 멀티프로그래밍 환경에서 공유 자원에 대한 접근을 제어하는 정수 변수 기반의 동기화 도구
- **세마포어랑 락(뮤텍스) 차이**: 세마포어(Semaphore)는 공유 자원에 접근하는 프로세스/스레드의 수를 제어하는 신호등 역할(카운터)의 동기화 도구이며, 락(Lock, 특히 뮤텍스)은 단 하나만 접근하도록 막는(1개 제한) 잠금 메커니즘
- **모니터(monitor)**: 세마포어의 복잡한 구현과 교착 상태(Deadlock) 위험을 줄이기 위해 나온 고수준 동기화 도구

이러한 `cv`의 사용법은 아래와 같습니다. C/POSIX에서는 `pthread_mutex_t`와 `pthread_cond_t`가 짝을 이루고, 파이썬에서는 `threading.Condition`이 같은 역할을 묶어 줍니다.

```python
import threading

done = False
cv = threading.Condition()  # 내부 락 + 조건 변수

def thr_exit():
    global done
    with cv:
        done = True
        cv.notify()  # pthread_cond_signal 에 대응

def child():
    print("child")
    thr_exit()

def thr_join():
    with cv:
        while not done:
            cv.wait()  # pthread_cond_wait : 락을 풀고 대기 큐로, 깨어나면 락 재획득

def main():
    print("parent: begin")
    t = threading.Thread(target=child)
    t.start()
    thr_join()
    print("parent: end")


if __name__ == "__main__":
    main()
```

위 코드는 같은 출력 값을 지니지만 `cv`를 사용함으로써 CPU 사이클 낭비를 일으키지 않죠.

```bash
parent: begin
child
parent: end
```

스케줄링에 따라 두 가지 경우를 구분해서 보면 위 코드를 이해하기 쉽습니다.
- 한쪽에서는 부모가 `thr_join()`에서 먼저 `wait()`에 들어가고, 나중에 자식이 끝내면서 `notify()`로 부모를 깨웁니다.
- 자식 스레드가 생성 직후 곧바로 실행되어 `done`을 참으로 만들고 잠든 스레드가 없으므로 `notify()`는 한 번 시도했다가 특별히 아무 일도 일어나지 않습니다. 그다음 부모가 `thr_join()`에 들어가면 `done`이 이미 참이므로 `wait()` 없이 바로 반환합니다.

부모가 조건 대기 여부를 `if` 한 번만이 아닌 `while not done:`으로 두는 이유는 다음에 나올 코드처럼 잘못된 경우를 보면 됩니다.
`done` 검사와 `wait()` 사이에 스레드 인터러빙이 생길 수 있는 코드로 이로 인해 판단이 틀어질 수 있기 때문입니다.
또한 허위 기상(spurious wakeup)이 있는 환경에서는 루프 없이 깨어난 뒤 상태를 다시 확인하지 않는 것 자체가 위험합니다.

- **spurious wakeup**: 대기 중인 스레드가 깨어날 조건이 충족되지 않았음에도 불구하고 스스로 깨어나는 현상

`thr_exit()` / `thr_join()`에서 각 요소가 왜 필요한지 보려면, 상태 변수 없이 컨디션 변수만 쓰거나 `lock`을 잡지 않는 변형을 떠올리면 됩니다. 아래 코드를 보며 `cv`를 이렇게 쓰는 이유를 이해해 봅시다.

**상태 변수 없이 신호만 보내는 경우** <br/>
공유 상태 `done` 없이 스레드를 `wake`하면 안 됩니다.

```python
import threading

cv = threading.Condition()


def thr_exit_broken_no_state():
    with cv:
        cv.notify()


def thr_join_broken_no_state():
    with cv:
        cv.wait()
```

이 경우는 자식이 부모보다 먼저 실행되어 `notify()`를 호출했을 때,
아직 `wait()`에 들어간 스레드가 없으면 그 신호는 소비될 곳 없이 사라집니다.
그 뒤 부모가 `wait()`에 들어가면 영원히 깨어나지 못하게 되죠. 그래서 스레드들이 공유해야 하는 값이 있어야 원활히 동작합니다.

**`lock` 없이 `signal/wait`로 상태 값을 읽는 경우**<br/>
또 다른 안 좋은 예로, `signal`/`wait` 호출 자체에는 락이 관여하지 않아도 된다고 가정하고 값만 건드리는 경우입니다. 
파이썬의 `threading.Condition.notify()`는 호출 스레드가 <u>`lock`을 잡은 채 호출해야 한다고 문서화되어 있지만</u>, 여기서는 교재와 같이 그 규칙을 어기는 실수가 있다고 가정하고 같은 **lost wakeup** 논증을 따라갑니다.
- **lost wakeup**: 멀티스레딩 환경에서 발생하는 대표적인 동기화 오류 중 하나로, 깨우라는 신호(Signal)를 보냈음에도 불구하고 대기 중인 스레드가 이를 받지 못해 영원히 잠들어 버리는 현상

```python
import threading

done = False
cv = threading.Condition()


def thr_exit_broken():
    global done
    done = True
    cv.notify()  # 올바른 패턴은 with cv 블록 안에서 호출하는 것이 일반적


def thr_join_broken():
    if not done:  # 락 바깥에서 공유 상태를 읽어 검사와 wait 사이가 원자적이지 않음
        with cv:
            cv.wait()
```

위 코드에서 발생 가능한 인터리빙 시나리오는 다음과 같습니다.
1. 부모는 `if not done`을 볼 때 `done`이 거짓이었고, `wait()`를 호출하기 전에 다른 스레드에게 실행이 넘어갈 수 있습니다.
2. 자식이 먼저 돌아가 `done`을 참으로 만들고 `notify()`했지만 아직 `wait()`에 들어간 스레드가 없어 깨울 대상이 없죠.
3. 부모가 다시 돌아와 `wait()`에 들어가면, 상태는 이미 참인데 앞선 분기 때문에 잠들어 남게 됩니다.

단순 `join` 예제만으로도 조건 변수를 쓸 때 조심할 점을 알 수 있습니다. 그래서 `notify`/`wait` 할 때도 `lock`을 든 채 하는 편이 단순하고 안전합니다.

다음 절에서 다룰 버퍼 문제로 넘어가기 전에, 가장 단순한 형태부터 짚습니다.
처음에는 버퍼가 비어 있다고 두고(`count == 0`), `put`은 비어 있을 때만 채울 수 있고 `get`은 차 있을 때만 꺼낼 수 있습니다.

```python
# 단일 슬롯 버퍼: count==0 이면 비어 있음, count==1 이면 가득 참
buffer = 0
count = 0


def put(value: int) -> None:
    global buffer, count
    assert count == 0
    count = 1
    buffer = value


def get() -> int:
    global buffer, count
    assert count == 1
    count = 0
    return buffer
```

실제 코드에서는 위 `put`/`get`을 여러 스레드가 동시에 부르므로 단순히 `assert`만으로 값을 구분하는 걸로는 부족합니다. 
다음 내용에서 `lock`과 `cv`로 동기화 문제를 어떻게 다루는지 볼 수 있습니다.

# The Producer/Consumer (Bounded Buffer) Problem
하나 이상의 생산자 스레드와 하나 이상의 소비자 스레드를 상상해봅시다.
생산자는 데이터를 만들어 버퍼에 넣고, 소비자는 버퍼에서 항목을 꺼내 소비합니다.
이런 형태는 여러 시스템에서 쓰입니다. 예를 들어 다중 스레드 웹 서버에서는 생산자가 HTTP 요청을 작업 큐(제한된 버퍼)에 넣고,
소비자 스레드는 그 큐에서 요청을 꺼내 처리합니다.

유한 버퍼는 한 프로그램의 출력을 다른 프로그램으로 파이프할 때도 쓰입니다. 예를 들어 `grep`이 있습니다.

```bash
grep foo file.txt | wc -l
```

위 명령에서 `grep`은 파일에서 패턴과 맞는 줄을 뽑아 주는 생산자 역할을 하고, `wc -l` 프로세스는 소비자로 표준 입력에 연결되어 있어 앞쪽에서 넘어온 스트림의 줄 수를 세어 출력합니다.

유한 버퍼는 공유 자원이므로 동기화된 접근이 필요합니다. 그렇지 않으면 경쟁 상태가 발생할 수 있습니다.

가장 먼저, 앞에서 정의한 단일 슬롯 버퍼 `put`/`get`을 생산자·소비자가 이렇게 부르는 형태만 짚습니다.

```python
def producer(loops: int) -> None:
    for i in range(loops):
        put(i)


def consumer() -> None:
    while True:
        tmp = get()
        print(tmp)
```
위 코드는 생산자가 `put(i)`만 반복하고, 소비자는 `while True`로 `get()`·`print`만 돌리는 형태입니다. 다만 앞 절의 `get`은 버퍼가 비어 있으면(`count == 0`) `assert`로 곧장 실패합니다.
현재 로직에는 두 스레드를 동시에 돌리더라도, 버퍼가 비었을 때는 `get`을, 찼을 때는 `put`을 막고 기다리게 하며 경쟁을 피하게 하는 동기화가 없어서 의미 있는 파이프라인이라 보기 어렵습니다.

그 이유는 대략 다음과 같습니다.
- 소비자가 버퍼에 값이 들어올 때까지 `get` 안팎에서 바쁜 대기(스핀)나 짧은 간격 폴링으로 버틸 수밖에 없을 때가 있습니다.
- 생산자가 아무것도 넣지 않는 동안에도 소비자는 CPU를 허비합니다.
그래서 의미 있는 파이프라인을 만들려면 버퍼 상태를 볼 때 `lock`을 두고, 기다릴 때는 `cv`로 잠들었다가 깨우는 편이 낫습니다.

단일 슬롯 버퍼에 뮤텍스·조건 변수를 얹은 생산자·소비자 루프입니다. `spurious wakeup`을 대비해 `wait` 전 조건 검사에는 `while`을 씁니다.

---
참고로 `spurious wakeup`의 주된 발생 이유는 다음과 같습니다.
- OS 수준의 인터럽트나 시그널(프로세스에 OS 시그널로 인한 강제 깨움)
- 현대의 멀티코어 환경에서도 정확히 신호를 받은 스레드만 깨우는 것은 비용이 크므로, 스레드 스케줄러가 시스템 처리량을 높이려고 조건을 완화해 스레드 중 일부를 느슨하게 깨우는 경우가 존재
---

유한 버퍼에 `cv`를 추가해 봅시다.
파이썬의 `threading.Condition()`은 기본으로 내부에 `RLock`을 두므로, 락과 조건 변수를 묶어 쓰는 요구와 잘 맞습니다.

```python
import threading

# 위의 「단일 슬롯 버퍼」 블록과 같이 두어야 함
# buffer, count = 0, put, get

loops = 10  # 실제로는 인자 등으로 초기화
cond = threading.Condition()

def producer() -> None:
    for i in range(loops):
        with cond:
            # 버퍼가 찼으면(count==1) 넣을 수 없으니 wait으로 락을 풀고 대기
            while count == 1:
                cond.wait()
            put(i)
            # 대기 중인 스레드 하나를 깨움(누가 깨워지는지·순서는 구현/OS에 따름)
            cond.notify()


def consumer() -> None:
    for _ in range(loops):
        with cond:
            while count == 0:
                cond.wait()
            tmp = get()
            cond.notify()
        print(tmp)
```

위 코드는 생산자·소비자가 각각 한 스레드일 때는 원활하게 돌아갑니다. `while`으로 재검사하는 부분은 깨어난 직후 락을 잡은 채 공유 상태를 다시 확인해, 안 맞으면 다시 자는 패턴이라 가짜 깨움과 재스케줄 타이밍에도 안전합니다.

위 코드의 문제는 이번에 깨워야 할 역할이 생산자인지 소비자인지를 구분하지 않는다는 점입니다. 소비자가 버퍼를 비운 뒤에는 값을 넣을 생산자를 깨우는 편이 맞는데, `notify()`가 다른 소비자만 깨우면 그 스레드는 `while count == 0`에서 다시 잠들고, 버퍼에 빈 자리가 있어도 생산자는 실행 못한 채 잠든 채로 남을 수 있습니다. 

이를 해결하기 위해 조건 변수를 둘로 나누어 생산자는 `empty`(빈 슬롯), 소비자는 `fill`(채워짐) 쪽 큐에서만 기다리게 하고, 각자 상대 역할 큐로만 신호를 보내도록 고칩니다.

파이썬에서 같은 분리를 쓰려면 두 `Condition`이 같은 뮤텍스를 물려받아야 `wait`와 `notify` 전후로 `count`와 버퍼가 한 락 아래에서만 바뀌게 할 수 있습니다.

```python
import threading

# 위의 `단일 슬롯 버퍼` 코드 이용
# buffer, count = 0, put, get

loops = 10  # 실제로는 인자 등으로 초기화
mutex = threading.Lock()
empty = threading.Condition(mutex)
fill = threading.Condition(mutex)

def producer() -> None:
    for i in range(loops):
        with empty:
            while count == 1:
                empty.wait()
            put(i)
            fill.notify()


def consumer() -> None:
    for _ in range(loops):
        with fill:
            while count == 0:
                fill.wait()
            tmp = get()
            empty.notify()
        print(tmp)
```
이렇게 하면 같은 공유 상태에 들어가는 임계 구역은 하나의 락으로 묶되, 역할별로 조건 변수만 나뉘어 소비자가 비운 뒤에는 `empty` 쪽만 기다리는 생산자를 깨우고, 생산자가 넣은 뒤에는 `fill` 쪽만 기다리는 소비자를 깨울 수 있어 위에서 말한 문제를 줄입니다.

이제 동작하는 생산자·소비자 솔루션을 만들었지만, 아직 단일 슬롯만 가정한 형태라 완전히 일반적이지는 않습니다.
아래처럼 바꾸면 슬롯을 여럿 두어 동시에 여러 값을 넣고 꺼낼 수 있어, 다중 슬롯 유한 버퍼에 더 가깝습니다.
- 버퍼 슬롯을 여러 개 두어 생산 측이 연속으로 넣을 여유가 생김
- 소비 측도 같은 칸을 돌며 꺼낼 수 있음

```python
import threading
import time

# 공유 자원 및 설정
MAX = 5  # 버퍼 슬롯 수
buffer = [0] * MAX
fill_ptr = 0
use_ptr = 0
count = 0

# 동기화 객체
mutex = threading.Lock()
# 하나의 Lock을 공유하는 두 개의 Condition 객체
empty_cond = threading.Condition(mutex)
fill_cond = threading.Condition(mutex)

def put(value):
    global fill_ptr, count
    buffer[fill_ptr] = value
    fill_ptr = (fill_ptr + 1) % MAX # ring 형태로 번갈아가며 할당
    count += 1

def get():
    global use_ptr, count
    tmp = buffer[use_ptr]
    use_ptr = (use_ptr + 1) % MAX
    count -= 1
    return tmp

def producer(loops):
    for i in range(loops):
        with empty_cond:
            # 버퍼가 가득 찼을 경우 대기
            while count == MAX:
                empty_cond.wait()
            put(i)
            print(f"Producer: put {i} (count={count})")
            # 소비자에게 신호 전달
            fill_cond.notify()
        time.sleep(0.1)

def consumer(loops):
    for _ in range(loops):
        with fill_cond:
            # 버퍼가 비었을 경우 대기
            while count == 0:
                fill_cond.wait()
            tmp = get()
            print(f"Consumer: got {tmp} (count={count})")
            # 생산자에 신호 전달
            empty_cond.notify()
        time.sleep(0.15)

if __name__ == "__main__":
    loop_count = 15

    p = threading.Thread(target=producer, args=(loop_count,))
    c = threading.Thread(target=consumer, args=(loop_count,))
    p.start()
    c.start()
    p.join()
    c.join()
    print("Done")
```

위와 같이 슬롯 다섯 칸짜리 유한 버퍼를 두었습니다.
`fill_ptr`·`use_ptr`를 모듈러로 증가시키는 링 버퍼라, 칸을 순환하며 쓰고 읽습니다.
`time.sleep`은 로그가 겹쳐 보이도록 넣은 데모용입니다. 실제로는 버퍼 크기를 키우고, 고정 `loop_count` 대신 요청이 들어오는 동안 돌아가는 워커 루프 같은 형태가 됩니다.

# Covering Conditions
조건 변수 사용의 또 다른 예제를 살펴보겠습니다.
이 코드의 특이한 점은, 원하는 크기만큼 빈 공간이 생길 때까지 기다려야 할 수 있다는 것입니다.
반대로 스레드가 메모리를 해제하면 `bytesLeft`가 늘고, 그때 조건 변수로 신호를 보냅니다.

```python
import threading

MAX_HEAP_SIZE = 10_000  # 예시
bytes_left = MAX_HEAP_SIZE
cv = threading.Condition()

# 메모리 할당
def allocate(size: int) -> object:
    global bytes_left
    with cv:
        # 요청 크기를 만족할 때까지 대기
        while bytes_left < size:
            cv.wait()
        ptr = object()  # 실제로는 힙·풀에서 블록을 받아옴
        bytes_left -= size
        return ptr

# 메모리 반환
def release(ptr: object, size: int) -> None:
    global bytes_left
    with cv:
        bytes_left += size
        cv.notify()  # 어떤 대기자를 깨울지는 비결정적
```

이 코드의 핵심 논점은 `signal` 한 번으로는 어떤 대기자를 깨울지 보장하기 어렵다는 점입니다.
`Lampson`과 `Redell`이 말한 covering condition 접근은 모든 대기자를 깨운 뒤, 조건이 맞지 않는 스레드는 다시 잠들게 하는 방식입니다.
다만 이 방식은 불필요한 깨움이 많아 비용이 커질 수 있습니다.
그래서 실무 구현에서는 조건을 역할별로 쪼개 `cv`를 여러 개 두고, 필요한 대기열만 깨우는 방향을 자주 택합니다.
- **Covering condition(커버링 컨디션)**: 특정 대기자 하나를 정밀하게 고르기 어렵다면 여러 대기자를 넓게 깨우고, 각 스레드가 `while` 재검사로 조건이 맞는지 다시 확인하게 하는 동기화 전략

# Summary
`lock` 외에도 중요한 `synchronization primitive`인 `condition variables`를 살펴봤습니다.
프로그램이 원하는 상태가 아닐 때 스레드를 잠들게 하고, `covering conditions` 문제를 다루는 데 도움을 줍니다.

# Homework

## Lock 시간에 따른 오버헤드
다음 코드로 `lock`을 데이터를 넣거나 가져올 때만 진행하여 최소 범위로 해야 병렬처리가 가능해집니다.
아래 코드서 Buffer의 크기를 아무리 키워도 `lock`로 잡히는 영역이 크면 `lock`을 못 얻어 병목 현상이 발생됩니다.

```python
import threading
import time
from collections import deque

MAX_BUFFER_SIZE = 100
N = 2000

def run_test(lock_hold_time=0.0):
    buffer = deque()
    mutex = threading.Lock()
    cv_empty = threading.Condition(mutex)  # 큐가 비었을 때 대기 (소비자 용)
    cv_full = threading.Condition(mutex)  # 큐가 꽉 찼을 떄 대기 (생산자 용)

    produced = 0
    consumed = 0

    def producer():
        nonlocal produced
        for i in range(N):
            # with cv_full:과 동일
            with mutex:
                while len(buffer) == MAX_BUFFER_SIZE:
                    cv_full.wait()  # 꽉 차면 대기
                if lock_hold_time > 0:
                    time.sleep(lock_hold_time)
                buffer.append(i)
                produced += 1
                cv_empty.notify()

    def consumer():
        nonlocal consumed
        for _ in range(N):
            # with cv_empty:과 동일
            with mutex:
                while len(buffer) == 0:
                    cv_empty.wait()
                if lock_hold_time > 0:
                    time.sleep(lock_hold_time)
                buffer.popleft()
                consumed += 1
                cv_full.notify()

    t0 = time.perf_counter()
    tp = threading.Thread(target=producer)
    tc = threading.Thread(target=consumer)
    tp.start()
    tc.start()
    tp.join()
    tc.join()
    elapsed = time.perf_counter() - t0

    # 초당 작업량량
    throughput = N / elapsed
    return elapsed, throughput, produced, consumed


for hold in [0, 0.0005, 0.001, 0.005, 0.01]:
    e, th, p, c = run_test(hold)
    print(f"hold={hold:>7.4f}s | elapsed={e:>8.3f}s | throughput={th:>10.1f} ops/s | p={p}, c={c}")
```

이 코드의 결과를 보면 다음과 같습니다.

**inside-lock**
```bash 
hold= 0.0000s | elapsed=   0.004s | throughput=  506136.9 ops/s | p=2000, c=2000
hold= 0.0005s | elapsed=   4.187s | throughput=     477.7 ops/s | p=2000, c=2000
hold= 0.0010s | elapsed=   6.251s | throughput=     319.9 ops/s | p=2000, c=2000
hold= 0.0050s | elapsed=  21.296s | throughput=      93.9 ops/s | p=2000, c=2000
hold= 0.0100s | elapsed=  42.430s | throughput=      47.1 ops/s | p=2000, c=2000
```
위 결과의 핵심은 `time.sleep(lock_hold_time)`이 **락 안에서 실행**된다는 점입니다.  
즉, 생산자/소비자가 대부분의 시간을 실제 작업보다 `mutex` 획득 대기 상태로 보내게 되고, `hold`가 커질수록 처리량(`throughput = N / elapsed`, 소비 완료 기준)이 크게 감소합니다.  
여기서 중요한 포인트는 임계 구역이 길어질수록 경합이 커져 처리량이 급격히 악화된다는 점입니다.  
버퍼 크기를 키우는 것은 일부 상황에서 도움을 줄 수 있지만, 결국 동시성 버퍼에서 중요한 점은 락 보유 시간입니다.

같은 지연 시간을 락 안/밖으로 옮겨 A/B 테스트하면 아래처럼 비교할 수 있습니다.

**outside-lock**
```bash
hold= 0.0000s | elapsed=   0.004s | throughput=  545836.6 ops/s | p=2000, c=2000
hold= 0.0005s | elapsed=   2.102s | throughput=     951.3 ops/s | p=2000, c=2000
hold= 0.0010s | elapsed=   3.082s | throughput=     649.0 ops/s | p=2000, c=2000
hold= 0.0050s | elapsed=  10.653s | throughput=     187.7 ops/s | p=2000, c=2000
hold= 0.0100s | elapsed=  20.506s | throughput=      97.5 ops/s | p=2000, c=2000
```

두 결과의 시간 차이는 지연(sleep)을 `lock` 내부가 아니라 `lock` 외부로 옮기면서 임계 구역 점유 시간이 짧아졌기 때문입니다. 표에서 보듯 `hold > 0` 구간에서는 `outside-lock`이 `inside-lock`보다 약 2배 높은 처리량을 보이며, 이는 생산자/소비자의 `mutex` 및 조건 변수 대기 시간이 크게 줄었음을 의미합니다.  
결론적으로 `lock` 점유 시간을 최소화하면 `cv` 대기 큐 병목과 스레드 레벨 오버헤드가 함께 줄어 성능이 향상됩니다.

---

## One cv일 때 주의점
위에서 언급했던 상황을 한 번 더 복습하면 다음과 같습니다.<br/>
하나의 `cv`로 생산자/소비자 패턴을 진행하면 `notify()`(C의 `signal`)를 호출했을 때 어느 스레드가 깨어날지 제어할 수 없습니다. 
소비자가 데이터를 소비하고 빈 자리가 생겨 생산자를 깨워야 하는데,  다른 소비자를 깨우는 경우가 발생합니다.
깨어난 소비자는 큐가 비어있어 다시 잠들고, 결국 생산자도 잠들어 있고 소비자도 잠들어버리는 **데드락(Deadlock)** 에 빠지게 됩니다. 

```python
# 조건 변수를 하나만 사용하는 생성자/소비자 패턴
cv_single = threading.Condition(mutex)

def producer_one_cv():
    with mutex:
        while len(buffer) == MAX_BUFFER_SIZE:
            cv_single.wait()
        buffer.append(1)
        # 이때 깨어나는 스레드가 생산자인지 소비자인지 확인할 수 없으므로 데드락 위험이 생김
        cv_single.notify() 
```

---

## while 조건 체크의 이유
또 다른 복습 포인트는 임계 구역의 조건을 `while`문으로 검사해야 한다는 점입니다.<br/>
스레드가 `notify()` 신호를 받고 깨어났다고 해서 즉시 실행(락 획득)된다는 보장이 없습니다. <br/>
깨어난 뒤 락을 획득하기 위해 기다리는 짧은 찰나에, 제3의 스레드가 인터리빙하여 큐의 데이터를 먼저 가져갈 수 있기 때문이죠.
그래서 `if` 문을 쓰면 깨어난 후 큐가 다시 비어버렸는지 확인하지 않고 곧바로 `pop()`을 시도하므로 `IndexError`나 데이터 오염이 발생합니다.

```python
def consumer_if_bug():
    with mutex:
        # if로 검사하면 깨어난 직후의 상태만 확인하게 됩니다.
        if len(buffer) == 0:
            cv_empty.wait()  # 잠들었다가 깨어난 뒤 mutex를 다시 가져오기 전에 if 조건이 다시 깨질 수 있습니다.
            # 이런 상황에 대응하려면 loop로 재검사해야 합니다.
        
        # 다른 스레드가 만약 먼저 데이터를 빼갔다면 아래 줄에서 버그가 발생합니다.
        item = buffer.pop(0) 
        cv_full.notify()
```

---

## Lock 해제로 인한 경쟁 상태

데이터를 추가할 때 임계 구역에서 `lock`을 조기에 해제하면, 스레드가 인터리빙하며 데이터를 동시에 수정할 수 있고 그로 인해 데이터가 깨지거나 경쟁 상태가 발생할 수 있습니다.

```python
def producer_extra_unlock():
    mutex.acquire()  # mutex 획득

    # 버퍼가 가득 차면 대기
    while len(buffer) == MAX_BUFFER_SIZE:
        cv_full.wait()
    
    # 데이터를 넣기 전에 `lock` 해제
    mutex.release() 
    
    # 데이터를 버퍼에 넣기 전에 다른 스레드가 인터리빙하면 원자성(Atomicity)이 깨져 Race Condition 발생
    buffer.append(1) 
    
    mutex.acquire()
    cv_empty.notify()
    mutex.release()
```