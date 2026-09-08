---
title: "강의 영상에 DRM 붙이기 — MPEG-DASH와 Clear Key (Class Project)"
date: 2026-09-08T10:00:00+09:00
categories: [ "Project", "Class Project" ]
series: [ "class-s-project" ]
tags: [ "DRM", "Clear Key", "MPEG-DASH", "Shaka Player" ]
draft: true
description: "넷플릭스와 라프텔의 상용 DRM을 참고하되 Widevine은 쓰지 않고, Class S 신규 강의를 MPEG-DASH와 Clear Key로 바꾼 과정. Shaka Player에서 라이선스가 안 나가던 이슈까지."
keywords: [ "DRM", "Clear Key", "MPEG-DASH", "Shaka Player", "EME", "CENC", "DASH" ]
author: "DSeung001"
lastmod: 2026-09-08T10:30:00+09:00
---

## OTT 사이트의 DRM 방식

<!-- 넷플릭스: Widevine / FairPlay / PlayReady, MPEG-DASH. 상용 라이선스 서버. 브라우저에서 직접 본 매니페스트·라이선스 경로. -->
<!-- 라프텔: 같은 기준으로 본 DRM과 플레이어. 넷플릭스와 다른 점. -->

상용 OTT는 브라우저 CDM(Content Decryption Module, 브라우저 안의 복호화 모듈)에 유료 키 시스템을 붙입니다. Widevine은 Google이 만든 DRM이고, Netflix 같은 서비스가 Chrome과 Android에서 씁니다. FairPlay는 Apple, PlayReady는 Microsoft 쪽입니다. Class S에는 그 라이선스 비용을 들일 이유가 없어서, 브라우저 EME(Encrypted Media Extensions, 웹에서 CDM에 라이선스를 요청하는 API) 경로만 검증하는 Clear Key로 범위를 잘랐습니다.

## Class 프로젝트에 적용 범위 정하기

목표는 세그먼트 파일만 따로 열어 재생하는 경로를 막고, 공개 강좌는 예전처럼 비로그인도 보게 하는 것이었습니다. 화면 녹화와 복호화 추출을 완전히 막는 상용 DRM은 범위 밖입니다. Clear Key는 라이선스 API가 열려 있으면 키도 같이 열리므로, 다운로드 차단의 최종 수단이 아닙니다.

기존 산출물은 MPEG-TS HLS였습니다. HLS는 HTTP로 플레이리스트와 세그먼트를 받아 이어 재생하는 방식이고, Class S는 `index.m3u8`과 평문 `seg_*.ts`를 `hls.js`로 붙이고 있었습니다. CENC(Common Encryption, ISO/IEC 23001-7)는 ISO BMFF(fMP4) 샘플 암호화라서, 그 `.ts` 위에 키만 얹을 수 없습니다.

HLS에 `#EXT-X-KEY:METHOD=AES-128`을 붙이는 방법도 있습니다. 그건 플레이어 JS가 키 파일을 GET하는 경로라서, 이번에 만든 `drm-license/clearkey`처럼 브라우저 CDM이 W3C Clear Key JSON을 POST하는 흐름을 검증하지 못합니다. Safari의 FairPlay는 SPC/CKC 바이너리라 이번 JSON API와 다른 스택입니다.

그래서 기존 HLS 파일은 `playback_format=hls`로 남기고, 신규 업로드만 DASH와 CENC로 패키징했습니다. 유튜브 소스는 이 파이프라인 밖입니다.

## 적용하기

신규 업로드는 `encode_dash_cenc_vod()`가 `-f dash`로 `manifest.mpd`, `init-*.m4s`, `chunk-*.m4s`를 만듭니다. MPEG-DASH는 HTTP 적응형 스트리밍이고, 플레이어가 MPD(Media Presentation Description, DASH 매니페스트)를 읽은 뒤 비트레이트에 맞는 세그먼트를 가져옵니다. 화질 프로필은 기존 HLS와 같고, 컨테이너와 `-format_options encryption_scheme=cenc-aes-ctr`만 바꿉니다. ffmpeg dash 뮤서는 세그먼트만 암호화하고 MPD에 `ContentProtection`을 쓰지 않아서, 인코딩이 끝난 뒤 `_inject_cenc_content_protection()`이 AdaptationSet에 직접 넣습니다.

`Video`에는 `playback_format`, `drm_key_id`, `encrypted_drm_key`를 추가했습니다. 영상마다 CENC kid/key를 만들고, key는 `DRM_FERNET_KEY`로 감싸 DB에 둡니다. 재생 응답의 `drm`에는 `org.w3.clearkey`, 라이선스 URL, kid만 내려갑니다.

백엔드는 `POST /api/v1/media/videos/{video_id}/drm-license/clearkey`입니다. 공개(`PUBLISHED`) 강좌는 `AllowAny`로 익명도 200을 받고, draft/비공개는 소유자와 커리큘럼 멤버만 받습니다. 프론트는 평문 HLS를 `hls.js`로 유지하고, `playback_format: "dash"`이거나 `.mpd`일 때만 Shaka Player를 동적 import합니다. Shaka의 `drm.servers['org.w3.clearkey']`가 그 JSON을 그대로 POST해서, FairPlay CKC나 Widevine protobuf 변환이 필요 없습니다.

자막 추출은 암호화된 DASH를 다시 읽어야 해서, `resolve_video_ffmpeg_input_options()`가 `-cenc_decryption_key`를 붙입니다. 로컬 Mac ffmpeg가 그 옵션이 없으면 STT가 깨지므로, `scripts/check-ffmpeg-drm.sh`가 DASH demuxer help에 `cenc_decryption_key`가 있는지 확인하고 worker 이미지 빌드에서도 같은 검사를 돌립니다.

강좌 수정 화면 미리보기는 처음에 `playback_format`과 `drm`을 안 넘겨서, DASH 영상을 HLS 엔진으로 열려고 했습니다. `VideoTimelineEditor`와 `VideoUploadTimelineStep`에 값을 배선하고, Shaka `error` 이벤트가 콘솔에만 묻히지 않게 화면에 띄웠습니다.

## 어려웠던 점

세그먼트는 암호화돼 있는데 재생이 안 되는 상태가 있었습니다. ffmpeg가 만든 MPD에 `ContentProtection`이 없으면 Shaka가 평문으로 보고 EME 세션을 시작하지 않습니다. 그래서 MPD에 `urn:mpeg:dash:mp4protection:2011`과 W3C ClearKey UUID `1077efec-c0b2-4d02-ace3-3c1e52e2fb4b`를 넣었습니다.

그래도 라이선스 요청이 나가지 않았습니다. Shaka는 DASH-IF UUID `e2719d58-a985-b3c9-781a-b030af78d30e`가 있을 때만 `default_KID`로 Clear Key initData를 만듭니다. `1077efec`만 있으면 ffmpeg CENC init에 없는 in-band pssh를 기다립니다. 인코더가 DASH-IF `ContentProtection`을 같이 넣고, 이미 올라간 MPD는 플레이어가 응답 필터에서 같은 태그를 보강하도록 고쳤습니다.
