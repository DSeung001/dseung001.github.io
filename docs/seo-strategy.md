# SEO 전략 메모 — 사용자 액션 필요 항목

코드/설정으로 바로 적용한 항목(본문 H1 정리, 관련 글, series 택소노미, llms.txt 확장)과 별개로,
계정 등록이나 콘텐츠 판단처럼 직접 결정/실행이 필요한 항목을 정리한 메모. 필요할 때마다 하나씩 처리하면 됨.

## 1. Bing Webmaster Tools + IndexNow

**왜 필요한가**: 현재 Google/Naver 인증만 돼 있음. Bing은 자체 검색뿐 아니라 Copilot(Bing Chat)의 근거 자료로도 쓰이므로 등록해두면 AI 검색 노출에도 도움됨.

**절차**:
1. https://www.bing.com/webmasters 접속 → 사이트 추가(`https://dseung001.github.io/`) → 메타태그 방식으로 인증하면 `<meta name="msvalidate.01" content="...">` 값을 줌.
2. `config.toml`의 `[params.seo]` 블록에 아래 줄 추가:
   ```toml
   bingSiteVerification = "발급받은-코드"
   ```
   `layouts/partials/head.html`이 이미 이 값을 읽어 메타태그를 자동 출력하므로 이 한 줄만 추가하면 됨.
3. Bing Webmaster Tools에서 사이트맵(`https://dseung001.github.io/sitemap.xml`) 제출.

**IndexNow(선택, 발행 즉시 색인 요청)**:
- https://www.bing.com/indexnow 에서 API 키 발급(임의의 문자열, 예: UUID) 후 `static/<키>.txt` 파일에 키 값 자체를 내용으로 저장(예: `static/abc123....txt`, 내용은 `abc123...`).
- `.github/workflows/hugo.yml`의 배포 스텝 뒤에 새 URL들을 IndexNow API로 POST하는 curl 스텝 추가:
  ```yaml
  - name: Ping IndexNow
    run: |
      curl -s -X POST "https://api.indexnow.org/indexnow" \
        -H "Content-Type: application/json" \
        -d '{
          "host": "dseung001.github.io",
          "key": "'"${{ secrets.INDEXNOW_KEY }}"'",
          "keyLocation": "https://dseung001.github.io/'"${{ secrets.INDEXNOW_KEY }}"'.txt",
          "urlList": ["https://dseung001.github.io/sitemap.xml"]
        }'
  ```
  Bing/Naver/Yandex가 이 프로토콜을 공유해서 하나로 세 곳에 다 핑이 감. 처음엔 sitemap.xml 하나만 넣어도 크롤러가 나머지를 따라감.

## 2. 포스트 제목 리라이팅 가이드

**문제**: "Class S", "Class Project" 같은 내부 프로젝트 코드네임이 제목 앞부분을 차지해서, 실제 사람들이 검색하는 키워드와 제목이 어긋남. 검색 결과 CTR과 AI 답변 인용률 둘 다에 불리.

**원칙**: 프로젝트명은 부제나 괄호로 뒤로 밀고, 실제 기술 키워드/문제 상황을 제목 앞에 둔다. URL(slug)은 이미 날짜+파일명 기반이라 제목만 바꿔도 URL이 안 깨짐.

| 현재 제목 | 개선 예시 |
|---|---|
| Class Project 발행 STT 비용 최적화 | Whisper STT 비용 60% 줄이기 — VAD와 Groq API 조합 (Class S) |
| Class Project 하이브리드 검색 구현하기 | PostgreSQL로 하이브리드 검색(FTS + 벡터) 구현하기 |
| Class Project 질의응답 RAG | 강의 영상에 RAG 기반 Q&A 붙이기 — 설계와 평가 |
| Class S 인코딩 서버 분리 비용 절감 | 인코딩 서버 분리로 AWS 비용 절감한 아키텍처 변경기 |
| Class S AI 썸네일 | AI 이미지 생성으로 영상 썸네일 자동화하기 |

바꿀 때 `description`/`keywords` 프런트매터도 같은 키워드로 맞춰주면 일관성이 생김. 한 번에 다 바꾸지 말고 트래픽 있는 글부터 우선순위 잡아서 진행 권장.

## 3. AI 인용 최적화용 요약 블록 패턴

**왜 필요한가**: Perplexity/ChatGPT 검색/Google AI Overview는 페이지 전체를 요약하기보다, 질문-답변 형태로 명확히 쪼개진 문단을 그대로 인용하는 경향이 있음. 포스트 본문 상단에 짧은 요약 블록을 넣으면 인용될 확률이 올라감.

**패턴 예시** (포스트 최상단, 첫 헤딩 앞에 삽입):

```markdown
> **요약**: Whisper API 대신 VAD로 무음을 제거하고 1.25배속 처리 후 Groq Whisper로 STT를 돌려서
> 강의 1일치 STT 비용을 $1.2~$1.5에서 약 40%까지 줄였습니다.
```

또는 소제목 자체를 질문형으로 쓰는 방식도 효과적:

```markdown
## STT 비용을 어떻게 줄였는가?
```
대신
```markdown
## 해결 과정
```

두 방식 모두 기존 톤을 크게 해치지 않으면서 AI 검색엔진이 뽑아 쓰기 좋은 형태. 신규 글부터 적용하고, 트래픽이 있는 기존 글에 점진 적용 권장.

## 4. GSC / 네이버 서치어드바이저 제출 체크리스트

인증 메타태그(`google-site-verification`, `naver-site-verification`)는 이미 사이트에 박혀 있음. 다만 인증 태그가 있다고 사이트맵이 자동 제출되는 건 아니므로 아래를 확인:

- [ ] Google Search Console(https://search.google.com/search-console) 에서 속성이 실제로 인증됐는지 확인
- [ ] GSC에 `https://dseung001.github.io/sitemap.xml` 제출 여부 확인, 안 됐으면 제출
- [ ] 네이버 서치어드바이저(https://searchadvisor.naver.com/) 에서도 동일하게 사이트맵 제출 여부 확인
- [ ] 이번에 새로 생긴 `/series/ostep-concurrency/`, `/series/class-s-project/`, `/series/rfc-study/` 3개 URL은 GSC의 "URL 검사" 도구로 색인 우선 요청(신규 페이지라 자연 크롤링까지 시간이 걸릴 수 있음)
- [ ] GSC "실적" 탭에서 현재 노출/클릭 상위 쿼리를 주기적으로 확인해 제목 리라이팅 우선순위(위 2번 항목) 판단에 활용
