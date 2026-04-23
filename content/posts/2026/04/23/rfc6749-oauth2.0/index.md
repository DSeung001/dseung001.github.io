---
title: "RFC 6749 — The OAuth 2.0 Authorization Framework"
date: 2026-04-23T00:00:00+09:00
categories: [ "Memo", "Digging", "RFC" ]
tags: [ "RFC 6749", "OAuth 2.0", "인증", "Authorization" ]
draft: false
description: "RFC 6749 OAuth 2.0 권한 부여 프레임워크의 핵심 흐름과 역할, 토큰을 정리합니다."
keywords: [ "RFC 6749", "OAuth 2.0", "Authorization", "Access Token", "Refresh Token" ]
author: "DSeung001"
lastmod: 2026-04-23T00:00:00+09:00
---

# OAuth
OAuth 2.0은 **인증(Authentication)** 자체보다 **권한 부여(Authorization)** 를 위한 프레임워크입니다.
즉, 제3자 애플리케이션이 리소스 소유자의 비밀번호를 직접 받지 않고도, 제한된 범위(scope)의 접근 권한을 얻도록 설계되었습니다.

네이버/카카오/구글 로그인에서 자주 보이는 흐름도 이 개념을 기반으로 하지만, "로그인(신원 확인)" 자체는 보통 OpenID Connect(OIDC) 같은 상위 프로토콜이 함께 쓰입니다.
- **※OpenID Connect(OIDC)**: OAuth 2.0 프로토콜을 기반으로, 웹과 모바일 앱에서 표준화된 방식으로 사용자의 신원을 확인(인증)하는 현대적인 인증 레이어입니다.

OAuth가 널리 쓰이기 전에는 제3자 앱이 사용자 자격 증명을 직접 보관/전송하는 방식이 많았고, 이는 과도한 권한 부여와 자격 증명 유출 위험을 키웠습니다.
OAuth 2.0은 이 문제를 "비밀번호 공유 없이 위임"하는 모델로 바꿉니다.

RFC 6749는 OAuth 2.0을 표준화하며 OAuth 1.0(RFC 5849)을 대체했습니다. 이 둘이 실무에서 체감되는 차이를 요약하면 다음과 같습니다.
1. 클라이언트 유형(기밀/공개)과 시나리오별 grant를 분리해 웹/모바일/서버 간 적용이 쉬워졌습니다.
2. `scope` 기반으로 권한 범위를 더 명확하게 분리할 수 있습니다.
3. `access token`과 `refresh token`을 분리해 단기 토큰 + 재발급 모델을 운영하기 쉬워졌습니다.
4. 서명 중심의 OAuth 1.0 메시지 방식보다, TLS 기반 HTTPS 전송과 단순한 HTTP 파라미터 모델로 구현 복잡도를 낮췄습니다.

이 글은 OAuth 2.0 권한 부여 프레임워크에서 **권한 서버, 리소스 API, 클라이언트**가 어떻게 맞물리는지 파악하는 데 목적이 있습니다.

## Roles
- **Resource Owner**: 보호된 리소스에 대한 접근 권한을 부여할 수 있는 주체입니다. 리소스 소유자가 사람인 경우에는 end-user라고 부릅니다.
- **Resource Server**: 보호된 리소스를 호스팅하는 서버입니다. 액세스 토큰을 사용한 보호 리소스 요청을 수신하고 응답할 수 있어야 합니다.
- **Client**: 리소스 소유자를 대신하고 그 권한을 받아 보호 리소스를 요청하는 애플리케이션입니다.
- **Authorization Server**: 리소스 소유자를 인증하고 권한 부여를 확인한 뒤, 클라이언트에게 액세스 토큰을 발급하는 서버입니다.

## Flow
```mermaid
sequenceDiagram
    actor U as User
    participant C as Client
    participant AS as Authorization Server
    participant RS as Resource Server

    U->>C: (A) 로그인 시작 (예: 네이버로 로그인)
    C->>AS: (B) 인가 요청 (redirect)
    U->>AS: (C1) 로그인 + 동의
    AS-->>C: (C2) 인가 코드 반환
    C->>AS: (D) 인가 코드로 Access Token 교환
    AS-->>C: Access Token (필요 시 Refresh Token)
    C->>RS: (E) Access Token으로 보호 리소스 요청
    RS-->>C: (F) 보호 리소스 응답
    C-->>U: (G) 결과 화면/데이터 반환
```
- 서비스 구조에 따라 Resource Server와 Authorization Server를 같은 시스템으로 운영할 수도 있습니다.
- 여기서 <u>Client는 제가 만든 새로운 서비스(서드파티 앱)</u>로 이해하는 편이 편합니다.
- 네이버/카카오/구글 로그인 시스템은 보통 **Authorization Server** 역할입니다.

# Client Registration
`Client Registration`은 클라이언트를 보통 Authorization Server(구글/카카오/네이버)에 자신의 정보를 등록하는 단계를 의미합니다.
"누가 토큰을 발급받을 수 있는 앱인지"를 권한 서버가 식별할 수 있도록 사전에 맞추는 과정입니다.

이 작업은 최초 설정 후에도 redirect URI/권한 정책 변경 시 갱신합니다.
 
## Types
클라이언트 타입은 "Authorization Server와 안전하게 인증할 수 있는가(클라이언트 자격 증명 기밀성 유지 가능 여부)"를 기준으로 나뉩니다.

- **confidential**: 클라이언트 자격 증명(`client_secret` 등)을 안전하게 보관할 수 있고, 서버와 안전한 클라이언트 인증이 가능한 타입
- **public**: 자격 증명을 안전하게 보관하기 어려워, 비밀 기반 클라이언트 인증을 전제로 삼기 어려운 타입

아래는 실제 앱 형태를 기준으로 했습니다.
- **web application**: 일반적으로 **confidential**. 서버에서 실행되고 토큰/시크릿을 서버 측에 보관할 수 있음
- **user-agent-based application**: 일반적으로 **public**. 브라우저(사용자 에이전트 ex: js) 안에서 코드가 실행되어 프로토콜 데이터가 사용자에게 노출되기 쉽습니다
- **native application**: 일반적으로 **public**. 사용자 기기에서 실행되므로 앱에 포함된 정적 시크릿은 추출될 수 있다고 가정

추가로, 하나의 서비스가 여러 개의 서버 컴포넌트와 브라우저 컴포넌트로 나뉘는 분산 구조일 수도 있습니다.
이 경우 Authorization Server의 가이드가 없다면 컴포넌트별로 별도 클라이언트 등록을 고려하는 것이 안전합니다.

## Registration Data
`Client Registration`에서 자주 보는 항목을 "공통/조건부"로 나누면 아래와 같습니다.

| 항목 | 공통 여부 | 설명 |
| --- | --- | --- |
| (선택) `response_type` | 공통(정책) | 인가 요청에서 사용할 수 있도록 사전 허용하는 응답 타입 정책(예: `code`) |
| `client_id` | 공통(사실상 필수) | 권한 서버가 클라이언트를 식별하기 위한 ID |
| `redirect_uri` | 공통(인가 코드/implicit 계열에서 중요) | 인가 응답을 돌려보낼 콜백 주소. 등록값과 요청값의 정확 일치 검증이 핵심 |
| (선택) `grant_type` | 공통(정책) | 토큰 요청에서 사용할 수 있도록 사전 허용하는 권한 부여 방식(예: `authorization_code`, `client_credentials`, `refresh_token`) |
| (선택) `scope` | 공통(정책) | 토큰으로 요청 가능한 권한 범위의 상한선(allowlist). scope 체계는 Authorization Server/플랫폼 제공자가 정의 |
| `client_secret` | 조건부(기밀 클라이언트) | 클라이언트 비밀. 서버 측 보관/회전이 필요하며 public 클라이언트에는 부적합 |

※ 위 표는 "처음 앱을 등록할 때(Registration)" 기준입니다. 실제 인가 요청에서는 `response_type`이 요청 파라미터로 필수이며, 그 값이 등록된 허용 정책과 일치해야 합니다.
※ Authorization Server마다 등록 화면/설정 키는 다를 수 있으며, 핵심은 "허용 정책(allowlist)을 사전에 고정"한다는 점입니다.

 - **※grant(권한 부여 방식)**: 클라이언트가 액세스 토큰을 얻는 "경로/절차"를 말합니다. 예를 들어 `authorization_code`, `client_credentials`, `refresh_token` 등이 있고, 서비스 형태(웹/모바일/서버 간)에 따라 허용할 grant를 권한 서버에서 제한합니다.
   - `authorization_code`: 사용자 로그인/동의를 거쳐 받은 인가 코드를 토큰으로 교환하는 방식입니다. 웹 서버, SPA, 네이티브 앱에서(보통 PKCE와 함께) 가장 표준적으로 사용됩니다.
   - `client_credentials`: 사용자 없이 클라이언트 자신이 자신의 자격으로 토큰을 받는 방식입니다. 서버 간 통신(M2M)에서 주로 사용됩니다.
   - `refresh_token`: 이미 발급받은 리프레시 토큰으로 새 액세스 토큰을 재발급받는 방식입니다. 재로그인 없이 세션을 이어 가는 데 사용됩니다.
 - **※implicit 계열**: 브라우저 기반 클라이언트에서 토큰을 빠르게 받기 위해 과거에 쓰이던 흐름을 가리킵니다. URL 프래그먼트로 토큰이 노출될 수 있어 보안상 약점이 지적되어, 현재 실무에서는 보통 `authorization_code + PKCE`를 권장합니다.

아래 요청 예시는 `refresh_token` grant를 사용해 새 액세스 토큰을 재발급받는 경우입니다. <br/>
`grant_type=refresh_token`으로 흐름을 지정하고, `refresh_token` 값과 함께 `client_id`, `client_secret`이 전달됩니다.

```
  POST /token HTTP/1.1
     Host: server.example.com
     Content-Type: application/x-www-form-urlencoded

     grant_type=refresh_token&refresh_token=tGzv3JOkF0XG5Qx2TlKWIA
     &client_id=s6BhdRkqt3&client_secret=7Fjfp0ZBr1KtDRbnfVdmIw
```

## Client Authentication
클라이언트 인증은 기본적으로 **confidential client**에서 사용합니다.

| 방식 | 주 대상 | 어떻게 인증하나 | 특징 |
| --- | --- | --- | --- |
| `client_secret_basic` | confidential | `Authorization: Basic base64(client_id:client_secret)` | 가장 보편적. 구현이 단순 |
| `client_secret_post` | confidential | 토큰 요청 body에 `client_id`, `client_secret` 포함 | 지원은 넓지만, 본문에 시크릿이 들어가므로 로그/추적 노출에 주의 |
| `private_key_jwt` | confidential | 클라이언트가 개인키로 서명한 JWT로 인증 | 시크릿 공유보다 강한 인증. 키 관리/회전 필요 |
| `mTLS` | confidential | TLS 핸드셰이크에서 클라이언트 인증서로 인증 | 강한 상호 인증. 인증서 운영 난이도 높음 |
| `public` + PKCE | public | 클라이언트 인증 대신 code verifier/challenge로 코드 탈취 위험 완화 | SPA/네이티브에서 사실상 표준 패턴 |

- public client는 시크릿 기반 인증을 전제로 삼기 어렵기 때문에, 보통 `authorization_code + PKCE`로 인가 코드 탈취 위험을 완화합니다.
- **※PKCE(Proof Key for Code Exchange)**: OAuth 2.0 및 OpenID Connect 프로토콜에서 인가 코드(Authorization Code) 탈취 공격을 방지하기 위해 설계된 보안 기술입니다.

# Protocol Endpoints
OAuth 2.0 권한 부여 흐름에서는 보통 **Authorization Server 엔드포인트 2개**와 **Client 측 Redirection endpoint 1개**가 핵심입니다.

- **Authorization endpoint**: 사용자(리소스 소유자)를 로그인/동의 화면으로 보내고, 권한 부여 결과(예: authorization code)를 발급하는 엔드포인트
- **Token endpoint**: 클라이언트가 authorization code(또는 refresh token 등)를 제출해 access token으로 교환하는 엔드포인트
- **Redirection endpoint(클라이언트 콜백)**: Authorization Server가 사용자 에이전트(브라우저)를 통해 결과를 되돌려 보내는 클라이언트의 수신 주소 (`redirect_uri`)

- **※용어 정리**: 여기서 핵심은 "인증(authentication)" 자체보다 "권한 부여(authorization)"의 과정입니다. 다만 실제 로그인(신원 확인)은 Authorization Server에서 함께 처리됩니다.

# Obtaining Authorization
"권한을 어떻게 얻을 것인가"를 정의합니다. <br/>
실무에서는 보통 **Authorization Code Grant** 를 기준으로 읽으면 흐름이 가장 명확합니다.

## Authorization Code Grant
1. 클라이언트가 사용자를 Authorization Endpoint로 리디렉션합니다.  
2. 사용자가 로그인/동의를 마치면 Authorization Server가 `code`를 `redirect_uri`로 반환합니다.  
3. 클라이언트는 `code`를 Token Endpoint에 보내 `access_token`(및 선택적으로 `refresh_token`)으로 교환합니다.

```mermaid
sequenceDiagram
    actor User
    participant Client
    participant AuthorizationServer
    participant ResourceServer

    User->>Client: 로그인 시작
    Client->>AuthorizationServer: Authorization Request (response_type=code, client_id, redirect_uri, scope, state)
    User->>AuthorizationServer: 로그인 + 동의
    AuthorizationServer-->>Client: Authorization Response (code, state)
    Client->>AuthorizationServer: Token Request (grant_type=authorization_code, code, redirect_uri)
    AuthorizationServer-->>Client: access_token (+ refresh_token)
    Client->>ResourceServer: Authorization: Bearer access_token
    ResourceServer-->>Client: Protected Resource
```

위 흐름을 진행하면 Access Token 또는 Refresh Token을 통해 권한을 얻을 수 있게 됩니다.

## Access Token
Access Token 발급 성공/실패 응답을 정리합니다.
### Token 발급 요청 예시 (authorization_code)
```http
POST /token HTTP/1.1
Host: server.example.com
Content-Type: application/x-www-form-urlencoded
Authorization: Basic czZCaGRSa3F0MzpnWDFmQmF0M2JW

grant_type=authorization_code&code=SplxlOBeZQQYbYS6WxSbIA&redirect_uri=https%3A%2F%2Fclient.example.com%2Fcb
```

### 성공 응답 예시
```json
{
  "access_token": "2YotnFZFEjr1zCsicMWpAA",
  "token_type": "Bearer",
  "expires_in": 3600,
  "refresh_token": "tGzv3JOkF0XG5Qx2TlKWIA",
  "scope": "read write"
}
```

- `token_type`: 보통 `Bearer`
- `expires_in`: 액세스 토큰 만료(초)
- `scope`: 실제 발급된 권한 범위(요청값과 다를 수 있음)
- **※Bearer**: 토큰 소지자에게 접근 권한을 부여하는 방식입니다. 즉, 유효한 토큰 문자열을 가진 주체가 별도 서명 없이 `Authorization: Bearer <token>`으로 리소스 접근 권한을 행사합니다. 그래서 HTTPS 전송, 짧은 만료 시간, 안전한 저장이 중요합니다.

API 호출 시에는 보통 아래처럼 사용합니다.
```http
GET /resource HTTP/1.1
Host: api.example.com
Authorization: Bearer 2YotnFZFEjr1zCsicMWpAA
```

### 실패 응답
`error`/`error_description`/`error_uri` 필드 형태로 전달됩니다.

```json
{
  "error": "invalid_grant",
  "error_description": "Authorization code expired"
}
```

자주 보는 실패 코드는 아래와 같습니다.
- `invalid_request`: 필수 파라미터 누락, 중복, 형식 오류
- `invalid_client`: 클라이언트 인증 실패(`client_secret` 불일치 등)
- `invalid_grant`: 인가 코드/리프레시 토큰이 만료, 폐기, 잘못됨, 또는 `redirect_uri` 불일치
- `unauthorized_client`: 해당 클라이언트에 허용되지 않은 grant 사용
- `unsupported_grant_type`: 서버가 지원하지 않는 `grant_type`
- `invalid_scope`: 요청한 scope가 허용 범위를 벗어남

## Refresh Token
리프레시 토큰으로 새 액세스 토큰을 재발급받는 방법을 정리합니다.

### Refresh 요청 예시
```http
POST /token HTTP/1.1
Host: server.example.com
Content-Type: application/x-www-form-urlencoded
Authorization: Basic czZCaGRSa3F0MzpnWDFmQmF0M2JW

grant_type=refresh_token&refresh_token=tGzv3JOkF0XG5Qx2TlKWIA
```

다음 상황에 사용합니다.
- 기존 `access_token`이 만료되었을 때
- 사용자 재로그인 없이 세션을 이어가고 싶을 때

### 운영 포인트
- 리프레시 토큰은 액세스 토큰보다 민감하므로 서버 측 안전 저장이 중요합니다.
- Authorization Server 정책에 따라 새 리프레시 토큰을 재발급(회전)할 수 있습니다.
- 탈취/의심 상황에서는 리프레시 토큰을 폐기하고 재인증을 요구해야 합니다.

# Security Considerations
실무에서 먼저 점검할 체크리스트를 위험 목록과 그에 대한 대응으로 정리하면 아래와 같습니다.

- **Redirect URI 변조/오용**:  등록된 `redirect_uri`와 요청값을 정확 일치로 검증
- **CSRF/응답 주입**: 인가 요청마다 `state`를 생성하고, 콜백의 `state`와 반드시 일치 검증
- **Public Client 코드 탈취**: SPA/네이티브는 `authorization_code + PKCE`를 기본으로 사용
- **토큰 노출/오남용**: `Access Token`/`Refresh Token`에 HTTPS 전송, 안전 저장, 짧은 만료, 최소 scope 원칙 적용
- **리프레시 토큰 장기 탈취**: 회전(rotation), 재사용 탐지, 의심 시 폐기(revocation) 운영
- **클라이언트 인증 약함**: confidential client는 `client_secret_basic` 또는 필요 시 `private_key_jwt`/`mTLS` 적용

OAUTH와 같이 언급되는 JWT는 클라이언트 인증(`private_key_jwt`) 외에도 액세스 토큰 형식, ID 토큰, `client_assertion` 등 여러 위치에서 사용될 수 있습니다.<br/>
다만 OAuth 2.0에서 JWT 사용 방식은 구현/확장 선택 사항입니다.