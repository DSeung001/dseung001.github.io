---
title: "FTS와 벡터 검색"
date: 2026-08-12T00:00:00+09:00
categories: [ "Database" ]
tags: [ "PostgreSQL", "FTS", "pgvector", "검색" ]
draft: true
description: "Postgres FTS와 pgvector 비교 정리"
keywords: [ "PostgreSQL", "FTS", "tsvector", "pgvector", "코사인 거리" ]
author: "DSeung001"
lastmod: 2026-08-12T00:00:00+09:00
---

# 개요
Class S를 만들었던 지난 [하이브리드 검색](../../07/class-s-hybrid-search/) 글에서 FTS 방식으로 텍스트를 토큰으로 나눠 검색하는 방식과, 임베딩 모델을 거쳐 수치로 표현해 비교하는 방식 두 개를 썼는데,
이 두 방식을 전에는 로직 흐름으로 짧게 지나갔지만 이를 더 면밀히 봐봅시다.

# FTS
FTS는 Full Text Search입니다. `LIKE '%키워드%'`보다 키워드와 토큰 검색에 적합하고, 보통 `tsvector`, `tsquery`, `GIN index`를 조합해서 사용합니다.<br/>
※ ts: Text Search의 약어
- `tsvector`: PostgreSQL의 데이터 타입으로, 문서를 검색 가능한 토큰 형태로 표현합니다
- `tsquery`: PostgreSQL의 데이터 타입으로, 검색 조건을 표현합니다. `plainto_tsquery()`, `to_tsquery()` 같은 함수가 `tsquery` 값을 만듭니다
- `GIN index`: `tsvector`의 토큰을 빠르게 찾기 위한 인덱스 구조입니다

주의점으로는 PostgreSQL 기본 FTS는 영어처럼 공백과 어간 처리가 명확한 언어에서 훨씬 잘 동작합니다. 한국어는 조사와 형태소 때문에 기본 `simple` 설정만으로는 검색 품질이 제한적일 수 있는 게 아쉽죠.

Class S에서는 각 청크의 `text`를 PostgreSQL FTS 검색용 데이터인 `tsvector`로 변환해 `search_vector` 컬럼에 저장해 적용했습니다.

```
원본 텍스트 → to_tsvector('simple', text) → search_vector
```

```sql
UPDATE content_ai_searchchunk
SET search_vector = to_tsvector('simple', text)
WHERE video_id = $1;
```

그리고 검색할 때는 사용자가 입력한 문장을 공백 기준으로 나누고, 각각을 `tsquery`로 만든 뒤 OR 조건으로 결합합니다.
사용자가 "벡터 검색"이라 치면 내부적으로 아래처럼 동작하게 해서 구현했죠.

```sql
plainto_tsquery('simple', '벡터') || plainto_tsquery('simple', '검색')
```

실제 검색 쿼리로 보면 아래와 같죠.
```sql
-- 검색어를 공백으로 나눈 토큰을 OR로 묶는다.
-- 예: '벡터 검색' → plainto_tsquery('simple', '벡터') || plainto_tsquery('simple', '검색')
SELECT
  sc.id,
  sc.video_id,
  sc.start_seconds,
  sc.end_seconds,
  left(sc.text, 120) AS text_preview,
  ts_rank(sc.search_vector, query) AS fts_rank
FROM content_ai_searchchunk AS sc
INNER JOIN media_video AS v ON v.id = sc.video_id
INNER JOIN media_course AS c ON c.id = v.course_id
CROSS JOIN LATERAL (
  SELECT (
    plainto_tsquery('simple', '벡터')
    || plainto_tsquery('simple', '검색')
  ) AS query
) AS q
WHERE sc.search_vector @@ q.query
  AND c.publication_status = 'published'
ORDER BY fts_rank DESC
LIMIT 20;
```

위 구조에서 조인을 제외하고 FTS 매칭을 담당하는 부분은 `search_vector @@ query`로 보면 됩니다.
`@@`는 `tsvector`에 `tsquery`가 매칭되는지를 검사하는 연산자입니다.

Class S 코드에서는 여기에 토큰별 적중 여부를 세어 `fts_rank * (적중 수 / 전체 토큰 수)`로 한 번 더 가중합니다.
`ts_rank`가 비슷하더라도 검색어를 더 많이 포함한 청크가 위로 올라갈 수 있게 했죠.
아래 표의 `coverage`는 앞의 SQL이 직접 반환하는 값이 아니라, Class S 코드에서 별도로 계산해 최종 점수에 곱하는 값입니다.

예를 들어 청크가 아래와 같다고 합시다.

| id | 청크 내용 |
| --- | --- |
| 101 | pgvector를 이용하면 벡터 검색으로 비슷한 문서를 찾을 수 있다 |
| 102 | PostgreSQL Full Text Search를 이용한 검색 방법을 알아본다 |
| 103 | 벡터 임베딩은 문장을 숫자 배열로 표현하는 방법이다 |
| 104 | 데이터베이스 인덱스를 이용하면 검색 속도를 높일 수 있다 |

검색어가 `벡터 검색`이라면 결과는 대략 다음처럼 나올 수 있습니다.

| id | text_preview | fts_rank | coverage |
| --- | --- | ---: | ---: |
| 101 | pgvector를 이용하면 벡터 검색으로 비슷한 문서를 찾을 수 있다 | 0.094 | 1.0 |
| 103 | 벡터 임베딩은 문장을 숫자 배열로 표현하는 방법이다 | 0.061 | 0.5 |
| 102 | PostgreSQL Full Text Search를 이용한 검색 방법을 알아본다 | 0.052 | 0.5 |
| 104 | 데이터베이스 인덱스를 이용하면 검색 속도를 높일 수 있다 | 0.038 | 0.5 |

추가로 `search_vector`에 GIN 인덱스를 만들어 두었다고 해서 항상 인덱스를 쓰는 것은 아닙니다. 데이터 양에 따라 옵티마이저가 순차 스캔으로 동작할 수 있어서, 실제 실행 계획은 아래처럼 확인해야 하죠.
- ※ GIN(Generalized Inverted Index): 토큰에서 해당 토큰을 포함하는 행을 역으로 찾을 수 있게 구성한 인덱스

```sql
EXPLAIN
SELECT id
FROM content_ai_searchchunk
WHERE search_vector @@ plainto_tsquery('simple', 'pgvector')
LIMIT 10;
```

GIN이 붙으면 보통 Bitmap Index Scan 쪽으로 계획이 잡히고, 행 수가 적으면 Seq Scan이 나올 수도 있습니다.

```
Limit  (cost=0.00..11.62 rows=1 width=8)
  ->  Seq Scan on content_ai_searchchunk  (cost=0.00..11.62 rows=1 width=8)
        Filter: (search_vector @@ '''pgvector'''::tsquery)
```

여기서는 행 수가 적어서 Seq Scan이군요.


# Vector
`Postgres`에서 `Vector` 값은 `PostgreSQL + pgvector` 확장(extension)을 사용해서 쓸 수 있습니다.
- PostgreSQL: 기존 DB와 같이 정확히 일치하는 값이나 조건을 찾음
- pgvector: 의미 검색 기능을 PostgreSQL에 추가한 것

벡터는 간단하게 수 배열입니다. 이 값을 좌표로도 볼 수 있는데, 이 수치들로 특정 텍스트/의미를 표현할 수 있습니다.
아래 예시에서 "고양이가 귀엽다"와 "귀여운 고양이"처럼 의미가 겹치는 두 문장은 수치가 비슷하고, "PostgreSQL 설치 방법"은 의미가 다르기에 다르게 표현될 수 있는 거죠.
```
"고양이가 귀엽다"
→ [0.81, 0.24, -0.13, ...]

"귀여운 고양이"
→ [0.79, 0.27, -0.11, ...]

"PostgreSQL 설치 방법"
→ [-0.31, 0.77, 0.55, ...]
```

이런 텍스트를 수치로 바꾸는 작업은 1990년대부터 꾸준히 성장해 왔죠.

| 시점 | 대표 기법 | 한 줄 요약 |
| --- | --- | --- |
| 2000 | TF-IDF | 단어 빈도 가중치. 의미보다 키워드 겹침에 가깝다 |
| 2013 | Word2Vec | 단어를 벡터로. 문장 단위 검색엔 약하다 |
| 2014 | Doc2Vec | 문서 단위 벡터. 문맥 이해는 얕다 |
| 2018 | BERT | 양방향 문맥. 문장 임베딩은 별도 처리가 필요하다 |
| 2019 | Sentence-BERT | 문장 유사도용으로 BERT를 재학습 |
| 2021 | SimCSE | 대조 학습으로 문장 표현을 더 단단히 |
| 2022~ | BGE / E5 등 | 검색과 RAG에 맞춘 최신 embedding |

Class S에서는 이 중 최신 쪽에 해당하는 OpenAI `text-embedding-3-small`(1536차원)로 청크를 만들었고, Postgres `pgvector`의 코사인 거리 연산자 `<=>`로 가까운 청크를 고르게 구현했습니다. `CosineDistance`는 거리가 작을수록 비슷하고, 점수로 쓸 때는 `1 - distance`로 대략 0~1 유사도로 바꿉니다.

위 프로젝트 예시를 가져와 쿼리로 보면 아래와 같죠.
```sql
-- 질의 문장을 embedding API로 만든 벡터를 $1 에 바인딩한다.
-- 예: $1 = '[0.01, -0.03, ...]'::vector(1536)
SELECT
  sc.id,
  sc.video_id,
  sc.start_seconds,
  sc.end_seconds,
  left(sc.text, 120) AS text_preview,
  sc.embedding <=> $1::vector AS cosine_distance,
  (1 - (sc.embedding <=> $1::vector)) AS similarity
FROM content_ai_searchchunk AS sc
INNER JOIN media_video AS v ON v.id = sc.video_id
INNER JOIN media_course AS c ON c.id = v.course_id
WHERE sc.embedding IS NOT NULL
  AND sc.embedding_model_version = 'openai:text-embedding-3-small'
  AND c.publication_status = 'published'
ORDER BY sc.embedding <=> $1::vector
LIMIT 20;
```

위 구조에서 조인을 제외하고 벡터 검색을 담당하는 부분은 `ORDER BY sc.embedding <=> $1::vector`로 보면 됩니다.

질의 벡터를 마지막 청크(id=14)로 잡았을 때, 같은 영상(video_id=8) 안에서 거리가 가까운 순으로 나온 예시입니다. 거리는 작을수록, 유사도는 클수록 의미가 가깝습니다.

| id | video | 구간(초) | distance | similarity |
| --- | --- | --- | ---: | ---: |
| 14 | 8 | 874–930 | 0.000 | 1.000 |
| 13 | 8 | 736–876 | 0.191 | 0.809 |
| 9 | 8 | 286–415 | 0.241 | 0.759 |
| 6 | 8 | 0–149 | 0.284 | 0.716 |
| 11 | 8 | 550–625 | 0.290 | 0.710 |
| 10 | 8 | 409–552 | 0.295 | 0.705 |
| 7 | 8 | 147–163 | 0.309 | 0.691 |
| 12 | 8 | 621–742 | 0.314 | 0.686 |
| 8 | 8 | 163–293 | 0.322 | 0.678 |

추가로 `embedding` 컬럼에 HNSW 인덱스(`vector_cosine_ops`)를 만들어 두었다고 해서 모든 벡터 검색에서 항상 인덱스를 쓰는 것은 아닙니다. 데이터 양에 따라 옵티마이저가 순차 스캔으로 동작할 수 있어서, 실제 실행 계획은 아래처럼 확인해야 하죠.
- ※ HNSW(Hierarchical Navigable Small World) 인덱스: 고차원 벡터에서 유사한 항목을 빠르게 찾는 근사 최근접 이웃(ANN) 검색용 인덱스

```sql
EXPLAIN
SELECT id
FROM content_ai_searchchunk
ORDER BY embedding <=> (
  SELECT embedding
  FROM content_ai_searchchunk
  WHERE embedding IS NOT NULL
  LIMIT 1
)
LIMIT 10;
```

`<=>` 연산자는 두 벡터의 Cosine Distance를 계산해서, 기준 벡터와 가장 가까운 데이터를 앞쪽에 정렬한 뒤 상위 10개를 가져옵니다. 이 쿼리의 실행 계획을 보면

```sql
Limit  (cost=14.52..14.55 rows=10 width=16)
  InitPlan 1 (returns $0)
    ->  Limit  (cost=0.00..0.09 rows=1 width=32)
          ->  Seq Scan on content_ai_searchchunk content_ai_searchchunk_1  (cost=0.00..11.30 rows=129 width=32)
                Filter: (embedding IS NOT NULL)
  ->  Sort  (cost=14.43..14.76 rows=130 width=16)
        Sort Key: ((content_ai_searchchunk.embedding <=> $0))
        ->  Seq Scan on content_ai_searchchunk  (cost=0.00..11.62 rows=130 width=16)
```

위처럼 Seq Scan → Sort → Limit로 나옵니다. 현재 데이터가 약 130 row라 순차 스캔 후 정렬로 동작하고 있음을 알 수 있죠.
그래서 HNSW 효과를 제대로 보려면 수천~수만 건 이상의 벡터 데이터를 넣은 뒤 실행해야 합니다.

결국 Class S에서는 정확한 토큰 매칭에 강한 FTS와 문맥이 비슷한 내용을 찾는 벡터 검색을 함께 사용합니다. 두 검색 결과에 조회수 점수까지 더해 최종 순위를 정하는 과정은 앞선 [하이브리드 검색](../../07/class-s-hybrid-search/) 글에서 확인할 수 있습니다.

# LIKE vs PostgreSQL FTS + GIN vs pgvector + HNSW