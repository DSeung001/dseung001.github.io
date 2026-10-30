---
title: "1편. 이미지 속에 데이터를 숨길까"
date: 2026-10-30T11:00:00+09:00
categories: [ "Watermark" ]
series: [ "watermark" ]
tags: [ "Pixel", "RGB", "LSB", "Steganography" ]
draft: true
description: "기초적인 워터마크 시스템을 알기위한 기초 작업"
keywords: [ "워터마크", "Pixel", "RGB", "LSB", "Steganography" ]
author: "DSeung001"
lastmod: 2026-10-30T12:30:00+09:00
---

## 이미지 데이터 구조 

## LSB 알고리즘 

## 성능 평가 지표

### PSNR: 이미지 품질
### SSIM: 구조적 유사성
### BER: 워터마크 복원 정확도
### Capacity: 삽입 용량

## 참고 자료

- 이미지 표현은 [PNG 4.2 Images](https://www.w3.org/TR/png-3/#4Concepts.Sourceimage), 샘플 깊이는 [4.4.5 Sample depth scaling](https://www.w3.org/TR/png-3/#x4-4-5-sample-depth-scaling), 무손실 압축은 [10. Compression](https://www.w3.org/TR/png-3/#x10-compression)에서 확인한다.
- 워터마킹 성질의 정의는 [Nyeem 등의 4장](https://asp-eurasipjournals.springeropen.com/articles/10.1186/1687-6180-2014-135#Sec10)에 있다.
- PSNR(Peak Signal-to-Noise Ratio, 최대 신호 대비 잡음 비율)의 한계와 SSIM(Structural Similarity Index, 구조 유사도)은 [Wang 등의 논문](https://ece.uwaterloo.ca/~z70wang/publications/ssim.pdf)에서 본다.
- PSNR, SSIM, MSE(Mean Squared Error, 평균 제곱 오차)의 계산식은 [scikit-image Metrics](https://scikit-image.org/docs/stable/api/skimage.metrics.html)에 있다.