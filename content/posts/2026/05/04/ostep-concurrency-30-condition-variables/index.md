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

같은 출력 값을 지니만 `cv`를 사용함으로써 cpu 사이클 낭비가 발생하지 않게 되죠.
```bash
parent: begin
child
parent: end
```

# The Producer/Consumer (Bounded Buffer) Problem
# Covering Conditions
# Summary