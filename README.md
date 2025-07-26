# DevSeung Blog - GitHub Pages 관리 가이드

이 저장소는 Hugo 정적 사이트 생성기를 사용하여 구축된 개인 블로그입니다. PaperMod 테마를 기반으로 하며, GitHub Pages를 통해 배포됩니다.

## 📋 목차

1. [테마 변경하기](#테마-변경하기)
2. [빌드하기](#빌드하기)
3. [페이지 추가하기](#페이지-추가하기)
4. [카테고리 추가하기](#카테고리-추가하기)

---

## 🎨 테마 변경하기

현재 **PaperMod** 테마를 사용하고 있습니다. 테마를 변경하려면:

### 1. Hugo 설정 파일 확인
- `config.toml`, `config.yaml`, 또는 `config.json` 파일을 찾아서 테마 설정을 확인하세요
- 현재 설정: `theme = "PaperMod"`

### 2. 새로운 테마 적용
```bash
# 1. 원하는 테마를 themes 폴더에 추가
git clone https://github.com/테마저장소/테마이름.git themes/테마이름

# 2. config 파일에서 테마 변경
theme = "새로운테마이름"

# 3. 빌드하여 확인
hugo server -D
```

### 3. CSS 커스터마이징
- `assets/css/stylesheet.css` 파일을 수정하여 스타일을 커스터마이징할 수 있습니다
- 또는 `assets/css/custom.css` 파일을 생성하여 추가 스타일을 적용할 수 있습니다

---

## 🔨 빌드하기

### 로컬 개발 환경 설정
```bash
# 1. Hugo 설치 (Windows)
# Chocolatey 사용
choco install hugo-extended

# 또는 직접 다운로드
# https://gohugo.io/installation/windows/

# 2. 의존성 설치 (테마가 있는 경우)
git submodule update --init --recursive

# 3. 로컬 서버 실행
hugo server -D
```

### 프로덕션 빌드
```bash
# 정적 파일 생성
hugo

# 또는 최적화된 빌드
hugo --minify
```

### GitHub Actions를 통한 자동 배포
`.github/workflows/hugo.yml` 파일을 생성하여 자동 배포를 설정할 수 있습니다:

```yaml
name: Deploy Hugo site to Pages

on:
  push:
    branches: ["main"]
  workflow_dispatch:

permissions:
  contents: read
  pages: write
  id-token: write

concurrency:
  group: "pages"
  cancel-in-progress: false

defaults:
  run:
    shell: bash

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - name: Install Hugo CLI
        run: |
          wget -O ${{ runner.temp }}/hugo.deb https://github.com/gohugoio/hugo/releases/download/v${HUGO_VERSION}/hugo_extended_${HUGO_VERSION}_linux-amd64.deb
          sudo dpkg -i ${{ runner.temp }}/hugo.deb
        env:
          HUGO_VERSION: 0.147.8

      - name: Checkout
        uses: actions/checkout@v4
        with:
          submodules: recursive
          fetch-depth: 0

      - name: Setup Pages
        id: pages
        uses: actions/configure-pages@v4

      - name: Build with Hugo
        env:
          HUGO_ENVIRONMENT: production
          HUGO_ENV: production
        run: |
          hugo \
            --gc \
            --minify \
            --baseURL "${{ steps.pages.outputs.base_url }}/"

      - name: Upload artifact
        uses: actions/upload-pages-artifact@v3
        with:
          path: ./public

  deploy:
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    runs-on: ubuntu-latest
    needs: build
    steps:
      - name: Deploy to GitHub Pages
        id: deployment
        uses: actions/deploy-pages@v4
```

---

## 📝 페이지 추가하기

### 새 포스트 작성
```bash
# 1. 새 포스트 생성
hugo new posts/포스트제목/index.md

# 2. 또는 content 폴더에 직접 생성
mkdir content/posts/포스트제목
touch content/posts/포스트제목/index.md
```

### 포스트 마크다운 템플릿
```markdown
---
title: "포스트 제목"
date: 2025-01-01T00:00:00+09:00
draft: false
description: "포스트 설명"
tags: ["태그1", "태그2"]
categories: ["카테고리명"]
author: "DSeung001"
---

포스트 내용을 여기에 작성하세요.

## 제목 1

내용...

## 제목 2

내용...
```

### 페이지 타입
- **포스트**: `content/posts/` 폴더에 저장
- **페이지**: `content/` 폴더에 직접 저장
- **섹션**: 폴더 구조에 따라 자동 생성

---

## 📂 카테고리 추가하기

### 1. 카테고리별 폴더 구조
```
content/
├── posts/
│   ├── category1/
│   │   ├── post1/
│   │   │   └── index.md
│   │   └── post2/
│   │       └── index.md
│   └── category2/
│       └── post3/
│           └── index.md
```

### 2. 포스트에 카테고리 지정
```markdown
---
title: "포스트 제목"
categories: ["카테고리명"]
---
```

### 3. 카테고리 페이지 생성
```bash
# 카테고리 목록 페이지 생성
hugo new categories/_index.md
```

### 4. 카테고리별 레이아웃 커스터마이징
- `layouts/categories/` 폴더에 카테고리별 템플릿 생성
- `layouts/categories/single.html` - 개별 카테고리 페이지
- `layouts/categories/list.html` - 카테고리 목록 페이지

---

## 🛠️ 추가 관리 팁

### 1. 환경 변수 설정
```bash
# 개발 환경
HUGO_ENV=development hugo server

# 프로덕션 환경
HUGO_ENV=production hugo
```

### 2. 이미지 관리
- `static/images/` 폴더에 이미지 저장
- 마크다운에서 `![alt](images/파일명.jpg)` 형식으로 사용

### 3. SEO 최적화
- 각 포스트의 front matter에 `description`, `keywords` 추가
- `robots.txt` 및 `sitemap.xml` 자동 생성

### 4. 댓글 시스템
- Disqus, Utterances, Giscus 등 추가 가능
- 테마 설정에서 활성화

---

## 📚 유용한 링크

- [Hugo 공식 문서](https://gohugo.io/documentation/)
- [PaperMod 테마 문서](https://github.com/adityatelange/hugo-PaperMod)
- [GitHub Pages 설정](https://pages.github.com/)

---

## 🤝 기여하기

이 블로그는 개인 프로젝트이지만, 개선 사항이나 버그 리포트는 언제든 환영합니다!

---

**마지막 업데이트**: 2025년 1월 