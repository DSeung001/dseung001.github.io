---
title: "Go 서비스에서 DB 커넥션 풀 문제 해결기"
date: 2025-09-25T11:58:05+09:00
categories: [ "Golang", "Database" ]
tags: [ "Go", "DB Connection Pool", "Worker Pool", "Trouble shooting" ]
draft: false
description: "DB 커넥션 풀 고갈이 이슈가 발생했을 때 원인을 찾기 위해 접근했던 방법을 정리했습니다."
keywords: [ "Golang", "DB 커넥션 풀", "Connection Pool", "Worker Pool", "Trouble shooting" ]
author: "DSeung001"
aliases: [ "/posts/2025/09/25/go-db-connection-pool-troubleshooting/" ]
---

## 문제 상황

### 프로젝트 배경
지금 다루고 있는 서비스는 안과의사 PC에서 돌아가는 온프레미스 서비스입니다.
장비 들에서 찍은 데이터들을 토대로 의사들이 정확한 진료를 내릴 수 있도록 도와주는 온프레미스 의료 데이터 통합 웹 툴이죠.
이 서비스에서 장비와의 데이터 통신 부터 받은 데이터에 대한 파이프라인, 프론트 작업과 퍼블리싱 작업까지 넓게 맡고 있습니다. 

해당 글에서 다룰 이슈는 다음과 같습니다.<br/>
특정 장비에서 부터 일정 양 이상의 데이터를 받으면 데이터베이스가 죽어버린다는 문제가 발생하였습니다.
장비의 데이터를 안정적으로 수신하여 의사한테 정확한 데이터를 보여줘하는 서비스 특징 상 매우 큰 이슈였습니다.

원인을 알 수 없다는 점이 때문에 더 위험하였고 해당 이슈에 우선 순위를 높게 부여 하고 분석을 진행했습니다.
결과 적으로 마무리 및 정리까지 대략 5일 정도를 소요하여 해결 할 수 있었습니다.

이번 경험을 통해 Go의 내장 SQL 패키지와 커넥션 풀의 관계를 더 자세히 알 수 있었고 로깅 리팩토링, 캐싱 기능 추가하면서 프로젝트에 안정성과 성능을 같이 챙기는 것에 대해 한번 더 생각할 수 있었습니다. 

## 원인 분석

### 문제 상황
데이터베이스로 사용중이던 Postgre SQL이 갑작스럽게 종료되는 원인을 추적하니 커넥션 풀이 반환 되지 않고 지속 적으로 묶여 있어서 
사용할 커넥션 풀이 고갈된다는 걸로 문제가 밝혀졌지만 정확히 무슨 로직에서 메모리 누수가 발생하는 지를 알 수 없었습니다.

알 수 있는 점은 프로젝트가 장비와 데이터를 통신할 때 어느 정도 횟수 이상으로 하면 발생하는 걸로 보아 로직에서 메모리가 정리 안되었다는 점을 알 수 있었죠.

아래는 커넥션풀이 고갈되는 과정입니다.</br>

커넥션 풀이 반환되지 않고 계속 잡고 있는 걸 "<b>Total DB Connections: 88</b>" 로그를 보시면 알 수 있습니다.
이는 현재 사용 중인 Connections의 개수가 남게끔 로그를 추가해서 알 수 있게 했습니다.
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

원래라면 절대로 커넥션 풀이 고갈되면 안되는 정도의 데이터 양 인데도 문제가 발생하고 있었습니다.
온프레미스 환경에서 커넥션 풀이 고갈될 정도의 접근이 발생하는 건 사실상 쉽지 않죠.

아래는 문제를 해결한 후 동일한 요청에서 찍히는 정상 로그입니다.<br/>
다음 코드를 보시면 "<b>Total DB Connections: 2</b>"로 커넥션 풀이 사용되자 말자 반환되었기에 수치가 늘지 않은 걸 알 수 있죠. 
```text
time="2025-09-26 16:59:12.175" level=info msg="Primary DB Pool Status - Open: 2, InUse: 0, Idle: 2, WaitCount: 0, WaitDuration: 0s"
time="2025-09-26 16:59:12.175" level=info msg="Total DB Connections: 2"
time="2025-09-26 16:59:12.175" level=info msg="Total DB GetDB() calls: 1080"
time="2025-09-26 17:00:02.175" level=info msg="Primary DB Pool Status - Open: 2, InUse: 0, Idle: 2, WaitCount: 0, WaitDuration: 0s"
time="2025-09-26 17:00:06.335" level=info msg="Total DB Connections: 2"
time="2025-09-26 17:00:06.335" level=info msg="Total DB GetDB() calls: 2136"
```

## 해결 과정
### 커넥션 풀 모니터링
커넥션 풀 문제로 의심이 되었지만 관련된 정보를 볼 수 있는 기능이 기존에 없었습니다.
면밀히 분석해서 의심했던 게 맞는 지 확인하기 위해 위에서 나왔던 모니터링 기능을 추가했습니다.
> 추가이유
> 1. 커넥션 풀 로직이 제대로 반환되었는 지를 확인하기 위함
> 2. 후에 사용하기 용이하게 설정 값으로 on/off 기능 추가, 앞으로도 비슷한 상황이 생겼을 때 쉽게 확인하기 위함

아래 코드는 모니터링 코드의 호출 부의 코드입니다. <br/>
10초마다 <b>logConnectionPoolStatus</b> 함수를 실행시켜 로깅을 찍게 구현해뒀죠.
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
커넥션 풀 모니터링 기능과 별도로 모든 DB 접근 쿼리를 로깅할 수 할 수 있도록 DB 인스턴스 로직을 사용할 때 래핑 클래스를 접근하게 해서 시스템에서 사용하는 모든 쿼리에 대해서도 로그를 남길 수 있게 했습니다.
혹여나 쿼리 중에 잘못된 부분이나 특정 쿼리가 많이 실행 되는 게 있다면 찾은 후 개선이 필요할 경우 쿼리 튜닝을 진행 하기 위해서죠

전체 적으로 나중에 비슷한 문제가 발생하더라도 모니터링에 쓸 수 있는 재사용성을 중요한 가치로 두고 작업 했습니다.


### 로깅 라이브러리 교체
모니터링 및 쿼리 로깅 작업을 진행하면서 기존 프로젝트에 로깅 기능이 정상적으로 동작하지 않는 다는 걸 점을 알게 되었습니다.
에러 레벨 분리 기능이 제대로 동작하고 있지 않았죠.

파일 롤링에 관련된 옵션을 넣을 수 없을 뿐 더러, 로깅 레벨에 대한 부분을 파라미터로 받지만 실제 코드 내부에서는 이를 기반으로 필터링을 하지 않는 다는 사실로 여태까지 더미 코드에 값을 던져줬다는 사실을 파악했습니다.
아래 문제의 기존 코드는 부분을 로깅 레벨을 받고 있지만 정작 라이브러리의 NewTimeBasedRollingFileHook에서는 이 값을 받고 저장만 할 뿐 사용하고 있지 않았습니다. 
> log.Level{log.DebugLevel, log.InfoLevel, log.WarnLevel, log.ErrorLevel}


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

위와 같은 이유로 다른 라이브러리로 바꿀 필요성이 생겼습니다.<br/>
우선 온프레미스 서비스다 보니 기존 프로젝트에 영향을 최소화하면서, GoLang 버전이 1.15에서 잘 돌아가는 걸로 거기에 생태계가 커 안정적으로 돌아가는 라이브러리를 우선으로 두고 아래와 같이 정했습니다.

> - github.com/sirupsen/logrus : 가장 널리 쓰이는 로깅 패키지로 go 1.15에서도 안정적을 ㅗ달아갑니다. 
> - gopkg.in/natefinch/lumberjack.v2 : 파일 사이즈, 개수 등 롤링에 관한 옵션을 다양하게 지원해서 사용성이 좋다는 점과 logrus와 같이 쓰기 좋습니다.

선택 이유는 다음과 같습니다.
- 더 속도가 빠른 zap이나 rs/zerolog 등이 존재했지만 goLang 버전을 1.15에서 올리기에는 SSL 이슈가 아직 검증되지 않음 
- 현재 go 버전에서 가장 안정적인 라이브러리를 우선순위로 둠


적용해보니 다음 코드처럼 아주 간단하게 로깅과 파일 롤링을 처리할 수 있고 설정이 직관적이여서 만족하며 쓰고 있습니다.
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
위와 같이 모니터링과 로깅을 손 보면서 분석하다보니 진단 목록에서 진단 ID를 기준으로 데이터를 가져오는 쿼리에 대한 호출이 상당히 불필요하게 많이 발생하고 있었습니다.<br/>

동일한 결과를 참조하는 쿼리 문을 장비와 데이터 통신을 할 때 40~50건 씩이나 호출한다는 점을 확인 했습니다.

이걸로 커넥션 풀이 고갈되는 현상을 100% 설명할 수 없었지만 혹시나 하는 마음에 캐싱을 추가했습니다. <br/>
데이터 통신 프로세스를 하나씩 다 분석하기에는 시리얼로 통신하는 경우, Http로 통신하는 경우 등 다양한 통신 법이 있고 그걸 또 다양한 장비에서 다 각자의 방법을 사용하고 있었기에 이들을 통합적으로 한번에 성능을 향상시키면서 적은 리소스를 넣을 수 있는 걸 생각해보니 캐싱 기능 추가가 가장 적합했습니다.<br/>
또 온프레미스 환경이기에 설치를 하는 과정에 복잡성을 최소화 하고 싶어서 외부 솔루션보다는 in-memory 방식을 선택하였습니다.

캐싱는 최대 1000개의 exam을 캐싱 해두고 30분의 ttl을 줘서 동일한 요청에 대한 데이터가 있을 경우 DB를 타지 않게 구현하였습니다.
진단 데이터 업데이트시는 관련 데이터를 캐시에서 지우는 방식을 채택했습니다, 업데이트 빈도가 크지 않았기에 그런 방식으로 가닥을 잡았습니다.
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
	// 캐시의 크기가 다 찼을 경우 evictOldest를 실행
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
// 이 부분에서는 AccessTime이 아닌 TTL을 기준으로만 데이터를 지우게 해두었습니다.
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

// Close stop the cleanup goroutine
func (c *ExamCache) Close() {
if c.cleanup != nil {
c.cleanup.Stop()
}
}

// Invalidate removes specific exam record from cache
// 업데이트시도 이 기능을 사용해서 캐싱에서 지우는 걸로 진행
func (c *ExamCache) Invalidate(examID int) {
c.mutex.Lock()
defer c.mutex.Unlock()
delete(c.items, examID)
}
```

캐싱 추가로 확실히 많은 양의 DB 접근이 줄었습니다. 

수치로 보면 230건이던 DB 접근이 진단에 대한 캐싱을 추가하는 걸로 180건으로 줄었죠.<br/>
모든 장비와의 데이터 통신시 적용되므로 범용적으로 약간의 성능 향상을 적용했습니다. 하지만 이 기능이 메모리 누수를 해결한 건 아니죠.

### 원인 발견

전체 프로젝트 코드를 훓어본 결과, 진짜 원인을 찾을 수 있었습니다. 
go 1.15 버전의 내장 sql 라이브러리에서 발생했습니다.<br/>

다음 로직을 사용하고 있었는데 여기서 커넥션 풀이 반환 없었다는 게 원인으로 이 문제는 에러 로그도 발생하지 않아서 놓치고 있었습니다.
```go
err := database.GetDB().QueryRow(query,
    &r.Iol_License_Tbl_Serial_id,
    &r.Device_Name,
    &r.Device_Serial_Number,
    r.Serial_Id,
).Err()
```
패키지 내부를 까보니 QueryRow는 사용 후 Scan을 통해서 데이터를 받을 경우에만 커넥션 풀이 반환되는데, 위 코드는 Scan을 사용하지 않았고 그로 인해 Context Deadline이 끝나지 않는 한 계속 커넥션 풀이 물려있어서 해당 이슈가 발생한거였습니다.
Exec는 사용 자체로 커넥션 풀이 반환 되었기에 이를 혼동해서 개발된 게 발생 이유로 추정 되었고 이를 다음 처럼 변경 한 뒤
```go
_, err := database.GetDB().Exec(query,
    &r.Iol_License_Tbl_Serial_id,
    &r.Device_Name,
    &r.Device_Serial_Number,
    r.Serial_Id,
)
```

시스템 테스트 및 부하 테스트를 진행해서 정상적으로 돌아가는 것을 확인했습니다.
조금 더 빨리 알아챘다면 더 빠르게 해결할 수 있는 이슈였던 게 아쉬웠습니다.

## 결과
결과 적으로 다음과 같은 개선 사항이 생겼고 메모리 누수 문제도 해결할 수 있었습니다.
- 캐싱이 추가되어 장비와 통신시 불필요한 DB 접근을 50건을 줄여 DB 객체 접근량을 230건에서 180건으로 78%로 감소
- 로깅 기능의 파일 롤링 기능에 대해서 파일 용량과 파일 개수와 자동 압축 기능까지 추가함으로써 메모리와 성능까지 보완
- 거기에 커넥션 풀 모니터링 기능을 추가하여 비슷한 문제가 발생하더라도 금방 알 수 있음
- 메모리 누수 케이스 확보 및 사내 공유

앞으로 개선 사항
- 모니터링이나 로깅 기능은 좀 더 손을 봐서 서비스에 맞춤 형태인 모듈로 발전