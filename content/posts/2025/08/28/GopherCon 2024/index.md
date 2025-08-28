---
title: "GopherCon 2024 정리"
date: 2025-08-28T11:58:05+09:00
categories: [ "Conference", "Diary" ]
tags: [ "GopherCon", "Golang", "컨퍼런스" ]
draft: false
description: "GopherCon 2024에서 다뤄진 주요 세션과 인사이트를 제멋 대로 짤막하게 정리 해봤습니다."
keywords: [ "GopherCon 2024", "Go", "고퍼콘", "컨퍼런스", "발표정리" ]
author: "DSeung001"
aliases: [ "/posts/2025/08/25/gophercon-2024-summary/" ]
---

## Go언어 프로젝트 가이드 A-Z - 변규현, 당근
### 주된 내용
Feather 단위에서 Enterprise 단위까지 Application 개발을 GoLang으로 할 때 어떻게 접근 하는 지에 대한 이야기

규모에 맞춰 아래와 같이 나눠서 접근
- 초기(스타트업/MVP 단계)
  - 사용자 검증을 위한 빠른 개발에 집중
  - 불필요한 라이브러리 최소화, 표준 라이브러리 활용
  - 기능 단위로 간단히 구현, HandlerFunc 중심의 빠른 개발 패턴 활용
- 서비스 확장 단계(유니콘/중간 규모)
  - 기능이 많아지고 의존성이 복잡해지므로 이 시기부터 패턴의 중요성 커짐
  - 단순 HandlerFunc에서 Handler 패턴으로 전환하는 시기로 특히 상태 관리, 의존성 명확화가 필요
    - Handler 패턴: 구조체에 의존성을 주입할 수 있게 하고, ServeHTTP를 구현하게 해서 어디든 사용 가능 하게 해서 확장성을 챙김
    ```go
    type PingHandler struct {
        DB *sql.DB
    }

    func (h *PingHandler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
        // DB 같은 의존성 명확하게 사용 가능
        w.Write([]byte("pong with DB"))
    }
    ```
  - 기능 단위에서 서비스 단위 아키텍처로 확장
- 엔터프라이즈 단계
  - DDD(Domain-Driven Design) 적용을 통해 기능 중심에서 비즈니스 도메인 중심으로 분리
  - Bounded Context로 경계 정의
  - 데이터 흐름을 확실히 나눔
  - API 모델과 내부 도메인 분리 (Presenter 패턴 활용)
  - 각 레이어 분리로 테스트 용이 (Fake 구현 활용)

운영 필수 도구
- APM(Application Performance Monitoring): Datadog
- Error Monitoring: Sentry/Datadog
- Metrics: Prometheus
- Logging 서비스

### 배운 점
가장 인상 깊게 본 파트는 엔터프라이즈 규모에서 DDD로 나눌 때 도메인을 나누는 규칙으로 API Model(API 로직), Domain(비즈니스 로직), Mode(DB 로직)을 나눈 게 가장 인상 깊었습니다.
```text
[----API Model----]                      [-------Model-------]
            [----------------Domain----------------]      

Presenter → Handler → Usecase → Service → Repository → Recorder
```
각각의 기능이 고유 특징을 잘 지켜가며 DDD 패턴을 지키는 데, DDD를 지향할 때 마다 맞닥뜨리는 부분을 딱 집어줘서 좋았습니다.
규모가 큰 프로젝트를 진행할 경우 이 구조를 기초로 두고 프로젝트 특징에 하위 도메인을 통해 분리 해가면 도메인을 더 좋게 나눌 수 있어 보입니다.

- presenter
  - 화면을 자유롭게 나눌 수 있음
- handler
  - http/grpc 요청과 응답 생성만 집중
  - 비즈니스 로직은 usecase에 위임
  - usecase를 mocking하여 handler를 독립적으로 테스트
- usecase
  - service 또는 repository의 의존성을 받음
  - 순수한 도메인 객체 사용
  - 단일 메서드에 여러 service, repository를 엮어서 복잡한 비즈니스 로직 처리 (비즈니스 로직의 최상위)
  - repository를 모킹하여 usecase 테스트 가능
- service
  - 무거운 로직을 분리함으로써 usecase의 복잡성을 줄임
  - usecase에서 공통으로 쓰이는 로직을 service로 옮겨 재사용성 높임 (usecase는 흐름과 조정, service는 구체적인 비즈니스 로직)
  - 필요한 경우에만 서비스를 도입하여 불필요한 추상화 줄이고 시스템의 유연성 유지
- repository
  - 비즈니스 로직과 데이터 접근에서 오직 데이터 접근 로직을 담당하여 상위 계층은 저장 방식을 알 필요가 없음 
  - 도메인 모델을 반환하므로 repository는 domain을 의존하게 되는 데 이로써 의존성 역전 원칙을 따름(도메인 로직이 인프라(db) 세부 사항으로부터 독립)
- redocder(otpional)
  - dynamoDB의 특정 API나 쿼리 언어 추상화
  - 다른 db로 마이그레이션시 recorder마 수정하면 됨
  - 복잡한 쿼리가 많을 경우 고려

## GoLang으로 4일만에 아이디어스 Image 서버 성능 72% 개선
### 주된 내용
문제 상황
- 레거시 이미지 서버(10년 이상 유지된 PHP 기반)에서 CPU Throttling 문제 발생.
- CDN 캐시 만료 시 요청이 폭증 → 이미지 리사이즈 API가 병목.
- CPU 오토스케일링은 동작했지만 리소스 사용 효율이 매우 낮음.

개선 목표
- 기존보다 성능 2배 향상을 목표.
- Go 언어 기반으로 마이그레이션.
- 유지보수성과 문서화를 고려해 Gin 프레임워크 채택.
- DevOps 친화적인 언어 선택(CNCF/Kubernetes/ArgoCD와 자연스럽게 연결).
- 최소한의 리소스 투입

개선 과정
- 성능 테스트
  - Locust로 PHP vs Go 비교.
  - 초반엔 PHP가 더 빠름 → 이유는 라이브러리 차이.
  - PHP는 C 기반 고성능 라이브러리 사용, Go는 단순한 nfnt/resize 사용.
- 라이브러리 교체
  - Go에서 libvips (C 기반) 채택 → 성능 크게 개선.
- 2차 테스트 결과
  - CPU Throttling은 동일.
  - Latency 개선.
  - CPU/Memory 효율 Go가 2배 이상 우수.
- 배포 전략
  - Canary 방식으로 점진적 배포.
  - Kubernetes + Istio Virtual Service로 트래픽 분산.
  - 빠른 롤백 가능성 확보.

성능 개선 성과
- 요청 처리 성능 74.7% 향상.
- Latency 감소.
- 빌드 속도 3배 증가.
- Go는 바이너리 빌드 덕분에 컨테이너 이미지 크기 최소화 가능.

PHP 레거시 코드를 적은 리소스 투입으로 프로세스 성능을 대폭 늘려 인프라 비용을 대폭 절감하는 효과를 나타낸 시나리오를 볼 수 있었습니다. 

### 배운 점
아래 사이클로 돌아 가는 개발 사이클을 엿볼 수 있다는 점이 가장 좋았고
```text
문제파악 → 문제정의 → 문제해결 → 테스트 → 테스트 검증 → 점진적 적용(Canary) → 전체 배포
```

**카나리 배포(Canary Deployment)** 를 사용한 시나리오가 좋았습니다.

서비스나 애플리케이션을 업데이트할 때 전체 사용자에게 한 번에 배포하지 않고, 일부 트래픽(소수의 사용자)에게만 점진적으로 배포하는 방식을 통해 안정성 체크와 성능 비교, 복구 기능도 같이 챙긴 점이 정말 좋더군요.


## 차량 업데이트 파일의 안전한 관리
### 주된 내용
42dot: SDV(Software Defined Vehicle, 소프트웨어 정의 자동차)에서 자율주행, OTA 업데이트 파일 관리법 공유
Go 기반 소프트웨어 업데이트 서버에서 어떻게 파일을 암호화 하는지 


보안 개념 정리 (CIA Triad)
- Confidentiality (기밀성): 업데이트 파일 암호화
- Integrity (무결성): 업데이트 파일 변조 방지 및 검증
- Availability (가용성): 업데이트 파일 접근 가능 보장

암호화 (Confidentiality)
- Go의 기본 암호화 모듈 사용.
- 자동차 OTA 업데이트는 GB 단위이므로 io.Reader, io.Writer 기반 스트리밍 방식으로 메모리 절약.
- Enveloped Encryption 방식 활용:
  - 목적: 업데이트 파일을 안전하게 암호화해서 외부에서 내용을 볼 수 없도록 함
  - 특징: 속도(대칭) + 안전한 키 관리(비대칭)를 동시에 잡음.
    - 대칭키(AES 등)로 대용량 파일을 빠르게 암호화.
    - 대칭키(RSA, ECC 등)로 대칭키를 암호화.
    - 수신자는 비대칭키 개인키로 대칭키를 복호화한 뒤, 그 대칭키로 파일을 해독.
- 문제점 보완:
  - 서버에 평문 파일 저장 → 위험.
  - 서버 측에서 암호화 비용 → 크므로 대칭+비대칭 혼합 방식 채택.

무결성 보장 (Integrity)
- OTA 업데이트 전송 중 변조 및 공격 방지 필요.
- UPTANE (CNCF 산하 프레임워크) 활용:
  - 차량 소프트웨어 업데이트 보안을 위한 오픈소스 표준.   
    메타데이터 기반 검증 → 어느 한쪽이 변조되면 즉시 감지 가능.

### 배운 점

대용량 업데이트 서버를 다루는 도메인에서 업데이트를 관리하는 법을 참고 수 있었습니다.

## Golang 웹 프레임워크, Gin 모니터링 서비스 개발
### 주된 내용

Gin 프레임워크
- Go 언어에서 가장 인기 있는 웹 프레임워크.
- Iris, Beego보다 사용자 수·스타 수 압도적.
- 최근 업그레이드로 성능 20% 향상.

Gin 모니터링이 중요한 이유
- Kubernetes, MSA(마이크로서비스 아키텍처) 확산으로 애플리케이션 단위가 작아지고 통신이 복잡해짐.

Metric Monitoring
- 수집 항목: Request Duration, Request Count, Status Code
- 미들웨어에서 요청 시작/종료 시간 체크 후 duration 계산.
- 동시성 문제 방지를 위해 Mutex 사용.
- 데이터는 **시계열 DB(InfluxDB)**에 저장.

Distributed Trace Monitoring
- Trace: 클라이언트 요청 전체 경로 추적 (Trace ID로 연결).
- Span: 각 구간별 ID, parent span ID로 호출 경로 파악.
- 구현 방식:
  - Go의 http.RoundTripper 커스텀 → 요청 헤더에 trace/span id 삽입.
  - 미들웨어에서 trace/span id 확인 후 갱신.
- 결과: 분산 환경에서도 요청 흐름을 추적 가능.

결과 저장
- Metric → InfluxDB (스케줄링으로 주기적 적재).
- Log → Grafana에서 시각화.

### 배운 점
Go에서 미들웨어를 통해 어떻게 모니터링 시스템을 구축하는 지를 볼 수 있었습니다. Trace와 Span을 추가하고 http.RoundTripper 로 커스텀 해서 자동으로 해더에 넣어 줌으로써 프로세스의 흐름을 파악 한다는 게 재밌었네요. 