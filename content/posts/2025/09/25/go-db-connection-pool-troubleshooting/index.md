---
title: "Go 서비스에서 DB 커넥션 풀 문제와 워커 풀 적용기"
date: 2025-09-25T11:58:05+09:00
categories: [ "Golang", "Database" ]
tags: [ "Go", "DB Connection Pool", "Worker Pool", "Trouble shooting" ]
draft: true
description: "원인을 알 수 없는 DB 커넥션 풀 고갈이 발생할 때 적용 했던 방법 들과 다소 허무한 결말을 담았습니다.."
keywords: [ "Golang", "DB 커넥션 풀", "Connection Pool", "Worker Pool", "Trouble shooting" ]
author: "DSeung001"
aliases: [ "/posts/2025/09/25/go-db-connection-pool-troubleshooting/" ]
---

## 문제 상황

### 프로젝트 배경
지금 다루고 있는 서비스는 안과의사 PC에서 돌아가는 온프레미스 서비스입니다.
장비 들에서 찍은 데이터를 의사들이 쉽게 보고, 관리, 수정하기 위한 일종의 의료 데이터 통합 웹 통합 툴 입니다.
이 서비스에서 장비와의 데이터 통신 부터 데이터 파이프라인, 프론트 작업까지를 담당하고 있습니다. 

해당 글에서 다룰 이슈는 다음과 같습니다.<br/>
특정 장비에서 부터 일정 양 이상의 데이터를 받으면 데이터베이스가 죽어버린다는 문제가 발생합니다. 
이를 해결하려면 사용자가 윈도우 서비스를 들어가서 DB를 껏다가 키거나 컴퓨터를 재부팅하지 않는 이상 해결되지 않는 이슈입니다.
다행인 점은 고객이 직접 요청한 VC가 아닌 내부에서 시스템 테스트를 통해 발견 되었고 또 해당 장비를 국내에서 많이 안 쓴다는 점이 다행이었죠.

하지만 원인을 알 수 없다는 점은 매우 큰 잠재적 이슈 이기에 해당 이슈에 우선 순위를 높게 두고 분석을 진행했습니다.
결과 적으로 마무리 및 정리까지 대략 5일 정도를 소요 되었네요 

## 원인 분석
일단 확실한 점은 데이터베이스가 정상 적으로 동작하지 못 한다는 것 이었고
원인을 추적하니 커넥션 풀이 반환되지 않고 지속 적으로 묶여있어서 사용할 커넥션 풀이 고갈된다는 점입니다.

이는 장비와의 데이터 통신시 아래와 같이 반환되지 않고 커넥션풀이 쌓이는 걸 보면 알 수 있습니다.
아래는 커넥션풀이 고갈되는 과정입니다, DB에 몇번 요청을 보내지 않았 는데도 커넥션 풀이 누적 되는걸 볼 수 있죠
```text
time="2025-09-26 17:01:34.744" level=info msg="Primary DB Pool Status - Open: 38, InUse: 36, Idle: 2, WaitCount: 0, WaitDuration: 0s"
time="2025-09-26 17:01:34.744" level=info msg="Total DB Connections: 38"
time="2025-09-26 17:01:34.744" level=info msg="Total DB GetDB() calls: 727"
time="2025-09-26 17:01:34.744" level=warning msg="Primary DB connection pool usage high: 94.7% (36/38 connections in use)"
time="2025-09-26 17:02:04.755" level=info msg="Primary DB Pool Status - Open: 88, InUse: 88, Idle: 0, WaitCount: 0, WaitDuration: 0s"
time="2025-09-26 17:02:04.755" level=info msg="Total DB Connections: 88"
time="2025-09-26 17:02:04.755" level=info msg="Total DB GetDB() calls: 1750"
time="2025-09-26 17:02:04.755" level=warning msg="Primary DB connection pool usage high: 100.0% (88/88 connections in use)"
```

원래라면 절대로 커넥션 풀이 고갈되면 안되죠(비교적 데이터 요청이 적은 온프레미스 환경이므로)
아래는 정상 로그 입니다.
```text
time="2025-09-26 16:59:12.175" level=info msg="Primary DB Pool Status - Open: 2, InUse: 0, Idle: 2, WaitCount: 0, WaitDuration: 0s"
time="2025-09-26 16:59:12.175" level=info msg="Total DB Connections: 2"
time="2025-09-26 16:59:12.175" level=info msg="Total DB GetDB() calls: 1080"
time="2025-09-26 17:00:02.175" level=info msg="Primary DB Pool Status - Open: 2, InUse: 0, Idle: 2, WaitCount: 0, WaitDuration: 0s"
time="2025-09-26 17:00:06.335" level=info msg="Total DB Connections: 2"
time="2025-09-26 17:00:06.335" level=info msg="Total DB GetDB() calls: 2136"
```

## 삽질들
### 커넥션 풀 모니터링
커넥션 풀 문제로 의심이 되었기에 위에서 나왔던 모니터링 기능을 추가했고 설정 파일을 통해 on/off가 되게끔 기능을 추가하고
모든 DB 접근 쿼리를 로깅할 수 하여 원인을 추적하는 데 애를 쓰면서 후에 비슷한 문제가 발생하더라도 모니터링에 쓸 수 있는 코드를 만드는 걸 목적으로 두고 작업했습니다.

아래 코드는 모니터링 코드의 호출 부의 코드입니다.
10초마다 logConnectionPoolStatus 함수를 실행시켜 로깅을 찍게 구현해뒀죠. 
```go
func StartConnectionPoolMonitoring() {
	enabled, err := config.GetConfigBool("connection_pool_monitoring")
	if err != nil || !enabled {
		log.Info("Connection pool monitoring is disabled")
		return
	}

	interval, err := config.GetConfigInt("connection_pool_monitoring_interval")
	if err != nil || interval <= 0 {
		interval = 10
	}

	log.Infof("Starting connection pool monitoring with %d second interval", interval)

	go func() {
		ticker := time.NewTicker(time.Duration(interval) * time.Second)
		defer ticker.Stop()

		for {
			select {
			case <-ticker.C:
				logConnectionPoolStatus()
			}
		}
	}()
}
```

### 로깅 라이브러리 교체
모니터링 및 쿼리 로깅 작업을 진행하면서 기존 프로젝트에 로깅 기능이 정상적으로 동작하지 않는 다는 걸 알게 되었죠.
파일 롤링에 관련된 옵션을 넣을 수 없을 뿐 더러, 로깅 레벨에 대한 부분을 파라미터로 받지만 실제 코드 내부에서는 이를 기반으로 필터링을 하지 않는 일종의 더미 코드가 있다는 부분을 확인했습니다.

```go
import lrh "github.com/gfremex/logrus-rollingfile-hook"

var logger *log.Entry

func init() {
    HookFormatter := new(prefixed.TextFormatter)
    HookFormatter.TimestampFormat = "2006-01-02 15:04:05.000"
    HookFormatter.FullTimestamp = true
    HookFormatter.ForceFormatting = true
    
    hook, _ := lrh.NewTimeBasedRollingFileHook("tbrfh",
        []log.Level{log.DebugLevel, log.InfoLevel, log.WarnLevel, log.ErrorLevel},
        HookFormatter,
        os.Getenv("HOCTROOT")+"/"+"log/svclog_"+time.Now().Format("2006-01-02")+".log"
	)
    
    new_log := log.New()
    
    Formatter := new(log.TextFormatter)
    
    Formatter.TimestampFormat = HookFormatter.TimestampFormat
```

롤링 옵션을 주는 기능도 없을 뿐더러 작동하는 줄 알았던 로깅 레벨 필러팅 기능까지 더미던 코드였기에 다른 라이브러리로 바꿀 필요성이 생겼습니다.
우선 온프레미스 서비스다 보니 기존 프로젝트에 영향을 최소화하면서, 생태계가 커 안정적으로 돌아가는 라이브러리를 우선으로 두고 아래와 같이 정했습니다.

- github.com/sirupsen/logrus : 가장 널리 쓰이는 로깅 패키지이므로 안전하기에 선택했습니다, 더 속도가 빠른 zap이나 rs/zerolog 등이 존재했지만 goLang 버전을 1.15에서 올리기에는 SSL 이슈가 아직 검증되지 않았기 버전업을 선택하고 싶지 않았고 속도 보다는 안정성이 중요한 프로젝트 특성상 해당 라이브러리를 선택하게 되었습니다. 
- gopkg.in/natefinch/lumberjack.v2 : 파일 사이즈, 개수 등 롤링에 관한 옵션을 다양하게 지원해서 사용성이 좋다는 점과 logrus와 같이 쓰기 좋다는 점으로 해당 라이브러리를 선택했습니다.

다음 코드처럼 아주 간단하게 로깅을 처리할 수 있고 설정이 직관적이여서 만족하며 쓰고 있습니다.
```go
var logger *logrus.Logger
func init() {
    logger = logrus.New()
	
	logger.SetOutput(io.MultiWriter(
            os.Stdout,
            &lumberjack.Logger{
            Filename:   os.Getenv("HOCTROOT") + "/log/svclog_" + time.Now().Format("2006-01-02") + ".log",
            MaxSize:    100,  // MB
            MaxBackups: 90,   // Number of files to archive
            MaxAge:     90,   // deleted after 90 days
            Compress:   true, // Compression status
        },
    ))
	
    logger.SetFormatter(&logrus.TextFormatter{
        TimestampFormat: "2006-01-02 15:04:05.000",
        FullTimestamp:   true,
        DisableColors:   true,
    })
```

### 캐싱
위와 같이 모니터링과 로깅을 손 보면서 디버깅을 하다보니 진단 목록에서 진단 ID를 기준으로 데이터를 가져오는게 호출이 상당히 많이 발생하고 있었습니다.
동일한 결과를 참조하는 쿼리 문이지만 장비와 데이터 통신을 할 때 40~50건이 발생되는 걸 확인 했습니다.
이걸로 커넥션 풀이 고갈되는 현상을 100% 설명할 수 없었지만 혹시나 하는 마음에 캐싱을 추가했습니다.

캐싱는 최대 1000개의 exam을 캐싱 해두고 30분의 ttl을 줘서 동일한 요청일 경우 DB를 타지 않게 구현 하였습니다.
핵심 로직은 다음과 같습니다.

```go
// ExamCache manages exam record caching with TTL and LRU(Least Recently Used) eviction
// 메모리 기능을 담당할 items, 동시성 이슈를 위해 mutex, 캐시의 지속 시간을 위한 ttl, 주기 적인 메모리 청소를 위한 cleanup
type ExamCache struct 
	items   map[int]*ExamCacheItem
	mutex   sync.RWMutex
	maxSize int
	ttl     time.Duration
	cleanup *time.Ticker
}

// NewExamCache creates a new exam cache with specified TTL and max size
// 캐시 생성
func NewExamCache(ttl time.Duration, maxSize int) *ExamCache {
	cache := &ExamCache{
		items:   make(map[int]*ExamCacheItem),
		maxSize: maxSize,
		ttl:     ttl,
	}

	// Start to clean up goroutine
	cache.cleanup = time.NewTicker(5 * time.Minute)
	go cache.cleanupExpired()
	return cache
}

// Get retrieves an exam record from cache
// 캐시에서 데이터 가져오기
func (c *ExamCache) Get(examID int) (ExamCacheRecord, bool) {
	c.mutex.Lock()
	defer c.mutex.Unlock()

	item, exists := c.items[examID]
	if !exists {
		return ExamCacheRecord{}, false
	}

	// Check if expired
	if time.Now().After(item.ExpireTime) {
		return ExamCacheRecord{}, false
	}

	// Update access time for LRU
	// 데이터가 있을 경우 LRU을 위해 Acess 시간을 업데이트 했습니다.
	item.AccessTime = time.Now()
	return item.Record, true
}

// Set stores an exam record in cache
func (c *ExamCache) Set(examID int, record ExamCacheRecord) {
	c.mutex.Lock()
	defer c.mutex.Unlock()

	now := time.Now()
	c.items[examID] = &ExamCacheItem{
		Record:     record,
		ExpireTime: now.Add(c.ttl), // TTL
		AccessTime: now,            // LRU
	}

	// Evict the oldest if the cache is full
	// 캐시의 크기가 다 찼을 경우
	if len(c.items) > c.maxSize {
		c.evictOldest()
	}
}

// evictOldest removes the least recently used item
// This function must be called while holding a write lock
// AccessTime 을 기준으로 가장 오래된 데이터 부터 삭제 합니다
func (c *ExamCache) evictOldest() {
	if len(c.items) == 0 {
		return
	}

	var oldestKey int
	var oldestTime time.Time
	first := true

	for key, item := range c.items {
		if first || item.AccessTime.Before(oldestTime) {
			oldestKey = key
			oldestTime = item.AccessTime
			first = false
		}
	}

	delete(c.items, oldestKey)
}

// cleanupExpired removes expired items periodically
// 업데이트 로직에 대처를 전부 해뒀지만 혹시 모르기에 데이터 무결성을 지키위해 
// 이 부분에서는 AccessTime이 아닌 TTL을 기준으로만 판단합니다.
func (c *ExamCache) cleanupExpired() {
	for range c.cleanup.C {
		c.mutex.Lock()
		now := time.Now()
		for key, item := range c.items {
			if now.After(item.ExpireTime) {
				delete(c.items, key)
			}
		}
		c.mutex.Unlock()
	}
}
```

확실히 많은 양의 DB 접근이 줄었습니다, 230건이던 DB 접근이 진단에 대한 캐싱을 추가하는 걸로 180건으로 줄었습니다.
하지만 캐싱을 추가해도 동일하게 커넥션 풀 고갈 현상은 발생했습니다.

### 진짜 원인 발견

커넥션 풀 고갈이 발생할 떄 까지 커넥션이 잠기는 횟수가 일정하다는 점을 근거로 로깅된 쿼리들과 대조해서 찾아내었습니다.
- QueryRow, Exec 버그 발견
진짜 원인은 go 1.15 버전의 내장 sql 라이브러리에서 발생했습니다.
패키지 내부를 까보니
- QueryRow는 Scan을 통해서만 커넥션 풀이 반환됨
- Exec는 사용 자체로 커넥션 풀이 반환됨


### Recovery 안티 패

## 삽질의 결과
- 캐싱을 통한 동일 진료 기준 50개 이상 줄어든 db 인스턴스 접근
- 좀더 클린해진 recovery 패턴
- 안정화된 로깅 기능 

## 배운점
- 커넥션 풀에 대한 이해, 반환안되는건 하자가 있는 거지
- 라이브러리 스타 수는 어느 정도 연관이 있다
- 캐싱 기능 추가