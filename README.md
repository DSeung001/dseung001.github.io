# DevSeung Blog

Hugo + PaperMod 테마로 구축된 개인 블로그입니다.

## 🎨 현재 테마

- **PaperMod**: 깔끔하고 모던한 Hugo 테마
- **GitHub**: https://github.com/adityatelange/hugo-PaperMod

## 🚀 로컬 실행 방법

```bash
# 1. Hugo 설치 (macOS)
brew install hugo

# 2. 의존성 설치
git submodule update --init --recursive

# 3. 로컬 서버 실행
hugo server -D

# 4. 브라우저에서 확인
# http://localhost:1313
```

## 🎨 테마 관리

### 테마 다운로드 (처음 설정 시)
```bash
# 테마 다운로드
git clone https://github.com/adityatelange/hugo-PaperMod.git themes/PaperMod

# .git 폴더 제거 (서브모듈이 아닌 일반 폴더로)
rm -rf themes/PaperMod/.git
```

### 테마 업데이트 (원할 때)
```bash
# 1. 기존 테마 백업 (선택사항)
mv themes/PaperMod themes/PaperMod_backup

# 2. 최신 테마 다운로드
git clone https://github.com/adityatelange/hugo-PaperMod.git themes/PaperMod

# 3. .git 폴더 제거
rm -rf themes/PaperMod/.git

# 4. 변경사항 커밋
git add .
git commit -m "Update PaperMod theme to latest version"
git push origin main
```

### 테마 커스터마이징
- `assets/css/custom.css` 파일을 생성하여 스타일 수정
- `layouts/` 폴더에 커스텀 템플릿 생성
- `config.toml`에서 테마 파라미터 설정

## 🔄 GitHub Actions

`.github/workflows/hugo.yml` 파일로 자동 배포가 설정되어 있습니다:

- **트리거**: main 브랜치에 push할 때
- **빌드**: Hugo Extended 버전으로 빌드
- **배포**: GitHub Pages에 자동 배포
- **URL**: https://dseung001.github.io/

## 📁 프로젝트 구조

```
dseung001.github.io/
├── content/           # 블로그 포스트 (마크다운 파일)
│   └── posts/        # 포스트 폴더
├── themes/           # Hugo 테마 (PaperMod)
├── config.toml       # Hugo 설정 파일
├── .github/          # GitHub Actions 설정
├── assets/           # CSS, JS 등 정적 파일
└── public/           # 빌드 결과물 (자동 생성)
```

## 📝 새 포스트 작성

```bash
# 1. content/posts/ 폴더에 마크다운 파일 생성
# 2. front matter 작성
---
title: "포스트 제목"
date: 2025-01-01T00:00:00+09:00
categories: ["카테고리"]
tags: ["태그1", "태그2"]
draft: false
---
# 3. 내용 작성
# 4. git add, commit, push
```

## 🔧 주요 설정

- **baseURL**: https://dseung001.github.io/
- **테마**: PaperMod
- **언어**: 한국어 (ko-kr)
- **자동 배포**: GitHub Actions

## 📚 유용한 링크

- [Hugo 공식 문서](https://gohugo.io/documentation/)
- [PaperMod 테마](https://github.com/adityatelange/hugo-PaperMod)
- [GitHub Pages](https://pages.github.com/)

## To do List
- 댓글 기능 
- 좋아요 같은 이모지 기능
- 글또 블로그에 있는 기능
  - AI 피드백
  - 글 쓰는데 소비된 시간 표시 