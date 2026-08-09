---
title: "Class Project 하이브리드 검색 구현하기"
date: 2026-08-07T00:00:00+09:00
categories: [ "Project", "Class Project" ]
tags: [ "Class Project", "하이브리드 검색", "인덱싱", "검색", "임베딩", "SQS" ]
draft: false
description: "Class S 프로젝트에 하이브리드 검색 파이프라인 구현하기"
keywords: [ "Class Project", "하이브리드 검색", "인덱싱", "검색", "영상", "텍스트 추출", "임베딩", "SQS" ]
author: "DSeung001"
lastmod: 2026-08-09T00:00:00+09:00
---

# 개요
처음에 강의 공유 사이트로 컨셉을 잡고 배포했던 이유에는, 동영상처럼 무거운 데이터를 다루고 싶었던 점도과 함께, 여기서 빠져나갈 갈래가 많다는 점도도 있었습니다. LLM 관련 기능을 붙이려면 콘텐츠가 필요한데, 그에 가장 잘 맞는 서비스라고 생각해 접근했습니다.

이번에는 사이트에 쌓인 콘텐츠에 LLM을 어떻게 녹일지 고민하다, 두 가지를 붙이기로 했습니다. 하나는 업로드할 때 기입하는 설명·태그·타임라인 정보를 자동으로 채우는 기능이고, 다른 하나는 영상 내용을 벡터화해 원하는 강의에 더 가깝게 다가가는 하이브리드 검색입니다.

이번 글에서는 코드 단위보다는 데이터가 어디서 어디로 가는지, 비동기 잡의 구성과 청킹, 임베딩, 랭킹 같은 핵심 비즈니스 로직이 어떻게 동작하는지를 따라갑니다.<br/>

읽는 순서는 개념 소개 → 데이터 흐름 → 비동기 작업 구조 → 상세 비즈니스 로직 → 검색 랭킹과 현재 로직 분석 순으로 이어집니다.

## 하이브리드 인덱싱

키워드 검색용 FTS 벡터와 의미 검색용 임베딩 벡터를 같은 청크 단위로 함께 적재하는 구조를 사용합니다.
보통 게시판에서는 규모가 작으면 `LIKE` 검색만 제공하고, 규모가 커지면 Full-Text Search(FTS)에 `Elasticsearch`/`OpenSearch` 같은 검색 엔진을 더해 검색하곤 합니다.

이 FTS 토큰 매칭에 의미 기반으로 가중치를 주는 검색을 혼합하며, 다음 시나리오에서 이점을 기대할 수 있습니다.
- 검색자가 특정 단어가 기억나지 않아도 결과에 근접할 수 있음
- 자연어로 검색할 수 있음
- 비슷한 뜻의 단어로도 원하는 결과를 찾을 수 있음

> FTS 벡터(`tsvector`): PostgreSQL 등에서 텍스트를 단어 단위로 나누고 정규화해, 검색에 쓰기 좋은 형태로 만든 자료 구조이자 데이터 타입입니다. 사용자가 "게시판 등록"을 검색하면 "등록", "게시판" 같은 토큰 기준으로 더 정교하게 찾을 수 있습니다.

> 의미 검색용(Semantic Search) 벡터: 텍스트가 가진 의미와 문맥을 수백~수천 개 숫자로 이뤄진 고차원 좌표로 표현한 데이터입니다. 흔히 임베딩이라고 부르며, 임베딩 모델로 자연어를 수치화합니다.


# 데이터 흐름
사용자가 영상을 업로드하면 워커가 HLS로 인코딩합니다. 이후 선택적으로 AI가 관련 테이블 데이터를 채우고 영상 사운드를 텍스트로 뽑을 수 있으며, 최종 발행 뒤에야 FTS 벡터화와 임베딩이 진행됩니다.

사용자는 다음처럼 강의 업로드로 영상을 올리고 AI로 요약하고 발행할 수 있습니다.<br/>
- 주소: [https://class.devseung.com/courses/108?return_to=main](https://class.devseung.com/courses/108?return_to=main)


※ 이미지에 마우스를 올려 확대해서 보시는 것을 권장드립니다.

**강의 업로드**
![upload](./upload.gif)
**업로드 확인**
![result](./result.gif)

또 발행된 강좌는 메인에서 영상 내용 기반으로 검색할 수 있습니다.
아직은 검증 단계로 개발자 친화적입니다.
![search](./search.webp)

아래는 전체 시퀀스 다이어그램입니다.

```mermaid
sequenceDiagram
  participant UI
  participant API
  participant SQS
  participant Worker
  participant S3
  participant DB

  UI->>S3: 원본 업로드 (presigned PUT)
  UI->>API: commit
  API->>SQS: type=publish
  SQS->>Worker: receive
  Worker->>S3: HLS 저장
  Worker->>DB: Course/Video draft
  Note over Worker: after_upload=ai 인 경우
  Worker->>DB: review=ai_processing
  Worker->>SQS: type=metadata
  SQS->>Worker: receive
  Worker->>S3: transcript JSON
  Worker->>DB: description / tags / timelines
  UI->>API: 최종 발행
  API->>DB: published
  API->>SQS: type=search_index
  SQS->>Worker: receive
  Worker->>DB: SearchChunk (FTS + embedding)
```

사용자 화면 기준으로 보면 기능이 돌아가는 구간은 크게 세 곳이고, 뒤에서 도는 잡도 세 개입니다.

1. 강의 업로드 화면에서는 영상을 올리고 인코딩이 끝날 때까지 기다립니다.
   `publish` 잡이 HLS 인코딩을 하고 Course/Video를 draft로 만듭니다.
2. AI 분석·검수 화면에서는 자동 채우기(AI)를 돌리거나, 설명·태그·타임라인을 직접 고친 뒤 발행을 준비합니다.
   `metadata` 잡이 STT(또는 자막)로 본문 텍스트를 뽑고, 요약·타임라인·태그를 만들어 media DB에 넣습니다.
3. 최종 발행 뒤에는 화면상으로는 발행 완료로 보이지만, 검색에 쓰일 준비가 이어서 진행됩니다.
   `search_index` 잡이 확정된 텍스트를 청킹한 뒤 FTS와 임베딩을 만들어 `SearchChunk`에 저장합니다.

`metadata`는 draft(검수) 단계에서 돌고, `search_index`는 `published` 이후에만 돕니다. 둘 다 영상의 텍스트 정보를 다루지만 시점과 목적이 다릅니다.

이어서 이 세 잡이 왜 갈라져 있는지, 큐에서는 어떻게 분기되는지 봅니다.

# 비동기 작업 구조

## 잡을 나눈 이유
세 작업 모두 외부 API 호출과 CPU 작업이 섞여 있습니다. ffmpeg 인코딩, Whisper·Gemini 호출, 청킹과 임베딩처럼 시간이 길고 실패 지점도 달라서, 처음부터 동기 API 한 번에 넣기는 어렵습니다.

그렇다면 하나의 긴 잡으로 묶을 수도 있었지만, 그렇게 하지 않은 이유는 사용자에게 선택지를 남기기 위해서입니다.<br/>
API 키를 등록해 AI로 내용을 채울 수도 있고, 키 없이(또는 AI 없이) 설명·태그·타임라인을 직접 적을 수도 있어야 합니다. 업로드에서 인코딩, 선택적 AI 채우기, 사람 검수, 발행, 검색 인덱싱까지 단계를 건너뛰거나 다시 돌리려면 잡 경계를 화면 흐름에 맞춰 나누는 편이 맞았습니다.

즉 제품 흐름의 유연성을 생각해서 분리해뒀습니다.<br/>
한 시점에 묶으면 실패 재시도와 선택적 AI 경로를 같이 다루기 어려워지기 때문이죠.

## SQS 공용 큐와 메시지 타입
운영에서는 publish, metadata, search_index는 브로커 `PUBLISH_SQS_QUEUE_URL`을 공유합니다.<br/>

```python
# SQS 공용 큐 분기용 message type
PUBLISH_MESSAGE_TYPE = "publish"
METADATA_MESSAGE_TYPE = "metadata"
SEARCH_INDEX_MESSAGE_TYPE = "search_index"
```

브로커를 통한 워커 진입점은 `python -m media.workers.sqs_worker`이고, 실제 분기는 내부에서 `process_sqs_message`로 이뤄집니다.

```python
# payload.type → publish | metadata | search_index
def process_sqs_message(...):
    payload = _parse_message_payload(message.get("Body") or "")
    msg_type = str(payload["type"]) if payload and payload.get("type") is not None else None

    if payload is not None and msg_type == PUBLISH_MESSAGE_TYPE:
        process_publish_message(...)
        return
    if payload is not None and msg_type == METADATA_MESSAGE_TYPE:
        process_metadata_message(...)
        return
    if payload is not None and msg_type == SEARCH_INDEX_MESSAGE_TYPE:
        process_search_index_message(...)
        return
    # unknown / unsupported type
```

메시지 형태는 대략 다음과 같습니다.

- publish: `{ "type": "publish", "job_id": "...", "enqueued_at": "..." }`
- metadata: `{ "type": "metadata", "job_id": "...", "course_id": ..., "video_id": ..., "pipeline_version": "v1", ... }`
- search_index: metadata와 같은 골격에 `type=search_index`

장시간 ffmpeg나 Whisper가 돌아가도 큐의 작업 시간 제한인 `visibility timeout`에 걸리지 않도록, 워커는 `heartbeat`로 `visibility`를 연장합니다.
성공하거나 스킵하면 `DeleteMessage`로 ack하고, 실패했는데 재시도 여유가 있으면 `visibility`를 0으로 돌려 재배달합니다.

## 상태 머신
파이프라인과 잡별로 글의 상태를 정리하면 더 분명해집니다.

| 기능 / 잡 | 상태 전이 | 비고 |
|-----------|-----------|------|
| `PublishJob` | `uploading` → `queued` → `processing` → `completed` \| `failed` | 업로드 후 인코딩·썸네일·DB 반영 |
| `Course.publication_status` | `draft` ⇄ `published` | 카탈로그 공개 여부 |
| `Course.review_status` | `none` → `ai_processing` → `review_required` \| `failed` | AI 검수 파이프라인 (`publication_status`와 독립). 잡 실패 시 `failed`, 성공 시 `review_required` |
| `VideoMetadataJob` | `queued` → `running` → `completed` \| `failed` | 스텝: `transcribe` → `summarize` |
| `SearchIndexJob` | `queued` → `running` → `completed` \| `failed` | `publication_status=published`일 때만 실행 |

아래부터는 잡별 핵심 비즈니스 로직을 따라갑니다.

# 핵심 비즈니스 로직

## publish
업로드 동작은 기존과 동일하지만, 변경점으로 인코딩이 끝나면 Course/Video는 항상 draft로 생성됩니다.<br/>
그 다음 사용자가 정한 `after_upload` 값에 따라 후속 동작이 갈립니다.

아래 분기는 사용자의 행동에 따라 여러 상태를 오갈 수 있기에 순서가 바뀌어도 돌아갈 수 있게 구상했습니다.

```python
# after_upload: draft | publish | ai
def apply_after_upload_action(*, course, user, after_upload):
    action = (after_upload or AfterUploadAction.DRAFT).strip().lower()
    if action in ("", AfterUploadAction.DRAFT):
        return course
    if action == AfterUploadAction.PUBLISH:
        return publish_course_final(course=course)
    if action == AfterUploadAction.AI:
        return start_ai_analysis(course=course, user=user)
    return course
```

발행 방법에 따라 후술할 인덱싱에 쓰는 텍스트 소스가 달라집니다.<br/>
최종 검수 후 강좌를 발행할 때 `publication_status=published`가 되는 시점에 적재되므로, 발행 전인 `ai`/`draft` 상태에서는 인덱싱하지 않습니다.<br/>

정확히는 AI로 값을 채우는 잡은 설명·태그·타임라인을 채우는 옵션이기에, 이후 검수 후 사람이 발행할 때 비로소 인덱싱이 붙습니다.
바로 발행(`publish`)하면 AI 없이 공개 상태가 되며, `transcript`를 따로 만들지 않기에 인덱싱할 데이터는 입력한 `description`/`tags`/`timeline` 같은 media 필드로 청크를 만듭니다. (AI 키는 강의를 올리는 사람의 것을 쓰므로, 키 등록 여부에 따라 선택 가능한 플로우로 구상했습니다)

이를 아래 다이어그램으로 표현이 가능하죠.

```mermaid
sequenceDiagram
  participant Worker
  participant DB
  participant SQS

  Note over Worker,DB: 인코딩 완료 후 Course/Video는 draft
  Note over Worker: apply_after_upload_action<br/>(manifest.after_upload)

  alt after_upload = ai
    Worker->>DB: review = ai_processing
    Worker->>DB: VideoMetadataJob 생성 (영상별)
    Worker->>SQS: enqueue type=metadata
    Note over Worker,SQS: 이 시점에는 search_index 없음<br/>검수 후 발행 때 인덱싱
  else after_upload = publish
    Worker->>DB: publication = published
    Worker->>SQS: enqueue type=search_index
    Note over SQS: transcript 없으면<br/>등록 metadata로 청킹
  else after_upload = draft (기본)
    Note over Worker,DB: draft 유지 후 종료<br/>(AI/발행/인덱싱 없음)
  end
```

즉 AI로 값을 채우는 단계는 옵션이고, 검색 인덱싱은 발행 완료 시점의 후속 작업입니다.

## metadata
AI로 내용 분석을 해서 채우기를 할 경우 강좌에 붙는 비디오마다 `VideoMetadataJob`을 만들고 SQS에 `type=metadata`를 넣습니다.
워커 `run_metadata_job`은 이를 받고 크게 두 작업을 합니다. `transcribe 추출` → `summarize 요약`

### 텍스트 추출
추출 시 직접 업로드하는 방식과 유튜브 링크를 사용하는지에 따라 분기가 나뉘죠.

| 소스 | 방식 |
| --- | --- |
| upload | HLS/원본 URL에서 ffmpeg로 모노 MP3 추출 → OpenAI Whisper |
| youtube | `youtube_transcript_api`로 한국어 자막(수동 우선, 없으면 자동 생성) |

```python
# YouTube → caption API / upload → ffmpeg + Whisper
def run_transcribe(job: VideoMetadataJob) -> VideoTranscript:
    video = job.video
    if video.source_type == VideoSourceType.YOUTUBE:
        merged = fetch_youtube_korean_captions(video.youtube_id or "")
        return _persist_transcript(...)

    # upload: extract mono mp3, chunk if over Whisper limit
    with extract_and_chunk_audio(video) as extracted:
        ...
```

업로드 후 영상에서 텍스트를 추출하는 STT(Speech To Text)는 Whisper를 채용했고 Whisper 업로드 바이트 한도(`WHISPER_MAX_UPLOAD_BYTES`, 기본 25MB)를 전제로 설계했습니다.<br/>

40~50분 정도인 영상에서 나오는 오디오가 25MB를 초과하면 데이터 손실이 발생할 수 있어서
한도를 넘을 때 청크 단위로 분리하여 진행해서 텍스트를 추출한 뒤 시간대를 기준으로 이어붙입니다.

세부 절차는 다음과 같습니다.

1. CDN HLS면 URL을 그대로 쓰고, 아니면 S3 key를 presign
2. 16kHz mono MP3로 오디오 추출
3. `WHISPER_MAX_UPLOAD_BYTES` 초과 시에만 분할 대상으로 보고 청크로 분할
4. 목표 청크 크기(`WHISPER_TARGET_CHUNK_BYTES`, 기본 22MB) 근처 무음 중점에서 자르고, 없으면 hard-cut
5. 청크마다 Whisper `verbose_json` 호출 후 `merge_chunk_results`로 병합
6. transcript JSON은 S3 `transcripts/.../raw.json`에 두고, DB `VideoTranscript`에는 object key만 남깁니다

`hard-cut`으로 나눌 때 데이터 손실이 발생할 수 있습니다.<br/>
그래서 다음 청크 시작을 `TRANSCRIPT_HARD_CUT_OVERLAP_SEC`(기본 0.8s)만큼 앞으로 당겨 경계 말을 한 번 더 듣게 하고, 병합 때는 이미 커버된 구간의 중복 세그먼트를 버립니다.

```python
# hard-cut: start를 overlap만큼 앞당겨 경계 설정
audio_start = start
if i > 0 and hard_flags.get(start, False):
    audio_start = max(0.0, start - overlap_sec)
    used_overlap = audio_start < start
```

```python
# overlap 구간: covered_until_ms와 겹는 부분 통합
if chunk.used_overlap and end_ms <= covered_until_ms:
    continue
if chunk.used_overlap and start_ms < covered_until_ms:
    start_ms = covered_until_ms
```

AI 키는 역할이 나뉩니다. upload STT(Whisper)는 OpenAI(데이터 추출) 키, 요약 LLM은 Gemini(텍스트) 키입니다. 필요한 키가 없으면 해당 단계가 stub으로 이어지고, 안내 description이 들어갑니다. YouTube 자막 추출은 OpenAI 키 없이 가능하고, 임베딩용 OpenAI 키는 `search_index` 단계에서 따로 씁니다.

### 요약과 media DB 적재
`transcript`가 준비되면 LLM(기본 Gemini)으로 DB에 적재할 데이터를 생성합니다.<br/>
프롬프트용으로 `transcript`를 나누는 청킹과 검색용 청킹은 한도와 용도, 파이프라인 시점이 달라지기에 서로 별개로 동작합니다.

LLM으로 다음 형태로 나오게 됩니다.
- `description`: 영상 요약(Markdown)
- `tags[]`
- `timelines[{ start_seconds, label, description }]` → `VideoTimeline`에 저장

검증과 repair를 거친 뒤 media 테이블에 직접 덮어씁니다.

```python
# LLM timelines → Video.description / tags / VideoTimeline
def apply_ai_fields_to_video(video, fields):
    video.description = str(fields.get("description") or "")
    video.save(update_fields=["description"])
    set_video_tags(video, list(fields.get("tags") or []))
    timelines = normalize_timelines_for_video(
        list(fields.get("timelines") or []),
        duration_seconds=video.duration_seconds,
    )
    sync_timelines_from_dicts(video, timelines)
```

코스 단위로는 비디오 메타 잡이 모두 끝나면, 최신 잡이 전부 성공이면 `review_status=review_required`로, 하나라도 실패하면 `failed`로 넘어갑니다. 사람이 확인한 뒤 발행하는 흐름이며, 이 단계에서는 검색 인덱싱을 하지 않습니다.

```mermaid
sequenceDiagram
  participant SQS
  participant Worker
  participant S3
  participant DB
  participant LLM as Gemini

  SQS->>Worker: type=metadata
  Worker->>DB: claim VideoMetadataJob
  Worker->>Worker: transcribe
  Worker->>S3: transcript JSON
  Worker->>DB: VideoTranscript key
  Worker->>LLM: summarize
  Worker->>DB: description / tags / timelines
  Worker->>DB: review_required
```

## search_index
검색 인덱스는 최종 발행 시점 이후에 오며 `publication_status=published`로 바꾼 뒤, 트랜잭션 commit 이후에 `search index job`을 적재합니다.

```python
# mark published
course.publication_status = CoursePublicationStatus.PUBLISHED
...
enqueue_search_index_after_publish(course_id=course.id)

# 발행 DB 커밋 성공 후에만 검색 인덱싱 enqueue (발행 실패면 넣지 않음)
def enqueue_search_index_after_publish(*, course_id: int) -> None:
    transaction.on_commit(
        lambda: schedule_search_index_for_published_course(course_id)
    )
```

`on_commit`을 쓰는 이유는 발행이 완료되면 인덱싱을 돌게 하고, 인덱싱이 실패해도 발행에는 영향을 주지 않기 위함입니다.

### 청킹
청크를 만드는 건 `VideoTimeline` 구간을 우선합니다.<br/>
하지만 청크에 넣는 본문 텍스트는 `transcript` 유무에 따라 갈리는데, transcript는 AI 메타 잡(`type=metadata`)의 STT/자막 단계에서만 생기고, 인코딩만으로는 만들어지지 않기 때문에 사용자의 행동에 따라 없을 수도 있습니다.
그래서 아래와 같이 동작합니다.

```mermaid
flowchart TB
  A["search_index 시작"] --> B{"VideoTranscript / segments 존재?"}
  B -->|예| C["타임라인 구간별 transcript 청킹"]
  C --> D["청크 = 영상명 + 태그 + 타임라인 메타 + 본문 텍스트"]
  B -->|아니오| E["metadata-only 청킹"]
  E --> F["청크 = 영상명 + description + 태그 + 타임라인 라벨/설명"]
  D --> G["embed + SearchChunk 적재"]
  F --> G
```

| 분기 | 조건 | 인덱싱에 쓰는 텍스트 |
| --- | --- | --- |
| transcript 기반 | S3 transcript JSON에 segment가 있음 | 영상 본문(STT/자막) + 영상명, 태그, 타임라인 정보 |
| metadata-only | transcript가 없거나 segment가 비어 있음 | `Video.name`, `description`, 태그, `VideoTimeline` 라벨/설명 |

metadata-only에 쓰이는 필드는 “사용자가 직접 쓴 값”일 수도 있고, 이전에 AI 요약이 채워 둔 값일 수도 있습니다.<br/>
AI 없이 바로 발행(`after_upload=publish`)하면 보통의 경우 transcript가 없어, 사람이 입력했거나 비어 있는 메타만으로 인덱싱됩니다.

조립한 청크 텍스트가 `SEARCH_CHUNK_MIN_CHARS`(기본 40)보다 짧으면 그 구간 청크는 만들지 않습니다.

transcript가 있을 때는 `VideoTimeline` 구간별로 segment를 모으고, `SEARCH_CHUNK_MAX_CHARS`(기본 1200)를 넘기면 저장(flush)하며 진행합니다. 이때도 영상명, 타임라인 라벨, 태그, 타임라인 설명은 헤더/보조 정보로 본문 앞에 붙습니다.

### 임베딩과 SearchChunk 적재
준비된 텍스트 목록을 `embed_texts`에 넘겨서 임베딩 작업을 합니다.<br/>
**※ 임베딩(Embedding)**: 사람이 쓰는 단어, 문장, 이미지 같은 복잡한 데이터를 컴퓨터가 이해할 수 있도록 숫자들의 배열(벡터)로 바꾸는 과정과 그 결과물

- 영상 소유자(`video.user`)의 OpenAI(transcript) 키가 있으면 `text-embedding-3-small`로 임베딩합니다.
- 키가 없으면 stub 해시 벡터로 파이프라인을 계속 진행합니다.

```python
# chunk → embed → replace SearchChunk
prepared = build_chunks_for_video(...)
texts = [c.text for c in prepared]

# embed_texts 내부: 키 유무 분기
# 내부에서 embedding_model_version을 토대로 사용
api_key, version = resolve_embedding_api_key(user=video.user)
if not api_key:
    embeddings = stub_embed_texts(texts)             # stub, 더미 벡터값 부여해서 의미 검색에서는 안쓰임
else:
    embeddings = openai_embed_texts(texts, api_key)  # text-embedding-3-small

chunk_count = _replace_chunks(
    video=video,
    prepared=prepared,
    embeddings=embeddings if texts else [],
    metadata_version=metadata_version,
    embedding_model_version=version,
)
```

임베딩이 끝나면 `_replace_chunks`가 해당 영상의 기존 `SearchChunk`를 지우고 새 행으로 업데이트합니다.<br/>
한 행에는 검색에 쓸 본문, FTS용 `search_vector`, 1536차원 `embedding`, 구간 시각, `metadata_version`이 같이 들어갑니다.

이미 같은 `metadata_version`과 `embedding_model_version`으로 `COMPLETED`인 인덱싱 잡이 있으면 다시 인덱싱하지 않게 하고,
강좌를 다시 draft로 내려도(`unpublish`) 청크 행은 지우지 않게 합니다. 대신 검색 API가 published 코스만 읽도록 막아 두었기 때문입니다.

```mermaid
sequenceDiagram
  participant API
  participant SQS
  participant Worker
  participant DB
  participant Emb as Embeddings

  API->>DB: published
  API->>SQS: type=search_index (on_commit)
  SQS->>Worker: receive
  Worker->>DB: published / transcript / timelines 확인
  Worker->>Worker: 타임라인 구간 우선 청킹
  Worker->>Emb: embed_texts
  Worker->>DB: SearchChunk replace (FTS + embedding)
```

## 검색 랭킹
발행된 강좌의 `SearchChunk`만 `GET /api/v1/search?q=`로 검색합니다.<br/>
최종 순위는 FTS·벡터·조회수라는 세 점수를 후보 집합 안에서 각각 0~1로 맞춘 뒤 가중합하는 점수 합산 방식입니다.

사용되는 점수는 세 가지입니다. 키워드 점수(FTS `SearchRank`), 의미 점수(임베딩 cosine), 인기 점수(강좌 `view_count`)입니다. 단위가 다른 점수들을 후보 집합 안에서 같은 스케일로 맞춘 뒤 더합니다.

### 이 방식의 이유
해보고 싶던 작업은 원하는 키워드로도 검색이 가능하고, 키워드가 살짝 다르지만 비슷하게 통용되는 단어로도 검색이 가능한 기능을 만드는 것이었습니다. 거기에 조회수를 조금 반영해, 비슷한 사용자들이 원하는 강의의 우선순위도 높이고 싶었습니다.

글을 쓰는 시점에서의 검색 기능은 다음과 같습니다.
- 키워드만 쓰면 표현이 조금만 달라도 놓치고, 벡터만 쓰면 고유명사·정확한 용어 매칭이 약해집니다. 둘을 후보로 모은 뒤 점수를 섞으면 둘의 빈틈을 서로 보완합니다.
- 조회수는 강좌의 `view_count`를 가져와 0.10 비중으로 소량만 반영합니다.
- 처음에는 비중을 `0.45 / 0.45 / 0.10`으로 두었습니다. 아직은 원활한 동작을 위한 점수 배점에 대한 데이터가 없기에, 개발자 친화적인 검색 결과 화면을 사용합니다.

추후에는 여러 모델에서 나온 벡터를 녹일 수 있도록 RRF도 고려해보고 있습니다.

### 모델명이 같아야 의미 점수가 붙는다
현재 벡터 비교는 같은 임베딩 모델이 만든 좌표끼리만 의미가 있습니다.<br/>
인덱싱·검색 모두 `embedding_model_version`에 `openai:<모델명>`(기본 `openai:text-embedding-3-small`) 또는 키 없을 때 `stub-v1`을 넣어서 동작합니다.

- 검색어를 임베딩한 모델명과 `SearchChunk.embedding_model_version`이 같으면 의미 점수를 쓰고 하이브리드 검색으로 갑니다.
- 키가 없거나 stub이거나, 모델명이 맞는 청크가 없으면 의미 점수를 빼고 FTS+조회수 기본 베이스(`fts_only`)로 갑니다.

```mermaid
sequenceDiagram
  participant Client
  participant API
  participant DB
  participant OpenAI

  Client->>API: GET /api/v1/search?q=
  API->>DB: 키워드 점수 FTS 후보 (SearchRank top-N)
  API->>API: 요청 유저의 OpenAI 키 확인
  alt OpenAI 키가 있고 임베딩 성공
    API->>OpenAI: 검색어 임베딩 요청
    OpenAI-->>API: 쿼리 벡터와 openai:모델명
    alt 같은 모델명의 인덱스 벡터가 있음
      API->>DB: 의미 점수 벡터 후보 (cosine top-N)
      Note over API: FTS와 벡터 후보를 합침
      Note over API: mode = hybrid
    else 같은 모델명 청크가 없음
      Note over API: 의미 점수 제외, FTS+조회수 베이스
      Note over API: mode = fts_only
    end
  else 익명 / 키 없음 / OpenAI가 아님 / 임베딩 실패
    Note over API: stub-v1이면 의미 점수를 건너뜀
    Note over API: mode = fts_only
  end
  API->>DB: 후보 청크와 인기 점수 view_count 조회
  Note over API: 점수별 0~1 정규화 후 가중합
  API-->>Client: 검색 결과
```

구현 흐름은 다음과 같습니다.

1. 키워드 점수: FTS로 `search_vector`에 걸린 청크를 상위 N개 뽑습니다. N은 `SEARCH_QUERY_CANDIDATE_LIMIT`(기본 50)입니다.
2. API는 검색 요청 유저의 transcript용 OpenAI credential을 확인합니다. 익명이거나 키가 없거나 provider가 OpenAI가 아니면 `stub-v1`입니다.
3. OpenAI 키가 있으면 그 키로 검색어를 임베딩하고, 쿼리 벡터와 `openai:<모델명>`을 얻습니다.
4. `SearchChunk.embedding_model_version`이 그 모델명과 같은 행만 cosine 상위 N개로 뽑습니다. 후보가 있으면 FTS와 합쳐 `hybrid`입니다.<br/>
   인덱스 벡터는 영상 소유자(교사) 키로 만들어지고, 검색 벡터는 요청 유저 키로 만들어집니다. 키가 달라도 모델명이 같으면 의미 점수를 쓸 수 있고, 모델명이 다르면 의미 점수만 빠집니다.
5. stub이거나 임베딩 실패이거나 같은 모델명 후보가 없으면 `fts_only`로, FTS+조회수 기본 베이스만 씁니다.
6. 인기 점수: 후보에 강좌 `view_count`를 붙입니다.
7. 세 점수를 각각 min-max로 0~1에 맞춘 뒤 가중합합니다. `hybrid`는 FTS 0.45 + Vector 0.45 + 조회수 0.10입니다. `fts_only`는 벡터 항을 빼고 두 비중의 합으로 나눕니다.

키워드 점수는 Postgres FTS로 가져옵니다. <br/>
`SearchQuery`로 `search_vector`에 걸린 발행 청크만 남기고, `SearchRank`로 정렬합니다, 짧은 검색어에서 `websearch`가 비면 `plain`으로 한 번 더 조회합니다.

```python
# chunk_id -> raw FTS rank (높을수록 좋음)
def _fts_candidates(*, query: str, limit: int) -> dict[int, float]:
    sq = SearchQuery(query, config="simple", search_type="websearch")
    qs = (
        _published_chunks()
        .filter(search_vector=sq)
        .annotate(fts_rank=SearchRank(F("search_vector"), sq))
        .order_by("-fts_rank")[:limit]
    )
    rows = list(qs)
    if not rows:
        sq = SearchQuery(query, config="simple")
        qs = (
            _published_chunks()
            .filter(search_vector=sq)
            .annotate(fts_rank=SearchRank(F("search_vector"), sq))
            .order_by("-fts_rank")[:limit]
        )
        rows = list(qs)
    return {row.id: float(row.fts_rank or 0.0) for row in rows}
```

의미 점수는 같은 `embedding_model_version` 행만 대상으로 `CosineDistance`를 씁니다. 거리가 작을수록 가깝고, 점수로 쓸 때는 `1 - distance`로 바꿔 대략 0~1 유사도로 둡니다.

```python
# chunk_id -> similarity ≈ 1 - cosine distance
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

후보 집합은 FTS 결과와 벡터 결과를 합친 `chunk_id`입니다. <br/>
이 집합 안에서 FTS·벡터·조회수를 각각 min-max로 0~1에 맞춘 뒤 가중합합니다.

```python
# hybrid: FTS+벡터+조회수 / fts_only: 벡터 제외
def combine_hybrid_scores(...):
    if mode == "fts_only":
        total_w = w["fts"] + w["popularity"]
        return (w["fts"] * fts_norm + w["popularity"] * popularity_norm) / total_w
    return (
        w["fts"] * fts_norm
        + w["vector"] * vector_norm
        + w["popularity"] * popularity_norm
    )
```

# 개선점
우선적으로 파악된 개선점과 기능 추가 건이 몇 건 있었습니다.

1. 유사도 하한이 없고, 결과는 청크 단위라 같은 강좌의 여러 구간이 상위권에 같이 올라올 수 있는 부분을 해결할 것
2. 현재 점수 배점 방식이 사용자에게 정말 편한 방식인지 확인할 것 (UI, UX, 점수 결과)
3. 임베딩 모델이 달라지면 의미 검색이 안 걸리는 방식에 대한 해결법을 적용할 것
4. 이미 검색했던 검색어는 DB에 저장해 임베딩 작업을 반복하지 않게 처리할 것
5. 한국어 FTS 최적화. 단순 토큰 방식이다 보니 한국어 형태소 단위 검색이 약한 점을 보완할 방법
6. Elasticsearch와 같은 검색 엔진 도입 검토

# 정리
인덱싱부터 검색까지를 한 장으로 보면 다음과 같습니다. metadata는 선택 경로이고, 검색 인덱싱은 발행 이후에만 붙습니다.

```mermaid
flowchart LR
  A["업로드"] --> B["publish<br/>HLS"]
  B --> C["metadata<br/>(선택: AI 채우기)"]
  B --> D["최종 발행"]
  C --> D
  D --> E["search_index<br/>청킹 / 임베딩"]
  E --> F["SearchChunk"]
  F --> G["search API<br/>FTS + vector + 조회수"]
```

다음 글에서는 개선점과 현재 기능 최적화, 테스트, 코드 리뷰를 더 정밀히 진행할 예정입니다.<br/>
가중치·융합 방식·임베딩 버전 일치·결과 집계처럼 파이프라인과 알고리즘 단위로 좀 더 나은 방안과 흐름을 이해하는 게 목적입니다.