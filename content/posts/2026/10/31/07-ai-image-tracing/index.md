---
title: "7편. AI가 만든 이미지도 추적할 수 있을까?"
date: 2026-10-31T11:06:00+09:00
categories: [ "Watermark" ]
series: [ "watermark" ]
tags: [ "AI Watermarking", "SynthID", "Provenance" ]
draft: true
description: "AI가 만든 이미지에 LSB 워터마크와 C2PA 출처 정보를 넣습니다. 수정과 재배포 이후에도 SynthID를 포함해 생성 사실을 추적할 수 있는지 같은 조건에서 비교합니다."
keywords: [ "AI Watermarking", "SynthID", "Provenance", "C2PA", "워터마크" ]
author: "DSeung001"
lastmod: 2026-10-31T11:51:00+09:00
---

AI가 만든 이미지에 워터마크와 출처 정보를 넣고, 수정과 재배포 이후에도 따라갈 수 있는지 비교합니다. SynthID는 Google이 생성형 미디어에 넣는 워터마크로 알려져 있으며, 삽입 방식의 세부 동작은 공개 명세만으로 단정하지 않고 실험에서 확인합니다.

> 임시 초안입니다. SynthID 삽입 절차는 사용 가능 여부를 확인하기 전에 적지 않습니다.

## 생성 이미지에 워터마크와 출처 정보 넣기

생성 결과에 1편의 LSB 식별자와 C2PA 출처 정보를 함께 붙이는 경우를 기준으로 둡니다. SynthID는 생성 모델이 출력에 직접 심는 워터마크로 알려져 있으나, 이 글의 실험 환경에서 그 API를 쓸 수 있는지는 확인이 필요합니다.

## 수정과 재배포 이후 추적 비교

같은 생성 이미지를 수정한 뒤, LSB 추출 성공 여부, C2PA 검증 결과, SynthID 검출 가능 여부를 표로 비교합니다. 검출이 안 되는 칸은 실패로 단정하기 전에 도구 지원 여부를 먼저 확인합니다.
