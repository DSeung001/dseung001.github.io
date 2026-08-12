---
title: "Class Project Postgres FTS와 벡터 검색"
date: 2026-08-12T00:00:00+09:00
categories: [ "Project", "Class Project" ]
tags: [ "Class Project", "PostgreSQL", "FTS", "pgvector", "검색" ]
draft: true
description: "Class S 검색 쿼리로 Postgres FTS와 pgvector 비교를 정리한다"
keywords: [ "Class Project", "PostgreSQL", "FTS", "tsvector", "pgvector", "코사인 거리" ]
author: "DSeung001"
lastmod: 2026-08-12T00:00:00+09:00
---

# 개요
Class S는 발행된 강의 자막과 메타를 `SearchChunk`로 쌓고, 한 행에 키워드용 `search_vector`와 의미용 `embedding`을 같이 둡니다. 이전 [하이브리드 검색](../../07/class-s-hybrid-search/)이 청킹과 랭킹 흐름이었다면, 이번 글은 검색 API가 그 값을 Postgres에서 어떻게 꺼내 비교하는지만 봅니다.

# Postgres 특징, 기존과 다른 점
키워드는 보통 `LIKE`나 Elasticsearch로, 의미 검색은 Qdrant 같은 벡터 DB로 나눕니다. Class S는 검색 엔진을 따로 두지 않고 Postgres 한 테이블에서 둘 다 조회합니다.

| 축 | 기존 | Postgres |
|---|---|---|
| 키워드 | `LIKE`, ES/OpenSearch | `tsvector`, `@@` |
| 의미 | 별도 벡터 DB | `pgvector`, `<=>` |

FTS는 Full-Text Search입니다. `tsvector`는 문서를 토큰으로 나눈 타입이고, `tsquery`는 그 토큰을 조건으로 묶은 질의입니다. `pgvector`는 임베딩 좌표와 거리 연산자를 더하는 확장입니다. 코사인 거리는 작을수록 가깝고, 점수로 쓸 때는 `1 - distance`로 뒤집습니다.

한국어는 `simple` 설정이라 형태소 단위가 약하고, 전용 ANN 엔진만큼 대규모 근사 검색에는 맞춰져 있지 않습니다.

# 서비스에서 가져오는 법
검색은 `GET /api/v1/search?q=`입니다. 발행된 `SearchChunk`만 읽고, FTS 후보와 벡터 후보를 각각 상위 N개 뽑습니다.

FTS는 검색어를 공백으로 나눈 뒤 `SearchQuery`를 OR로 결합합니다.

```python
def _fts_candidates_postgres(*, terms: list[str], limit: int) -> dict[int, float]:
    term_queries = [SearchQuery(term, config="simple") for term in terms]
    combined = term_queries[0]
    for tq in term_queries[1:]:
        combined = combined | tq
    # SearchRank * (적중 토큰 수 / 전체 토큰 수) → order_by("-fts_score")[:limit]
```

벡터는 같은 `embedding_model_version` 행만 `CosineDistance`로 가까운 순을 가져옵니다. 모델이 다르면 좌표 공간이 달라서 비교하지 않습니다.

```python
def _vector_candidates(
    *,
    query_vector: list[float],
    embedding_model_version: str,
    limit: int,
) -> dict[int, float]:
    qs = (
        _published_chunks()
        .filter(
            embedding__isnull=False,
            embedding_model_version=embedding_model_version,
        )
        .annotate(distance=CosineDistance("embedding", query_vector))
        .order_by("distance")[:limit]
    )
    scores = {}
    for row in qs:
        dist = float(row.distance if row.distance is not None else 1.0)
        scores[row.id] = max(0.0, min(1.0, 1.0 - dist))
    return scores
```

# 값 비교하는 문법
위 ORM이 Postgres에 보내는 비교는 두 가지입니다. 발행 강좌만 읽는 JOIN은 `_published_chunks()`가 붙입니다.

FTS는 문서를 `to_tsvector`로 저장하고, 검색어는 `plainto_tsquery('simple', term)`입니다. Django `SearchQuery | SearchQuery`는 `||`(OR)입니다. `@@`로 걸고, `ts_rank`로 순위를 매긴 뒤 앱에서 토큰 적중 비율을 곱습니다.

```sql
-- 저장
search_vector = to_tsvector('simple', chunk_text)

-- 조회. SearchQuery(config="simple") | SearchRank
SELECT id,
       ts_rank(
         search_vector,
         plainto_tsquery('simple', 'hls')
         || plainto_tsquery('simple', '세그먼트')
       ) AS rank
FROM search_chunk
WHERE search_vector @@ (
        plainto_tsquery('simple', 'hls')
        || plainto_tsquery('simple', '세그먼트')
      )
ORDER BY rank DESC
LIMIT 100;
```

벡터는 `embedding` 컬럼에 좌표를 넣고, `CosineDistance`가 `<=>`를 붙입니다. `WHERE`는 임베딩과 모델 버전만 거르고, 가까운지는 `ORDER BY distance`가 결정합니다. 점수는 `1 - distance`입니다.

```sql
-- 저장
embedding = '[...]'::vector(1536)

-- 조회. CosineDistance("embedding", query_vector)
SELECT id,
       embedding <=> '[...]'::vector AS distance
FROM search_chunk
WHERE embedding IS NOT NULL
  AND embedding_model_version = 'openai:text-embedding-3-small'
ORDER BY distance
LIMIT 100;
```

두 값의 단위가 달라서 DB 한 연산자로 최종 순위를 끝내지 않습니다. 후보 `chunk_id`를 합친 뒤 앱에서 0~1로 맞추고 가중합합니다.
