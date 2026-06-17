---
title: "Class Project 2차 회고"
date: 2026-06-17T00:00:00+09:00
categories: [ "Project", "Class Project" ]
tags: [ "Class Project", "Retrospective" ]
draft: true
description: "Class Project 진행 사항"
keywords: [ "Class Project", "회고", "Retrospective" ]
author: "DSeung001"
lastmod: 2026-06-17T00:00:00+09:00
---


# 이슈

## 디스크 공간

배포 중인 사이트를 업데이트할 때 디스크 8GB를 다 쓰게 되는 경우가 발생했습니다. <br/>
프론트 빌드 과정 중에 발생했는데, `docker compose build`하는 도중에 이미지 복사본이 공존하면서 해당 이슈가 발생하게 되었습니다, 디스크가 8GB면 충분할 줄 알았지만
실제 환경에서는 다음처럼 4.5GB를 차지한 상태에서 `docker compose build`로 빌드하는 과정에서 저장공간 을 벗어나서 에러가 발생했습니다.
```bash
$ df -h /
Filesystem      Size  Used Avail Use% Mounted on
/dev/nvme0n1p1  8.0G  4.5G  3.5G  57% /
$ sudo docker system df
TYPE            TOTAL     ACTIVE    SIZE      RECLAIMABLE
Images          6         6         1.89GB    691.1MB (36%)
Containers      6         6         2.191kB   0B (0%)
Local Volumes   5         5         53.11MB   0B (0%)
Build Cache     0         0         0B        0B
```

좀 더 자세히 보면 다음 흐름이 발생한거죠.
1. 빌드 캐시 및 임시 레이어가 생성되는 과정에서 Next.js를 사용하고 있으므로 node_modules를 설치하고 소스 코드를 컴파일하면서 대량의 임시 파일이 디스크에 생성되는데, 이게 거의 1~2GB로 추측됩니다.
2. 빌드된 새 이미지를 만들면서 이것도 1~2GB를 차지하게 되겠죠.
3. 신규 이미지 + 기존 이미지 + 캐시된 임시 파일들까지 합쳐지면서 남은 여유 공간인 3.5GB를 초과해서 터집니다.

간단하고 확실한 해결책은 하드웨어적으로 디스크 용량을 늘리는 거죠.<br/>
하지만 그 전에 Docker 관련해서 다음 최적화를 적용했습니다.
- Docker 전역 로그 제한 추가 (당장은 영향 없음)
- 백엔드/Celery 중복 빌드를 동일 이미지 사용으로 제거
- Next.js Standalone 최적화로 패키징 압축

```bash
$ df -h /
Filesystem      Size  Used Avail Use% Mounted on
/dev/nvme0n1p1  8.0G  3.9G  4.1G  49% /
$ sudo docker system df
TYPE            TOTAL     ACTIVE    SIZE      RECLAIMABLE
Images          5         5         1.231GB   8.45MB (0%)
Containers      6         6         1.653kB   0B (0%)
Local Volumes   5         5         53.13MB   0B (0%)
Build Cache     0         0         0B        0B
```

결과적으로 600MB 정도의 파일 용량을 줄였는데, 이는 빌드 과정에서는 2배 효과를 발휘할 테니 배포 과정에서의 안정성을 많이 올려 봤습니다. 조금 더 프로젝트를 다듬은 후에는 16GB로 메모리를 늘리는 걸 고려해야겠습니다.

## 활성화 이슈
어떻게 해야 학원에서 사용할까..

## 기능 추가

## TOdo


# 확장 해결한거
개발 예정인 기능이 아직 많습니다. <br/>
실질적으로 사용자에게 가장 큰 변화를 주는 기능을 먼저 구현할 예정입니다.
- 업로드가 아닌 유튜브 링크를 통한 공유
- 자유 게시판

그 후에는 테스트와 고도화를 병행할 생각이지만, 무엇보다 비용 절감에 초점을 둘 예정이죠. <br/>
고도화에서는 아래 영역에 대해서 작업이 필요하죠.
- HLS 세그먼트 다수 업로드: `.ts`마다 S3 PutObject가 늘어 요청 비용이 오르는 문제 해결
- 인코딩 서버 구현: ffmpeg를 쓰지 않고 직접 인코딩 구현해서 최적화
- 멀티파트 업로드로 바이트 단위 청크 전송을 최적화
- 디스크 문제: 로컬에 원본 파일과 인코딩 파일이 동시에 존재할 때도 괜찮은지 체크
- 배포 비용 절감의 필요

테스트 및 분석 영역
- 과부하 테스트
- 큰 파일이 들어왔을 때(GB 단위)
- 보안 이슈 체크