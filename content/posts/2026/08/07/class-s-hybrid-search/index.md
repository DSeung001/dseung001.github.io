---
title: "Class Project 하이브리드 검색 구현하기"
date: 2026-08-07T00:00:00+09:00
categories: [ "Project", "Class Project" ]
tags: [ "Class Project", "하이브리드 검색", "인덱싱", "검색" ]
draft: true
description: "Class S 프로젝트에 하이브리드 검색 파이프라인 구현하기"
keywords: [ "Class Project", "하이브리드 검색", "인덱싱", "검색", "영상", "텍스트 추출" ]
author: "DSeung001"
lastmod: 2026-08-07T00:00:00+09:00
---

## 1. 왜 만들었는지

벡터 검색을 붙여 키워드만으로는 놓치는 구간을 찾는 것이 목적이었다. 강좌명 검색을 넘어, 챕터와 자막 구간까지 찾아 재생 시점으로 보내는 제품이 목표다.

### 서브

- 기존 키워드 검색의 한계 (동의어, 표현 차이)
- 하이브리드로 가져가려 한 범위 (FTS + 벡터 + 인기도)
- 제품 진입점 (`GET /api/v1/search`, 프론트 `/search`)

## 2. 쓰기: 발행하면 인덱스가 생긴다

청킹하며 임베딩하는 과정을 코드베이스 기준으로 적는다. 발행 후 비동기로 `SearchChunk`를 쌓는 경로가 중심이다.

### 서브

- 발행 → `on_commit` enqueue → `SearchIndexJob` (발행을 막지 않음)
- 챕터 우선 청킹 (`build_chunks_for_video`, transcript 없으면 `metadata_only`)
- 임베딩 (OpenAI / stub, transcript credential 재사용)
- `SearchChunk` 교체와 FTS `search_vector` 갱신
- 같은 `metadata_version` + `embedding_model_version`이면 재처리 skip

## 3. 읽기: 검색 API가 점수를 매기는 방식

쿼리 한 번에 FTS 후보와 벡터 후보를 모은 뒤, 어떻게 점수를 배점하는지 코드 흐름으로 정리한다.

### 서브

- rate limit과 쿼리 길이 검증
- `_fts_candidates` (Postgres `SearchRank`)
- `_vector_candidates` (코사인 유사도, 동일 embedding 버전만)
- 후보 합집합 → min-max 정규화 → `combine_hybrid_scores`
- highlight, `timestamp_seconds`, `match_reasons` 응답

## 4. 결합 규칙: 알고리즘과 출처

구현은 RRF가 아니라 min-max 정규화 후 가중 합산(Weighted Sum)이다. 이 선택과 가중치(FTS 0.45, Vector 0.45, Popularity 0.10)의 근거, 논문·실무 출처를 따로 모은다.

### 서브

- 코드에 있는 수식과 `hybrid` / `fts_only` 모드 전환 조건
- RRF와의 차이 (rank fusion vs score fusion)
- 출처 후보 조사: Cormack et al. SIGIR 2009 (RRF), Weighted Sum / Relative Score Fusion(min-max + 가중합) 계열 문헌과 검색 엔진 문서
- 우리 구현이 어느 계열에 가까운지, 아직 출처가 비어 있는 부분 명시

## 5. 운영과 부하

운영 쪽은 아직 검증이 부족하다. 과부하(부하) 테스트를 전제로 확인할 항목만 적어 둔다.

### 서브

- unpublish 시 청크 유지, 노출은 published만
- `backfill_search_index`, `explain_search_indexes`, pgvector 전제
- 부하 테스트 계획 (후보: 프로젝트 `perf/k6/search.js`, 동시 검색·임베딩 호출)
- 측정할 지표 (latency, `fts_only` 비율, 인덱싱 지연) — 실측 전까지는 미기재
