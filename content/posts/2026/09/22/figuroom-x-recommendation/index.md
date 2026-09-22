---
title: "추천 시스템 분석 — FiguRoom 커뮤니티 전략"
date: 2026-09-22T09:00:00+09:00
categories: [ "Project", "FiguRoom", "Subculture" ]
series: [ "figuroom" ]
tags: [ "X", "추천 시스템", "SNS 마케팅", "서브컬처" ]
draft: true
description: "FiguRoom 커뮤니티 확장을 위해 X(트위터) 추천 시스템을 분석한 기록"
keywords: [ "FiguRoom", "X 추천 알고리즘", "Twitter", "SNS", "서브컬처", "커뮤니티" ]
author: "DSeung001"
lastmod: 2026-09-22T09:00:00+09:00
---

## 목표

모두의 창업을 통해 피규룸 서비스를 기획 중이고 준비 중에 가장 먼저 만난 장애물은 홍보와 초기 사용자 층 확보로 생각됩니다.

그래서 [저번 글](../../18/figuroom-landing-survey/)에서처럼 커뮤니티를 만들자고 생각했고, 서브컬처 문화에서 가장 홍보가 효과적인 곳은 X라는 생각이 들어 홍보 계정을 만들고 일일 2개에서 4개의 포스트를 작성하고 있습니다. 

그런데 당연한 이야기지만 조회수 20~40에서 머무르고 있다는 게 마음에 들지 않았고 이를 해결할 방법을 고민한 결과 X 알고리즘에 대해서도 궁금증이 들었습니다, 현재 1차 MVP로 생각하는 것도 결국 X와 유사한 시스템이니 미리 공부해 두면 좋을 것 같고요.

## 조사 방향

전체 다 일일이 로직을 까보는 것도 좋지만, 전체적인 데이터 흐름과 시스템 구조를 파악하는 데 우선을 둡니다.
Class 프로젝트에서 검색(Search), 추천(Recommendation), 랭킹(Ranking), 임베딩(Embedding)을 다뤄봤기에, 우선 대형 시스템의 Retrieval → Ranking → Re-ranking이라는 큰 구조를 중심으로 검색과 추천을 이해해 보려 합니다.

검색 자체는 사용자의 사용 이력과 경험을 바탕으로 가중치를 높여 주는 걸로 나뉩니다.
> 후보를 먼저 좁히고(Retrieval), 후보마다 여러 신호를 계산한 다음, 그 신호들을 조합해서 최종 점수를 만드는 경쟁이다.

이에 대해서 23년도에 일론 머스크가 트위터 추천 알고리즘을 공개했기에 그걸 참고하는 걸 가장 큰 축으로 둡니다.
또한 현재 코드 또한 상용 버전이 아닌 실험 버전이지만 공개하고 있기에, 이를 토대로 X 계정 운영 방향에 도움도 받을 수 있을 것 같습니다.

## 참고 자료

### xAI x-algorithm — 현재 X For You 파이프라인의 공개 실험 코드

> https://github.com/xai-org/x-algorithm/blob/main/README.md

xAI가 공개한 최근 X 추천 코드입니다. 
상용 로직과는 다를 수 있지만, 지금 계정 운영에 맞대볼 후보 생성, 랭킹, 필터 흐름을 코드 기준으로 따라가기 위해 인용합니다.

### twitter/the-algorithm — 2023년 공개된 Home Timeline 추천 오픈소스

> https://github.com/twitter/the-algorithm/blob/main/README.md

일론 머스크 인수 직후 Twitter가 공개한 추천 시스템입니다. 
현재 x-algorithm과 비교해 무엇이 남고 바뀌었는지 보는 기준선으로 씁니다.

### GraphJet (VLDB 2016) — Twitter의 실시간 그래프 기반 콘텐츠 추천

> https://www.vldb.org/pvldb/vol9/p1281-sharma.pdf

유저-트윗 상호작용을 메모리 위 이분 그래프로 유지하고, random walk 계열로 실시간 후보를 뽑는 구조를 설명한 Twitter 논문입니다. Retrieval 단계가 왜 그래프와 상호작용 신호에 기대는지 이해하려고 인용합니다.

### Deep Neural Networks for YouTube Recommendations (RecSys 2016) — Candidate Generation + Ranking 이단 구조

> https://dl.acm.org/doi/epdf/10.1145/2959100.2959190

수백만 후보를 가벼운 모델로 수백 개로 줄인 뒤(Candidate Generation), 무거운 모델로 정밀 점수화(Ranking)하는 산업 표준 이단 구조를 YouTube 사례로 정리한 논문입니다. 글에서 잡은 Retrieval → Ranking → Re-ranking 큰 틀을 다른 대형 서비스와 맞춰 보는 데 씁니다.
