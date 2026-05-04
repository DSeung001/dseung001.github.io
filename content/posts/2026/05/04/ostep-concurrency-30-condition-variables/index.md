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

부모가 조건 대기 여부를 `if` 한 번만이 아닌 `while not done:`으로 두는 이유는, 다음에 나올 코드처럼 잘못된 코드의 경우 `done` 검사와 `wait()` 사이에 스레드 인터러빙이 생겨서 판단이 틀어질 수 있기 때문입니다.
허위 기상(spurious wakeup)이 있는 환경에서는 루프 없이 깨어난 뒤 상태를 다시 확인하지 않는 것 자체가 위험합니다.
그래서 이런 현상을 막기위해 루프를 돕니다.
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

실제 코드에서는 위 `put`/`get`을 여러 스레드가 동시에 부르므로 단순 `assert`만으로는 부족합니다. 다음 절에서 `lock`과 `cv`로 동기화 문제를 어떻게 다루는지 볼 수 있습니다.

# The Producer/Consumer (Bounded Buffer) Problem
# Covering Conditions
# Summary
