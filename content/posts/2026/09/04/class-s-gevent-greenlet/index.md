---
title: "새벽에 발생한 에러 고치기 (Class Project)"
date: 2026-09-04T14:00:00+09:00
categories: [ "Project", "Class Project" ]
series: [ "class-s-project" ]
tags: [ "gunicorn", "gevent", "greenlet", "SSE", "PostgreSQL", "sitemap" ]
draft: false
description: "원인은 Postgres too many clients였고 이게 발생하게 된 이유를 추적해보자."
keywords: [ "gunicorn", "gevent", "greenlet", "SSE", "sitemap", "too many clients", "CONN_MAX_AGE", "PostgreSQL" ]
author: "DSeung001"
lastmod: 2026-09-04T15:35:00+09:00
---

## 문제

갑자기 운영중이던 서버에서 여러개의 메일이 발송되어서 놀랐던 적이 있습니다.<br/>
잘 운영되다가 갑자기 새벽시간에 이렇게 서버에서 에러가 발생한다는게 신기했기에, 최근에 SEO를 손봐서 봇이 접근한걸까라는 의문이 들기도 했죠.
![오전 4시 38분에 Class S ERROR 알림 메일이 한꺼번에 도착한 화면](./email.webp)

아래는 내용의 일부입니다, `too many clients alread`로 pg에서 허용된 connection 보다 더 많은 개수가 부여된걸 알 수 있는데 여기서 의문이 들었죠, 내 서비스는 지금 일일 사용자가 10명도 안되는데?
```text
timestamp: 2026-09-04T04:39:00.499+09:00
logger: django.request
level: ERROR
message: Internal Server Error: /api/v1/media/courses/121
FATAL: sorry, too many clients already
```

## 분석

다시 위 문구를 보면 `too many clients already`는 Postgres가 `max_connections` 한도로 새 커넥션을 거부한거죠.
같은 시각 `logs/access.log`에는 0.3초 안에 GET이 26개 들어왔고, 그중 `courses/121`이 `56362ms`(약 56.36초) 기다리다 500을 낸걸 확인해볼 수 있었습니다. 성공과 실패 모두 IP가 `172.18.0.4`이고 `user_id`는 없었죠.

로컬 `runserver`에서는 같은 Django 코드가 멀쩡했습니다. 깨진 쪽은 배포 서버이므로 메모리 누수나/커넥션 풀/동시성 모델 이슈로 추측이 되었죠.

### 서버 변경

배포 API는 gunicorn이고, WSGI 서버입니다. 
WSGI는 Python 웹 앱과 웹 서버가 요청을 주고받는 표준 인터페이스이고, 
Class S에서는 `config.wsgi:application`을 워커 프로세스로 띄웁니다.

이전에는 `--worker-class`를 생략해서 gunicorn 기본 값인 `sync`로 워커 하나가 요청 하나를 끝날 때까지 붙잡고, 워커 3개면 동시 요청도 3개인 방식으로 진행되었습ㅂ니다.

```bash
gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3 --timeout 120
```

하지만 이후에 [SSE 알림](/posts/2026/07/24/class-s-sse-notification/)이 생기면서 긴 Redis 대기 연결과 기존 API가 한 서버에 같이 들어왔습니다. 즉 네트워크 비용이 증가해서 `gevent`로 바꿨을 때 이득이 커졌다고 판단되었죠.
`gunicorn`에서는 `gevent`을 쓸 수 있는 옵션을 제공해서 이를 적용했습니다.

```bash
gunicorn config.wsgi:application --bind 0.0.0.0:8000 \
  --worker-class gevent \
  --workers 2 \
  --timeout 120
```

이 명령에는 `--worker-connections`가 없습니다. gunicorn 26 기본이 워커당 1000이라, 워커 2개면 이론상 2000개 요청을 동시에 붙잡을 수 있고 Django가 연 Postgres 소켓도 그만큼 늘어날 수 있습니다.
하지만 에러가 발생했을 당시 Postgres `max_connections`는 100개로 설정되어있습니다.

아래처럼 서버가 변경되면서 해당 문제가 발생하게 될 원인을 제공하게되었죠.

| 구분 | 기동 | 동시 요청 | Postgres 슬롯 |
|---|---|---|---|
| 이전 | gunicorn `sync`, 워커 3 | 3 | 이미지 기본 약 100 |
| 이후, 핫픽스 전 | gunicorn `gevent`, 워커 2, connections 미지정 | gunicorn 기본 워커당 1000, 이론상 2000 | 이미지 기본 약 100 |

### gunicorn, gevent, greenlet

다음 3개는 묶어서 보는 게 편합니다. 에러 원인을 이해하려면 이 계층만 알면 됩니다.

- gunicorn은 Django 앱을 워커 프로세스로 띄우는 WSGI 서버입니다. `--workers 2`면 OS 프로세스가 2개입니다.
- gevent는 greenlet 위에 네트워크 I/O, 이벤트 루프 등을 구현해놓은 더 높은 수준의 라이브러리로 동시성 처리가 아닌 네트워크 스위칭을 빠르게 지원해줍니다
- greenlet은 그때 요청 하나가 쓰는 실행 흐름입니다. 스레드가 아니라, Python이 같은 OS 스레드를 나눠 쓰는 경량 단위입니다.

```
Gunicorn Master
│
├─ Worker Process
│   └─ Thread
│       ├─ Greenlet
│       ├─ Greenlet
│       └─ Greenlet
│
└─ Worker Process
    └─ Thread
        ├─ Greenlet
        ├─ Greenlet
        └─ Greenlet
```

### 문제 원인 분석