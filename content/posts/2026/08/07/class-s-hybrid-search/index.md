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

# 개요

Class S 프로젝트에 하이브리드 검색을 붙이려 합니다.

영상 업로드부터 검색까지 이어지는 흐름을 한 줄로 정리하면 다음과 같습니다.

1. 영상 업로드
2. 영상을 텍스트로 변환
3. 텍스트에서 검색에 쓸 데이터 추출
4. 추출한 데이터를 인덱싱
5. 인덱스를 바탕으로 검색

이후 글에서는 각 단계를 구현하면서 겪은 선택과 결과를 정리할 예정입니다.


업로드 AI/검색 파이프라인은 이미 잡 단위로 나뉘어 있고, 말씀하신 4가지는 그 안에서 이렇게 매핑됩니다.

현재 구조 (범위 기준선)
PublishJob (HLS/초안)
  └─ after_upload=ai → VideoMetadataJob
        ├─ 1) transcribe   (자막/STT)
        └─ 2) summarize    (요약·태그·타임라인/챕터)  ← 4번에 해당
  └─ 최종 공개(publish_course_final)
        └─ SearchIndexJob
              ├─ chunk + embed  ← 2번
              └─ SearchChunk
                    └─ search_query (읽기)  ← 3번
중요: VideoMetadataJobStep에 chapters / embed가 있지만, 메타 러너는 실질적으로 transcribe → summarize만 돌립니다. 타임라인은 summarize 안에서 media에 쓰고, EMBED는 SearchIndexJob으로 분리되어 있습니다 (docs/tving/03-ai-metadata-slice.md에도 명시).

제안 범위 (In / Out)
In scope — 말씀하신 4개
#	영역	실제 경계	핵심 파일
1
자막 추출
run_transcribe + provider + audio/YouTube
transcribe.py, audio_extract.py, youtube_captions.py, providers
2
인덱스 임베딩
SearchIndexJob runner + chunking + embedding
search_index_job_runner.py, search_chunking.py, search_embedding.py
3
검색
읽기 경로 hybrid query
search_query.py, views_search.py
4
요약·타임라인
generate_and_apply_metadata + schema/apply
metadata_generate.py, metadata_schema.py, ai_stub.py(timeline 적용)
함께 손대면 좋은 “경계 레이어” (반쯤 In)
고도화만 해도 자주 걸리므로, 잡 orchestration은 범위에 넣는 것을 추천합니다.

metadata_job_runner / search_index_job_runner — step 재개, claim, fail/retry
job_service / enqueue / queue — 재시도·배치 abort
finalize_course_review_if_ready — 코스 review_status 전이
상수 정리 — CHAPTERS/EMBED 레거시 vs 실제 SearchIndexJob
Out of scope로 두는 게 좋은 것 (1차)
영역	이유
PublishJob / HLS 인코딩
업로드·미디어 파이프라인. AI 고도화와 목적이 다름
썸네일 AI
별도 동기 잡, Gemini 키만 공유
publish discard / staging cleanup
미디어 수명주기
프론트 업로드 UI 전면 개편
폴링/실패 메시지 정도만 필요할 수 있음
다만 트리거 지점은 인지해야 합니다: AI는 start_ai_analysis, 검색 인덱스는 publish_course_final의 on_commit.

추가로 신경 쓸 부분 (범위 지정 시)
큐 격리
publish / metadata / search_index가 같은 SQS·워커입니다. STT·임베딩 최적화해도 인코딩과 서로 블로킹될 수 있어, “성능” 목표면 큐/워커 분리를 별 이슈로 빼두는 게 좋습니다.

아티팩트 SSOT
transcript는 VideoTranscript(+S3), 메타 산출은 output_object_key, 검색은 SearchChunk + metadata_version. 리팩터 시 어느 것이 진실인지를 먼저 고정하세요.

공개 후 수정 → 인덱스 stale
최종 공개 때만 인덱싱하고, course/video edit 후 재인덱싱 트리거가 약합니다. 검색 고도화 범위에 **“재인덱싱 정책”**을 넣을지 미리 정하세요.

AI 재실행 = media 덮어쓰기
description/tags/timeline 보호 없음. 요약·타임라인 개선 시 UX/정책도 범위에 넣을지 결정이 필요합니다.

실패 격리
SearchIndex 실패해도 publication은 유지, metadata 일부 실패 시 course failed. 최적화 중 “성공 정의”가 흔들리지 않게 문서화하는 게 좋습니다.

비용·usage
STT(OpenAI) / 메타(Gemini) / embed(OpenAI)가 갈라져 있고 usage 로그가 있습니다. 재시도·repair 시 중복 과금이 회귀 포인트입니다.

범위 지정 추천 (작업 쪼개기)
고도화 순서도 의존성에 맞추면 이렇게가 깔끔합니다.

자막 — 독립적, 이후 전부 의존
요약·타임라인 — transcript 입력 계약 유지
인덱싱(임베딩) — transcript + 확정 media 필드 계약
검색 — SearchChunk 스키마/버전 계약
또는 “계약 먼저”로:

Phase 0: 입출력 계약 정리 (transcript JSON, metadata schema, chunk/metadata_version, search response)
Phase 1~4: 위 순서대로 내부 최적화
한 줄로 정리
In: 자막 → 메타(요약·타임라인) → 검색인덱싱 → 검색 쿼리 (+ 각 job runner/재시도).
Out(1차): Publish/HLS, 썸네일, discard.
별도 이슈로 명시: 공용 SQS 블로킹, 공개 후 재인덱싱, AI 덮어쓰기 정책.

원하시면 다음으로 Phase 0 계약 체크리스트(필드·버전·idempotency)나 영역별 고도화 후보 목록(병목 추정)으로 더 좁혀 드리겠습니다. Agent 모드로 전환하시면 코드 기준으로 이슈 백로그도 같이 잡을 수 있습니다.