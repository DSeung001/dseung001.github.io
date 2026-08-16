---
title: "Class S 실행영상 정리"
date: 2026-08-16T00:00:00+09:00
categories: [ "Project", "Class Project" ]
tags: [ "Class Project", "인코딩", "글쓰기", "추천" ]
draft: true
description: "Class S에서 CV로 가져갈 기능을 실행영상으로 정리"
keywords: [ "Class Project", "인코딩", "글쓰기", "추천", "실행영상" ]
author: "DSeung001"
lastmod: 2026-08-16T00:00:00+09:00
---

# 개요
Class S는 학원 강의 녹화본을 올려 재생하는 서비스로 시작해, 업로드부터 HLS 재생, 검색, 강좌 추천까지 한 흐름으로 붙인 프로젝트입니다. 주소는 [https://class.devseung.com/](https://class.devseung.com/)입니다.

이 글은 구현 세부를 다시 쓰지 않습니다. CV에서 미디어 처리와 검색과 AI로 나눠 적는 문장을, 실제로 돌아가는 화면과 맞춰 두기 위한 실행영상 허브입니다. 로직과 수치는 각 챕터의 기존 글로 보냅니다.

전체 흐름은 아래와 같습니다.

```mermaid
flowchart LR
  upload["업로드 Presigned S3"] --> encode["SQS Worker HLS"]
  encode --> write["AI 설명 태그 타임라인"]
  write --> index["FTS Embedding 청크"]
  index --> search["하이브리드 검색 A/B"]
  search --> rag["RAG 강좌 추천"]
```

## 인코딩

### Presigned Direct Upload
처음에는 대용량 영상이 Backend API를 거쳐 S3에 저장됐습니다. 파일 크기가 커질수록 API 서버의 메모리와 디스크를 점유할 수 있다고 판단해, 클라이언트는 Presigned URL로 S3에 직접 올리고 API는 권한 확인, 메타데이터 검증, 상태 관리와 Job 생성만 담당하도록 나눴습니다.

CV 3절의 `Client → Presigned URL → S3 → PublishJob` 구간에 해당합니다.

촬영: `init` → S3 Presigned `PUT` → `commit` → Job 상태가 `uploading`에서 `queued`로 바뀌는 화면.<br/>
상세: [인코딩 서버 분리로 비용 절감하기](../../../06/23/class-s-encoding-server-split-cost-saving/)

<video controls width="100%" preload="metadata">
  <source src="./upload.mp4" type="video/mp4">
</video>

### SQS Encoding Worker
인코딩은 처음에 Celery와 Redis 기반 단일 서버에서 처리했습니다. API와 인코딩의 리소스 사용 패턴이 달라, SQS와 Auto Scaling 기반의 별도 Worker로 나눴습니다. API와 인코딩을 각각 확장할 수 있게 하려는 선택이었습니다.

CV 3절의 `PublishJob → SQS → Encoding Worker`에 해당합니다.

촬영: SQS에 메시지가 쌓인 뒤 워커가 기동하고, 인코딩이 끝난 영상을 플레이어가 재생하는 화면.<br/>
상세: [인코딩 서버 분리로 비용 절감하기](../../../06/23/class-s-encoding-server-split-cost-saving/)

<video controls width="100%" preload="metadata">
  <source src="./worker.mp4" type="video/mp4">
</video>

### HLS copy와 transcode
워커는 원본을 HLS로 패키징해 S3와 CloudFront에 올립니다. 재생은 서버가 세그먼트를 밀어 넣는 방식이 아니라, 플레이어가 매니페스트와 세그먼트를 요청하는 방식입니다.

코덱 이름만 보고 재인코딩하지는 않습니다. `ffprobe`로 컨테이너와 스트림 메타데이터를 읽고, Apple HLS Authoring Specification과 RFC 8216 기준을 이미 만족하면 `-c copy`로 패키징만 하고, 아니면 `libx264`와 `aac`로 transcode합니다. 내부 테스트에서 5분 영상 기준 copy 경로는 transcode 대비 약 164배 빨랐습니다.

촬영: copy 분기와 transcode 분기가 갈리는 Job 로그, 이어서 HLS 재생.<br/>
상세: [코덱 분리 개념 정리 및 적용](../../../06/19/ffmpeg-codec-processing-strategy/)

<video controls width="100%" preload="metadata">
  <source src="./hls.mp4" type="video/mp4">
</video>

### 비용과 스케일
인코딩을 상시 대기하는 큰 인스턴스에서 빼면, API 서버 스펙을 낮출 수 있습니다. 큐 깊이를 CloudWatch가 보고 ASG가 Worker를 켰다 끄게 바꿨습니다. 적용 전 일 운영 비용은 약 3달러 수준이었고, 분리 이후 약 1.17달러 수준으로 내려갔습니다.

촬영: SQS 큐 깊이 알람과 ASG desired capacity가 오르내리는 CloudWatch 화면.<br/>
상세: [인코딩 서버 분리로 비용 절감하기](../../../06/23/class-s-encoding-server-split-cost-saving/)

<video controls width="100%" preload="metadata">
  <source src="./cost.mp4" type="video/mp4">
</video>

### Job 재처리와 VFR
운영 중에 완료된 비동기 Job이 다시 전달돼 재실행되는 문제가 있었습니다. 원인을 확인한 뒤 중복 실행을 막는 로직을 넣었습니다. 특정 WebM/VFR 영상에서는 비정상적인 FPS 메타데이터 때문에 인코딩이 4시간 이상 걸렸고, 프레임 타임라인을 확인해 약 40분 수준으로 줄였습니다.

촬영: 같은 Job이 다시 들어와도 재실행되지 않는 상태, VFR 영상의 처리 시간 전후를 보여주는 Job 상세.<br/>
상세: [Celery와 Redis Time Limit](../../../06/16/class-project-bug-celery-redis-time-limit/)

<video controls width="100%" preload="metadata">
  <source src="./job-fix.mp4" type="video/mp4">
</video>

## 글쓰기

### AI 설명, 태그, 타임라인
업로드가 끝나면 설명과 태그, 타임라인을 처음부터 사람이 쓰지 않아도 됩니다. 워커가 자막과 확정 메타데이터를 읽고 초안을 채운 뒤, 발행 전에 고칠 수 있게 두었습니다. AI가 만든 결과를 기존 강좌 데이터에 연결하는 단계입니다.

CV 4절의 “결과를 만드는 것뿐 아니라 기존 데이터와 어떻게 연결할지”에 해당합니다.

촬영: 강의 업로드 후 description, tags, timelines가 채워지고, 발행 전에 수정하는 화면.<br/>
상세: [하이브리드 검색 구현하기](../../07/class-s-hybrid-search/)

<video controls width="100%" preload="metadata">
  <source src="./metadata.mp4" type="video/mp4">
</video>

### AI 썸네일
영상 프레임을 고르는 방식 위에, 프롬프트로 레이어를 만들고 캔버스에서 수정하는 썸네일 경로를 붙였습니다. 이미지와 도형, 텍스트를 나눠 두어 한 장을 통째로 다시 그리지 않고 고칠 수 있습니다.

촬영: 테마와 프롬프트를 넣고 레이어가 생성된 뒤, 위치와 텍스트를 고치는 화면.<br/>
상세: [썸네일 직접 만들기 + AI 이미지 생성](../../../07/06/class-s-ai-thumbnail/)

<video controls width="100%" preload="metadata">
  <source src="./thumbnail.mp4" type="video/mp4">
</video>

## 추천

### 하이브리드 검색
강의 내용을 청크 단위로 나누고, PostgreSQL FTS와 Embedding을 같은 행에 쌓았습니다. 검색과 이후 RAG가 이 청크를 같이 씁니다. 토큰이 맞는 결과와 문맥이 가까운 결과를 한 순위로 보여 주기 위한 구조입니다.

CV 4절의 Hybrid Search 문장에 해당합니다.

촬영: 자연어로 검색한 뒤 결과 항목을 열고, 해당 구간으로 이동하는 화면.<br/>
상세: [하이브리드 검색 구현하기](../../07/class-s-hybrid-search/)

<video controls width="100%" preload="metadata">
  <source src="./search.mp4" type="video/mp4">
</video>

### 검색 랭킹 A/B
FTS, 벡터, 조회수 비중은 처음에 `0.45 / 0.45 / 0.10`으로 동작만 하게 둔 값이었습니다. 정해진 값을 그대로 쓰기보다 실제 결과를 확인할 필요가 있다고 생각해, 검색 후 재생이나 구간 이동을 행동 데이터로 모으고 가중치 조합을 비교하는 A/B 구조를 넣었습니다.

CV 4절의 A/B Test 문장에 해당합니다.

촬영: variant마다 검색 순서가 달라지는 화면과, Admin에서 실험 설정과 이벤트를 보는 화면.<br/>
상세: [검색 랭킹 A/B 테스트](../../11/class-s-search-ab-test/)

<video controls width="100%" preload="metadata">
  <source src="./search-ab.mp4" type="video/mp4">
</video>

### RAG 강좌 추천
RAG는 LLM API 한 번으로 끝내지 않았습니다. Hybrid Search로 관련 청크를 찾고, Context를 구성한 뒤 LLM 응답을 Schema로 검증하고, 맞지 않는 id는 버리며, 근거가 없으면 `no_result`로 두고, Golden Dataset으로 회귀합니다.

`Hybrid Search → Context 구성 → LLM 응답 → Schema 검증 → 잘못된 결과 필터링 → Fallback → Golden Dataset 평가`

Golden `full` run 13건(추천 11건, 없어야 하는 질문 2건)에서 course hit와 video hit는 1.0이었습니다. 지금 재는 값은 이 추천 계약이지, 서비스 전체 품질 주장은 아닙니다.

촬영: 질문에 강좌 카드와 관련 구간이 나오는 화면, 근거가 없는 질문은 `no_result`로 끝나는 화면.<br/>
상세: [질의응답 RAG](../../13/class-s-qa-rag/)

<video controls width="100%" preload="metadata">
  <source src="./rag.mp4" type="video/mp4">
</video>

## 운영

### GitHub Actions 배포
배포는 EC2에서 직접 빌드하던 방식에서, GitHub Actions가 이미지를 만들어 ECR에 올리고 SSM으로 EC2가 pull 하는 구조로 바꿨습니다. API 서버 스펙을 줄이려면 배포 경로에서 빌드를 빼야 했기 때문입니다.

CV 3절의 GitHub Actions와 ECR 자동화에 해당합니다.

촬영: `release` push 이후 Actions 로그, ECR 태그, EC2에서 pull과 restart가 이어지는 화면.<br/>
상세: [GitHub Actions 자동 배포](../../../06/26/class-project-github-actions-auto-deploy/)

<video controls width="100%" preload="metadata">
  <source src="./deploy.mp4" type="video/mp4">
</video>

### SSE 공지
공지는 페이지를 새로고침하지 않아도 연결된 클라이언트에 바로 보이게 SSE로 붙였습니다. 업로드와 인코딩, 검색이 돌아가는 동안에도 운영 메시지를 같은 서비스 안에서 전달하기 위한 경로입니다.

촬영: 관리자가 공지를 올리면 열려 있는 화면에 알림이 뜨는 장면.<br/>
상세: [공지 기능 만들기](../../../07/24/class-s-sse-notification/)

<video controls width="100%" preload="metadata">
  <source src="./notice.mp4" type="video/mp4">
</video>
