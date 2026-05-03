---
title: "더미 타이틀 — 29강 메모"
date: 2026-05-03T12:00:00+09:00
categories: [ "Memo", "Dummy" ]
tags: [ "dummy", "OSTEP", "Concurrency", "placeholder" ]
draft: false
description: "더미 설명: 근사 카운터 메모용 페이지. 나중에 다른 글과 병합 예정."
keywords: [ "dummy", "approximate counter", "concurrency" ]
author: "DSeung001"
lastmod: 2026-05-03T12:00:00+09:00
---

근사 카운터는 각 CPU 코어당 하나의 로컬 물리적 카운터와 글로벌 카운터를 두어, 단일 논리 카운터를 나타내는 방식으로 동작합니다.
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

```c
#include <pthread.h>
#define NUMCPUS 4

typedef struct __counter_t {
    int             global;
    pthread_mutex_t glock;
    int             local[NUMCPUS];
    pthread_mutex_t llock[NUMCPUS];
    int             threshold;
} counter_t;

// init: record threshold, init locks, locals, and global
void init(counter_t *c, int threshold) {
    c->threshold = threshold;
    c->global = 0;
    pthread_mutex_init(&c->glock, NULL);
    int i;
    for (i = 0; i < NUMCPUS; i++) {
        c->local[i] = 0;
        pthread_mutex_init(&c->llock[i], NULL);
    }
}

// update: usually only take local lock; when local >= threshold,
// take global lock, flush local into global, reset local to 0.
void update(counter_t *c, int threadID, int amt) {
    // CPU 슬롯 인덱스를 얻기 위한 모듈러; 균등 부하 분배를 보장하진 않음
    int cpu = threadID % NUMCPUS;
    pthread_mutex_lock(&c->llock[cpu]);
    c->local[cpu] += amt;
    if (c->local[cpu] >= c->threshold) {
        // transfer to global (textbook assumes amt > 0)
        pthread_mutex_lock(&c->glock);
        c->global += c->local[cpu];
        pthread_mutex_unlock(&c->glock);
        c->local[cpu] = 0;
    }
    pthread_mutex_unlock(&c->llock[cpu]);
}

// get: return global only (not G + sum(local); hence approximate)
int get(counter_t *c) {
    pthread_mutex_lock(&c->glock);
    int val = c->global;
    pthread_mutex_unlock(&c->glock);
    return val; // only approximate!
}
```
다음 29.5 그림은 전통적인 카운터와 근사치 카운터를 스레드 개수와 시간을 두고 비교한 지표입니다.<br/>
29.6은 근사치 카운터에서 임계값(threshold)에 따른 비교죠, 위에서 언급했던 특징이 잘 드러납니다.

![Comparison Counter](./Counter-Compare.png)

이러한 아이디어에서 중요한건 결국 성능 테스트입니다.<br/>
내가 생각해낸 아이디어는 빠르거나 느리거나 하나의 결과를 도출하기 때문이죠.

# Concurrent Linked Lists
더 복잡한 구조인 연결 리스트를 짧게 살펴봅니다. 기본 성질은 생략하고, 삽입과 조회만 다룹니다.

일반(단일 스레드) 연결 리스트와의 차이는, 자료구조의 모양이 아니라 누가 동시에 `head`와 `next`를 바꾸느냐에 있습니다.
한 스레드만 리스트를 건드린다면 `head`를 갱신하는 삽입·순회는 추가 동기화 없이도 안전합니다. 반면 여러 스레드가 같은 리스트에 삽입·조회하면, 같은 시점에 `head`나 노드의 `next`를 읽고 쓰는 순서가 섞여 데이터 경쟁(data race)이 날 수 있습니다.
그래서 아래 코드처럼 리스트에 `pthread_mutex_t`를 두고, 공유 포인터를 바꾸는 구간을 임계 구역으로 묶습니다.

`List_Insert`에서 `malloc`은 오래 걸리거나 실패할 수 있으므로 `lock`을 잡기 전에 할당합니다. 그러면 `malloc`이 실패했을 때는 아직 `lock`을 잡지 않았으므로 `unlock`이 필요 없고, 성공한 뒤에만 짧게 락을 잡아 `head`를 갱신합니다.
반대로 먼저 `lock`을 잡은 뒤 `malloc`을 하면, 실패·조기 반환 경로마다 `unlock`을 빠뜨리기 쉬워집니다.
```c
#include <pthread.h>
#include <stdlib.h>
#include <stdio.h>

typedef struct __node_t {
    int                key;
    struct __node_t   *next;
} node_t;

typedef struct __list_t {
    node_t            *head;
    pthread_mutex_t    lock;
} list_t;

void List_Init(list_t *L) {
    L->head = NULL;
    pthread_mutex_init(&L->lock, NULL);
}

int List_Insert(list_t *L, int key) {
    // malloc outside the lock (no synchronization needed here)
    node_t *new = malloc(sizeof(node_t));
    if (new == NULL) {
        perror("malloc");
        return -1;
    }

    new->key = key;
    // only the list update is the critical section
    pthread_mutex_lock(&L->lock);
    new->next = L->head;
    L->head   = new;
    pthread_mutex_unlock(&L->lock);
    return 0;
}

int List_Lookup(list_t *L, int key) {
    int rv = -1;
    pthread_mutex_lock(&L->lock);
    node_t *curr = L->head;
    while (curr) {
        if (curr->key == key) {
            rv = 0;
            break;
        }
        curr = curr->next;
    }
    pthread_mutex_unlock(&L->lock);
    return rv; // 0 on success, -1 on failure
}
```
위 연결 리스트 구현은 **확장성** 측면에서 한계가 큽니다.

- 전역 `lock`이 하나라 삽입·조회가 모두 그 락 하나로 직렬화됩니다. `CPU`를 늘려도 처리량이 거의 비례해서 늘지 않는 대표적인 이유입니다.
- `List_Lookup`은 `while`으로 도는 동안 락을 놓지 않습니다. 리스트 길이를 `n`이라 하면 임계 구역 길이가 **O(n)**이 되어, 다른 스레드가 오래 기다리게 됩니다.
- `lock`과 `head`가 들어 있는 캐시 라인을 여러 코어가 번갈아 건드리면 **캐시 무효화**와 메모리 트래픽 부담이 커질 수 있습니다.

이에 대한 대안으로 **hand-over-hand**(잠금 연쇄, lock coupling)가 있습니다. 리스트 전체 뮤텍스 대신 노드마다 뮤텍스를 두고, 탐색할 때는 (이미 잡고 있는) 현재 노드의 다음 노드 락을 잡은 뒤 현재 노드 락을 해제하는 식으로 한 칸씩 전진합니다. `lookup`이 대표적인 사용처입니다.

다만 hand-over-hand는 노드마다 `lock`/`unlock`이 들어가 **오버헤드**가 큽니다. 그래서 일정 개수의 노드마다 락을 두는 식의 하이브리드를 찾아볼 가치는 있습니다.

# Concurrent Queues
동시성 데이터 구조를 만드는 데는 표준적인 접근이 항상 있고, 가장 쉬운 방법은 큰 `lock` 하나를 두는 것입니다. 여기서 더 나아가면 확장성을 위해 `lock`을 쪼개거나 다른 방법을 찾는 등의 방향으로 나아갑니다.

여기서는 이 부분을 이해했다고 가정하고 바로 약간 더 동시적인 큐를 보여줍니다.
이 큐의 핵심은 `head`와 `tail`에 각각 `lock`이 존재하는 것으로 이 두 `lock`의 목표는 `enqueue/dequeue` 작업의 동시성을 가능하게 하는 것이죠.
일반적인 경우 `enqueue` 루틴은 `tail lock`을 `dequeue`는 `head lock`만을 접근합니다.

큐는 멀티 스레드 애플리케이션에서 일반적으로 사용되지만, 여기서 소개되는 큐(`lock`)는 요구사항을 충족하지 못합니다. 큐가 비어있거나, 완전히 차 있을 때 스레드가 대기할 수 있게 해주는 보다 완전한 `bounded queue`는 다음 장의 `condition variables`에서 다룰 예정입니다.

다시 본문으로 돌아와 동시성 큐는 다음과 같이 구현됩니다.
```c
#include <pthread.h>
#include <stdlib.h>
#include <assert.h>

typedef struct __node_t {
    int                value;
    struct __node_t   *next;
} node_t;

typedef struct __queue_t {
    node_t            *head;
    node_t            *tail;
    pthread_mutex_t    head_lock;
    pthread_mutex_t    tail_lock;
} queue_t;

void Queue_Init(queue_t *q) {
    node_t *tmp = malloc(sizeof(node_t));
    assert(tmp != NULL);
    tmp->next = NULL;
    q->head = q->tail = tmp;
    pthread_mutex_init(&q->head_lock, NULL);
    pthread_mutex_init(&q->tail_lock, NULL);
}

void Queue_Enqueue(queue_t *q, int value) {
    // malloc은 오래 걸리거나 실패할 수 있으므로 tail_lock 전에 수행
    node_t *tmp = malloc(sizeof(node_t));
    assert(tmp != NULL);
    tmp->value = value;
    tmp->next  = NULL;

    pthread_mutex_lock(&q->tail_lock);
    q->tail->next = tmp;
    q->tail = tmp;
    pthread_mutex_unlock(&q->tail_lock);
}

int Queue_Dequeue(queue_t *q, int *value) {
    pthread_mutex_lock(&q->head_lock);
    node_t *tmp = q->head;
    node_t *new_head = tmp->next;
    if (new_head == NULL) {
        pthread_mutex_unlock(&q->head_lock);
        return -1; // queue was empty
    }
    *value = new_head->value;
    q->head = new_head;
    pthread_mutex_unlock(&q->head_lock);
    free(tmp);
    return 0;
}
```
# Concurrent Hash Table
크기를 조정하지 않는 간단한 해시 테이블을 `linked list` 코드를 활용하여 다음 처럼 만들 수 있습니다, 전체 구조에 대한 단일 `lock`을 사용하는 대신 해시 버킷마다 `lock`을 사용하기 떄문입니다.
```c
#define BUCKETS 101

typedef struct __hash_t {
    list_t lists[BUCKETS];
} hash_t;

void Hash_Init(hash_t *H) {
    int i;
    for (i = 0; i < BUCKETS; i++) {
        List_Init(&H->lists[i]);
    }
}

int Hash_Insert(hash_t *H, int key) {
    return List_Insert(&H->lists[key % BUCKETS], key);
}

int Hash_Lookup(hash_t *H, int key) {
    return List_Lookup(&H->lists[key % BUCKETS], key);
}
```

# Summary
카운터, 리스트, 큐, 해시 테이블까지 데이터 구조에 동시성이 적용되면 어떻게 바뀌는지에 대해 살펴봤습니다. 다룬 내용처럼 제어 흐름에서 `lock` 획득 및 해제는 어떻게를 다루냐에 따라 확장성이 크게 차이가 발생합니다.