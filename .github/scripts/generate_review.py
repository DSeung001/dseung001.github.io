#!/usr/bin/env python3
"""
블로그 포스트에 대한 AI 리뷰를 생성하고 Giscus Discussion에 코멘트로 추가
- 한 글당 리뷰 하나만 생성 (중복 방지)
- 전체 글 내용에 대한 리뷰
"""
import os
import re
import sys
import subprocess
from pathlib import Path
import google.generativeai as genai
import requests
from datetime import datetime

# 환경 변수
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
GITHUB_REPO = 'DSeung001/dseung001.github.io'
TARGET_FILE = os.getenv('TARGET_FILE', '')  # 특정 파일 지정 (선택적)

# GitHub API 설정
GITHUB_API_BASE = 'https://api.github.com'
GITHUB_HEADERS = {
    'Authorization': f'token {GITHUB_TOKEN}',
    'Accept': 'application/vnd.github.v3+json',
    'X-GitHub-Api-Version': '2022-11-28'
}

# Gemini API 설정
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-pro')

# 리뷰 프롬프트
REVIEW_PROMPT = """당신은 기술 블로그 글을 전문적으로 리뷰하는 AI 어시스턴트입니다. 
다음 블로그 글을 읽고 아래 항목들을 포함한 상세한 리뷰를 작성해주세요:

1. **글의 강점**: 글의 잘된 점, 명확하게 설명된 부분
2. **개선 제안**: 더 명확하게 할 수 있는 부분, 추가하면 좋을 내용
3. **기술적 정확성**: 기술적 내용의 정확성과 개선점
4. **가독성**: 구조, 문장, 예제 코드의 가독성
5. **고찰**: 이 글에 대한 고찰
6. **종합 평가**: 전체적인 평가와 추천 사항

리뷰는 건설적이고 친절한 톤으로 작성하며, 구체적인 예시와 함께 제안해주세요.
리뷰는 마크다운 형식으로 작성해주세요.
"""

def get_target_files():
    """리뷰할 파일 목록 가져오기"""
    # 1. TARGET_FILE 환경 변수로 특정 파일 지정
    if TARGET_FILE:
        if os.path.exists(TARGET_FILE):
            return [TARGET_FILE]
        else:
            print(f"⚠️  지정된 파일을 찾을 수 없습니다: {TARGET_FILE}")
            return []
    
    # 2. workflow_dispatch의 inputs에서 파일 지정
    event_path = os.getenv('GITHUB_EVENT_PATH')
    if event_path and os.path.exists(event_path):
        try:
            import json
            with open(event_path, 'r') as f:
                event = json.load(f)
                inputs = event.get('inputs', {})
                target = inputs.get('file_path', '')
                if target and os.path.exists(target):
                    return [target]
        except:
            pass
    
    # 3. Push 이벤트의 경우 변경된 파일만
    if os.getenv('GITHUB_EVENT_NAME') == 'push':
        try:
            before = os.getenv('GITHUB_SHA') + '~1'
            after = os.getenv('GITHUB_SHA')
            
            result = subprocess.run(
                ['git', 'diff', '--name-only', '--diff-filter=AM', before, after],
                capture_output=True,
                text=True,
                check=True
            )
            files = [
                f.strip() for f in result.stdout.split('\n')
                if f.strip().endswith('.md') and 'content/posts' in f
            ]
            return files
        except Exception as e:
            print(f"Error getting changed files: {e}")
            return []
    
    # 4. 모든 포스트 파일 (workflow_dispatch에서 전체 리뷰 옵션)
    posts_dir = Path('content/posts')
    if posts_dir.exists():
        md_files = list(posts_dir.rglob('*.md'))
        return [str(f) for f in md_files]
    
    return []

def read_markdown_file(filepath):
    """마크다운 파일 읽기"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return None

def extract_front_matter(content):
    """Front matter에서 제목과 메타데이터 추출"""
    front_matter_match = re.match(r'^---\n(.*?)\n---\n(.*)$', content, re.DOTALL)
    if front_matter_match:
        front_matter = front_matter_match.group(1)
        body = front_matter_match.group(2)
        
        title_match = re.search(r'^title:\s*["\']?(.*?)["\']?$', front_matter, re.MULTILINE)
        title = title_match.group(1) if title_match else "Unknown"
        
        return title, body
    return None, content

def filepath_to_permalink(filepath):
    """
    파일 경로를 Hugo permalink로 변환
    config.toml: posts = "/posts/:year/:month/:day/:contentbasename/"
    """
    path = Path(filepath)
    parts = path.parts
    
    if 'content' in parts and 'posts' in parts:
        posts_idx = parts.index('posts')
        post_parts = parts[posts_idx + 1:]
    else:
        return None
    
    if len(post_parts) < 4:
        return None
    
    year = post_parts[0]
    month = post_parts[1]
    day = post_parts[2]
    
    if len(post_parts) > 4:
        basename = post_parts[3]
    else:
        basename = post_parts[3].replace('.md', '').replace('index', '')
    
    basename = re.sub(r'[^\w\s-]', '', basename).strip()
    basename = re.sub(r'[-\s]+', '-', basename).lower()
    
    permalink = f"/posts/{year}/{month}/{day}/{basename}/"
    return permalink

def find_discussion_by_permalink(permalink):
    """permalink로 Discussion 찾기"""
    url = f"{GITHUB_API_BASE}/repos/{GITHUB_REPO}/discussions"
    params = {'per_page': 100, 'state': 'all'}
    
    page = 1
    while True:
        params['page'] = page
        response = requests.get(url, headers=GITHUB_HEADERS, params=params)
        
        if response.status_code != 200:
            print(f"Error fetching discussions: {response.status_code}")
            return None
        
        discussions = response.json()
        if not discussions:
            break
        
        for discussion in discussions:
            body = discussion.get('body', '').lower()
            title = discussion.get('title', '').lower()
            permalink_lower = permalink.lower()
            
            if permalink_lower in body or permalink_lower in title:
                return discussion['number']
            
            discussion_url = discussion.get('html_url', '')
            if permalink_lower.replace('/', '') in discussion_url.lower():
                return discussion['number']
        
        page += 1
        if len(discussions) < 100:
            break
    
    return None

def get_discussion_category_id():
    """Discussion 카테고리 ID 가져오기"""
    print(f"🔍 카테고리 ID 조회 중...")
    
    # 기존 Discussions에서 카테고리 정보 가져오기
    url = f"{GITHUB_API_BASE}/repos/{GITHUB_REPO}/discussions"
    params = {'per_page': 1}
    
    print(f"   1단계: 기존 Discussions에서 카테고리 정보 조회")
    print(f"   URL: {url}")
    
    response = requests.get(url, headers=GITHUB_HEADERS, params=params)
    
    print(f"   응답 상태: {response.status_code}")
    
    if response.status_code == 200:
        discussions = response.json()
        print(f"   조회된 Discussions 수: {len(discussions)}")
        
        if discussions:
            # 기존 Discussion에서 카테고리 ID 가져오기
            category = discussions[0].get('category', {})
            category_id = category.get('id')
            category_name = category.get('name', 'Unknown')
            
            if category_id:
                print(f"✅ 카테고리 ID: {category_id} (이름: {category_name})")
                return category_id
            else:
                print(f"   ⚠️  Discussion에 카테고리 정보가 없습니다.")
        else:
            print(f"   ⚠️  기존 Discussion이 없습니다.")
    elif response.status_code == 404:
        print(f"   ⚠️  Discussions API를 찾을 수 없습니다. Discussions가 활성화되지 않았을 수 있습니다.")
    else:
        print(f"   ⚠️  Discussions 조회 실패: {response.status_code}")
        try:
            error_data = response.json()
            print(f"   에러 메시지: {error_data.get('message', 'N/A')}")
        except:
            print(f"   응답: {response.text[:200]}")
    
    # Discussions가 없거나 카테고리를 찾을 수 없는 경우
    # 카테고리 목록 API 시도 (일부 저장소에서는 작동하지 않을 수 있음)
    print(f"   2단계: 카테고리 목록 API로 조회 시도")
    categories_url = f"{GITHUB_API_BASE}/repos/{GITHUB_REPO}/discussions/categories"
    print(f"   URL: {categories_url}")
    
    response = requests.get(categories_url, headers=GITHUB_HEADERS)
    
    print(f"   응답 상태: {response.status_code}")
    
    if response.status_code == 200:
        categories = response.json()
        print(f"   조회된 카테고리 수: {len(categories)}")
        
        if categories:
            print(f"   사용 가능한 카테고리:")
            for cat in categories:
                print(f"     - {cat.get('name')} (ID: {cat.get('id')})")
        
        # "Blog Comments" 카테고리 찾기
        for category in categories:
            if category.get('name') == 'Blog Comments':
                category_id = category.get('id')
                print(f"✅ 'Blog Comments' 카테고리 ID: {category_id}")
                return category_id
        
        # "Blog Comments"가 없으면 첫 번째 카테고리 사용
        if categories:
            first_category = categories[0]
            category_id = first_category.get('id')
            category_name = first_category.get('name')
            print(f"⚠️  'Blog Comments' 카테고리를 찾을 수 없어 첫 번째 카테고리를 사용합니다.")
            print(f"   사용할 카테고리: {category_name} (ID: {category_id})")
            return category_id
    elif response.status_code == 404:
        print(f"   ⚠️  카테고리 목록 API를 찾을 수 없습니다.")
    else:
        print(f"   ⚠️  카테고리 목록 조회 실패: {response.status_code}")
        try:
            error_data = response.json()
            print(f"   에러 메시지: {error_data.get('message', 'N/A')}")
        except:
            print(f"   응답: {response.text[:200]}")
    
    print(f"❌ 카테고리 ID를 찾을 수 없습니다.")
    print(f"💡 해결 방법:")
    print(f"   1. GitHub 저장소 Settings → General → Features에서 Discussions 활성화 확인")
    print(f"   2. 'Blog Comments' 카테고리가 생성되어 있는지 확인")
    return None

def create_discussion(permalink, post_title, post_url):
    """Discussion 자동 생성"""
    # 카테고리 ID 가져오기
    category_id = get_discussion_category_id()
    
    if not category_id:
        print(f"❌ 카테고리 ID를 가져올 수 없습니다.")
        return None
    
    url = f"{GITHUB_API_BASE}/repos/{GITHUB_REPO}/discussions"
    
    print(f"📋 Discussion 생성 정보:")
    print(f"   URL: {url}")
    print(f"   저장소: {GITHUB_REPO}")
    print(f"   카테고리 ID: {category_id}")
    print(f"   제목: {post_title}")
    
    # Giscus가 인식할 수 있도록 permalink를 body에 포함
    discussion_body = f"""이 Discussion은 다음 블로그 포스트에 대한 댓글을 위한 것입니다:

- **제목**: {post_title}
- **URL**: {post_url}
- **Permalink**: {permalink}

이 Discussion은 Giscus 댓글 시스템에서 자동으로 사용됩니다.
"""
    
    data = {
        'title': f"{post_title}",
        'body': discussion_body,
        'category': category_id  # 숫자 ID 사용
    }
    
    print(f"📤 요청 데이터:")
    print(f"   - title: {data['title']}")
    print(f"   - category: {data['category']}")
    print(f"   - body 길이: {len(data['body'])} 문자")
    
    # 헤더 정보 (토큰은 마스킹)
    auth_header = GITHUB_HEADERS.get('Authorization', '')
    masked_token = auth_header[:20] + '***' if auth_header else 'None'
    print(f"📤 요청 헤더:")
    print(f"   - Authorization: {masked_token}")
    print(f"   - Accept: {GITHUB_HEADERS.get('Accept', 'N/A')}")
    print(f"   - X-GitHub-Api-Version: {GITHUB_HEADERS.get('X-GitHub-Api-Version', 'N/A')}")
    
    try:
        response = requests.post(url, headers=GITHUB_HEADERS, json=data)
        
        print(f"📥 응답 정보:")
        print(f"   - 상태 코드: {response.status_code}")
        print(f"   - 응답 헤더: {dict(response.headers)}")
        
        if response.status_code == 201:
            discussion = response.json()
            print(f"✅ Discussion #{discussion['number']} 생성 완료")
            print(f"   Discussion URL: {discussion.get('html_url', 'N/A')}")
            return discussion['number']
        else:
            print(f"❌ Discussion 생성 실패: {response.status_code}")
            print(f"📥 응답 본문:")
            try:
                error_data = response.json()
                print(f"   {error_data}")
                
                # 에러 메시지 분석
                if 'message' in error_data:
                    print(f"\n🔍 에러 분석:")
                    error_msg = error_data['message']
                    print(f"   메시지: {error_msg}")
                    
                    if 'Not Found' in error_msg:
                        print(f"   💡 가능한 원인:")
                        print(f"      1. 저장소에 Discussions가 활성화되지 않았을 수 있습니다.")
                        print(f"         → GitHub 저장소 Settings → General → Features에서 Discussions 활성화 확인")
                        print(f"      2. 카테고리 ID가 잘못되었을 수 있습니다.")
                        print(f"         → 현재 카테고리 ID: {category_id}")
                        print(f"      3. API 권한이 부족할 수 있습니다.")
                        print(f"         → GITHUB_TOKEN에 'write:discussions' 권한이 있는지 확인")
                    elif 'Bad Request' in error_msg or 'Validation Failed' in error_msg:
                        print(f"   💡 가능한 원인:")
                        print(f"      1. 요청 데이터 형식이 잘못되었을 수 있습니다.")
                        print(f"      2. 카테고리 ID가 유효하지 않을 수 있습니다.")
                        print(f"      3. 제목이나 본문이 너무 길 수 있습니다.")
                elif 'errors' in error_data:
                    print(f"   상세 에러:")
                    for error in error_data['errors']:
                        print(f"     - {error}")
                        
            except ValueError:
                print(f"   (JSON 파싱 실패) 원본 텍스트:")
                print(f"   {response.text}")
            
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"❌ 네트워크 오류 발생:")
        print(f"   {str(e)}")
        return None

def has_existing_ai_review(discussion_number):
    """Discussion에 이미 AI 리뷰 코멘트가 있는지 확인"""
    url = f"{GITHUB_API_BASE}/repos/{GITHUB_REPO}/discussions/{discussion_number}/comments"
    params = {'per_page': 100}
    
    page = 1
    while True:
        params['page'] = page
        response = requests.get(url, headers=GITHUB_HEADERS, params=params)
        
        if response.status_code != 200:
            return False
        
        comments = response.json()
        if not comments:
            break
        
        for comment in comments:
            body = comment.get('body', '')
            # AI 리뷰 마커 확인
            if '🤖 AI 리뷰:' in body or 'Google Gemini API를 사용하여 자동으로 생성' in body:
                return True
        
        page += 1
        if len(comments) < 100:
            break
    
    return False

def generate_review(content):
    """Gemini API를 사용하여 리뷰 생성 (전체 내용)"""
    try:
        # 전체 내용 사용 (변경 내역이 아닌)
        # Gemini 토큰 제한 고려하여 최대 30000자까지
        content_for_review = content[:30000] if len(content) > 30000 else content
        
        if len(content) > 30000:
            print(f"⚠️  내용이 길어서 처음 30000자만 사용합니다.")
        
        prompt = REVIEW_PROMPT + content_for_review
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"Error generating review: {e}")
        return None

def create_discussion_comment(discussion_number, review_text, post_title):
    """Discussion에 리뷰 코멘트 추가"""
    url = f"{GITHUB_API_BASE}/repos/{GITHUB_REPO}/discussions/{discussion_number}/comments"
    
    comment_body = f"""## 🤖 AI 리뷰: {post_title}

{review_text}

---
*이 리뷰는 Google Gemini API를 사용하여 자동으로 생성되었습니다.*  
*생성 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S KST')}*
"""
    
    data = {'body': comment_body}
    
    response = requests.post(url, headers=GITHUB_HEADERS, json=data)
    
    if response.status_code == 201:
        comment_url = response.json().get('html_url', '')
        print(f"✅ 리뷰 코멘트가 성공적으로 추가되었습니다!")
        print(f"   코멘트 URL: {comment_url}")
        return True
    else:
        print(f"❌ 코멘트 추가 실패: {response.status_code}")
        print(f"Response: {response.text}")
        return False

def main():
    """메인 함수"""
    if not GEMINI_API_KEY:
        print("❌ GEMINI_API_KEY 환경 변수가 설정되지 않았습니다.")
        sys.exit(1)
    
    if not GITHUB_TOKEN:
        print("❌ GITHUB_TOKEN 환경 변수가 설정되지 않았습니다.")
        sys.exit(1)
    
    # 대상 파일 가져오기
    target_files = get_target_files()
    
    if not target_files:
        print("📝 리뷰할 포스트 파일이 없습니다.")
        return
    
    print(f"📝 리뷰할 파일: {len(target_files)}개\n")
    
    success_count = 0
    skip_count = 0
    error_count = 0
    
    for filepath in target_files:
        print(f"{'='*60}")
        print(f"📄 처리 중: {filepath}")
        
        # 파일 읽기
        content = read_markdown_file(filepath)
        if not content:
            print("⚠️  파일을 읽을 수 없습니다. 건너뜁니다.\n")
            error_count += 1
            continue
        
        # Front matter에서 제목 추출
        title, body = extract_front_matter(content)
        print(f"📌 제목: {title}")
        
        # Permalink 계산
        permalink = filepath_to_permalink(filepath)
        if not permalink:
            print(f"⚠️  Permalink를 계산할 수 없습니다. 건너뜁니다.\n")
            error_count += 1
            continue
        print(f"🔗 Permalink: {permalink}")
        
        # Discussion 찾기
        print(f"🔍 Discussion 찾는 중...")
        discussion_number = find_discussion_by_permalink(permalink)
        
        if not discussion_number:
            print(f"⚠️  Discussion을 찾을 수 없습니다.")
            print(f"   Permalink: {permalink}")
            print(f"🔄 Discussion 자동 생성 중...")
            
            # 블로그 URL 생성
            base_url = "https://dseung001.github.io"
            post_url = f"{base_url}{permalink}"
            
            # Discussion 자동 생성
            discussion_number = create_discussion(permalink, title, post_url)
            
            if not discussion_number:
                print(f"❌ Discussion 생성 실패. 건너뜁니다.\n")
                error_count += 1
                continue
            
            print(f"✅ Discussion #{discussion_number} 생성 완료")
        else:
            print(f"✅ Discussion #{discussion_number} 찾음")
        
        # 이미 리뷰가 있는지 확인
        print(f"🔍 기존 리뷰 확인 중...")
        if has_existing_ai_review(discussion_number):
            print(f"⏭️  이미 AI 리뷰가 존재합니다. 건너뜁니다.\n")
            skip_count += 1
            continue
        
        print(f"✅ 새로운 리뷰 생성 가능")
        
        # 리뷰 생성 (전체 내용)
        print("🤖 AI 리뷰 생성 중...")
        review = generate_review(body)
        
        if not review:
            print("❌ 리뷰 생성 실패\n")
            error_count += 1
            continue
        
        print("✅ 리뷰 생성 완료")
        
        # 코멘트 추가
        print(f"💬 Discussion에 코멘트 추가 중...")
        if create_discussion_comment(discussion_number, review, title):
            success_count += 1
        else:
            error_count += 1
        print()
    
    # 결과 요약
    print(f"{'='*60}")
    print(f"📊 처리 결과:")
    print(f"   ✅ 성공: {success_count}개")
    print(f"   ⏭️  건너뜀 (이미 리뷰 존재): {skip_count}개")
    print(f"   ❌ 실패: {error_count}개")

if __name__ == '__main__':
    main()