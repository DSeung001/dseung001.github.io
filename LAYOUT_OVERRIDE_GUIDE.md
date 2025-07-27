# 🎨 Hugo 레이아웃 오버라이드 가이드

## 📋 개요

Hugo에서는 테마를 직접 수정하지 않고도 **레이아웃 오버라이드** 기능을 사용해서 커스터마이징할 수 있습니다. 이 방법을 사용하면 테마 업데이트 시에도 커스텀 설정이 유지됩니다.

## 🚀 레이아웃 오버라이드 방법

### 1. **디렉토리 구조**

```
your-site/
├── layouts/           # 커스텀 레이아웃 (우선순위 높음)
│   ├── partials/      # 부분 템플릿
│   ├── _default/      # 기본 레이아웃
│   └── shortcodes/    # 숏코드
├── assets/            # CSS, JS, 이미지 등
│   ├── css/
│   ├── js/
│   └── images/
├── content/           # 콘텐츠
├── themes/            # 테마 (우선순위 낮음)
└── config.toml        # 설정 파일
```

### 2. **우선순위 규칙**

Hugo는 다음 순서로 템플릿을 찾습니다:

1. `layouts/` (사이트 레이아웃)
2. `themes/[theme]/layouts/` (테마 레이아웃)

## 🛠️ 커스터마이징 방법

### **방법 1: 전체 파일 오버라이드**

테마의 파일을 완전히 교체하고 싶을 때:

1. 테마의 파일을 `layouts/` 디렉토리로 복사
2. 원하는 대로 수정

```bash
# 예시: header.html 오버라이드
cp themes/PaperMod/layouts/partials/header.html layouts/partials/header.html
# 이제 layouts/partials/header.html을 수정하면 됩니다
```

### **방법 2: 부분 오버라이드 (extend_head.html 활용)**

테마의 `extend_head.html` 파일을 활용:

```html
<!-- layouts/partials/extend_head.html -->
<style>
.custom-header {
    background-color: #your-color;
}
</style>
```

### **방법 3: CSS 오버라이드**

`assets/css/` 디렉토리에 CSS 파일 생성:

```css
/* assets/css/custom.css */
.header {
    background-color: #your-color;
}
```

## 📁 주요 오버라이드 가능한 파일들

### **Partial Templates (layouts/partials/)**
- `header.html` - 헤더
- `footer.html` - 푸터
- `head.html` - HTML head 섹션
- `nav.html` - 네비게이션
- `sidebar.html` - 사이드바

### **Default Layouts (layouts/_default/)**
- `baseof.html` - 기본 레이아웃
- `list.html` - 목록 페이지
- `single.html` - 단일 페이지
- `index.html` - 홈페이지

### **Shortcodes (layouts/shortcodes/)**
- `figure.html` - 이미지
- `youtube.html` - 유튜브
- `tweet.html` - 트위터

## 🎯 실제 사용 예시

### **헤더 커스터마이징**

1. **파일 복사**:
```bash
mkdir -p layouts/partials
cp themes/PaperMod/layouts/partials/header.html layouts/partials/header.html
```

2. **수정**:
```html
<!-- layouts/partials/header.html -->
<header class="header custom-header">
    <!-- 커스텀 헤더 내용 -->
</header>
```

### **CSS 커스터마이징**

```css
/* assets/css/custom.css */
.custom-header {
    background: linear-gradient(45deg, #667eea 0%, #764ba2 100%);
    color: white;
}

.custom-header .nav {
    padding: 1rem 2rem;
}
```

### **메뉴 추가**

```toml
# config.toml
[menu]
  [[menu.main]]
    identifier = "about"
    name = "About"
    url = "/about/"
    weight = 10
  [[menu.main]]
    identifier = "contact"
    name = "Contact"
    url = "/contact/"
    weight = 20
```

## 🔧 고급 커스터마이징

### **조건부 렌더링**

```html
{{- if .IsHome }}
    <!-- 홈페이지에서만 표시 -->
    <div class="home-banner">Welcome!</div>
{{- end }}
```

### **동적 메뉴**

```html
{{- range site.Menus.main }}
<li>
    <a href="{{ .URL }}" {{ if .HasChildren }}class="has-children"{{ end }}>
        {{ .Name }}
    </a>
    {{- if .HasChildren }}
    <ul class="submenu">
        {{- range .Children }}
        <li><a href="{{ .URL }}">{{ .Name }}</a></li>
        {{- end }}
    </ul>
    {{- end }}
</li>
{{- end }}
```

## 📝 주의사항

### **테마 업데이트 시**
- 오버라이드한 파일은 테마 업데이트의 영향을 받지 않음
- 새로운 테마 기능을 사용하려면 수동으로 업데이트 필요

### **파일 경로**
- 정확한 디렉토리 구조 유지
- 파일명과 확장자 정확히 일치

### **캐시 문제**
- 변경사항이 반영되지 않으면 캐시 삭제:
```bash
hugo --gc
rm -rf public/
```

## 🎨 스타일링 팁

### **CSS 변수 활용**

```css
:root {
    --primary-color: #4a9eff;
    --secondary-color: #2e2e33;
    --text-color: #ffffff;
}

.header {
    background-color: var(--secondary-color);
    color: var(--text-color);
}
```

### **반응형 디자인**

```css
@media (max-width: 768px) {
    .header {
        flex-direction: column;
    }
    
    #menu {
        display: none;
    }
}
```

## 🔍 디버깅

### **템플릿 확인**
```bash
hugo --templateMetrics
```

### **빌드 확인**
```bash
hugo server --disableFastRender
```

이 가이드를 따라하면 테마를 건드리지 않고도 원하는 대로 커스터마이징할 수 있습니다! 🚀 