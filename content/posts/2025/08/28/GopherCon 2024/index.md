---
title: "GopherCon 2024 정리"
date: 2025-08-28T11:58:05+09:00
categories: [ "Conference", "Diary" ]
tags: [ "GopherCon", "Golang", "컨퍼런스" ]
draft: true
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

### 배운 점

## 차량 업데이트 파일의 안전한 관리
### 주된 내용

### 배운 점

## Golang 웹 프레임워크, Gin 모니터링 서비스 개발
### 주된 내용

### 배운 점