---
title: "Operating Systems: Three Easy Pieces - Event-based Concurrency"
date: 2026-05-08T00:00:00+09:00
categories: [ "OSTEP" ]
tags: [ "OSTEP", "Operating Systems", "Concurrency", "Event-based Concurrency", "select", "poll", "Async I/O", "State Machine" ]
draft: false
description: "OSTEP Concurrency 33강 Event-based Concurrency 정리"
keywords: [ "OSTEP", "Event-based Concurrency", "select", "poll", "Async I/O", "State Machine", "Non-blocking I/O", "Web Server" ]
author: "DSeung001"
lastmod: 2026-05-08T00:00:00+09:00
---

지금까지 동시성 프로그램을 스레드 기반 동시성만으로 구축하는 것이 유일한 방법인 것처럼 작성해왔습니다.
이는 당연히 전혀 사실과는 거리가 멀고, 여러 다른 스타일의 동시 프로그래밍이 있습니다.

이 스타일은 이벤트 기반 동시성으로 알려져 있으며 `node.js`와 같은 서버 측 프레임워크를 포함한 현대 시스템에서 인기를 얻고 있습니다. 그 뿌리는 아래에서 논의할 `C/UNIX` 시스템에 있습니다.
- `node.js`는 단일 스레드임에도 이벤트 루프와 비동기 I/O를 통해 `non-blocking I/O` 모델로 동작
- `C/UNIX` 시스템은 1969년 미국 벨 연구소(Bell Labs)에서 개발된 UNIX 운영체제와, 이 운영체제를 작성하는 데 사용된 C 언어의 긴밀한 관계를 기반으로 하는 서버 및 워크스테이션용 운영체제 환경

이벤트 기반 동시성이 해결하는 문제는 두 가지입니다.
1. 다중 스레드 애플리케이션에서 동시성을 올바르게 관리하는 데 어려움을 해소
    - 교착 상태 등 문제에 대한 부분에 신경을 덜 써도 됨
2. 다중 스레드 애플리케이션에서 개발자가 특정 시점에 무엇이 실행될지에 대한 대부분의 부분을 제어할 수 없음
    - OS가 합리적으로 CPU를 걸쳐 스케줄링해 주기를 희망하게 됨
    - 모든 부하 조건에서 잘 작동하는 범용 스케줄러 구축의 어려움

# The Basic Idea: An Event Loop
이번에 다룰 접근 방식은 위에서 언급한 대로 이벤트 기반 동시성입니다.
이 개념은 간단히 이해할 수 있습니다. 그저 무언가(event)가 발생하기를 기다리고, 이벤트가 발생하면 그것이 무엇인지 확인한 뒤 필요한 작업을 수행합니다.

전형적인 이벤트 기반 서버는 다음 코드처럼 간단히 돌아갑니다.
```
while (1) {
    events = getEvents();
    for (e in events)
        processEvent(e);
}
```
정말로 간단해서, 메인 루프를 통해 이벤트를 기다리고 이벤트가 발생하면 하나씩 처리합니다. 중요한 점은 핸들러가 이벤트를 처리할 때 시스템에서 발생하는 유일한 활동이라는 것입니다.
따라서 다음에 어떤 이벤트를 처리할지 결정하는 것은 스케줄링과 같습니다.
스케줄링에 대한 이러한 명시적 제어는 이벤트 기반 접근 방식의 가장 기본적인 장점입니다.

하지만 여기서는 이벤트를 어떻게 정확히 감지하는지, 특히 네트워크 및 디스크 I/O와 관련해 이벤트 서버가 메시지가 도착했는지(혹은 I/O가 완료됐는지) 어떻게 알 수 있는지에 대한 의문이 남습니다.

# An Important API: select() (or poll())
위에서 보여준 기본적인 이벤트 루프를 염두에 두고, 우리는 이벤트를 어떻게 수신할지에 대한 질문을 가지게 됩니다. 대부분의 시스템에서는 `select()`, `poll()` 같은 호출을 기본 API로 사용할 수 있습니다.
- `select()/poll()` 자체는 OS가 제공하는 I/O 다중화 API이고, 이를 바인딩/래핑한 형태로 파이썬/노드 같은 언어에도 존재합니다.

네트워크 애플리케이션(웹 서버)에 도착한 네트워크 패킷이 있는지 확인하는 작업을 처리한다고 상상해 볼 때, 이 시스템 호출은 정확히 그 작업을 수행할 수 있게 해줍니다.
`select()`를 살펴보면 macOS에서는 다음 매뉴얼로 API를 설명하고 있으니 참고하시면 좋을 것 같습니다. ([mac developer - select](
https://developer.apple.com/library/archive/documentation/System/Conceptual/ManPages_iPhoneOS/man2/select.2.html#//apple_ref/doc/man/2/select))


```c
int select(int nfds,
            fd_set *restrict readfds,
            fd_set *restrict writefds,
            fd_set *restrict errorfds,
            struct timeval *restrict timeout);
```
여기서 먼저 짚어야 하는 개념이 `blocking`(동기)과 `non-blocking`(비동기)입니다.
`blocking`은 호출이 끝날 때까지 필요한 일을 모두 마치고 결과를 반환하고, `non-blocking`은 호출은 바로 반환하지만 실제 작업은 시간이 걸립니다.

`blocking`을 유발하는 대표적인 원인은 I/O입니다. 예를 들어 어떤 함수가 디스크에서 데이터를 읽어야만 완료될 수 있다면, 디스크 I/O 요청이 끝날 때까지 호출자는 대기하게 됩니다.
`non-blocking` 인터페이스는 스레드 기반 프로그램에서도 활용할 수 있지만, 이벤트 기반 접근에서는 특히 중요합니다. 이벤트 루프 안에서 어떤 호출이든 막히는 순간 전체 진행이 멈추기 때문입니다.

`select()`는 이런 이벤트 기반 서버가 지금 처리할 일이 있는지 확인하는 대표적인 방법입니다. 
인자 값인 `readfds`/`writefds`/`errorfds`에 관심 있는 파일 디스크립터 집합을 넘기면, 0부터 `nfds-1`까지 디스크립터를 검사한 뒤 준비된 디스크립터만 남기도록 집합을 갱신하고, 준비된 디스크립터의(처리가 가능한) 총 개수를 반환합니다.
- 파일 디스크립터(file descriptor, FD): OS가 열린 파일/소켓/파이프 같은 I/O 대상을 구분할 수 있도록 프로세스에 부여하는 정수 번호입니다.

`select()` 또 두 가지 특징을 지닙니다. 
1. 읽기 가능 여부와 쓰기 가능 여부를 구분해서 확인할 수 있다는 점입니다. 읽기 가능은 해당 디스크립터에서 읽을 데이터가 준비된 상태이고, 쓰기 가능은 응답을 보내도 막히지 않을 상태(예: 송신 버퍼가 가득 차 있지 않은 상태)입니다.
2. `timeout`입니다. `timeout`을 `NULL`로 두면 준비된 디스크립터가 생길 때까지 무기한 대기할 수 있고, 반대로 0으로 두면 즉시 반환하게 만들어 지금 당장 준비된 일이 있는지만 확인하는 식으로 사용할 수 있습니다.

`poll()`도 비슷한 용도의 시스템 콜입니다, 상태가 변경되었는 지를 확인하는 방법입니다.
결국 이런 기본 프리미티브(primitives)를 이용하면, 들어오는 패킷을 확인하고 준비된 소켓에서 읽고 필요하면 응답하는 형태의 이벤트 루프를 구성할 수 있습니다.

# Using select()
이를 더 구체적으로 만들기 위해 `select()`를 사용해 어떤 네트워크 디스크립터에 메시지가 도착했는지 확인하는 방법을 살펴보겠습니다.
```python
import selectors
import socket

# OS에 맞는 I/O 다중화 방식(select/poll/epoll/kqueue 등)을 선택
sel = selectors.DefaultSelector()

# 접속(accept) 핸들러
def accept_handler(sock, mask):
    conn, addr = sock.accept()
    print(f"accepted: {addr}")
    conn.setblocking(False)
    # 읽기 이벤트가 준비되면 read_handler 실행
    sel.register(conn, selectors.EVENT_READ, read_handler)

# 읽기 핸들러
def read_handler(conn, mask):
    try:
        data = conn.recv(4096)  # 4KB
        if data:
            print(f"[{conn.fileno()}] received: {data.decode().strip()}")
        else:
            raise Exception("Disconnected")
    except Exception:
        print(f"[{conn.fileno()}] disconnected")
        sel.unregister(conn)
        conn.close()

server = socket.socket()
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind(('127.0.0.1', 8080))
server.listen()
server.setblocking(False)

# server 소켓은 새 연결(accept) 가능 여부만 감시
sel.register(server, selectors.EVENT_READ, accept_handler)
print("event loop start")

while True:
    events = sel.select()  # 이벤트가 준비될 때까지 대기
    for key, mask in events:
        callback = key.data  # 등록한 핸들러 함수
        callback(key.fileobj, mask)  # 함수 실행
```
위 코드에서 `selector`의 핵심 역할은 여러 소켓을 대상으로 I/O 준비 상태를 확인하는 일을 OS의 I/O 다중화 API 위에서 추상화해 주는 것입니다.
`register`에서 `sel.register(fileobj, events, data)` 형태로 인자를 넘기는데 의미는 다음과 같습니다.
- fileobj(감시할 객체): 감시할 대상입니다. 소켓 객체를 넘기면 내부적으로 해당 소켓의 시스템 FD(File Descriptor)를 사용합니다.
- events(감시할 이벤트): `fileobj`에서 어떤 준비 상태를 볼지 결정합니다.
    - selectors.EVENT_READ: 읽기 가능(데이터 도착, 혹은 server 소켓이면 accept 가능)
    - selectors.EVENT_WRITE: 쓰기 가능(보내도 막히지 않을 가능성이 큼)
- data(부가 데이터): 보통 콜백(핸들러) 함수를 넣어두고, 이벤트가 준비되면 그 함수를 호출하는 데 사용합니다.

이 코드를 실행하고 소켓 클라이언트 역할을 하기 위해선 `mac` 기준으로 별도의 cmd를 띄우고 다음처럼 명령어를 보내면 됩니다.
```bash
nc localhost 8080
Hello selector
```
그러면 server는 다음과 같이 출력을 보여주며 정상 작동하는 것을 보여주죠
```bash
accepted: ('127.0.0.1', 61965)
[5] received: Hello selector
```

# Why Simpler? No Locks Needed
단일 CPU에서 단일 스레드 이벤트 루프 기반으로 동작하는 이벤트 기반 애플리케이션은 동시 프로그램에서 흔히 발견되는 문제를 크게 줄일 수 있습니다.

구체적으로는 한 번에 하나의 이벤트만 처리하기 때문에 `lock`을 획득하거나 해제할 필요가 없습니다. 
이벤트 기반 서버는 명백히 단일 스레드이기 때문에 다른 스레드에 의해 중단될 수 없습니다. 따라서 일반적으로 발생하는 동시성 버그는 기본 이벤트 기반 접근 방식에는 나타나지 않습니다.

각종 프레임워크나 엔진에 이 방식이 적용된 걸 확인할 수 있죠.
| 언어 | 프레임워크/엔진 | 핵심 특징 |
| --- | --- | --- |
| JavaScript | Node.js | 싱글 스레드 루프의 정석, 거대한 생태계 |
| Python | asyncio | 표준 라이브러리, 높은 생산성 |
| Java | Netty | 엔터프라이즈급 성능, 저수준 제어 최강 |
| Rust | Tokio | 고성능, 메모리 안전성, 멀티 스레드 루프 |
| Go | Runtime Scheduler | CSP 모델, 동기식 코드로 비동기 효과 |
Golang은 `CSP(Communicating Sequential Processes)` 모델을 따르며, 형식은 동기식 코드지만 내부적으로 고루틴을 스케줄링해 처리합니다. 그래서 Go에서는 타 언어들과 달리 `lock`을 신경 쓰지 않고 데이터 통신을 더 자유롭게 할 수 있었습니다.
이 부분이 Golang에서 동시성 코드를 다룰 때 가장 편했던 점 중 하나였던 것 같습니다.

# A Problem: Blocking System Calls
지금까지 이야기한 바에 따르면 이벤트 기반 프로그래밍이 더 나은 방안처럼 들립니다. 하지만 간단한 루프를 만들고 동작을 다 이벤트로 처리하면 `lock`을 신경 쓸 필요가 없어지니 말이죠.

하지만 이벤트가 블로킹될 수 있는 시스템 호출을 요구하면 이야기는 달라집니다. 예를 들어 클라이언트로부터 서버에 디스크에서 파일을 읽고 내용을 반환해 달라는 요청이 들어왔다고 해봅시다.
이러한 요청을 처리하기 위해 파일을 열기 위한 `open()` 시스템 호출을 하고, 그다음 파일을 읽기 위해 `read()` 시스템 호출도 이어서 수행해야겠죠. 그렇게 메모리에 파일 데이터가 저장되고, 이 결과를 클라이언트에게 전송할 겁니다.

위 작업을 위해 `open()`, `read()` 같은 호출이 일어나고, 필요한 데이터가 메모리에 없으면 디스크 I/O 요청까지 발생합니다. 이 일련의 동작은 시간이 오래 걸릴 수 있습니다.
스레드 기반 서버에서는 한 스레드가 기다리는 동안 다른 스레드가 일을 할 수 있으니 문제가 덜하지만, 이벤트 방식에서는 오직 메인 이벤트 루프만 존재하기에 전체 서버가 블로킹될 수 있습니다.
호출이 완료될 때까지 블로킹되는데, 이는 서버 자원 측면에서 큰 손해입니다.
따라서 이벤트 기반 시스템에서는 블로킹 호출을 허용하지 않습니다.

이 절까지 본 후 가장 큰 의문점은 블로킹 호출을 지원하지 않으면 타 솔루션과의 통신을 어떻게 다룰지가 궁금했습니다.
이에 대한 내용도 곧 다루지만 간단히 정리하면 다음과 같죠.
- Non-blocking I/O: 가장 이상적인 방법으로, 소켓에 데이터를 보내 달라는 요청만 하고 즉시 제어권을 이벤트 루프에 반환합니다. 그리고 이벤트가 도착했을 때 OS가 이벤트를 발생시키고 콜백이 실행됩니다.
- Thread/Process Pool: 외부 솔루션의 드라이버가 블로킹 방식만 지원한다면, 별도의 스레드/프로세스 풀에 작업을 던집니다. 이런 작업만 실행하는 풀을 따로 두는 방식이죠.
- Message Queue를 이용한 비동기 통신: 시스템 간 결합도를 낮추고 대규모 처리를 할 때 사용하는 아키텍처 레벨의 해결책입니다. 외부 솔루션에 직접 요청을 보내는 대신 `RabbitMQ`나 `Kafka` 같은 메시지 브로커에 작업 메시지를 발행(publish)하고 끝냅니다. 외부 솔루션이 처리를 완료하면 다른 큐로 결과를 돌려주거나 웹훅(webhook)으로 알려줍니다.

# A Solution: Asynchronous I/O
블로킹의 한계를 극복하기 위해 OS는 비동기 I/O(asynchronous I/O)라고 불리는, 디스크 시스템에 I/O 요청을 발행하는 새로운 방법을 도입했습니다.
이런 인터페이스는 I/O 요청을 발행한 뒤 I/O가 완료되기 전에 즉시 호출자에게 제어를 반환할 수 있게 해줍니다. 그리고 I/O 작업이 완료됐는지, 성공/실패했는지를 확인하는 추가 인터페이스도 제공합니다.

예를 들어 macOS는 POSIX AIO 계열의 인터페이스를 제공합니다.
API는 기본 구조체인 `struct aiocb`(AIO control block)를 중심으로 구성되며, 이를 간소화하면 다음과 같습니다.
```c
struct aiocb {
    int aio_fildes; // File descriptor
    off_t aio_offset; // File offset
    volatile void *aio_buf; // Location of buffer
    size_t aio_nbytes; // Length of transfer
};
```
파일에 비동기 읽기를 발행하려면 위 구조체에 관련 정보를 채웁니다.
그 다음 비동기 읽기 API로 실행할 수 있습니다.
```c
int aio_read(struct aiocb *aiocbp);
```
이 호출은 I/O를 발행하고 성공하면 즉시 반환되며 애플리케이션은 작업을 계속할 수 있습니다.
그리고 I/O 작업이 종료돼 버퍼(`aio_buf`)에 요청된 데이터가 채워졌는지 확인하기 위해 다음 API를 사용합니다. 이름이 다소 혼란스럽긴 합니다.
```c
int aio_error(const struct aiocb *aiocbp);
```
이 호출은 `aiocbp`가 참조하는 요청의 상태를 확인합니다.
완료되지 않았으면 `EINPROGRESS`를 반환하고, 완료됐다면 0(성공) 또는 0이 아닌 에러 코드를 반환합니다. 따라서 단순한 방식으로는 애플리케이션이 주기적으로 `aio_error()`를 호출해 완료 여부를 확인(폴링)할 수 있습니다.
또한 완료 후에는 결과(예: 실제로 읽힌 바이트 수)를 회수하기 위해 `aio_return()`을 호출하는 것이 일반적입니다.

이는 예상 가능하듯이 작업이 수백 개가 되면 굉장히 무거운 작업이 됩니다. 이 문제를 줄이기 위해 일부 시스템은 완료 통지(completion notification)를 지원합니다.
예를 들어 요청을 발행할 때 신호(signal) 등으로 완료를 알리도록 설정하면, 애플리케이션이 반복적으로 상태를 체크할 필요가 줄어듭니다.

즉 이벤트 기반 접근 방식에서 비동기 I/O는 빠질 수 없습니다.
스레드 풀을 사용해 블로킹 I/O를 다른 스레드로 넘겨 처리하는 하이브리드 방식도 있으니, 환경에 따라 다양한 선택지가 있다는 점을 참고해 주세요.

# Another Problem: State Management
이벤트 기반 접근 방식의 또 다른 문제점은 코드를 작성하는 일이 전통적인 스레드 기반 코드보다 일반적으로 더 복잡하다는 점입니다.

그 이유는 다음과 같습니다.<br/>
이벤트 핸들러가 비동기 I/O를 발행하면, I/O가 나중에 완료되는 시점에 이어서 처리할 수 있도록 필요한 프로그램 상태를 따로 저장해 둬야 합니다. 이 추가 작업은 스레드 기반 프로그램에서는 필요하지 않은 경우가 많습니다. 스레드 기반에서는 다음 줄로 자연스럽게 실행이 이어지고, 필요한 상태가 스레드의 스택(로컬 변수 등)에 남아 있기 때문입니다.

이벤트 기반에서는 이런 작업을 `manual stack management`라고 부르며, 이벤트 기반 프로그래밍에서 자주 마주치는 기본적인 부담입니다.
이 점을 더 구체적으로 설명하기 위해, 스레드 기반 서버가 파일을 읽고 완료되면 읽은 데이터를 네트워크 소켓에 쓰는 예를 살펴보겠습니다(오류 코드는 무시).

```c
int rc = read(fd, buffer, size);
rc = write(sd, buffer, size);
```

멀티 스레드 프로그램에서 위 작업은 사소하죠. `read()`가 반환되면 코드는 즉시 어떤 소켓에 쓸지를 알 수 있습니다, 그 정보가 스레드의 스택에 있기 때문이죠.(변수 sd)

이벤트 기반 시스템에서는 상황이 간단치 않습니다.
동일한 작업을 수행하려면 먼저 비동기적으로 `read` 요청을 발행해 두고, 나중에 I/O 완료 이벤트가 도착했을 때 남은 작업을 이어서 처리해야 합니다. 문제는 그 시점에 필요한 정보(예: 어떤 소켓 `sd`로 응답을 써야 하는지)가 자동으로 남아 있지 않다는 점입니다.

이때 흔히 쓰는 해법이 `continuation`(컨티뉴에이션)입니다. 핵심 아이디어는 단순합니다. 이 이벤트 처리를 마무리하는 데 필요한 정보를 어떤 자료구조에 기록해 두었다가, I/O 완료 이벤트가 발생하면 그 정보를 찾아서 나머지 처리를 수행하는 방식입니다.

예를 들어 파일 디스크립터 `fd`로 비동기 디스크 읽기를 발행했다면, `fd -> sd` 매핑을 해시 테이블 같은 곳에 저장해 둡니다. 그리고 디스크 I/O가 완료됐다는 이벤트가 오면(즉 `fd`가 준비됐음을 알게 되면), 이벤트 핸들러는 `fd`를 키로 해당 `continuation`을 찾아 `sd`를 복원하고, 마지막으로 읽어온 데이터를 그 소켓에 `write()`합니다.

---
**ASIDE: UNIX SIGNALS** <br/>
이벤트 기반 접근에서는 유닉스 신호를 통해 I/O 완료 같은 정보를 알 수 있습니다(시스템/설정에 따라 다름).
유닉스에는 `signal`이라는 큰 메커니즘이 있는데, 간단히 말해 프로세스에게 특정 사건을 알리고 그에 대한 처리를 실행할 수 있게 해주는 수단입니다.

신호가 도착하면 실행 중이던 흐름이 잠시 중단되고, 등록해 둔 신호 처리기(`signal handler`)가 실행됩니다. 처리기가 끝나면 프로세스는 원래 하던 일을 계속 진행합니다.

신호는 커널이 직접 보내기도 합니다. 예를 들어 프로그램이 잘못된 메모리 접근을 하면 OS가 `SIGSEGV`를 보내고, 이 신호를 잡도록 설정돼 있다면 디버깅 목적의 코드를 실행할 수도 있습니다. 반대로 해당 신호를 처리하도록 설정하지 않았다면 기본 동작이 수행되며, `SIGSEGV`의 경우 보통 프로세스가 종료됩니다.

아래는 `SIGHUP` 신호를 처리하도록 핸들러를 등록한 뒤 무한 루프를 도는 간단한 예시입니다.

```python
import signal
import time


def handle(signum, frame):
    print("stop wakin' me up...")


signal.signal(signal.SIGHUP, handle)

while True:
    time.sleep(1)
```

실행 중인 프로세스에는 `kill` 명령으로 신호를 보내면 메인 루프가 끊기고 등록한 핸들러가 실행됩니다.

# What Is Still Difficult With Events
이벤트 기반에서도 아직 언급할 여러 가지 어려움이 존재합니다.

**멀티코어환경**<br/>
특히 시스템이 단일 CPU에서 다중 CPU(멀티코어)로 이동할 때, 이벤트 기반 접근 방식의 단순함은 옅어집니다.

단일 스레드 이벤트 루프에서는 이벤트 핸들러가 기본적으로 직렬로 실행되기 때문에, 한 코어 위에서는 동시성 버그를 피하기가 상대적으로 쉽습니다.
하지만 멀티코어의 성능을 활용하려면 결국 여러 이벤트 루프/스레드/프로세스로 처리를 병렬화해야 하고, 이때부터는 공유 상태가 생기는 순간 일반적인 임계구역 문제가 다시 등장합니다.
그래서 멀티코어 환경에서는 `lock` 같은 동기화가 필요해지거나, 공유 상태를 피하는 구조(프로세스 분리, 메시지 패싱 등)를 설계해야 합니다.

그러면 결국 내부적으로는 `lock`을 사용하지 않는다는 간단함은 사라지게 되죠. 그래도 이는 내부 로직이므로 활용할 때는 `lock`을 신경 쓰지 않아도 됩니다.

**시스템 활동 통합**<br/>
페이지 매핑과 같은 특정 종류의 시스템 활동과 잘 통합되지 않습니다.
예를 들어 이벤트 핸들러가 페이지 결함(`page fault`)을 일으켜 차단되면, 서버는 해당 페이지 결함 처리가 완료될 때까지 진행되지 않습니다.
- 페이지 폴트(Page Fault): 프로그램이 실행 중 물리 메모리(RAM)에 없는 데이터를 가상 메모리에서 참조하려고 할 때 운영체제(OS)가 발생하는 예외 상황

이벤트 기반 서버는 `read()` 같은 명시적인 블로킹 호출을 피하도록 구조화되었지만, 페이지 결함은 메모리 접근 과정에서 OS가 디스크 I/O를 수행하면서 발생할 수 있어 이를 파악하고 시스템에서 처리하기 어렵습니다.
따라서 단일 이벤트 루프가 페이지 결함으로 멈추면 다른 이벤트 처리도 함께 지연되어 큰 성능 문제로 이어질 수 있습니다.

**API 의미 변화**<br/>
이벤트 기반 코드는 시간이 지날수록 유지보수가 어려워질 수 있습니다. 이유는 애플리케이션이 의존하는 라이브러리/시스템/OS API의 동작 의미(blocking/non-blocking 등)가 바뀔 수 있기 때문입니다.

예를 들어 어떤 함수가 원래는 논블로킹처럼 동작했는데 이후 버전에서 블로킹으로 바뀔 경우, 그 함수를 호출하는 이벤트 핸들러도 그 변화에 맞춰 구조를 바꿔야 합니다.

보통은 하나의 핸들러를 I/O 전/후 두 단계로 쪼개는 식으로 흐름을 다시 구성해야 하는데, 이벤트 루프에서는 블로킹이 전체 서버를 멈추게 만들 수 있으므로, 개발자는 각 이벤트가 사용하는 API가 여전히 블로킹을 일으키지 않는지 계속 주의하며 개발하기에 유지보수 난이도가 올라갑니다.

**디스크 I/O와 네트워크 I/O의 비대칭성**<br/>
오늘날 대부분의 플랫폼에서 비동기 디스크 I/O가 가능해졌지만, 네트워크 I/O처럼 단순하고 일관된 방식으로 통합되지는 않는 경우가 많습니다.
이상적으로는 `select()` 같은 인터페이스 하나로 모든 I/O를 함께 관리하고 싶지만, 실제 네트워크는 `select()/poll()` 계열로 처리하고 디스크 I/O는 AIO 호출로 처리하는 식으로 서로 다른 메커니즘을 같이 써야하는 경우가 있어 혼란이 생길 수 있습니다.

# Summary
이벤트 기반으로 한 다른 스타일의 동시성을 살펴봤습니다.
이는 스케줄링 제어를 애플리케이션 단에서 해결할 수 있지만, 시간이 흐르면서 생기는 여러 가지 복잡성과 통합의 어려움으로 다른 트레이드오프가 생기게 되었죠.

스레드 방식과 이벤트 방식은 앞으로도 수년간 공존할 가능성이 크므로 알아두면 좋을 것 같습니다.

# Homework

`accept()`나 `recv()` 같은 호출은 기본적으로 블로킹입니다. <br/>
한 번 들어가면 데이터가 올 때까지 멈춰 있고, 그 시간 동안 서버는 다른 일을 못 합니다.
그래서 이벤트 기반에서는 소켓을 `setblocking(False)`로 바꾸고, `select()`가 준비된 소켓을 알려주면 그때 처리를 합니다. 
이렇게하면 스케줄링을 OS에 맡겨두는 대신 애플리케이션이 직접 처리 순서를 정할 수 있게 되죠.

아래 코드는 `selectors`로 이벤트 루프를 만들고, 간단한 요청 두 가지를 처리합니다.
- `TIME`은 현재 시간을 돌려줍니다.
- `GET <name>`은 `files/` 아래의 파일 내용을 돌려줍니다.

```python
import os
import selectors
import socket

sel = selectors.DefaultSelector()
ROOT = os.path.abspath("files")


def safe_path(name: str) -> str:
    p = os.path.abspath(os.path.join(ROOT, name))
    if not p.startswith(ROOT + os.sep):
        raise ValueError("bad path")
    return p


def accept(sock):
    conn, _addr = sock.accept()
    conn.setblocking(False)
    sel.register(conn, selectors.EVENT_READ, handle_get)


def handle_get(conn):
    req = conn.recv(4096)
    if not req:
        sel.unregister(conn)
        conn.close()
        return

    try:
        line = req.decode(errors="ignore").strip()
        parts = line.split(maxsplit=1)
        cmd = parts[0].upper() if parts else ""
        arg = parts[1] if len(parts) == 2 else ""

        if cmd == "TIME":
            import time

            now = time.strftime("%Y-%m-%d %H:%M:%S")
            conn.sendall((now + "\n").encode())
        elif cmd == "GET":
            path = safe_path(arg)
            # 파일 읽기는 블로킹이라 느리면 이벤트 루프도 같이 느려질 수 있음
            with open(path, "rb") as f:
                conn.sendall(f.read() + b"\n")
        else:
            raise ValueError("bad request")
    except Exception:
        conn.sendall(b"ERR\n")


def serve_files(host="127.0.0.1", port=9000):
    os.makedirs(ROOT, exist_ok=True)
    lsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    lsock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    lsock.bind((host, port))
    lsock.listen()
    lsock.setblocking(False)
    sel.register(lsock, selectors.EVENT_READ, accept)
    print(f"file server on {host}:{port}, root={ROOT}")

    while True:
        for key, _mask in sel.select(timeout=1.0):
            key.data(key.fileobj)


if __name__ == "__main__":
    serve_files()
```

여기서 이벤트 기반의 주의점이 보입니다. <br/>

네트워크는 `select()`로 준비 상태를 깔끔하게 받을 수 있지만 I/O 작업인 `read()`는 다루기 애매한 경우가 많습니다. 
큰 파일을 읽거나 디스크가 바쁘면, 핸들러가 오래 걸리면서 이벤트 루프가 같이 느려질 수 있습니다.
파이썬에서는 `OS AIO`를 직접 쓰지 않더라도, `asyncio`에서 파일 읽기를 executor로 넘겨 이벤트 루프를 계속 돌릴 수 있습니다. 
아래는 핵심 코드입니다.

```python
import asyncio

cache: dict[str, bytes] = {}


async def read_file_cached(path: str) -> bytes:
    if path in cache:
        return cache[path]

    loop = asyncio.get_running_loop()

    def blocking_read():
        with open(path, "rb") as f:
            return f.read()

    data = await loop.run_in_executor(None, blocking_read)
    cache[path] = data
    return data
```

작은 요청을 여러 개 섞어서 보내다가 중간에 큰 파일 요청을 한 번 테스트해보면 더 명확히 알 수 있습니다.

블로킹 서버는 큰 요청이 들어오는 순간 다른 요청이 같이 밀리는 게 보입니다. <br/>
이벤트 루프를 써도 파일 읽기를 핸들러에서 해버리면 결국 I/O 작업으로 전체가 느려질 수 있습니다. 
그래서 이벤트 기반에서는 어디까지를 이벤트로 묶고 어디부터는 다른 방식으로 분리할지 판단하는 일이 중요합니다.