---
title: "6편. 콘텐츠의 출처를 증명하는 C2PA는 무엇일까?"
date: 2026-10-31T11:05:00+09:00
categories: [ "Watermark" ]
series: [ "watermark" ]
tags: [ "C2PA", "Content Credentials", "Provenance" ]
draft: true
description: "콘텐츠 출처 표준 C2PA의 Manifest를 생성하고 서명과 검증을 거칩니다. 이미지를 수정한 뒤 Content Credentials와 출처 이력이 어떻게 바뀌는지도 실험합니다."
keywords: [ "C2PA", "Content Credentials", "Provenance", "Manifest", "워터마크" ]
author: "DSeung001"
lastmod: 2026-10-31T11:51:00+09:00
---

C2PA Manifest를 만들어 서명하고 검증한 뒤, 콘텐츠를 수정하면 무엇이 바뀌는지 봅니다. C2PA(Coalition for Content Provenance and Authenticity)는 콘텐츠의 출처와 편집 이력을 담는 표준이고, Content Credentials는 그 표준으로 콘텐츠에 붙는 출처 정보입니다. 프로비넌스(Provenance)는 콘텐츠가 어디서 왔고 이후 어떻게 바뀌었는지에 대한 이력입니다.

> 임시 초안입니다. Manifest 필드 이름은 스펙을 대조하기 전에 확정하지 않습니다.

## Manifest 생성

Manifest에는 콘텐츠에 대한 주장과 그 근거가 들어갑니다. 임시로 다룰 항목은 작성 도구, 생성 시각, 원본 해시입니다. 실제 필드 이름과 필수 여부는 스펙을 대조한 뒤에 이 문단을 고칩니다.

## 서명과 검증

Manifest를 서명하고, 검증기에서 서명이 유효한지와 해시가 현재 바이트와 맞는지 확인합니다. 사용할 라이브러리와 인증서 형식은 구현 전에 고릅니다.

## 수정 이후의 변화

이미지를 크롭하거나 다시 저장한 뒤 같은 검증을 돌립니다. 서명이 깨지는지, 수정 이력이 새 Manifest로 이어지는지 관찰하고 결과를 이 자리에 적습니다. 지금은 관찰 항목만 있습니다.
