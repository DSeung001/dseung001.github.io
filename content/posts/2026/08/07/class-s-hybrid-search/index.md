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
