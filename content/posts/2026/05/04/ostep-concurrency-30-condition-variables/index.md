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

# Covering Conditions
# Summary
