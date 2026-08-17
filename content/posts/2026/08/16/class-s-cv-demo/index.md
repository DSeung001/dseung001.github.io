---
title: "Class S 시연"
date: 2026-08-16T00:00:00+09:00
categories: [ "Project", "Class Project" ]
tags: [ "Class Project", "시연" ]
draft: true
description: "Class S 시연"
keywords: [ "Class Project", "시연" ]
author: "DSeung001"
lastmod: 2026-08-16T00:00:00+09:00
---

# 개요
다른 사람들한테 보여줄 때 사이트로 보여주는 방법을 지금 사용하고 있지만, RAG 시스템에 경우 API 키 등록이 필요하고 요청마다 비용이 발생하고 있습니다.
이를 해결할 방법을 고민하던 중, 영상으로 담아 정리하면 좋을것 같다는 생각이 들었죠

영상의 좋은 점은
1. 페이지 이동 없이 전체 기능을 보여줄 수 있다
2. RAG 비용이 발생하지 않는다
3. 현재 버전을 코드가 아닌 시각자료로 저장해둘 수 있다.
4. 영상을 통해 다른 시각으로 사이트를 다시 볼 수 있다.

단일 흐름으로 보면 아래와 같이 말할 수 있으며

```mermaid
flowchart LR
  upload["업로드 Presigned S3"] --> encode["SQS Worker HLS"]
  encode --> write["메타 데이터 추출"]
  write --> index["FTS Embedding 청크"]
  index --> search["하이브리드 검색 A/B"]
  search --> rag["RAG 강좌 추천"]
```

다음 부분에서 크게 4개의 세션으로 나눠 시연합니다.

## 업로드
## 시청
## 추천
## 운영