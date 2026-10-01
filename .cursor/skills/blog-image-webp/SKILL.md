---
name: blog-image-webp
description: >-
  기술 블로그 글의 스크린샷과 이미지를 WebP로 바꾸고, 파일명을 정리한 뒤 본문에 넣는다.
  사용자가 스크린샷, webp, 확장자 변경, 이미지 최적화, 이미지 연결, 이미지 크기 지정을 요청할 때 적용한다.
---

# 블로그 이미지 WebP

프런트매터, H1 금지, alt 텍스트, Hugo 빌드는 저장소 루트 `AGENTS.md`를 따른다. 문장 말투는 바꾸지 않는다. 사용자가 넣은 자리 주변에만 이미지를 연결한다.

## 변환

원본은 해당 글의 `image/`에 둔다. macOS 스크린샷 이름(`스크린샷 날짜.png`)은 그대로 두지 않는다.

1. 이미지를 보고 내용을 설명하는 영문 kebab-case 파일명을 정한다. 예: `x-post-123-views.webp`.
2. 아래 스크립트로 변환한다. 스크린샷, UI 캡처, 메일은 `--kind screenshot`. 투명 배경이 있는 단색 일러스트만 `--kind illustration`.

```bash
python3 .cursor/skills/blog-image-webp/scripts/to_webp.py SRC DST --kind screenshot
```

3. WebP가 생성된 뒤에만 원본 png, jpg를 삭제한다.
4. 본문에는 `![대체텍스트](./image/파일.webp)`를 넣는다. 대체텍스트는 비우지 않고, 화면에 보이는 내용을 한국어로 적는다.

스크립트 규칙:

- screenshot: 알파가 전부 불투명하면 RGB로 버리고, 가로가 1600px을 넘으면 비율을 유지해 줄인다. `cwebp -q 82 -m 6`.
- illustration: RGBA를 유지하고 `cwebp -lossless`. 크기는 줄이지 않는다.

## 표시 크기

사용자가 크기를 지정하라고 하면 마크다운 이미지 대신 아래를 쓴다. 본문 크기는 `width` 숫자만 바꾼다. `content-image-wrap`과 확대 버튼이 있어야 클릭해서 원본에 가깝게 볼 수 있다. 버튼 SVG는 `layouts/_default/_markup/render-image.html`과 같다.

```html
<span class="content-image-wrap is-sized">
  <button type="button" class="content-image-expand" aria-label="이미지 확대" title="확대">
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
      <path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3"/>
    </svg>
  </button>
  <img src="./image/파일.webp" alt="대체텍스트" style="width: 220px; max-width: 100%; height: auto;">
</span>
```

크기를 말하지 않았으면 마크다운 이미지를 쓰고, 가로를 임의로 줄이지 않는다. 마크다운 이미지는 렌더 훅이 확대 버튼을 붙인다.
