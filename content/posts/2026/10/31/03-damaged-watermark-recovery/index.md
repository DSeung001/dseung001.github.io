---
title: "3편. 훼손된 워터마크를 복구할 수 있을까?"
date: 2026-10-31T11:03:00+09:00
categories: [ "Watermark" ]
series: [ "watermark" ]
tags: [ "ECC", "Reed-Solomon", "Redundancy" ]
draft: true
description: "훼손된 LSB와 DCT 워터마크를 반복 삽입과 오류 정정으로 복원하고, 압축과 블러, 해상도 변경 이후의 복구율을 비교합니다."
keywords: [ "워터마크", "ECC", "Reed-Solomon", "Redundancy", "오류정정" ]
author: "DSeung001"
lastmod: 2026-10-31T21:22:00+09:00
slug: "03-damaged-watermark-recovery"
aliases:
  - /posts/2026/10/31/03-watermark-recovery/
---

## 워터마크 복구
- 훼손된 이미지에서 삽입된 데이터를 얼마나 정확하게 복원할 수 있는지 알아본다.
## 전략
- 반복 삽입과 다수결(Majority Voting): 동일한 비트를 여러 위치에 삽입하고 다수결로 복구한다.
- 오류 정정 코드(ECC): Hamming Code, Reed–Solomon 등을 활용해 손상된 데이터를 복구한다.
## LSB와 DCT에 적용
- 기존 LSB와 DCT 구현에 복구 전략을 적용하고 차이를 확인한다.
## 실험
- JPEG 압축, Blur, Resize 공격 이후 각 알고리즘의 복구 성능을 측정한다.
- BER, 완전 복구율, 삽입 용량 등을 기준으로 복구 전후 성능을 비교한다.
## 한계
- 복구가 불가능한 상황과 복구율을 높이기 위한 대가를 분석한다.
- 실험 결과를 바탕으로 실제 이미지 유출 추적 시스템에 적용할 수 있는지 판단한다