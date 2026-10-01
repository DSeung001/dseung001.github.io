---
title: "Bavelmo 배포"
date: 2026-10-01T14:30:00+09:00
categories: [ "Project", "Bavelmo", "Subculture" ]
series: [ "bavelmo" ]
tags: [ "피규어", "장식장", "런칭", "Bavelmo", "서비스", "sns" ]
draft: false
description: "FiguRoom으로 기획하던 피규어 컬렉션 서비스를 Bavelmo로 이름을 바꾸고 런칭한 기록입니다."
keywords: [ "Bavelmo", "피규어", "장식장", "컬렉션", "런칭" ]
author: "DSeung001"
lastmod: 2026-10-01T16:12:00+09:00
---

## 서비스 런칭

이 시리즈에서 [기획했던 서비스](../../../09/18/figuroom-landing-survey/)를 배포했습니다!<br/>
컨샙은 살짝 달라져 커뮤니티 성을 강화해서 콘셉트는 피규어 전용 컬렉터 SNS로 IP, 피규어, 전시가 메인입니다.
![Bavelmo 피드 화면: 피규어 장식장 3D 컬렉션](./image/bavelmo-feed.webp)
> 사용자 점유 시간을 늘리고 싶어 고민해본 결과 SNS 형태가 답같는 1차 결과를 내렸기 때문이죠.

서비스 주소는 https://bavelmo.com/입니다.

처음의 프로젝트 기획하고 모두의 창업을 신청하고 [X 알고리즘 분석](../../../09/22/figuroom-x-recommendation/)을 하고 X에 계정을 만들고 개발을 시작했기에 [블로그 글은 18일](../../../09/18/figuroom-landing-survey/)이어도 실제 개발 기간은 21일부터 해서 대략 10일만 정도 걸린 거 같네요.

MVP를 목적으로 개발하다 보니 자세한 기능들의 최적화보다는 빠른 서비스 기준을 목표로 했고 후에 리팩토링을 한다는 전제로 진행했습니다. 이제 천천히 사용자 모집과 기능 개선 및 고도화를 같이 해야겠습니다.

## 배포
Class 프로젝트는 단일 EC2로 부담했기에 편하게 했지만 이번에는 확장성을 고려해야 했습니다.
그러다 보니 굉장히 복잡해지기도 했습니다.
또 확장성을 고려해서 서버를 Fargate로 선택하여 비용은 더 낼 수 있어도 수평적 확장을 언제든지 가능하게 했습니다.
사용자 트래픽이 몰리면 자동으로 서버를 늘려주는 점을 높게 봤습니다.

### Stack Yaml

설정한 요소들의 관계를 하나하나 짚으면 너무 많고 추상적이고 가장 큰 문제는 추적하기도 어렵다는 점이었습니다.
그래서 GPT에게 기술 스택을 정리시키고, 그 정리를 Amazon Q에 넘겨 스택 파일을 만들게 한 다음, 검증하고 실행했습니다. 비밀 키는 파라미터로 두고 프로젝트에는 AWS 스택 YAML로 남기는 방식으로 코드 에이전트가 서버의 구성에 접근할 수 있는 형태로 이번에 배포 방식을 택해봤습니다.

반나절이면 끝날 줄 알았는데, 버그도 고치고 기능도 추가하고 배포 설정도 하느라 새벽까지 달렸었네요.

이번에 진행한 배포 범위는 다음과 같습니다.<br/> 
가상 네트워크와 보안 그룹, 운영 DB와 이미지 파일 저장, 가입 메일 서버와 구글 로그인, Fargate로 띄운 API와 웹, 그리고 도메인과 배포 권한, 장애 알람입니다.<br/>
Amazon Q는 위 목록 요소들을 하나하나 스택 파일을 생성해줬고 이를 검증하는 프로세스였죠.

이 방식의 가장 좋은 점은 서버 환경이 텍스트로 보여진다는 부분입니다.
에이전트가 언제든 인프라 상황을 추적할 수 있죠.

## 이슈
### 1. 구글 SES 발급 기간 소요
이전 사이드 프로젝트는 OTT 서비스 공부가 목적이었지만 이번에는 정말 서비스가 목적이었기에 비싸더라도 구글 SMTP가 아닌 Amazon SES를 택했습니다. 생태계가 합쳐져 있으니 쉽게 가능할 거라는 판단이었지만 제품 인증 단계가 별도로 있는 줄 알았더라면 미리 해 둘걸 그랬네요.

그래서 지금 배포된 서버 기준에서는 이메일 회원가입은 임시로 풀어두고, 구글 로그인을 권장하는 상태입니다.
![Amazon SES 발송 한도 상향 요청에 추가 정보를 요구하는 메일](./image/amazon-ses-sending-limit.webp)

### 2. 모바일 렌더링
주된 파일들이 3D다 보니 모바일 쪽에서 렌더링의 시간이 생각 이상으로 걸리는 문제가 발생하고 있습니다, PC 기준으로는 신경 쓰일 정도가 아니었기에 후에 고도화 범위로 넣으려 했지만 현재 SNS 앱 특성상 모바일 편의성이 중요하니 빠르게 고쳐야겠습니다.
우선 인터넷 대역폭에 맞춰 모바일은 2개 씩 랜더링 하도록 제한을 뒀습니다.

지금 컬렉션 부분에서 렌더링 전에는 피규어들이 이미지로 보이기 때문에 사용자들이 이 3D 컬렉션이 아닌 2D 컬렉션으로 오해하는 상황이 벌어지고 있어서 급한 불이었죠.

추가적으로 토스트 메시지로 렌더링 중임을 알리는 걸로 대처를 해 적용해뒀습니다.

### 3. 디자인 외주
라프텔 서비스의 푸밍이나 당근 모임 서비스의 고양이 캐릭터처럼 사이트 자체의 캐릭터를 만들고 그걸 통해 기본 프로필 사진과 이모티콘 기능을 넣고 싶었습니다.
<span class="content-image-wrap is-sized">
  <button type="button" class="content-image-expand" aria-label="이미지 확대" title="확대">
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
      <path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3"/>
    </svg>
  </button>
  <img src="./image/laftel-puming.webp" alt="라프텔 마스코트 푸밍이" style="width: 220px; max-width: 100%; height: auto;">
</span>
그래서 디자이너 오픈 채팅이나 서브컬처 모임, 아는 지인들에게 외주 의뢰를 넣어봤습니다.
금방 구해질 줄 알았는데 생각보다 구하는 게 어렵더군요. 아직 구한 지 일주일 정도밖에 지나지 않았으니 좀 더 기다려 봐야겠습니다.

## 서비스 이름
그리고 서비스 이름을 Figuroom에서 bavelmo로 변경되었습니다.

프로젝트를 진행하며 마케팅/브랜딩의 영역으로도 확장하고 싶었고 이를 공부하고자 사업하는 지인께 책을 추천받았죠.
그러다가 책을 읽고 난 뒤 프로젝트명을 보니 굉장히 제 마음에 들지 않는 합성어라는 점을 깨달았죠.

그때 책을 읽으며 적은 블로그 ["독서 블로그의 브랜드로 남는다는 것"](https://seung.tistory.com/entry/%EB%B8%8C%EB%9E%9C%EB%93%9C%EB%A1%9C-%EB%82%A8%EB%8A%94%EB%8B%A4%EB%8A%94-%EA%B2%83)입니다.

지인이 브랜딩의 교과서 같은 책이라고 해서 재밌게 쭉 읽어봤네요.
원래는 "바벨로"로 하려 했지만 누가 해당 Domain을 선점했고 .com이 가지는 사용자 신뢰성을 버리기 싫어서 "바벨모"로 바꿨습니다.

뜻은 오타쿠 전용 SNS라는 혼돈의 장이라는 의미를 내포하고 있고 피규어 전시가 마치 탑과 같은 느낌을 주기도 해서 만족스러웠습니다.
마지막 글자인 "모"라는 단어가 모으다라는 뉘앙스를 주고 거기에 일본어에서도 쉽게 말할 수 있으며 3글자라는 게 외우기 쉬울거라고 생각해서 스스로 생각하기에 꽤 타당한 이름 같습니다.ㅎㅎ

이렇게 도메인 사는 과정에서 웬만한 건 다 있어서 골치 아팠는데 그래서 많은 회사들이 고유 이름을 만드는거 같네요.

## 홍보
### 근황
처음 X에 글을 올리고 그래도 팔로워가 4명 생겼습니다.
9월 19일에 글을 올리고 여태까지 총 104개의 게시물을 적었습니다.
걱정하던 조회수 문제도 100 이상 쌓이는 등 천천히 성장하고 있는 거 같군요.

그리고 3일 전에 올린 글이 조회수 100을 넘는 것처럼 점차 속도가 붙는 거 같아서 한편으로 안심이 되네요.

<span class="content-image-wrap is-sized">
  <button type="button" class="content-image-expand" aria-label="이미지 확대" title="확대">
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
      <path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3"/>
    </svg>
  </button>
  <img src="./image/x-post-123-views.webp" alt="조회수 123이 표시된 피규가토 X 게시물" style="width: 480px; max-width: 100%; height: auto;">
</span>

### 진행방향
앞으로는 바벨모 서비스를 통해 신규 피규어를 3D로 보여주게해서 꾸준한 트래픽 유도를 조성하려합니다.
그래서 사람들이 관심있어하는 애니, 피규어 쪽으로 제품을 게시하려 합니다.

하지만 너무 이런식의 글만 올리면 사이트 홍보성이 짙어지니 정보성 글도 꾸준히 유지해야겠습니다.
점차 확장해나가는게 재밌네요.

<span class="content-image-wrap is-sized">
  <button type="button" class="content-image-expand" aria-label="이미지 확대" title="확대">
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
      <path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3"/>
    </svg>
  </button>
  <img src="./image/x-3d-figure-display.webp" alt="품절 제품을 3D 장식장으로 올린 피규가토 X 게시물" style="width: 480px; max-width: 100%; height: auto;">
</span>
