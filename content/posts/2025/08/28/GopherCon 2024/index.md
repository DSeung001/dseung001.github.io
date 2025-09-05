---
title: "GopherCon 2024 정리"
date: 2025-08-28T11:58:05+09:00
categories: [ "Conference", "Diary" ]
tags: [ "GopherCon", "Golang", "컨퍼런스" ]
draft: false
description: "GopherCon 2024에서 다뤄진 주요 세션과 인사이트를 제멋대로 짤막하게 정리해봤습니다."
keywords: [ "GopherCon 2024", "Go", "고퍼콘", "컨퍼런스", "발표정리" ]
author: "DSeung001"
aliases: [ "/posts/2025/08/25/gophercon-2024-summary/" ]
---

## Go언어 프로젝트 가이드 A-Z
### 주된 내용
Feather 단위에서 Enterprise 단위까지 Application 개발을 GoLang으로 할 때 어떻게 접근하는지에 대한 이야기

**규모에 맞춰 아래와 같이 나눠서 접근**
- 초기(스타트업/MVP 단계)
  - 사용자 검증을 위한 빠른 개발에 집중
  - 불필요한 라이브러리 최소화, 표준 라이브러리 활용
  - 기능 단위로 간단히 구현, HandlerFunc 중심의 빠른 개발 패턴 활용
- 서비스 확장 단계(유니콘/중간 규모)
  - 기능이 많아지고 의존성이 복잡해지므로 이 시기부터 패턴의 중요성 커짐
  - 단순 HandlerFunc에서 Handler 패턴으로 전환하는 시기로 특히 상태 관리, 의존성 명확화가 필요
    - Handler 패턴: 구조체에 의존성을 주입할 수 있게 하고, ServeHTTP를 구현하게 해서 어디든 사용 가능하게 해서 확장성을 챙김
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

**운영 필수 도구**
- APM(Application Performance Monitoring): Datadog
- Error Monitoring: Sentry/Datadog
- Metrics: Prometheus
- Logging 서비스

### 배운 점
가장 인상 깊게 본 파트는 엔터프라이즈 규모에서 DDD로 나눌 때 도메인을 나누는 규칙으로 API Model(API 로직), Domain(비즈니스 로직), Model(DB 로직)을 나눈 게 가장 인상 깊었습니다.
```text
[----API Model----]                      [-------Model-------]
            [----------------Domain----------------]      

Presenter → Handler → Usecase → Service → Repository → Recorder

```
각각의 기능이 고유 특징을 잘 지켜가며 DDD 패턴을 지키는데, DDD를 지향할 때마다 맞닥뜨리는 부분을 딱 집어줘서 좋았습니다.
규모가 큰 프로젝트를 진행할 경우 이 구조를 기초로 두고 프로젝트 특징에 하위 도메인을 통해 분리해가면 도메인을 더 좋게 나눌 수 있어 보입니다.

**도메인 분리**
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
  - 도메인 모델을 반환하므로 repository는 domain을 의존하게 되는데 이로써 의존성 역전 원칙을 따름(도메인 로직이 인프라(db) 세부 사항으로부터 독립)
- recorder(optional)
  - dynamoDB의 특정 API나 쿼리 언어 추상화
  - 다른 db로 마이그레이션시 recorder만 수정하면 됨
  - 복잡한 쿼리가 많을 경우 고려

## GoLang으로 4일만에 아이디어스 Image 서버 성능 72% 개선
### 주된 내용
**문제 상황**
- 레거시 이미지 서버(10년 이상 유지된 PHP 기반)에서 CPU Throttling 문제 발생.
- CDN 캐시 만료 시 요청이 폭증 → 이미지 리사이즈 API가 병목.
- CPU 오토스케일링은 동작했지만 리소스 사용 효율이 매우 낮음.

**개선 목표**
- 기존보다 성능 2배 향상을 목표.
- Go 언어 기반으로 마이그레이션.
- 유지보수성과 문서화를 고려해 Gin 프레임워크 채택.
- DevOps 친화적인 언어 선택(CNCF/Kubernetes/ArgoCD와 자연스럽게 연결).
- 최소한의 리소스 투입

**개선 과정**
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

**성능 개선 성과**
- 요청 처리 성능 74.7% 향상.
- Latency 감소.
- 빌드 속도 3배 증가.
- Go는 바이너리 빌드 덕분에 컨테이너 이미지 크기 최소화 가능.

PHP 레거시 코드를 적은 리소스 투입으로 프로세스 성능을 대폭 늘려 인프라 비용을 대폭 절감하는 효과를 나타낸 시나리오를 볼 수 있었습니다.

### 배운 점
아래 사이클로 돌아가는 개발 사이클을 엿볼 수 있다는 점이 가장 좋았고
```text
문제파악 → 문제정의 → 문제해결 → 테스트 → 테스트 검증 → 점진적 적용(Canary) → 전체 배포
```

**카나리 배포(Canary Deployment)** 를 사용한 시나리오가 좋았습니다.

서비스나 애플리케이션을 업데이트할 때 전체 사용자에게 한 번에 배포하지 않고, 일부 트래픽(소수의 사용자)에게만 점진적으로 배포하는 방식을 통해 안정성 체크와 성능 비교, 복구 기능도 같이 챙긴 점이 정말 좋더군요.


## 차량 업데이트 파일의 안전한 관리
### 주된 내용
42dot: SDV(Software Defined Vehicle, 소프트웨어 정의 자동차)에서 자율주행, OTA 업데이트 파일 관리법 공유
Go 기반 소프트웨어 업데이트 서버에서 어떻게 파일을 암호화하는지


**보안 개념 정리 (CIA Triad)**
- Confidentiality (기밀성): 업데이트 파일 암호화
- Integrity (무결성): 업데이트 파일 변조 방지 및 검증
- Availability (가용성): 업데이트 파일 접근 가능 보장

**암호화 (Confidentiality)**
- Go의 기본 암호화 모듈 사용.
- 자동차 OTA 업데이트는 GB 단위이므로 io.Reader, io.Writer 기반 스트리밍 방식으로 메모리 절약.
- Enveloped Encryption 방식 활용:
  - 목적: 업데이트 파일을 안전하게 암호화해서 외부에서 내용을 볼 수 없도록 함
  - 특징: 속도(대칭) + 안전한 키 관리(비대칭)를 동시에 잡음.
    - 대칭키(AES 등)로 대용량 파일을 빠르게 암호화.
    - 비대칭키(RSA, ECC 등)로 대칭키를 암호화.
    - 수신자는 비대칭키 개인키로 대칭키를 복호화한 뒤, 그 대칭키로 파일을 해독.
- 문제점 보완:
  - 서버에 평문 파일 저장 → 위험.
  - 서버 측에서 암호화 비용 → 크므로 대칭+비대칭 혼합 방식 채택.

**무결성 보장 (Integrity)**
- OTA 업데이트 전송 중 변조 및 공격 방지 필요.
- UPTANE (CNCF 산하 프레임워크) 활용:
  - 차량 소프트웨어 업데이트 보안을 위한 오픈소스 표준.   
    메타데이터 기반 검증 → 어느 한쪽이 변조되면 즉시 감지 가능.

### 배운 점

대용량 업데이트 서버를 다루는 도메인에서 업데이트를 관리하는 법을 참고할 수 있었습니다.

## Golang 웹 프레임워크, Gin 모니터링 서비스 개발
### 주된 내용

**Gin 프레임워크**
- Go 언어에서 가장 인기 있는 웹 프레임워크.
- Iris, Beego보다 사용자 수·스타 수 압도적.
- 최근 업그레이드로 성능 20% 향상.

**Gin 모니터링이 중요한 이유**
- Kubernetes, MSA(마이크로서비스 아키텍처) 확산으로 애플리케이션 단위가 작아지고 통신이 복잡해짐.

**Metric Monitoring**
- 수집 항목: Request Duration, Request Count, Status Code
- 미들웨어에서 요청 시작/종료 시간 체크 후 duration 계산.
- 동시성 문제 방지를 위해 Mutex 사용.
- 데이터는 **시계열 DB(InfluxDB)**에 저장.

**Distributed Trace Monitoring**
- Trace: 클라이언트 요청 전체 경로 추적 (Trace ID로 연결).
- Span: 각 구간별 ID, parent span ID로 호출 경로 파악.
- 구현 방식:
  - Go의 http.RoundTripper 커스텀 → 요청 헤더에 trace/span id 삽입.
  - 미들웨어에서 trace/span id 확인 후 갱신.
- 결과: 분산 환경에서도 요청 흐름을 추적 가능.

**결과 저장**
- Metric → InfluxDB (스케줄링으로 주기적 적재).
- Log → Grafana에서 시각화.

### 배운 점
Go에서 미들웨어를 통해 어떻게 모니터링 시스템을 구축하는지를 볼 수 있었습니다. Trace와 Span을 추가하고 http.RoundTripper로 커스텀해서 자동으로 헤더에 넣어 줌으로써 프로세스의 흐름을 파악한다는 게 재밌었네요.

## Deterministic testing in Go
### 주된 내용
Deterministic Testing in Go란 테스트가 매번 같은 입력을 보장하여 같은 결과를 보장하도록 만드는 기법입니다. <br/>
즉, 랜덤/시간/고루틴 순서 등 비결정적 요소로 생기는 **Flaky Test(간헐적 실패 테스트)**를 제거하는 방법에 관한 내용이죠.

**Non-Deterministic Testing (비결정적 테스트)**
- 결과가 매번 달라질 수 있는 테스트
- 원인:
  - 네트워크 호출
  - 파일 입출력
  - 랜덤 값 (UUID, nonce 등)
  - 시간(time.Now)
  - 고루틴/채널 실행 순서
  - map 순회 순서
  - marshal/json 변환 시 출력 순서 불일치
- Flaky Test는 프로덕션 배포의 불안 요소이기에 해소하는 편이 좋음

**Deterministic Testing 방법**
- 의존성 주입
  - 랜덤 값, 시간, ID 생성 등은 함수 인자로 주입하거나 interface로 추상화.
  - time.Now, uuid.New 같은 값은 직접 호출하지 않고 외부에서 넘겨받기.
- 랜덤/생성 값 고정하기
  - uuid/nonce는 생성 함수 인자로 받기.
  - 기존 코드 수정 어려운 경우 값 자체 비교 대신 형식/속성 검증(길이, charset 등).
- map / slice 순서 문제
  - go의 map 순회 순서는 보장되지 않음.
    - 해결법: slice에 저장 후 **정렬(sorting)** 해서 비교.
    - map은 단순 lookup 용도로만 사용.
- 시간 고정하기
  - time.Since, time.Until을 내부에서 time.Now 사용하므로 테스트에 넣지 않도록 하기.
  - 해결법
    - nowFunc 같은 함수 인자 주입.
    - 고정된 시간을 넘길 수 있도록 설계.
    - sleep, ticker, timer 같은 경우는 Clock 인터페이스 도입.
- 타임아웃 테스트
  - 10초 기다릴 수 없음.
  - 해결법
    - context.WithTimeout(ctx, 0) 사용 → 즉시 timeout 상태 전달.
- 고루틴 테스트
  - runtime.Gosched()만으로 실행 보장을 할 수 없음
  - 해결법:
    - assert.Eventually (testify)
    - 채널/WaitGroup 사용해 완료 보장
    - 고루틴 실행 순서를 제어하려면 Group 인터페이스 추상화해서 mock 구현으로 테스트
    - fan-out/fan-in 패턴에서 정해진 인덱스에 결과 저장해서 해결(실패 케이스 대처 필요)

**Flaky Test 탐지**
- GitHub Actions 등에서 재실행 시 성공/실패가 번갈아 나오는 경우
- go test -count 10 / -count 100으로 반복 실행
- Go 1.17+ → go test -shuffle=on으로 테스트 실행 순서 섞기

**결론**
- 결정적 테스트를 이루려면 의존성 주입을 통해 모든 외부 요인(시간, 랜덤, 고루틴, 순서)을 통제하면 가능.
- Go는 컴파일 언어이므로 파이썬처럼 monkey patch를 사용하지 못한다, 대신 아키텍처 패턴으로 해결.
- Flaky Test를 줄여서 보다 안정적 CI/CD로 신뢰할 수 있는 배포 가능

### 배운 점
Non-Deterministic Testing과 Deterministic Testing 테스팅의 차이점을 알 수 있었고 기존에는 테스트는 다양하면 좋다고 해서 오히려 Non-Deterministic Testing 패턴으로 접근해서 작성하기도 했었습니다.

하지만 이번 강좌를 보니 그 부분을 피해서 좀 더 안정적인 테스트를 지향하더군요
테스트의 목적은 로직의 검증이니 항상 결과가 다를 수 있다는 요인을 남겨둔다면 그건 테스트의 본질을 잃는 것이니 이쪽이 더 맞는 것 같습니다. 

## 쿠버네티스 플랫폼 프로그래밍
### 주된 내용
쿠버네티스(K8s)
- 컨테이너화된 애플리케이션을 자동으로 배포·관리·확장하는 플랫폼
- 배포, 스케일링, 복구, 로드밸런싱을 자동화
- 클라우드/온프레미스 어디서든 동일한 방식으로 운영 가능

쿠버네티스 API
- HTTP 기반 API로 클러스터 및 리소스 제어
- 리소스 목록 조회, 생성, 상태 모니터링 가능
- https://<APISERVER>/<GROUP>/<VERSION>/<RESOURCE>/<NAME> 구조

client-go
- 쿠버네티스 API를 추상화하여 Go에서 쉽게 사용 가능
- informer 기반 캐싱/변경 감지 지원
- 리소스 충돌 시 resourceVersion을 통한 무결성 체크, RetryOnConflict로 재시도 가능

컨트롤러와 오퍼레이터
- 컨트롤러: 기본 리소스(Pod, Deployment, Service) 관리
- 오퍼레이터: 사용자 정의 리소스를 통해 복잡한 앱 상태를 자동으로 관리

Kubebuilder 프레임워크
- Go 기반으로 컨트롤러·오퍼레이터 개발을 돕는 도구
- Manager, Controller, Reconciler 구조 제공
- Spec(리소스 특징이나 원하는 상태)과 Status(리소스 현재 상태)로 리소스 상태를 관리

쿠버네티스 배포 방식
- Dockerfile 작성 → docker build & push
- Deployment, ConfigMap, Secret, Service 등 리소스 생성
- Helm 차트로 리소스 템플릿 관리

### 배운점
쿠버네티스는 단순 컨테이너 실행 도구가 아니라 앱 배포·운영 자동화를 위한 표준 플랫폼임을 알게 되었고 client-go로 GoLang 애플리케이션에서 직접 쿠버네티스 리소스를 제어하는 일련의 작업을 직접 볼 수 있어서 좋았습니다.

Kubebuilder를 통해 Reconciler에 집중하여 리소스 상태를 관리할 수 있고, 오퍼레이터를 활용하면 복잡한 애플리케이션도 자동으로 운영 가능하다는 것도 인상깊었는데

문제는 쿠버네티스를 사용해본 적이 없어서 와닿기 어려웠다는 점입니다.
그래도 앱 운영을 체계적이고 안정적으로 만들 수 있는 핵심 개념이라는 점으로 이해를 했습니다.

## Building Minimalistic Backend Microservice in Go
### 주된 내용
Go 언어로 마이크로서비스를 만들 때 반복적으로 신경써야 하는 요소들과 팁들(Config 읽기, Graceful Shutdown, 테스트 가능성, API 문서, 로깅, 모니터링/메트릭/트레이싱)
최소한의 코드(200 LOC 이하, 단일 main.go, 표준 패키지만)로 프로토타입 성격의 프로젝트 구현

**코드 스타일 철학**
- Keep minimal: 외부 라이브러리 대신 표준 패키지로 구현, 의존성 최소화
- Testability: main() → run() 함수로 분리하여 테스트 가능하게
- Conciseness: 함수 분산보다 한 곳에서 해결을 선호
- Trade-off: 간결성과 기능성 사이의 균형 필요

**주요 기능 구현**
- Health Check API: 버전, Uptime, Commit Hash 등 반환
- 빌드 시 ldflags로 버전 정보 삽입
- embed 패키지로 YAML(OpenAPI 문서 등) 포함 → 배포 용이
- Logging: JSON 로그 표준화, slog + stdout, Fluentbit 연계
- Middleware/Decorator 패턴으로 로깅과 에러 복구(Recover) 처리

**문서화 강조**
- OpenAPI YAML을 코드와 함께 관리, /openapi.yaml endpoint 제공

### 배운 점
다음 깃이 해당 내용을 담고 있습니다.
https://github.com/raeperd/kickstart.go.git

최대한 적은 코드로 테스트가 용이하며, 문서와 로깅을 반드시 포함하는 프로젝트의 구조가 직관적이어서 좋았고
다음에 프로젝트를 시작한다면 kickstart.go를 꼭 적용해보고 싶네요.

## Go 서버 아키텍처 만들기, 근데 이제 리브랜딩을 곁들인
### 주된 내용
리브랜딩 배경
- 챌린저스가 습관 형성 서비스에서 사업 확장을 위해 뷰티 득템 앱으로 전환하기 위해 리브랜딩을 진행
- 기업 고객에게는 성과 보장, 개인 고객에게는 혜택 제공이라는 새로운 BM을 구축.

서버 전환 과정에서의 고민
- Go 선택: Python 기반 API에서 복잡한 API가 필요해졌는데 여기서 성능 이슈가 발생하여, 러닝커브와 성능 측면까지 고려하여 Go를 채택.
- 클린 아키텍처: 의존성 분리, 테스트 용이성, 확장성을 고려해 채택.
- 의존성 주입: Wire(컴파일 타임) vs Fx(런타임) 중 고민 끝에 Fx 선택.
  - Wire를 사용하는게 좀 더 Go 같지 않나라는 생각이 드네요
- HTTP 프레임워크: Chi(기존 파이썬 코드와의 호환성) → Gin (직관성과 커뮤니티 지원 때문).
- ORM: 유지보수성과 개발 속도를 위해 ORM 채택, 그 중에서 최종적으로 GORM 선택.

기타 도구:
- 문서화: swaggo
- 설정 관리: viper
- 로깅: zap

그 외 에러 처리/테스트는 여전히 과제로 남음.

Gopher들 사이의 논의 주제
- Don't Panic: 실무에서 panic & recovery 패턴으로 모든 에러를 해결했던 경험을 공유, 새 아키텍처에서는 꼭 필요할 때만 Panic을 제한적으로 사용.
- Named result parameter: 가독성 문제로 인해 프로젝트 컨벤션상 지양하기로 합의.
  ```go
  func ReadFull(r io.Reader, buf []byte) (n int, err error){
      for len(buf) > 0 && err == nil {
          var nr int
          nr, err = r.Read(buf)
          n += nr
          buf = buf[nr:]
      }
  }
  ```

향후 방향
- 검색 기능 고도화, 양방향 통신, 메시지 큐 기반 이벤트 처리 등을 통한 확장.

### 배운점
프로젝트는 비즈니스에 맞춰 설계할 수밖에 없고 또 코드를 보면 비즈니스가 어떻게 흘러갔는지를 알 수 있다는 걸 다시금 깨달았습니다.<br/>
의존성 주입, HTTP 프레임워크, ORM 선택 등 오픈소스 도입은 신중해야 하고 이는 곧 성능·개발속도·유지보수성·커뮤니티 지원 등 다양한 관점을 고려해야 하며, 기업의 성장 단계마다 최적의 선택이 달라질 수 있습니다.<br/>
실무에서 쓰인 코드가 내 생각에 안티 패턴일 경우 어떻게 접근해야 할까라는 생각이 드네요 <br/>
확실히 기업 사례 기반 발표가라서 몰입도를 높게 가져가며 볼 수 있었네요.