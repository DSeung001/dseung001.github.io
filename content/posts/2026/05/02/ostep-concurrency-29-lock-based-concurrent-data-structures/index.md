---
title: "Operating Systems: Three Easy Pieces - Lock-based Concurrent Data Structures"
date: 2026-05-02T00:00:00+09:00
categories: [ "Memo", "Digging", "OSTEP" ]
tags: [ "OSTEP", "Operating Systems", "Concurrency", "Lock", "Data structures", "Synchronization" ]
draft: false
description: "OSTEP Concurrency 29강 Lock-based Concurrent Data Structures 정리"
keywords: [ "OSTEP", "Concurrency", "Lock", "Concurrent data structures", "Linked list", "Queue", "Scalability" ]
author: "DSeung001"
lastmod: 2026-05-02T00:00:00+09:00
---

`Lock`을 다음 주제로 넘어가기 전에 일반 데이터 구조에 `Lock`을 얹어 쓰는 방법을 다룹니다.<br/>
모든 상황에 두루 통하는 방법을 찾기 어렵기 때문에 시나리오별로 나눠 살펴봅니다.

이번 챕터는 자료 구조이므로 공부 중인 `pyhton`으로 진행합니다

# Concurrent Counters
가장 단순한 데이터 구조 중 하나인 카운터입니다, 특정 값을 카운트 하는 자료구조로 이 데이터 구조는 간단하게 아래처럼 표현할 수 있죠.
```python
class Counter:
    def __init__(self):
        self.value = 0

    def increment(self):
        self.value += 1

    def decrement(self):
        self.value -= 1

    def get(self):
        return self.value
```

위 코드에 `lock`과 동시성을 추가해서 멀티 스레드로 돌려 봅시다.

OSTEP에서는 이 벤치마크를 `Intel 2.7 GHz i5`(4코어)가 달린 `iMac`에서 돌렸고, 동기화된 카운터에 대해 스레드 수만 바꿔 스레드마다 공유 카운터를 백만 번씩 증가하는 로직을 측정하면 대략 아래처럼 나옵니다.
- 단일 스레드: 약 0.03초
- 스레드 2개로 동시에 돌림: 약 5초

아래 코드처럼 단일 `lock`을 추가하고 로직을 진행하면 스레드가 늘수록 더 나빠집니다. 카운터를 같은 락 하나로만 보호하면 갱신이 직렬화되고, 대기 비용과 캐시 라인 경합 비용이 커지기 때문입니다.

```python
import threading

class Counter:
    def __init__(self):
        self.value = 0
        self.lock = threading.Lock() 

    def increment(self):
        with self.lock:
            self.value += 1

    def decrement(self):
        with self.lock:
            self.value -= 1

    def get(self):
        with self.lock:
            return self.value
```
이상적으로는 여러 프로세서에서 코어와 스레드가 늘어도, 단일 스레드일 때처럼 전체 시간이 크게 불어나지 않는 확장성(scalability)을 기대합니다. 
그런데 위와 같은 단일 글로벌 락 카운터만으로는 그 기대를 충족하기 어렵기 때문에, 한계를 보완할 방법을 사람들이 추구했고 찾아 냈죠.

`approximate counter`(근사 카운터)가 그 중 하나입니다.
근사 카운터는 각 CPU 코어당 하나의 로컬 물리적 카운터와 글로벌 카운터로 단일 논리 카운터를 나타내는 방식으로 동작합니다.
구체적으로 CPU가 네 개인 머신에서는 로컬 카운터 네 개와 글로벌 카운터 하나가 있는 셈이죠.

아래 표는 시간 스텝마다 로컬 카운터(L1~L4)와 글로벌 카운터(G)가 어떻게 바뀌는지 보여 줍니다. 이를 보면 개념을 잡기 쉽습니다.

| 시간 | L1 | L2 | L3 | L4 | G |
|:----:|:--:|:--:|:--:|:--:|:--:|
| 0 | 0 | 0 | 0 | 0 | 0 | 
| 1 | 0 | 0 | 1 | 1 | 0 | 
| 2 | 1 | 0 | 2 | 1 | 0 | 
| 3 | 2 | 0 | 3 | 1 | 0 | 
| 4 | 3 | 0 | 3 | 2 | 0 | 
| 5 | 4 | 1 | 3 | 3 | 0 | 

시간 6과 7에서는 로컬 카운터가 글로벌 카운터에 병합됩니다.

| 시간 | 설명| L1 | L2 | L3 | L4 | G |
|:----:|-----------------|:--:|:--:|:--:|:--:|:--:|
| 6 | L1이 G에 병합 | 0 | 1 | 3 | 4 | 5 |
| 7 | L4가 G에 병합 | 0 | 2 | 4 | 5 | 10 |

근사 카운팅의 기본 개념은 이렇습니다. 주어진 코어에서 실행 중인 스레드가 카운팅할 때 로컬 카운터를 올리고, 그 로컬 카운터에 대한 접근은 해당 로컬 `lock`으로 동기화합니다.
각 `CPU`는 자기 로컬 카운터만 두므로 `CPU` 끼리는 서로의 로컬을 두고 경쟁하지 않아, 카운팅 쪽 확장성을 얻을 수 있습니다.

스레드가 카운터 값을 읽을 때를 대비해, 로컬 값은 주기적으로 글로벌 카운터에 병합됩니다. 이때 글로벌 `lock`을 잡은 뒤 로컬에 쌓인 만큼 글로벌 카운터를 올리고 로컬은 `0`으로 리셋하는 식으로 동작합니다.

로컬에서 글로벌로 넘기는 주기는 임계값으로 정해집니다, 로컬 카운터의 값이 임계값 수치를 넘어가면 글로벌 카운터에 병합하는 방식입니다.
- 임계값이 작으면 앞에서 본 비확장 카운터에 가깝게 동작.
- 임계값이 크면 확장성은 좋아지지만 근사 카운터이기 때문에 실제 값과의 오차는 임계값이 클수록 정비례로 커짐.

다음은 근사 카운터의 구현 코드입니다. `NUMCPUS`는 로컬 슬롯 개수(보통 물리 코어 수에 맞춤)입니다.

```python
import threading

class ApproximateCounter:
    def __init__(self, threshold, num_cpus=4):
        self.threshold = threshold
        self.num_cpus = num_cpus

        # global counter & lock
        self.global_counter = 0
        self.glock = threading.Lock()

        # local counter & lock list
        self.local = [0] * num_cpus
        self.llock = [threading.Lock() for _ in range(num_cpus)]

    def update(self, thread_id, amt):
        # CPU 슬롯 인덱스를 얻기 위한 모듈러; 균등 부하 분배를 보장하진 않음
        cpu = thread_id % self.num_cpus

        with self.llock[cpu]:
            self.local[cpu] += amt

            if self.local[cpu] >= self.threshold:
                with self.glock:
                    self.global_counter += self.local[cpu]
                self.local[cpu] = 0

    def get(self):
        with self.glock:
            val = self.global_counter
        return val
```
다음 29.5 그림은 전통적인 카운터와 근사치 카운터를 스레드 개수와 시간을 두고 비교한 지표입니다.<br/>
29.6은 근사치 카운터에서 임계값(threshold)에 따른 비교죠, 위에서 언급했던 특징이 잘 드러납니다.

![Comparison Counter](../../02/ostep-concurrency-29-lock-based-concurrent-data-structures/Counter-Compare.png)

이러한 아이디어에서 중요한건 결국 성능 테스트입니다.<br/>
내가 생각해낸 아이디어는 빠르거나 느리거나 하나의 결과를 도출하기 때문이죠.

# Concurrent Linked Lists
더 복잡한 구조인 연결 리스트를 짧게 살펴봅니다. 기본 성질은 생략하고, 삽입과 조회만 다룹니다.

일반(단일 스레드) 연결 리스트와의 차이는, 자료구조의 모양이 아니라 누가 동시에 `head`와 `next`를 바꾸느냐에 있습니다.
한 스레드만 리스트를 건드린다면 `head`를 갱신하는 삽입·순회는 추가 동기화 없이도 안전합니다. 반면 여러 스레드가 같은 리스트에 삽입·조회하면, 같은 시점에 `head`나 노드의 `next`를 읽고 쓰는 순서가 섞여 데이터 경쟁(data race)이 날 수 있습니다.
그래서 아래 코드처럼 리스트에 `pthread_mutex_t`를 두고, 공유 포인터를 바꾸는 구간을 임계 구역으로 묶습니다.

`insert`에서 `malloc`은 오래 걸리거나 실패할 수 있으므로 `lock`을 잡기 전에 할당합니다. 그러면 `malloc`이 실패했을 때는 아직 `lock`을 잡지 않았으므로 `unlock`이 필요 없고, 성공한 뒤에만 짧게 락을 잡아 `head`를 갱신합니다.
반대로 먼저 `lock`을 잡은 뒤 `malloc`을 하면, 실패·조기 반환 경로마다 `unlock`을 빠뜨리기 쉬워집니다.

python에는 `malloc`이 없으니 같은 역할하는 곳에 주석을 남겼습니다.
```python
import threading

class Node:
    def __init__(self, key):
        self.key = key
        self.next = None

class ConcurrentList:
    def __init__(self):
        self.head = None
        self.lock = threading.Lock()

    def insert(self, key):
        # malloc 역할, lock 밖에서 실행 (효율적)
        new_node = Node(key)

        with self.lock:
            new_node.next = self.head
            self.head = new_node

    def lookup(self, key):
        rv = -1
        with self.lock:
            curr = self.head
            while curr:
                if curr.key == key:
                    rv = 0 # 성공
                    break
                curr = curr.next
        return rv
```
위 연결 리스트 구현은 **확장성** 측면에서 한계가 큽니다.

- 전역 `lock`이 하나라 삽입·조회가 모두 그 락 하나로 직렬화됩니다. `CPU`를 늘려도 처리량이 거의 비례해서 늘지 않는 대표적인 이유입니다.
- `List_Lookup`은 `while`으로 도는 동안 락을 놓지 않습니다. 리스트 길이를 `n`이라 하면 임계 구역 길이가 **O(n)** 이 되어, 다른 스레드가 오래 기다리게 됩니다.
- `lock`과 `head`가 들어 있는 캐시 라인을 여러 코어가 번갈아 건드리면 **캐시 무효화**와 메모리 트래픽 부담이 커질 수 있습니다.

이에 대한 대안으로 **hand-over-hand**(잠금 연쇄, lock coupling)가 있습니다.<br/>리스트 전체 뮤텍스 대신 노드마다 뮤텍스를 두고, 탐색할 때는 (이미 잡고 있는) 현재 노드의 다음 노드 락을 잡은 뒤 현재 노드 락을 해제하는 식으로 한 칸씩 전진합니다. 이 방법이 사다리 타듯 다음 걸 잡고 놓는다고해서 이름이 저렇게 붙여졌습니다. 
사용처는 `lookup`이 대표적인 사용처입니다.

```python
import threading

class Node:
    def __init__(self, key):
        self.key = key
        self.next = None
        # 각 노드 별로 `lock`을 지님
        self.lock = threading.Lock()


class HandOverHandList:
    def __init__(self):
        self.head = None
        self.head_lock = threading.Lock()

    def insert(self, key):
        new_node = Node(key)
        with self.head_lock:
            new_node.next = self.head
            self.head = new_node

    def lookup(self, key):
        """Hand-over-hand 방식 적용"""
        self.head_lock.acquire()
        curr = self.head

        # 빈 경우 -1로 에러 처리
        if curr is None:
            self.head_lock.release()
            return -1

        # 노드 락으로 변경
        curr.lock.acquire()
        self.head_lock.release()

        try:
            while curr:
                if curr.key == key:
                    return 0 # 노드 찾음

                next_node = curr.next

                if next_node is None:
                    break

                # 다음 노드 락으로 변경
                next_node.lock.acquire()
                curr.lock.release()
                curr = next_node

            return -1 # 못 찾음
        finally:
            # 루프를 어떻게 나오든 락은 해제 해야함
            if curr:
                curr.lock.release()

```

다만 hand-over-hand는 노드마다 `lock`/`unlock`이 들어가 **오버헤드**가 큽니다. 그래서 일정 개수의 노드마다 락을 두는 식의 하이브리드를 찾아볼 가치는 있습니다.

# Concurrent Queues
동시성 데이터 구조를 만드는 데는 표준적인 접근이 항상 있고, 가장 쉬운 방법은 큰 `lock` 하나를 두는 것입니다. 여기서 더 나아가면 확장성을 위해 `lock`을 쪼개거나 다른 방법을 찾는 등의 방향으로 나아갑니다.

먼저 단일 `lock`으로 큐를 구현하면 다음과 같습니다
```python
import threading

class Node:
    def __init__(self, value=None):
        self.value = value
        self.next = None

class Queue:
    def __init__(self):
        tmp = Node()
        self.head = tmp
        self.tail = tmp
        self.lock = threading.Lock()

    def enqueue(self, value):
        new_node = Node(value)
        with self.lock:
            # tail 뒤에 노드를 추가 후 tail 이동
            self.tail.next = new_node
            self.tail = new_node

    def dequeue(self):
        with self.lock:
            old_head = self.head
            new_head = self.head.next

            # 큐 빈지 체크
            if new_head is None:
                return -1

            value = new_head.value
            self.head = new_head

            return value
```

단일 `lock`을 이용한 큐 역시 단일 `lock`을 지닌 `linked list`와 동일한 확장성 문제를 가집니다.

동시성 큐의 핵심은 `head`와 `tail`에 각각 `lock`이 존재하는 것으로 이 두 `lock`의 목표는 `enqueue/dequeue` 작업의 동시성을 가능하게 하는 것이죠.
일반적인 경우 `enqueue` 루틴은 `tail lock`을 `dequeue`는 `head lock`만을 접근합니다.

큐는 멀티 스레드 애플리케이션에서 일반적으로 사용되지만, 여기서 소개되는 큐(`lock`)는 요구사항을 충족하지 못합니다. 큐가 비어있거나, 완전히 차 있을 때 스레드가 대기할 수 있게 해주는 보다 완전한 `bounded queue`는 다음 장의 `condition variables`에서 다룰 예정입니다.

다시 본문으로 돌아와 동시성 큐는 다음과 같이 구현됩니다.
```python
import threading

class Node:
    def __init__(self, value=None):
        self.value = value
        self.next = None

class ConcurrentQueue:
    def __init__(self):
        tmp = Node()
        self.head = tmp
        self.tail = tmp

        # head, tail에 대한 lock 분리
        self.head_lock = threading.Lock()
        self.tail_lock = threading.Lock()

    def enqueue(self, value):
        new_node = Node(value)
        with self.tail_lock:
            self.tail.next = new_node
            self.tail = new_node

    def dequeue(self):
        with self.head_lock:
            old_head = self.head
            new_head = self.head.next

            # 큐 빈지 체크
            if new_head is None:
                return -1

            value = new_head.value
            self.head = new_head

            return value
```
# Concurrent Hash Table
크기를 조정하지 않는 간단한 해시 테이블을 `linked list` 코드를 활용하여 다음 처럼 만들 수 있습니다, 전체 구조에 대한 단일 `lock`을 사용하는 대신 해시 버킷마다 `lock`을 사용하기 떄문입니다.
```python
...
# 이전에 만든 스레드 안전 연결 리스트를 사용합니다.

class ConcurrentHashTable:
    def __init__(self, buckets=101):
        self.num_buckets = buckets
        # 각 버킷마다 독립적인 ConcurrentList(자신만의 락을 가짐)를 생성
        self.lists = [ConcurrentList() for _ in range(self.num_buckets)]

    def insert(self, key):
        """Hash_Insert: 키를 해싱하여 해당 버킷에 삽입"""
        bucket_index = key % self.num_buckets
        return self.lists[bucket_index].insert(key)

    def lookup(self, key):
        """Hash_Lookup: 키를 해싱하여 해당 버킷에서 검색"""
        bucket_index = key % self.num_buckets
        return self.lists[bucket_index].lookup(key)
```

# Summary
카운터, 리스트, 큐, 해시 테이블까지 데이터 구조에 동시성이 적용되면 어떻게 바뀌는지에 대해 살펴봤습니다. 다룬 내용처럼 제어 흐름에서 `lock` 획득 및 해제는 어떻게를 다루냐에 따라 확장성이 크게 차이가 발생합니다.