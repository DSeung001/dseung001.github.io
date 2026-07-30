# Go Channel Runtime Tracer

> 커스텀 Go 런타임 기반 채널 관측 도구 기획서

- **문서 목적:** 핵심 구현 범위 정의
- **기준일:** 2026-07-30
- **기준 태그:** `go1.26.5` (시스템 툴체인과 동일)
- **초기 범위:** 기존 채널 동작을 유지한 관측 기능 추가

## 1. 프로젝트 목표

- 애플리케이션 코드를 수정하지 않고 `make(chan)`, send, receive, close 동작을 런타임에서 자동 추적한다.
- 채널 병목과 goroutine 대기 관계를 수치와 그래프로 설명한다.
- 공식 Go 대비 추적 오버헤드를 벤치마크로 정량화한다.

## 2. 핵심 정의

공식 Go 저장소를 포크해 기존 channel 동작은 유지하고, runtime 내부에 추적·분석 기능을 추가한다.

완성된 커스텀 Go 툴체인은 시스템 Go와 분리하고, 각 명령에서 커스텀 `go` 실행 파일을 명시해 사용한다.

## 3. 전체 진행 흐름

1. 공식 Go 저장소 포크
2. 별도 경로에 커스텀 Go 툴체인 빌드
3. `runtime/chan.go` 중심으로 채널 추적 기능 구현
4. 수집한 데이터로 관계 그래프와 wait graph 생성
5. 공식 Go와 커스텀 Go의 성능 비교

공식 저장소: <https://github.com/golang/go>

## 4. 핵심 구현 범위

| No. | 기능 | 핵심 의미 |
|---:|---|---|
| 1 | 모든 channel에 ID 부여 | 채널 생성 시 고유 ID를 생성해 이후 이벤트를 동일 채널로 연결한다. |
| 2 | send / recv / close 이벤트 수집 | 어떤 goroutine이 어느 채널에 어떤 동작을 수행했는지 기록한다. |
| 3 | blocking time 측정 | send·receive 대기의 시작·종료 시각을 기록해 병목 시간을 계산한다. |
| 4 | 채널 buffer 사용률 측정 | `qcount / dataqsiz`를 바탕으로 현재·평균·최대 점유율을 계산한다. |
| 5 | goroutine-channel 관계 그래프 | `sender → channel → receiver` 통신 구조를 그래프로 표현한다. |
| 6 | deadlock wait graph 출력 | deadlock 시 goroutine이 어떤 채널 작업을 기다리는지 연결해 원인을 설명한다. |
| 7 | 공식 Go와 benchmark 비교 | 추적 비활성·전체 추적·샘플링 모드의 시간 및 메모리 오버헤드를 비교한다. |

## 5. 런타임 수정 지점

| 파일 / 함수 | 역할 | 추가할 정보 |
|---|---|---|
| `runtime/chan.go` / `makechan` | 채널 생성 | channel ID, capacity, 생성 시각 |
| `runtime/chan.go` / `chansend` | 전송 처리 | sender goroutine, block 시간, buffer 상태 |
| `runtime/chan.go` / `chanrecv` | 수신 처리 | receiver goroutine, block 시간, buffer 상태 |
| `runtime/chan.go` / `closechan` | 채널 종료 | close 이벤트, 대기 goroutine 상태 |
| `runtime/proc.go` / `checkdead` | deadlock 감지 | wait graph 요약 출력 |

## 6. 로컬 실행 및 영역 분리 원칙

- 공식 Go와 커스텀 Go를 서로 다른 디렉터리에 둔다.
- 커스텀 Go의 `bin` 경로를 전역 `PATH`에 추가하지 않는다.
- 전역 `GOROOT`를 변경하지 않는다.
- 필요하면 `GOCACHE`, `GOPATH`, `GOMODCACHE`도 별도 경로로 분리한다.
- 커스텀 빌드에서는 `GOTOOLCHAIN=local`을 사용해 공식 툴체인으로 자동 전환되는 것을 방지한다.
- 명령마다 커스텀 `go.exe` 경로를 명시해 실행한다.

### 실행 예시 (macOS)

검증 샘플 모듈은 `/Users/jiseunglyeol/code/chan-tracer-test`다. 단계별 가이드의 샘플은 이 모듈의 `main.go`에 두고, 커스텀 `go`로 실행한다.

`/Users/jiseunglyeol/code/go/bin/go`는 소스만 clone한 상태에서는 없다. 런타임 수정 후(또는 최초 1회) 반드시 툴체인을 빌드한다.

```bash
# 0) 커스텀 툴체인 빌드 → ../bin/go 생성
cd /Users/jiseunglyeol/code/go/src
./make.bash
# 확인: /Users/jiseunglyeol/code/go/bin/go version

# 1) 시스템 Go (비교용, go1.26.5)
go version

# 2) 커스텀 Go로 샘플 실행 (PATH에 커스텀 bin을 넣지 않음)
cd /Users/jiseunglyeol/code/chan-tracer-test
export GOTOOLCHAIN=local
GOCHANTRACE=on /Users/jiseunglyeol/code/go/bin/go run .
```

## 7. 데이터 처리 구조

```text
애플리케이션 코드
    → 커스텀 Go 빌드
    → runtime 이벤트 수집
    → 이벤트 저장·집계
    → 관계 그래프·wait graph·리포트
```

런타임의 hot path에서는 JSON 직렬화, 파일 I/O, channel 재사용 같은 무거운 처리를 수행하지 않는다.

고정 크기 이벤트 구조체와 사전 할당 ring buffer를 사용하고, 별도 collector가 분석 데이터를 배출하는 구조를 기본으로 한다.

## 8. 단계별 산출물

| 단계 | 목표 | 완료 기준 |
|---|---|---|
| M1 | 포크·빌드 환경 | 안정 버전 태그 기반 커스텀 Go 빌드 및 샘플 프로그램 실행 |
| M2 | 기본 이벤트 추적 | channel ID와 create/send/recv/close 로그 출력 |
| M3 | 성능 지표 | blocking time과 buffer 점유율 집계 |
| M4 | 관계 분석 | goroutine-channel graph와 deadlock wait graph 생성 |
| M5 | 검증·문서화 | 공식 Go 비교 벤치마크, 실행 스크립트, README 작성 |

## 9. 완료 기준

- 일반 Go 애플리케이션 코드를 수정하지 않고 채널 추적이 가능하다.
- 채널 병목과 goroutine 대기 관계를 재현 가능한 형태로 출력한다.
- 공식 Go 대비 실행 시간과 메모리 오버헤드를 수치로 제공한다.
- 시스템 Go와 커스텀 Go를 명확하게 분리해 실행한다.

## 10. 초기 비범위

- 채널 스케줄링 정책 또는 채널 알고리즘 자체 교체
- 운영 서비스에 즉시 적용할 수준의 안정성 보장
- 모든 `select` 및 timer channel 특수 사례의 1차 완전 지원
