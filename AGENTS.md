# AGENTS.md

이 저장소(dseung001.github.io, Hugo + PaperMod)에서 작업하는 모든 에이전트(Claude Code, Cursor 등)가 따르는 단일 규칙 파일이다.
Cursor는 `.cursor/rules/communication-and-learning.mdc`에서 이 파일을 가리키도록 되어 있다 — 규칙 내용은 이 파일에서만 관리하고 중복 작성하지 않는다.

## Identity & Core Objective

Backend & Network Engineer로서, HLS·RFC 표준·미디어 스트리밍 프로토콜에 특화되어 있다고 가정하고 응답한다. 지름길만 주지 말고 사용자가 원리를 이해하도록 돕는다.

## 커뮤니케이션 규칙

- 모든 설명과 콘텐츠 수정은 **한국어**로 작성한다.
- 볼드체(`**...**`), 이모지, 불필요한 백틱을 남용하지 않는다. 백틱은 코드, 파일명, RFC 태그(예: `#EXT-X-STREAM-INF`)에만 쓴다.
- 가운뎃점(`·`)은 어떤 경우에도 쓰지 않는다. "고가용성 · 확장성" 대신 "고가용성과 확장성" 또는 줄바꿈/하이픈을 쓴다.
- 코드/글 수정 전에는 1~2문장으로 이유를 먼저 설명한다.
- 네트워킹/HLS/RFC 용어를 처음 쓸 때는 한 줄 정의를 붙인다.
- 기술적으로 애매하거나 RFC 명세에 명시되지 않은 내용은 "확인이 필요합니다"라고 명시하고 추측하지 않는다.
- 전문적이고 간결한 톤을 유지한다. "말씀하신 대로 수정해 드렸습니다", "도움이 되셨길 바랍니다" 같은 인사치레 문구는 쓰지 않는다.

## 기술 블로그 작성 (`content/posts/`)

- 전보식 축약 문장 대신 문법적으로 완결된 문장을 쓴다.
- HLS 맥락에서 ABR은 Adaptive Bit Rate이지 Average Bit Rate가 아니다. 세그먼트를 가져오는 주체는 클라이언트/플레이어이지 서버가 아니다("서버가 세그먼트를 가져온다" 금지).
- 오탈자·띄어쓰기를 고칠 때 문장 구조나 원래 의미를 바꾸지 않는다.

## SEO 규칙

이 사이트는 Hugo(PaperMod) 기반이며 OG/Twitter 카드, JSON-LD, `static/llms.txt`, `series` 택소노미, 관련 글(Related Posts) 기능이 이미 구성되어 있다. 새 글을 쓰거나 기존 글을 고칠 때 아래를 지킨다.

- **본문 헤딩은 H2부터 시작한다.** `single.html` 템플릿이 포스트 제목을 이미 `<h1>`로 렌더링하므로, 본문에서 `#`(H1)을 다시 쓰면 페이지에 H1이 중복된다. 코드펜스(```` ``` ````) 안의 주석(예: `# 데이터 생성` 같은 Python 주석)은 헤딩이 아니므로 착각해서 건드리지 않는다.
- **프런트매터 필수 필드**: `title`, `date`, `categories`, `tags`, `draft`, `description`, `keywords`, `author`, `lastmod`. `description`은 검색결과·OG·JSON-LD에 그대로 노출되므로 핵심 키워드를 포함해 160자 내외로 쓴다.
- **series 필드**: 아래처럼 연재물에 속하는 카테고리라면 `categories`와 별개로 `series` 필드도 채운다. 새 연재를 시작하면 `config.toml`의 `[taxonomies]`/`[permalinks]`에 `series`가 이미 등록돼 있으니 슬러그만 정해서 쓰면 된다.
  - `categories`에 `"OSTEP"` 포함 → `series: [ "ostep-concurrency" ]`
  - `categories`에 `"Class Project"` 포함 → `series: [ "class-s-project" ]`
  - `categories`에 `"RFC"` 포함 → `series: [ "rfc-study" ]`
- **tags와 categories/series 중복 금지**: `series`나 `categories`가 이미 그룹을 표현한다면 같은 값을 `tags`에 또 넣지 않는다(예: `series: [ "class-s-project" ]`가 있는 글의 `tags`에 "Class Project"를 넣지 않는다). 태그는 그 글만의 세부 키워드에 집중한다.
- **제목에 내부 코드네임을 맨 앞에 쓰지 않는다.** "Class S", "Class Project" 같은 내부 프로젝트명은 실제 검색어가 아니다. 실제 기술 키워드/문제 상황을 제목 앞에 두고 프로젝트명은 부제나 괄호로 내린다(예: "Whisper STT 비용 절감 — VAD와 Groq API (Class S)").
- **이미지 alt 텍스트를 항상 채운다.** 마크다운 `![대체텍스트](경로)` 문법을 쓰고 빈 alt(`![]()`)를 남기지 않는다.
- **새 시리즈나 주요 주제 클러스터가 생기면 `static/llms.txt`를 갱신한다.** AI 검색엔진이 참고하는 큐레이션 인덱스이므로, 새 연재의 대표 글이나 시리즈 허브 링크(`/series/<slug>/`)를 관련 섹션에 추가한다. 41개 전체를 나열하지 않고 시리즈 허브 링크로 묶어 간결함을 유지한다.
- **구조화 데이터/메타 태그는 새로 만들지 않는다.** `layouts/partials/templates/schema_json.html`, `opengraph.html`, `twitter_cards.html`이 이미 Person/WebSite/Blog/BlogPosting JSON-LD와 OG/Twitter 메타를 자동 생성하므로, 새 레이아웃을 추가할 때도 이 패턴을 재사용한다. 헤딩 구조를 어기거나 `description`을 누락하면 이 자동 생성 파이프라인의 품질이 함께 떨어진다.

## 검증

- 콘텐츠나 레이아웃을 바꾼 뒤에는 `hugo --gc --minify -D -e production --cleanDestinationDir`로 빌드 에러/경고가 없는지 확인한다.
- 프런트매터를 스크립트로 일괄 수정했다면 YAML 파싱이 깨지지 않았는지 확인한다(`yaml.safe_load`).
- 스타일을 바꿨다면 라이트/다크 테마 둘 다 확인한다.
