---
title: "RFC 7540 — HTTP/2 개요와 핵심 개념"
date: 2026-04-18T00:00:00+09:00
categories: [ "Memo", "Digging" ]
tags: [ "HTTP/2", "RFC 7540", "네트워크", "TLS", "HPACK" ]
draft: false
description: "HTTP/2의 바이너리 프레이밍, 스트림·멀티플렉싱, HPACK 등 RFC 7540 기준 핵심만 정리합니다."
keywords: [ "HTTP/2", "RFC 7540", "멀티플렉싱", "HPACK", "ALPN" ]
author: "DSeung001"
lastmod: 2026-04-18T00:00:00+09:00
---

### 서론

HTTP 1에서 HTTP/1.1 업데이트 하면서 HTTP Pipelining을 추가했지만 이는 요청 동시성 문제를 일부분만 해결했기에 문제가 남아있었다.

또한 head of line blocking 문제도 있었고 HTTP 헤더 필드는 중복도 있고 불필요한 데이터들도 많아서 불필요한 네트워크 트래픽이 발생할 뿐만 아니라 여러 문제를 야기했는데

TCP 혼잡 윈도우(Congestion Window)가 발생하여 새로운 TCP 요청에 과도한 지연이 발생한다

HTTP/2는 최적화 매핑을 통해 이 문제를 해결하는데 HTTP 의미론(HTTP Semantics)을  기본 연결에 적용하는 걸로, 동일한 트랜잭션 안에서 여러 요청과 응답을 번갈아 가며 전송할 수 있다 
연결을 생성하고 HTTP 해더 필드를 효율적으로 사용하고 또한 우선순위 지정을 허용하여 중요도가 높은 요청을 우선적으로 처리할 수 있다, 또 요청 처리 시간이 빨라져 성능이 더욱 향상된다.

결과적으로 생성된 프로토콜이 더 적은 수의 요소로 네트워크 친화적이고 TCP 연결를 1.1에 비해 더 오래 연결하 다른 흐름과 경쟁이 적다

### 핵심용어

- client:  HTTP/2 연결을 시작하는 엔드포인트. 클라이언트 HTTP 요청을 보내고 HTTP 응답을 받음
- connection:  두 엔드 포인트 간의 전송 계층 연결
- connection error:  HTTP/2 전체에 영향을 미치는 에러
- endpoint:  연결을 위한 서버 또는 클라이언트
- frame:  HTTP/2 내에서 가장 작은 통신 단위, 연결은 헤더와 가변 길이 시퀀스로 구성되고 frame type에 따라 구성되는 Octet(8bit)
- peer: 특정 end point를 의미할 때 사용하며 기본 주체와 원격에 있는 end point를 의미
- receiver: 프레임을 수신하는 end point
- sender: 프레임을 전송하는 end point
- server:  HTTP/2 연결을 수락하는 엔드포인트. 서버 HTTP 요청을 수신하고 HTTP 응답을 전송
- stream:  HTTP/2 연결 내에서 프레임이 양방향으로 흐르는 것을 의미
- stream error:  개별 HTTP/2 스트림에서 오류가 발생했습니다.
- gateway(reverse proxy): 요청을 처리하고 다른 서버로 수신되는 요청을 전달하는데, 레거시 시스템이나 신뢰할 수 없는 시스템을 캡슐화 하는 데 자주 사용
- intermediar: server와 clinet를 각각 다른 시간대에서 접속 되게 해줌
- tunnel: 방화벽이나 NAT 등을 제한된 네트워크 환경에서 HTTP/HTTPS 프로토콜을 사용하여 데이터를 캡슐화하고 외부 서버와 통신하는 기능
- payload body: HTTP 메시지 본문으로 전송되는 데이터가 있는 부분

### HTTP/2

HTTP/2인지를 구분하는 법은 TSL에서 h2 또는 h2c 문자열이 있는 지 보면 됨
이 식별자가 있을 시 업그레이드 요청으로  HTTP2로 업그레이드를 요청하는 HTTP/1.1 요청을 생성하는 데 이게 완료되면 이전 연결 사용이 차단 될 수도 있으므로 대규모 작업이 필요해질 수 있음

만약 서버가 HTTP2를 지원못하면 서버는 업그레이드 필드의 h2 토큰을 무시해야 함
토큰에 h2가 있다는 것은 TLS를 통한 HTTP/2를 의미하기 때문이고 다음 같은 응답을 보냄

```go
   HTTP/1.1 200 OK
     콘텐츠 길이: 243
     콘텐츠 유형: 텍스트/html
```