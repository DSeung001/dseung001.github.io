---
title: "Class Project 질의응답 RAG"
date: 2026-08-13T00:00:00+09:00
categories: [ "Project", "Class Project" ]
tags: [ "Class Project", "RAG", "질의응답", "LLM" ]
draft: true
description: "Class S에 질의응답 RAG를 붙이기 위한 방향"
keywords: [ "Class Project", "RAG", "질의응답", "LLM", "검색 증강 생성" ]
author: "DSeung001"
lastmod: 2026-08-13T00:00:00+09:00
---

# 개요
이전 [하이브리드 검색](../../07/class-s-hybrid-search/)에서 강의 내용을 청크로 나누고 FTS와 임베딩을 쌓아 두었습니다. 이번에는 그 인덱스를 써서, 질문에 관련 구간을 찾은 뒤 LLM이 답하게 하는 RAG를 붙이려 합니다.

RAG는 사용자의 질문과 관련된 정보를 외부 데이터 소스에서 검색(Retrieval)하고, 검색된 정보를 LLM의 컨텍스트로 제공해 답변을 생성(Generation)하는 방식입니다. 이번 글의 목표는 이 방식으로 사용자의 상황과 의도를 파악해 강좌를 매칭하는 것입니다.

이렇게 정한 이유는, 영상에 대한 개념 질문만 받는다면 단순 LLM API 요청과 크게 다른 차별점을 만들 수가 없더군요.
그래서 원하는 강의를 추천해 주는 시스템을 생각했습니다. 이전에 만든 의미 기반 검색에서 조금 더 고도화된 방향이죠.

벡터 검색은 이전 [Anime Search Project](/posts/2026/05/10/anime-search-project/) 글로 어느 정도 익숙해서 접근이 가벼웠지만, RAG는 구조와 이론 공부가 더 필요해 다음 글을 참고했습니다.

## 참고글
[인프런: 학습에이전트 - Building the Brain](https://tech.inflab.com/20260621-study-agent/%ED%95%99%EC%8A%B5%EC%97%90%EC%9D%B4%EC%A0%84%ED%8A%B8%20-%20Building%20the%20Brain/)
> 목표로 하는 시스템과 가장 비슷한 RAG 시스템임

* **ADR**: 빠르게 바뀌는 LLM 스택의 선택 이유를 문서로 남기고, AI 컨텍스트에도 넣어 개발 의도를 유지함
* **LLM-as-a-Judge**: Golden Dataset을 기준으로 답변 품질을 자동 평가하고, 반복되는 실패 패턴으로 프롬프트를 고침
* **과적합 방지**: 실패 한 건마다 프롬프트를 고치지 않고, 같은 문제가 반복될 때만 고쳐 평가 데이터에 맞추는 일을 막음
* **프롬프트 캐싱**: 반복되는 System Prompt와 Tool Definition은 캐시해 입력 토큰과 비용을 줄이고, 질문이나 검색 결과 같은 동적 데이터는 따로 보냄
    - System Prompt: LLM의 역할과 답변 규칙을 정하는 지침
    - Tool Definition: LLM이 호출할 도구의 이름, 용도, 입력 형식

---

[우아한형제들: RAG, 들어는 봤는데… 내 서비스엔 어떻게 쓰지?](https://techblog.woowahan.com/25900/)
> RAG 시스템 평가 기준과 전체 파이프라인을 참고함

* **RAG 파이프라인**: Loading → Chunking → Embedding → Storage로 색인하고, Retrieval → Augmentation → Generation으로 질문에 답함
* **검색 품질**: 청크 크기, 메타데이터, 검색 개수, 유사도 기준이 Retrieval 품질을 좌우하므로 검색 결과 자체를 계속 튜닝해야 함
* **Query Optimization**: 사용자 질문을 그대로 쓰지 않고, LLM으로 핵심을 뽑아 검색용 Query로 바꿈
* **RAG 평가**: Contextual Relevance, Answer Faithfulness, Answer Relevance로 검색의 적절성과 답변의 근거 충실도를 봄
    - Contextual Relevance: 검색된 Context가 질문과 얼마나 관련 있는지 봄. 낮으면 Retrieval, Chunking, Query를 고쳐야 함
    - Answer Faithfulness: 답변이 검색된 Context를 얼마나 근거로 삼았는지 봄. 낮으면 사실이 아닌 내용을 생성하는 Hallucination 가능성임
    - Answer Relevance: 최종 답변이 질문에 얼마나 직접적으로 답했는지 봄. 관련 없는 설명이 많거나 의도를 놓치면 낮아짐

---

[Netflix: Foundation Model for Personalized Recommendation](https://netflixtechblog.com/foundation-model-for-personalized-recommendation-1a0bd8e02d39)
> RAG 자체보다는 이후 개인화된 강의 추천으로 확장할 때 참고함

* **사용자 행동 기반 추천**: 시청 기록과 같은 사용자의 행동 이력을 시퀀스로 학습해 최근 행동뿐 아니라 장기적인 취향까지 추천에 반영함
* **Embedding을 추천에 활용**: 사용자와 콘텐츠의 Embedding을 만들어 추천 모델의 Feature나 사용자에게 보여줄 콘텐츠 후보를 검색하는 데 활용함
* **신규 콘텐츠 문제 해결**: 사용자 행동 데이터가 부족한 신규 콘텐츠는 장르, 스토리, 분위기 같은 Metadata Embedding을 함께 사용해 보완함

---

## 적용점
RAG를 붙이려하지만 대규모 수정보다는 이전 [하이브리드 검색](../../07/class-s-hybrid-search/)에서 자막과 확정 메타데이터를 청크로 나누고 FTS와 임베딩을 쌓아 두었으니, 이를 Retrieval의 출발점인 `SearchChunk`로 삼으려합니다.

현재 청크 하나에는 영상명, 타임라인 라벨, 태그, 타임라인 설명, 해당 구간 자막이 같이 들어갑니다. 자막이 없으면 `Video.description`로 청크를 만들게 구성되어있죠.
현재는 다음 테이블로 표시할 수 있는데, RAG를 하면 아래 모든 데이터를 참고하는편이 좋겠습니다.

| 이미 쓰는 것 | 아직 안 쓰는 것 |
|---|---|
| `SearchChunk` (자막, 영상명, 태그, 타임라인, 구간 시각, FTS, 임베딩) | 강좌명/설명, 커리큘럼 |
| 조회수 (하이브리드 검색 popularity) | 시청 기록, 완강 기록 |
| | 검색/play/seek 로그, QnA |

## 방향성
1차는 기존 `SearchChunk`로 관련 구간을 찾고, 강좌/영상 정보를 붙여 LLM이 강의와 이유, 관련 구간을 답하게 합니다.

아래와 같은 방향으로 진행되겠군요.

```mermaid
flowchart LR
  Q["사용자 질문"] --> R["하이브리드 Retrieval"]
  R --> C["관련 SearchChunk"]
  C --> M["Course / Video 정보 결합"]
  M --> L["LLM"]
  L --> A["추천 강의 + 이유 + 관련 구간"]
```

2차로 개인화를 추가하여 시청 기록이나 사용자 QnA 내용을 참고하게 합니다.