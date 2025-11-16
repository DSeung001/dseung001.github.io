---
title: "언어별 동시성 로직 정리"
date: 2025-11-15T22:42:59+09:00
categories: [ "Memo" ]
tags: [ "동시성", "Concurrency", "Async", "Parallel" ]
draft: true
description: "Go의 장점인 동시성을 타 언어들과 비교해본 글입니다."
keywords: [ "동시성", "Concurrency", "언어 철학", "Parallel" ]
author: "DSeung001"
lastmod: 2025-11-15T22:42:59+09:00
---

## 개요

### 1-1. Go의 장점으로 동시성을 내세울 수 있을까?

GoLang의 사용처를 묻는 질문이 들어온다면 블록체인, 게임서버, 네트워크, 실시간 데이터 처리, 고성능 API 등 중에서 아마 대답이 나올 겁니다.

결국 고루틴(goroutine) 기반의 강력한 동시성을 GoLang의 핵심으로 보고 이를 장점으로 이야기 하는 것이죠.
이는 GoLang에 대해 공부하면 경량화된 쓰레드 자체 특징에 더해 채널, 락관리 등도 매우 편리하게 할 수 있는 걸 알고 있죠.

하지만 한 번더 꼬리물기 질문을 한다면?
> - 진짜 이게 장점일까?
> - 다른 언어에 비해 월등히 좋을까?
> - Rust도 좋다고들 하던데 Rust 보다도 좋을까?
> - Python은 느리다던데 유의미한 퍼포먼스 차이가 있을까?

이런 질문들에 대해서는 실제로 해본적은 없으니 <b>"그래도 메모리는 조금 덜 먹고 더 빠른 편이지 않을까"</b>라는 막연한 생각만이 떠오릅니다.
그래서 이번 포스트는 여러 언어들에서 동시성 로직을 다룰 때 무슨 특징들이 있는 지를 다뤄볼겁니다.

### 1-2. 동시성 로직 비교 대상 언어

이번 포스트에서는 같은 동시성 로직을 두고 여러 언어들은 다음과 같습니다.
> Go
>> - 고성능 API 서버, 마이크로서비스, 클라우드/인프라(Kubernetes·Docker·Terraform), 블록체인 등에 쓰이는 언어
>> - 경량 쓰레드라는 특징 덕분에 대규모 트래픽 서비스 모두에서 점유율 향상 중
>
> Python
>> - AI/ML, 데이터 분석, 웹 백엔드(Django/Flask), 자동화 스크립트 분야에서 절대적인 입지
>> - 동시성은 약하지만 생태계와 생산성 덕분에 빠른 개발이 필요한 곳에서 자주 사용
> 
> Java
>> - 엔터프라이즈 서버, 금융권, 대규모 트래픽 플랫폼의 대표 언어
>> - 안정성·성능·JVM 생태계 덕분에 기업 환경에서 가장 널리 쓰이고 한국에서는 국밥언어
> 
> C
>> - OS, 커널, 임베디드, 네트워크 드라이버 등 시스템 영역에서 단단한 입지를 지님
>> - 로우 레벨에서의 쓰레드 제어가 가능
> 
> Rust
>> - 메모리 안전성과 고성능을 동시에 추구하며 시스템 프로그래밍에서 사용
>> - WebAssembly, 고성능 서버, CLI, 블록체인 등에서 C/C++의 영역을 일부 대체하는 중

## 본론

### 2-1. 동시성 알고리즘 정의

비교할 떄 적용해볼 문제는 숫자 1을 1,000,000번 더하는 작업 10개를 동시에 실행하는 로직을 만들어볼 겁니다.
공유 메모리에 대한 비교까지 다룰 경우 양이 너무 많아지므로 동시성 로직에만 집중할 겁니다.

### 2-2. 언어별 동시성 코드

각 언어는 동일한 로직을 수행하는 다음 코드로 비교를 해봤습니다.

<b>C Code</b>

```C
#include <pthread.h>
#include <stdio.h>

#define JOBS 10
#define ITERS 1000000

int results[JOBS];

void* worker(void* arg) {
    long idx = (long)arg;
    int sum = 0;

    for (int i = 0; i < ITERS; i++) {
        sum++;
    }

    results[idx] = sum;
    return NULL;
}

int main(void) {
    pthread_t threads[JOBS];

    for (long i = 0; i < JOBS; i++) {
        pthread_create(&threads[i], NULL, worker, (void*)i);
    }

    int total = 0;
    for (int i = 0; i < JOBS; i++) {
        pthread_join(threads[i], NULL);
        total += results[i];
    }

    printf("lang=c total=%d\n", total);
    return 0;
}

```

<b>Rust Code</b>

```Rust
use std::thread;

const JOBS: usize = 10;
const ITERS: i32 = 1_000_000;

fn main() {
    let mut handles = Vec::with_capacity(JOBS);

    for _ in 0..JOBS {
        handles.push(thread::spawn(|| {
            let mut sum = 0;
            for _ in 0..ITERS {
                sum += 1;
            }
            sum
        }));
    }

    let mut total = 0;
    for h in handles {
        total += h.join().unwrap();
    }

    println!("lang=rust total={}", total);
}

```

<b>GoLang Code</b>

```GoLang
package main

import (
	"fmt"
	"sync"
)

const (
	JOBS  = 10
	ITERS = 1_000_000
)

func main() {
	var wg sync.WaitGroup
	ch := make(chan int, JOBS)

	for i := 0; i < JOBS; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			sum := 0
			for j := 0; j < ITERS; j++ {
				sum++
			}
			ch <- sum
		}()
	}

	go func() {
		wg.Wait()
		close(ch)
	}()

	total := 0
	for v := range ch {
		total += v
	}

	fmt.Printf("lang=go total=%d\n", total)
}

```

<b>Java Code</b>

```Java
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.*;

public class Main {
    static final int JOBS = 10;
    static final int ITERS = 1_000_000;

    public static void main(String[] args) throws Exception {
        ExecutorService exec = Executors.newFixedThreadPool(JOBS);
        List<Future<Integer>> futures = new ArrayList<>();

        for (int i = 0; i < JOBS; i++) {
            futures.add(exec.submit(() -> {
                int sum = 0;
                for (int j = 0; j < ITERS; j++) {
                    sum++;
                }
                return sum;
            }));
        }

        int total = 0;
        for (Future<Integer> f : futures) {
            total += f.get();
        }
        exec.shutdown();

        System.out.printf("lang=java total=%d%n", total);
    }
}
```

<b>Python Code</b>

```Python
from concurrent.futures import ThreadPoolExecutor

JOBS = 10
ITERS = 1_000_000

def worker():
    s = 0
    for _ in range(ITERS):
        s += 1
    return s

def main():
    with ThreadPoolExecutor(max_workers=JOBS) as ex:
        total = sum(ex.map(lambda _: worker(), range(JOBS)))
    print(f"lang=python total={total}")

if __name__ == "__main__":
    main()

```

### 2-3 테스트 환경

도커로 테스트를 진행하였고 도커 환경은 다음과 같아요.
> Ram : 2GB, CPU: 4개으로 제한

언어 버전은 다음과 같아요.
> C: gcc (Ubuntu 11.4.0-1ubuntu1~22.04.2) 11.4.0
> 
> Rust: rustc 1.91.1 (ed61e7d7e 2025-11-07)
> 
> Go: go version go1.18.1 linux/amd64
> 
> Java
>> - openjdk version "11.0.28" 2025-07-15
>> - OpenJDK Runtime Environment (build 11.0.28+6-post-Ubuntu-1ubuntu122.04.1)
>> - OpenJDK 64-Bit Server VM (build 11.0.28+6-post-Ubuntu-1ubuntu122.04.1, mixed mode, sharing)
> - Python: 3.10.12

### 2-4. 벤치마킹 값

벤치 마킹은 각 언어별로 동일한 코드를 10번 실행했습니다.

```markdown

============================
BENCH: c concurrent (runs=10)
Command: /app/bin/bench_c
RESULT label="c concurrent" elapsed_ms=4 user_ms=0 sys_ms=0 max_rss_kb=1696
RESULT label="c concurrent" elapsed_ms=4 user_ms=0 sys_ms=0 max_rss_kb=1784
RESULT label="c concurrent" elapsed_ms=4 user_ms=0 sys_ms=0 max_rss_kb=1728
RESULT label="c concurrent" elapsed_ms=4 user_ms=0 sys_ms=0 max_rss_kb=1688
RESULT label="c concurrent" elapsed_ms=4 user_ms=0 sys_ms=0 max_rss_kb=1716
RESULT label="c concurrent" elapsed_ms=4 user_ms=0 sys_ms=0 max_rss_kb=1740
RESULT label="c concurrent" elapsed_ms=4 user_ms=0 sys_ms=0 max_rss_kb=1764
RESULT label="c concurrent" elapsed_ms=3 user_ms=0 sys_ms=0 max_rss_kb=1688
RESULT label="c concurrent" elapsed_ms=3 user_ms=0 sys_ms=0 max_rss_kb=1804
RESULT label="c concurrent" elapsed_ms=4 user_ms=0 sys_ms=0 max_rss_kb=1796
============================
BENCH: rust concurrent (runs=10)
Command: /app/bin/bench_rust
RESULT label="rust concurrent" elapsed_ms=5 user_ms=0 sys_ms=0 max_rss_kb=2208
RESULT label="rust concurrent" elapsed_ms=4 user_ms=0 sys_ms=0 max_rss_kb=2316
RESULT label="rust concurrent" elapsed_ms=4 user_ms=0 sys_ms=0 max_rss_kb=2332
RESULT label="rust concurrent" elapsed_ms=4 user_ms=0 sys_ms=0 max_rss_kb=2296
RESULT label="rust concurrent" elapsed_ms=4 user_ms=0 sys_ms=0 max_rss_kb=2328
RESULT label="rust concurrent" elapsed_ms=4 user_ms=0 sys_ms=0 max_rss_kb=2312
RESULT label="rust concurrent" elapsed_ms=4 user_ms=0 sys_ms=0 max_rss_kb=2280
RESULT label="rust concurrent" elapsed_ms=4 user_ms=0 sys_ms=0 max_rss_kb=2164
RESULT label="rust concurrent" elapsed_ms=4 user_ms=0 sys_ms=0 max_rss_kb=2236
RESULT label="rust concurrent" elapsed_ms=4 user_ms=0 sys_ms=0 max_rss_kb=2332
============================
BENCH: go concurrent (runs=10)
Command: /app/bin/bench_go
RESULT label="go concurrent" elapsed_ms=5 user_ms=0 sys_ms=0 max_rss_kb=3420
RESULT label="go concurrent" elapsed_ms=4 user_ms=0 sys_ms=0 max_rss_kb=3416
RESULT label="go concurrent" elapsed_ms=4 user_ms=0 sys_ms=0 max_rss_kb=3428
RESULT label="go concurrent" elapsed_ms=5 user_ms=0 sys_ms=0 max_rss_kb=3428
RESULT label="go concurrent" elapsed_ms=4 user_ms=0 sys_ms=0 max_rss_kb=3420
RESULT label="go concurrent" elapsed_ms=5 user_ms=0 sys_ms=0 max_rss_kb=3428
RESULT label="go concurrent" elapsed_ms=5 user_ms=0 sys_ms=0 max_rss_kb=3416
RESULT label="go concurrent" elapsed_ms=4 user_ms=0 sys_ms=0 max_rss_kb=3424
RESULT label="go concurrent" elapsed_ms=5 user_ms=0 sys_ms=0 max_rss_kb=3420
RESULT label="go concurrent" elapsed_ms=5 user_ms=0 sys_ms=0 max_rss_kb=3420
============================
BENCH: java concurrent (runs=10)
Command: java -cp /app/java Main
RESULT label="java concurrent" elapsed_ms=165 user_ms=470 sys_ms=30 max_rss_kb=42508
RESULT label="java concurrent" elapsed_ms=51 user_ms=70 sys_ms=0 max_rss_kb=44040
RESULT label="java concurrent" elapsed_ms=119 user_ms=270 sys_ms=50 max_rss_kb=44160
RESULT label="java concurrent" elapsed_ms=51 user_ms=50 sys_ms=20 max_rss_kb=42480
RESULT label="java concurrent" elapsed_ms=51 user_ms=80 sys_ms=0 max_rss_kb=42816
RESULT label="java concurrent" elapsed_ms=54 user_ms=70 sys_ms=0 max_rss_kb=44560
RESULT label="java concurrent" elapsed_ms=53 user_ms=60 sys_ms=20 max_rss_kb=44068
RESULT label="java concurrent" elapsed_ms=51 user_ms=70 sys_ms=10 max_rss_kb=42412
RESULT label="java concurrent" elapsed_ms=82 user_ms=160 sys_ms=10 max_rss_kb=44448
RESULT label="java concurrent" elapsed_ms=51 user_ms=60 sys_ms=10 max_rss_kb=42384
============================
BENCH: python concurrent (runs=10)
Command: python3 /app/python/main.py
RESULT label="python concurrent" elapsed_ms=432 user_ms=420 sys_ms=10 max_rss_kb=12248
RESULT label="python concurrent" elapsed_ms=426 user_ms=410 sys_ms=10 max_rss_kb=12376
RESULT label="python concurrent" elapsed_ms=437 user_ms=410 sys_ms=10 max_rss_kb=12072
RESULT label="python concurrent" elapsed_ms=429 user_ms=400 sys_ms=10 max_rss_kb=12440
RESULT label="python concurrent" elapsed_ms=430 user_ms=410 sys_ms=0 max_rss_kb=12172
RESULT label="python concurrent" elapsed_ms=440 user_ms=430 sys_ms=10 max_rss_kb=12392
RESULT label="python concurrent" elapsed_ms=430 user_ms=410 sys_ms=0 max_rss_kb=12220
RESULT label="python concurrent" elapsed_ms=425 user_ms=420 sys_ms=0 max_rss_kb=12228
RESULT label="python concurrent" elapsed_ms=422 user_ms=390 sys_ms=20 max_rss_kb=10684
RESULT label="python concurrent" elapsed_ms=433 user_ms=410 sys_ms=20 max_rss_kb=12044
```

### 2-5. 정리

다음 기준으로 정리했습니다.

- elapsed_ms: 실제로 얼만큼의 시간이 걸려서 끝났는 지
- user_ms: CPU 에서 얼마나 많은 리소스를 차지하는 지
- sys_ms: OS 커널에서 오버헤드 비용이 발생해서 별도의 시간이 소모 되는 지
- max_rss_kb: 최대 메모리 사용량으로 GC 힙이나 언어 런타임 무게, 스레드 수에 대한 지표
- code_line: 실질 라인 수
  요약 테이블

| Language | avg_elapsed_ms | avg_user_ms | avg_sys_ms | avg_rss_kb | code_line |
|----------|----------------|-------------|------------|------------|-----------|
| c        | 3.8            | 0           | 0          | 1740.4     | 28        |
| rust     | 4.1            | 0           | 0          | 2270.4     | 20        |
| go       | 4.6            | 0           | 0          | 3422       | 33        |
| java     | 72.8           | 136         | 15         | 43387.6    | 26        |
| python   | 420.4          | 411         | 9          | 12117.6    | 14        |

<b>평균 시간 경과 (avg_elapsed_ms)</b>

- C, Rust, Go는 매우 낮은 평균 시간을 보여주지만 확실히 성능면에서 C가 제일 좋네요.
- Rust와 Go가 큰 차이가 발생하지 않는 다는 점과 이 정도의 차이면 좋은 PC에서는 차이가 더 미미할걸로 보입니다.
- 예상대로 파이썬은 매우 느리군요
- <b>평균 시간 경과 (avg_elapsed_ms)</b>

<b>평균 사용자 시간 및 시스템 시간 (user_ms, sys_ms)</b>

- C, Rust, Go는 사용자 시간과 시스템 시간 모두 평균 0.0ms를 기록
- Java는 Raw 데이터를 보시면 알 수 있듯이 처음과 세번째에서 user_ms가 이상하게 튀는 현상이 발생하는 데 이는 JVM 부팅이나 GC 문제로 추측됩니다.

<b>평균 최대 메모리 (max_rss_kb)</b>
- C와 Rust는 메모리를 거의 비슷하게 점유하고 Go는 살짝 더 많이 먹는데 아마 GC와 고루틴 스케줄러로 인해 Rust 보다는 많이 먹습니다.
- Java는 JVM 으로 인해 메모리를 많이 먹을 수 밖에 없군요

처음에 꼬리물기 질문을 했던 것들에 답한다면
> - 진짜 이게 장점일까?
>> C, Rust 보다는 느리지만 이는 유의미한 차이는 아니며 그 대신에 GoLang의 강력한 키워드들로 더 안전하게 동시성을 관리할 수 있다면 장점이다.
> - 다른 언어에 비해 월등히 좋을까?
>> Go는 컴파일 언어지만 C, Rust 같은 네이티브 언어와 견줄 수 있는 성능이다. 
> - Rust도 좋다고들 하던데 Rust 보다도 좋을까?
>> 당연하게도 Rust 보다는 메모리나 속도 면에서 느리다.
> - Python은 느리다던데 유의미한 퍼포먼스 차이가 있을까?
>> Python은 진짜 느리다.