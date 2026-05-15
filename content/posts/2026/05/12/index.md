---
title: "Anime Search Project: Whisper와 Timestamp Transcript"
date: 2026-05-12T00:00:00+09:00
categories: [ "Project", "Anime Search", "Digging" ]
tags: [ "Anime Search", "Whisper", "STT", "Timestamp Transcript", "Audio", "Speech Recognition" ]
draft: true
description: "애니메이션 대사로 검색해보자"
keywords: [ "Anime Search", "Whisper", "STT", "Timestamp Transcript", "Speech Recognition", "Audio Transcription" ]
author: "DSeung001"
lastmod: 2026-05-12T00:00:00+09:00
---

애니메이션 명장면 자연어 검색을 만들 때 이미지 프레임을 이해하는 일과 대사를 이해하는 일은 서로 다른 문제라고 느꼈습니다. 그래서 `CLIP`은 프레임 이미지와 텍스트 쿼리의 유사도를 비교하는 쪽으로 두고, `Whisper`는 오디오를 전사해 시간 정보가 붙은 대사 데이터를 만드는 쪽으로 나누어 접근하려 합니다.

# Whisper와 Timestamp Transcript
`Whisper`는 비정형 오디오 스트림을 구조화된 텍스트와 시간 데이터로 변환해주는 Transformer 기반 음성 인식 모델입니다.
`Whisper`는 기본적으로 Transformer 기반의 Encoder-Decoder 아키텍처를 가지고 흐름은 다음과 같습니다.
- **Audio Input & Chunking**: 긴 오디오 파일을 30초 단위의 청크(Chunk)로 자릅니다. (Out Of Memory 방지)
- **Log-Mel Spectrogram 변환 (전처리)**: 오디오 파형(Waveform)을 주파수 대역의 시각적 이미지 형태(Spectrogram)로 변환합니다. 즉, 소리를 이미지로 바꾸어 처리합니다.
- **Encoder**: 스펙트로그램 데이터를 분석하여 오디오의 특징(Feature) 벡터를 추출합니다.
- **Decoder**: 추출된 특징 벡터를 바탕으로 다음 단어를 예측하며 텍스트를 생성합니다. 이때 언어 감지(Language ID), 음성 인식, 번역 등의 태스크를 동시에 수행할 수 있습니다.

이에 따른 처리 순서는 아래와 같습니다.

1. Audio Input & Chunking
2. Log-Mel Spectrogram
3. Encoder가 특징(Feature) 벡터를 뽑습니다.
4. Decoder가 그걸 보고 다음 단어를 예측하며 텍스트를 만들고, 타임스탬프·언어 감지(Language ID)·번역 등도 같은 Encoder-Decoder 구조에서 함께 다룰 수 있습니다.

`Whisper`는 아래 그림처럼 `Seq2Seq(Sequence-to-Sequence)`로 이해할 수 있습니다.
오디오 신호를 수치 배열의 시퀀스로 받아, 전사 텍스트와 구간 정보가 담긴 `Timestamp Transcript` 쪽 시퀀스로 바꾸는 흐름입니다.
![whisper](./whisper.webp)

`Timestamp Transcript`는 일반적인 `STT(Speech-to-Text)`가 텍스트만 내는 경우와 달리, 특수 토큰 등을 통해 시작/종료 시간과 함께 반환합니다. 아래 예시처럼 구간별로 시작/종료 시간이 붙은 형태라고 보면 됩니다.

```json
{
  "text": "나는 해적왕이 될 거야!",
  "segments": [
    {
      "id": 0,
      "start": 12.5,
      "end": 14.8,
      "text": "나는 해적왕이",
      "tokens": [...]
    },
    {
      "id": 1,
      "start": 14.8,
      "end": 16.0,
      "text": "될 거야!",
      "tokens": [...]
    }
  ]
}
```

# Anime Search에서 Whisper가 맡는 역할
`Whisper`를 프로젝트에 적용하면 영상의 오디오를 대사 구간 단위의 텍스트 데이터로 바꿀 수 있습니다. 이 데이터는 이미지 프레임 임베딩과 같은 벡터로 바로 섞기보다는, 시간 구간을 기준으로 별도 인덱싱한 뒤 대사 검색 흐름으로 분리하는 방식이 더 자연스러워 보입니다.

예를 들어 사용자가 "나는 해적왕이 될 거야"처럼 대사에 가까운 문장을 검색하면 Whisper 전사 결과에서 먼저 후보 구간을 찾고, 그 시간대 주변 프레임을 결과로 보여줄 수 있습니다. 반대로 "비 오는 사이버펑크 거리"처럼 시각적인 질의는 `CLIP` 기반 이미지 검색이 더 적합합니다.

따라서 지금 단계에서는 역할을 다음처럼 나누어 생각하려 합니다.
- `CLIP`: 프레임 이미지와 텍스트 쿼리의 시각적 의미 비교
- `Whisper`: 오디오를 타임스탬프가 있는 대사 텍스트로 변환
- 검색 단계: 이미지 검색과 대사 검색을 같은 벡터 공간에 섞지 않고 별도 흐름으로 평가
