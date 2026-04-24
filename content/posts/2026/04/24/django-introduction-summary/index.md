---
title: "Django 6.0 Introduction Summary"
date: 2026-04-24T00:00:00+09:00
categories: [ "Memo", "Digging", "Django" ]
tags: [ "Django", "Python", "Web", "ORM", "MVT", "Tutorial" ]
draft: false
description: "Django 6.0 Introduction 문서 흐름 정리"
keywords: [ "Django 6.0", "Django tutorial", "Polls app", "Django admin", "CMS", ]
author: "DSeung001"
lastmod: 2026-04-24T00:00:00+09:00
---

# 서론
해당 글은 Laravel, Spring, Gin 등 다양한 프레임워크를 사용해 본 입장에서 Django를 살펴보며 정리한 메모입니다.
Django 6.0 기준으로 [Introduction](https://docs.djangoproject.com/ko/6.0/intro/)은 다음과 같이 구성되어 있습니다.

```
Django 훑어보기
빠른 설치 가이드
장고 앱 작성하기, part 1 ~ 8
심화 튜토리얼: 재사용 가능한 앱을 만드는 법
다음에 읽을 내용
장고에 처음으로 기여하기
```

# Django 훑어보기
튜토리얼이 아닌 제목 그대로 Django의 동작 방식에 대해 설명하고 있습니다. <br/>
## Model
처음은 모델과 ORM(object-relational mapper)으로 시작하며, Django의 [Model](https://docs.djangoproject.com/ko/6.0/topics/db/models/)을 먼저 보여줍니다.

Reporter와 Article로 모델 클래스의 관계를 다음처럼 표현합니다.
파이썬의 `__str__` 매직 메서드로 모델 객체의 표시 형태도 지정합니다.
```python
from django.db import models


class Reporter(models.Model):
    full_name = models.CharField(max_length=70)

    def __str__(self):
        return self.full_name


class Article(models.Model):
    pub_date = models.DateField()
    headline = models.CharField(max_length=200)
    content = models.TextField()
    reporter = models.ForeignKey(Reporter, on_delete=models.CASCADE)

    def __str__(self):
        return self.headline
```
## CLI & Python API
그다음 풀스택 프레임워크에서 중요한 CLI로 [migrations](https://docs.djangoproject.com/ko/6.0/topics/migrations/)를 보여줍니다.
```bash
python manage.py makemigrations # 생성 가능한 모델을 찾아 테이블이 존재하지 않는 경우 마이그레이션 생성
python manage.py migrate # 마이그레이션을 실행하고 사용자 DB에 테이블 생성
```
CLI에서 Python API(데이터베이스 추상화 API)를 사용해 Reporter 데이터를 다루는 부분은 Laravel의 Artisan CLI와 굉장히 비슷하네요.
```python
# class import
>>> from news.models import Article, Reporter 

 # 리스트 출력 
>>> Reporter.objects.all()
<QuerySet []>
# 데이터 생성
>>> r = Reporter(full_name="John Smith") 
# 데이터 저장
>>> r.save()
# ID 출력 
>>> r.id
1

# 리스트 재출력 
>>> Reporter.objects.all()
<QuerySet [<Reporter: John Smith>]>

# 이름 출력 
>>> r.full_name
'John Smith'

# Django DB lookup API 사용
# id 검색
>>> Reporter.objects.get(id=1)
<Reporter: John Smith>
# full_name 중에 `John`로 시작하는 거 검색
>>> Reporter.objects.get(full_name__startswith="John")
<Reporter: John Smith>
# full_name에 `mith` 포함되는 거 검색
>>> Reporter.objects.get(full_name__contains="mith")
<Reporter: John Smith>
# 존재하지 않는 데이터 검색
>>> Reporter.objects.get(id=2)
Traceback (most recent call last):
    ...
DoesNotExist: Reporter matching query does not exist.

# article 생성
>>> from datetime import date
>>> a = Article(
...     pub_date=date.today(), headline="Django is cool", content="Yeah.", reporter=r
... )
>>> a.save()

>>> Article.objects.all()
<QuerySet [<Article: Django is cool>]>

# Article과 관련된 Reporter 가져오기
>>> r = a.reporter
>>> r.full_name
'John Smith'

# Reporter와 관련된 Article 가져오기
>>> r.article_set.all()
<QuerySet [<Article: Django is cool>]>

# 조인된 관계를 이용해 reporter 조건으로 데이터 검색
>>> Article.objects.filter(reporter__full_name__startswith="John")
<QuerySet [<Article: Django is cool>]>

# 리포터 이름 업데이트
>>> r.full_name = "Billy Goat"
>>> r.save()

# 리포터 삭제
>>> r.delete()
```
## Admin interface
신기한 점은 Django에서 제공하는 admin 관련 기능은 단순 스케폴딩이 아닌 완성되었다는 점을 어필하는 부분이네요.
모델만 정의되면 바로 전문적으로 사용할 수 있기 때문에 모델의 등록만을 언급하고 있습니다.
사이트 관리를 위한 단순 CRUD 같은 부분은 자동으로 해주기 때문에 별도 인터페이스를 일일이 만들 필요가 없다고 언급하네요.

아래와 같이 모델이 있을 경우
<br/>
`news/models.py`
```python
from django.db import models


class Article(models.Model):
    pub_date = models.DateField()
    headline = models.CharField(max_length=200)
    content = models.TextField()
    reporter = models.ForeignKey(Reporter, on_delete=models.CASCADE)
```
admin에 등록만 하면 바로 관련 기능이 추가됩니다. <br/>
`news/admin.py`
```python
from django.contrib import admin

from . import models

admin.site.register(models.Article)
```
데이터 CRUD가 위처럼 연결만 하면 구현되니, 바로 URL 설계로 넘어가는 흐름이 좋더군요.
물론 더 복잡한 데이터나 업무 규칙이 있다면 커스텀이 필요하겠지만, 단순 CRUD에서는 확실히 편리합니다.
## URL
다른 프레임워크와 마찬가지로 `.php`나 `.go` 같은 파일 확장자가 URL에 노출되지 않으며, URL 패턴을 코드로 선언할 수 있습니다.
이와 관련해서 Django는 [URL Dispatcher](https://docs.djangoproject.com/en/6.0/topics/http/urls/)를 별도 문서로 분리해 설명하고 있네요.<br/>
`news/urls.py`
```python
from django.urls import path

from . import views

urlpatterns = [
    path("articles/<int:year>/", views.year_archive),
    path("articles/<int:year>/<int:month>/", views.month_archive),
    path("articles/<int:year>/<int:month>/<int:pk>/", views.article_detail),
]
```
사용자 요청 URL이 패턴 중 하나와 일치하면 Django는 해당 뷰를 호출합니다.
각 뷰에는 요청 메타데이터가 담긴 request 객체와, 패턴(URL 변수)에서 캡처한 값이 전달됩니다.

예를 들어 `/articles/2005/05/39323/`로 요청이 들어오면, view는 다음처럼 변수를 받습니다.
`news.views.article_detail(request, year=2005, month=5, pk=39323)`
## View
뷰의 역할은 response 객체를 반환하거나 예외를 처리하는 것이고, 일반적으로 템플릿을 렌더링해 응답을 만듭니다.
아래 코드를 보면 `render()` 함수를 통해 context 값을 넘기는 걸 알 수 있습니다.<br/>

`news/views.py`
```python
from django.shortcuts import render

from .models import Article

def year_archive(request, year):
    a_list = Article.objects.filter(pub_date__year=year)
    context = {"year": year, "article_list": a_list}
    return render(request, "news/year_archive.html", context)
```
## Template 
[Template](https://docs.djangoproject.com/ko/6.0/topics/templates/)로 사용자에게 보여줄 화면을 만들고
View에서 전달받은 데이터를 렌더링할 수 있습니다. Template은 상속도 할 수 있습니다. <br/>

`templates/base.html`
```html
{% load static %}
<html lang="en">
<head>
    <title>{% block title %}{% endblock %}</title>
</head>
<body>
    <img src="{% static 'images/sitelogo.png' %}" alt="Logo">
    {% block content %}{% endblock %}
</body>
</html>
```

`news/templates/news/year_archive.html`
```html
{% extends "base.html" %}

{% block title %}Articles for {{ year }}{% endblock %}

{% block content %}
<h1>Articles for {{ year }}</h1>

{% for article in article_list %}
    <p>{{ article.headline }}</p>
    <p>By {{ article.reporter.full_name }}</p>
    <p>Published {{ article.pub_date|date:"F j, Y" }}</p>
{% endfor %}
{% endblock %}
```
`extends` 키워드로 템플릿을 상속할 수 있고, `{{}}`로 템플릿 안에 데이터를 표현할 수 있으며, `load static`으로 정적 파일에 접근할 수 있습니다. 여기까지는 다른 프레임워크와 크게 다르지 않아 보이네요.

Introduction에서는 여기까지가 Django의 겉모습(개요)이고, 아래 고급 기능도 있다고 언급합니다.
- memcached나 기타 백엔드와 통합된 캐시 프레임워크
- Python 클래스를 약간만 작성해도 RSS 및 Atom 피드를 만들어주는 syndication framework
- 지금 글 보다 더 매력적인 자동생성 관리자 기능 

Django의 특징은 MVC 패턴의 Controller를 별도 계층으로 분리하기보다는 View + URLconf(+ 일부 미들웨어)로 역할을 나눠 갖는다는 점입니다.
그래서 Django를 MVC가 아닌 MVT(Model-View-Template)라 칭합니다.
- MVC의 Model → Django Model
- MVC의 View(화면) → Django Template
- MVC의 Controller → Django View 함수/클래스(CBV) + URL dispatcher

# 빠른 설치 가이드
설치는 pip을 설치 후 os 환경에 맞게 python 가상환경을 만들어 작업을 진행합니다.
<br/>

`Linux`

```bash
python3 -m venv ~/.virtualenvs/djangodev
source ~/.virtualenvs/djangodev/bin/activate 
# source가 안될 경우
. ~/.virtualenvs/djangodev/bin/activate
python -m pip install Django
```

`Window`
```bash
py -m venv %HOMEPATH%\.virtualenvs\djangodev
%HOMEPATH%\.virtualenvs\djangodev\Scripts\activate.bat
py -m pip install Django
```

다음처럼 djangodev이라는 이름으로 가상환경을 활성화했습니다.
```bash
(djangodev) C:\Users\seung\.virtualenvs>python
Python 3.13.13 (tags/v3.13.13:01104ce, Apr  7 2026, 19:25:48) [MSC v.1944 64 bit (AMD64)] on win32
Type "help", "copyright", "credits" or "license" for more information.
>>> import django
>>> print(django.get_version())
6.0.4
```

# 장고 앱 작성하기, part 1 ~ 8
Introduction은 설문조사 앱을 튜토리얼로 만들었습니다.
특징은 다음 기능을 포함하고 있는거네요.
- 여론조사를 보고 투표할 수 있는 공개 사이트
- 설문조사를 추가, 변경 및 삭제 할 수 있는 관리자 사이트

## part 1 
아래 명령어로 djangotutorial 디렉터리에 Django 프로젝트를 만들면서 프로젝트 패키지인 `mysite`가 함께 생성합니다.
```bash
django-admin startproject mysite djangotutorial
```

``` bash
djangotutorial/
    manage.py # Django CLI utility 
    mysite/ # 패키지명
        __init__.py # 패키지 식별자 파일
        settings.py # Django 프로젝트 설정/구성
        urls.py # [URL dispatcher](https://docs.djangoproject.com/en/6.0/topics/http/urls/)
        asgi.py # ASGI 호환 웹 서버가 프로젝트를 제공하기 위한 진입점
        wsgi.py # WSGI 호환 웹 서버가 프로젝트를 제공하기 위한 진입점
```

**※ CGI**<br/>
CGI(Common Gateway Interface)는 웹 서버가 동적 페이지를 제공하기 위해 외부 프로그램을 실행할 수 있게 해 주는 초기 표준 인터페이스입니다. 초기 웹은 정적 문서를 주로 제공했지만, 사용자 요청(URL)에 따라 다른 결과를 만들어야 하면서 CGI 같은 방식이 필요해졌습니다.<br/>

**※ WSGI와 ASGI**<br/>
CGI 이후 파이썬 웹 생태계에서는 WSGI(Web Server Gateway Interface)가 오랫동안 표준으로 사용되었고, 현재는 비동기 처리와 장기 연결을 지원하는 ASGI(Asynchronous Server Gateway Interface)도 널리 사용됩니다.

| 구분 | WSGI (Web Server Gateway Interface) | ASGI (Asynchronous Server Gateway Interface) |
| ---- | ----------------------------------- | -------------------------------------------- |
| 처리 방식 | 동기 (Synchronous, 순차적) | 비동기 (Asynchronous, 병렬적) |
| 주요 용도 | 전통적인 CRUD 웹 사이트 | 실시간 채팅, 게임, IoT, 알림 서비스 |
| 연결 방식 | 한 요청당 한 응답 (Short-lived) | 연결 유지 및 양방향 통신 (Long-lived) |
| 장고 파일 | wsgi.py | asgi.py |

- **동기(WSGI)**: 같은 워커(또는 스레드)가 한 건의 요청을 처리할 때 DB·파일 I/O를 기다리는 동안 흐름이 멈추는(블로킹) 전통적인 처리 방식에 가깝다는 의미입니다.

- **비동기(ASGI)**: I/O(네트워크, DB, 파일)를 기다릴 때 하나의 스레드가 계속 묶여 있을 필요 없이, 이벤트 루프가 다른 작업을 이어서 처리할 수 있는 방식에 가깝습니다. HTTP 응답 자체는 WSGI/ASGI 모두 가능하지만, 장기 연결·WebSocket·높은 동시 I/O 같은 **연결/동시성 모델**에서 차이가 보입니다.

이제 개발 서버를 다음 명령어로 실행할 수 있습니다.
```
py manage.py runserver
```

이제 본격적으로 설문조사 앱을 만드는데, mysite 패키지와 동일한 곳에 polls 패키지를 생성합니다.
```
py manage.py startapp polls
```
이번에는 `startproject`가 아니라 `startapp` 관리 명령어를 사용했기 때문에, 생성되는 폴더 구조가 다릅니다.
```bash
polls/
    migrations/
        __init__.py # 마이그레이션 패키지 식별자 파일
    __init__.py # polls 패키지 식별자 파일
    admin.py # Django 관리자 사이트 등록/설정
    apps.py # 앱 설정 클래스(AppConfig) 정의
    models.py # 데이터 모델 정의
    tests.py # 앱 테스트 코드 작성
    views.py # 요청 처리 로직(뷰) 작성
```
Django에서 자주 사용하는 관리 명령어를 간단히 정리하면 다음과 같습니다.

| 명령어 | 용도 |
| --- | --- |
| `startproject` | 프로젝트 뼈대 생성 |
| `startapp` | 앱(기능 모듈) 뼈대 생성 |
| `runserver` | 개발 서버 실행 |
| `makemigrations` | 모델 변경사항을 마이그레이션 파일로 생성 |
| `migrate` | DB에 마이그레이션 적용 |
| `createsuperuser` | 관리자 계정 생성 |

여기까지 프로젝트와 앱의 뼈대를 생성했습니다. 이제 뷰를 URL에 연결하는 작업을 진행합니다.
다음 코드를 따라가면서 `polls` 앱에 view와 urls를 등록하고, 메인 프로젝트 URLconf에 include 하면 `http://localhost:8000/polls/`에서 다음 문구를 확인할 수 있습니다.
```
Hello, world. You're at the polls index.
```
`polls/views.py`
```python
from django.http import HttpResponse

def index(request):
    # 아직은 템플릿을 사용하지 않고 HttpResponse를 직접 반환
    return HttpResponse("Hello, world. You're at the polls index.") 
```
`polls/urls.py`
```python
from django.urls import path
from . import views

# polls 앱의 URLconf 설정
urlpatterns = [
    path("", views.index, name="index"),
]
```
`mysite/urls.py`
```python
from django.contrib import admin
from django.urls import include, path

# 프로젝트 루트 URLconf mysite에 polls.urls를 포함
urlpatterns = [
    path("polls/", include("polls.urls")),
    path("admin/", admin.site.urls),
]
```

## part 2
`mysite/settings.py.`에서 DB나 Time zone 설정이 가능하다는 점과 Django에서 제공하는 `INSTALLED_APPS`를 보여줍니다.
`INSTALLED_APPS`는 Django 설치에서 활성화된 모든 애플리케이션을 지정하는 문자열 목록입니다.

기본적으로 `mysite/settings.py.`에 다음 앱들이 포함되어 있는데, 필요에 따라 주석 처리하거나 삭제로 기능을 뺄 수 있습니다다.
```python
# Application definition

INSTALLED_APPS = [
    'django.contrib.admin', # 관리자 사이트
    'django.contrib.auth', # 인증 시스템
    'django.contrib.contenttypes', # 콘텐츠 유형을 위한 프레임워크
    'django.contrib.sessions', # 세션 프레임워크
    'django.contrib.messages', # 메시징 프레임워크
    'django.contrib.staticfiles', # 정적 파일을 관리하기 위한 프레임워크
] 
```

이제 다시 본론으로 돌아와 설문조사 앱의 모델을 만들겠습니다.<br/><br/>
**※ 모델(Model)**: 모델은 데이터의 구조와 동작을 정의하는 객체입니다. Django는 [DRY 원칙](https://docs.djangoproject.com/en/6.0/misc/design-philosophies/#dry)을 따르며, 목표는 데이터 모델을 한 곳에 정의하고 그로부터 필요한 정보를 자동으로 도출하는 것입니다.<br/>
**※ 마이그레이션(Migration)**: Django가 현재 모델에 맞춰 데이터베이스 스키마를 업데이트하는 데 사용하는 이력을 형성합니다.

설문조사 앱을 만들기 위해 아래 2개의 모델을 만듭니다.
- **Question**: 설문지와 발행일 정보
- **Choice**: 선택 내용과 득표 수

```python
from django.db import models

class Question(models.Model):
    question_text = models.CharField(max_length=200)
    pub_date = models.DateTimeField('date published')

class Choice(models.Model):
    # Question의 외래 키를 참조하고, Question이 삭제되면 관련 레코드도 삭제됩니다.
    # 여기서는 1(Question):N(Choice) 관계를 구현합니다.
    question = models.ForeignKey(Question, on_delete=models.CASCADE) 
    choice_text = models.CharField(max_length=200)
    votes = models.IntegerField(default=0)
```

위처럼 모델을 생성했다면 해당 모델이 포함된 앱을 `INSTALLED_APPS`에 등록해야 Django가 모델을 로드하고 `makemigrations`/`migrate` 대상에 포함할 수 있습니다.
```python
INSTALLED_APPS = [
    "polls.apps.PollsConfig",
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]
```
이제 마이그레이션을 실행하면 `migrations` 폴더에 파일이 생기는 것을 확인할 수 있습니다.<br/>
마이그레이션과 모델 개념은 라라벨과 유사합니다. 풀스택 프레임워크의 공통적인 방향성을 볼 수 있습니다.
```bash
py manage.py makemigrations polls
Migrations for 'polls':
  polls\migrations\0001_initial.py
    + Create model Question
    + Create model Choice
```
생성된 `polls\migrations\0001_initial.py`으로 수동으로 수정할 수도 있습니다.<br/>
이 마이그레이션이 실제로 어떤 SQL로 변환되는지도 확인할 수 있습니다.

```bash
py manage.py sqlmigrate polls 0001
```
```sql
BEGIN;
--
-- Create model Question
--
CREATE TABLE "polls_question" (
    "id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, 
    "question_text" varchar(200) NOT NULL, 
    "pub_date" datetime NOT NULL
);
--
-- Create model Choice
-- polls_question의 키가 ForeignKey로 인해 생긴걸 확인할 수 있네요
CREATE TABLE "polls_choice" (
    "id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, 
    "choice_text" varchar(200) NOT NULL, 
    "votes" integer NOT NULL, 
    "question_id" bigint NOT NULL  
    REFERENCES "polls_question" ("id") DEFERRABLE INITIALLY DEFERRED);
CREATE INDEX "polls_choice_question_id_c5b4b260" ON "polls_choice" ("question_id");
COMMIT;
```
여기서 주의할 점은 다음과 같습니다.
- 사용 중인 DB에 따라 결과가 달라집니다. 여기서는 기본 설정인 SQLite 기준입니다.
- 테이블 이름은 APP이름과 모델 이름이 소문자로 자동 조합되어 생성됩니다.
- 기본 키는 기본적으로 `id` 필드가 추가됩니다. (`DEFAULT_AUTO_FIELD`로 기본 타입을 설정할 수 있습니다.)
- 외래 키 컬럼명은 기본적으로 `<필드명>_id` 형태로 생성됩니다.
- 자료형은 사용 중인 DB에 맞춰 매핑됩니다.
- `sqlmigrate`는 실제 데이터베이스에서 마이그레이션을 실행하는 것이 아니라 SQL 문을 화면에 출력하는 명령입니다. 
Django가 어떤 작업을 수행할지 확인하거나, 변경을 위해 SQL 스크립트가 필요한 데이터베이스 관리자가 있는 경우에 유용합니다.

이제 migrate을 실행하면 DB에 생성이 됩니다.<br/>
**※ 마이그레이트(Migrate)**: 모델의 변경 사항을 DB 스키마에 동기화
```bash
py manage.py migrate
Operations to perform:
  Apply all migrations: admin, auth, contenttypes, polls, sessions
Running migrations:
  Applying contenttypes.0001_initial... OK
  Applying auth.0001_initial... OK
  Applying admin.0001_initial... OK
  Applying admin.0002_logentry_remove_auto_add... OK
  Applying admin.0003_logentry_add_action_flag_choices... OK
  Applying contenttypes.0002_remove_content_type_name... OK
  Applying auth.0002_alter_permission_name_max_length... OK
  Applying auth.0003_alter_user_email_max_length... OK
  Applying auth.0004_alter_user_username_opts... OK
  Applying auth.0005_alter_user_last_login_null... OK
  Applying auth.0006_require_contenttypes_0002... OK
  Applying auth.0007_alter_validators_add_error_messages... OK
  Applying auth.0008_alter_user_username_max_length... OK
  Applying auth.0009_alter_user_last_name_max_length... OK
  Applying auth.0010_alter_group_name_max_length... OK
  Applying auth.0011_update_proxy_permissions... OK
  Applying auth.0012_alter_user_first_name_max_length... OK
  Applying polls.0001_initial... OK
```

이제 Python API로 [쿼리](https://docs.djangoproject.com/en/6.0/topics/db/queries/)를 만들며 테스트해 봅시다.
간단하게 Question 만들고, 데이터 수정한 뒤 저장하는 플로우입니다.
```bash
py manage.py shell

>>> Question.objects.all()
<QuerySet []>

>>> from django.utils import timezone
>>> q = Question(question_text="What's new?", pub_date=timezone.now())
>>> q.save()
>>> q.id
1
>>> q.question_text
"What's new?"
>>> q.pub_date
datetime.datetime(2012, 2, 26, 13, 0, 0, 775217, tzinfo=datetime.UTC)

>>> q.question_text = "What is up?"
>>> q.save()
>>> Question.objects.all()
<QuerySet [<Question: Question object (1)>]>
```

여기서 `<QuerySet [<Question: Question object (1)>]>` 표현이 마음에 들지 않는다면 파이썬 매직 메서드인 `__str__()`를 추가하면 객체 표현 방식이 더 읽기 좋아집니다.

`polls/models.py`
```python
from django.db import models


class Question(models.Model):
    # ...
    def __str__(self):
        return self.question_text


class Choice(models.Model):
    # ...
    def __str__(self):
        return self.choice_text
```
모델에 사용자 정의 메서드도 다음처럼 추가할 수 있습니다.<br/>
`polls/models.py`
```python
import datetime

from django.db import models
from django.utils import timezone


class Question(models.Model):
    # ...

    # 최근 발행글인지 체크하는 메서드
    def was_published_recently(self):
        return self.pub_date >= timezone.now() - datetime.timedelta(days=1)
```
그다음 한 번 더 `Python API`로 Question, Choice 데이터를 제어해 봅시다.
```bash
>>> Question.objects.all()
<QuerySet [<Question: What is up?>]>

# 필터
>>> Question.objects.filter(id=1)
<QuerySet [<Question: What is up?>]>
>>> Question.objects.filter(question_text__startswith="What")
<QuerySet [<Question: What is up?>]>

# current_year 변수 선언
>>> from django.utils import timezone
>>> current_year = timezone.now().year
>>> Question.objects.get(pub_date__year=current_year)
<Question: What is up?>

>>> Question.objects.get(id=2)
# 존재하지 않는 데이터로 에러 발생
Traceback (most recent call last):
    ...
DoesNotExist: Question matching query does not exist.

# pk(실제 컬럼 키 id)로 검색, Question.objects.get(id=1)와 동일
>>> Question.objects.get(pk=1)
<Question: What is up?>

# 사용자 정의 메서드 테스트
>>> q = Question.objects.get(pk=1)
>>> q.was_published_recently()
True

# 외래 키 역참조 `choice_set` 테스트
>>> q = Question.objects.get(pk=1)
>>> q.choice_set.all()
<QuerySet []>

# choice_set으로 choice 데이터 생성
>>> q.choice_set.create(choice_text="Not much", votes=0)
<Choice: Not much>
>>> q.choice_set.create(choice_text="The sky", votes=0)
<Choice: The sky>
>>> c = q.choice_set.create(choice_text="Just hacking again", votes=0)

>>> c.question
<Question: What is up?>

# q와 매핑된 choice 목록
>>> q.choice_set.all()
<QuerySet [<Choice: Not much>, <Choice: The sky>, <Choice: Just hacking again>]>
>>> q.choice_set.count()
3

>>> Choice.objects.filter(question__pub_date__year=current_year)
<QuerySet [<Choice: Not much>, <Choice: The sky>, <Choice: Just hacking again>]>

# choice 데이터 필터로 가져온 뒤 삭제
>>> c = q.choice_set.filter(choice_text__startswith="Just hacking")
>>> c.delete()
```

모델 관계를 많이 다뤘는데, 더 자세한 부분은 [모델 관계](https://docs.djangoproject.com/en/6.0/ref/models/relations/)로 볼 수 있습니다.
필드는 [field lookup](https://docs.djangoproject.com/en/6.0/topics/db/queries/#field-lookups-intro)에서 볼 수 있습니다.

이제는 Django 관리자 단을 연결합니다. <br/>
**※ Django 관리자**: 데이터 CRUD는 반복 업무이므로 관리자 인터페이스로 자동화할 수 있습니다. 또한 뉴스룸 환경에 맞춰 개발되었기에 `콘텐츠 게시자`와 `공개 콘텐츠츠`의 구분이 명확합니다.

분명한 점은 관리자 페이지는 방문자용이 아닌 사이트 관리자 전용입니다.<br/>

다음 명령어를 통해 관리자 계정을 만들고, `http://127.0.0.1:8000/admin`를 접속하여 로그인을 할 수 있습니다.
```bash
(djangodev) C:\Users\seung\.virtualenvs\djangotutorial>py manage.py createsuperuser
Username (leave blank to use 'seung'):
Email address: seung@gmail.com
Password:
Password (again):
This password is too short. It must contain at least 8 characters.
This password is too common.
This password is entirely numeric.
Bypass password validation and create user anyway? [y/N]: y
Superuser created successfully.
```

하지만 처음 접속 시에는 Question을 관리할 수 없으므로 등록해 줘야 합니다.<br/>
`polls/admin.py`
```python
from django.contrib import admin

from .models import Question

admin.site.register(Question)
```
등록해주고 `http://127.0.0.1:8000/admin`을 접속하면 POLLS/Questions 항목이 생기는 걸 확인할 수 있죠.
이제 Questions 테이블의 컬럼에 맞춘 입력 폼과 CRUD 기능을 확인할 수 있습니다. <br/>

이 자동화 기능은 꽤 편리합니다. 단순 CRUD 작업을 위해 일일이 모델 작성, 서비스 로직 구성, API 연결, 뷰 작성 등 반복하는 부담을 줄여 주기 때문에 특히 단순한 관리 기능에서 유용한 것 같습니다, 복잡한 모델 관계가 생기면 어떻게 될지는 봐야겠군요.

## part 3
설문조사 앱은 다음 보기 방식을 가집니다.
- 설문지 "색인" 페이지: 최근 설문지 몇 개를 표시합니다.
- 설문지 "상세" 페이지: 설문지 텍스트만 표시되고 결과는 없지만 투표 양식이 있습니다.
- 설문지 "결과" 페이지: 특정 설문지에 대한 결과를 표시합니다.
- 투표 동작: 특정 설문지에서 특정 선택에 투표하는 것을 처리합니다.
이를 URLconf로 세련되게 만든다고 하군요, URL Dispachter랑 같이 개념을 명확히 하자만
- **URL Dispatcher**: Django의 URL 라우팅 시스템 전체 개념/메커니즘으로 Reuqest URL을 받아 `urlpatters`를 순서대로 매치앺서 view를 호출하는 **동작**이 `URL Dispatcher`입니다.
- **URLconf**: `Dispatcher` 참고하는 실제 URL 설정 파일입니다. 즉 `mysite/urls.py`, `polls/urls.py`가 설정 파일이죠.
<br/>

아래와 같이 `view`와 `URLconf`를 설정해주면
`polls/views.py`
```python
def detail(request, question_id):
    # 파이썬 문자열 포메팅으로 %s에 변수 매핑, 2개 이상이면 튜플로 넘겨줘야함 (x, y)
    return HttpResponse("You're looking at question %s." % question_id)

def results(request, question_id):
    response = "You're  looking at the results of question %s." % question_id
    return HttpResponse(response)

def vote(request, question_id):
    return HttpResponse("You're voting on question %s." % question_id)
```

`polls/urls.py`
```python
urlpatterns = [
    # /polls/
    path("", views.index, name="index"),
    # /polls/:id
    path("<int:question_id>/", views.detail, name="detail"),
    # /polls/:id/results
    path("<int:question_id>/results/", views.results, name="results"),
    # /polls/5/vote
    path("<int:question_id>/vote/", views.vote, name="vote"),
]
```
이제 `urls`에 해당하는 주소로 접속이 됩니다.
- http://localhost:8000/polls/34/
- http://localhost:8000/polls/34/results/
- http://localhost:8000/polls/34/vote/

Django에서의 View는 Laravel과 달리 살짝 Controller의 역할을 더 담고 있었습니다. 
대신에 Template를 별도로 분리해서 레이어 마다의 역할을 구분했죠.

Django의 View는 다음 역할들을 기대할 수 있습니다.
- HTTP 상태코드 반환, 에러 반환
- DB에서 레코드를 읽어오기
- Django의 Template나 다른 Python Template 읽어오기 
- PDF, XML, ZIP 관련 기능 등 원하는 Python 라이브러리는 뭐든 할 수 있음
- Django 시스템에서는 반환으로 `HttpResponse`나 `Exception`만 주면 됨

지금까지는 정적 페이지에 가까웠습니다, 이제 View, Template를 연결하여 동적 페이지로 바꿔봅시다.
우선 Template를 2개 추가합니다.
<br/><br/>
`polls/templates/polls/index.html`<br/>
설문지 "색인" 페이지입니다, View에서 전달할 `latest_question_list` 딕셔너리를 for in 문과 HTML을 이용해 리스트로 뿌려주고 있죠.
또 `"{% url 'detail' question.id %}">`로 urls에서 경로가 바뀌어도 동적으로 연결되게 구성했습니다.
여기서 정한 `'detail'`은 `urls.py`에서 `path("<int:question_id>/", views.detail, name="detail"),`로  name 값을 정해줬기 때문에 연결이 되는 것 입니다.
```python
{% if latest_question_list %}
<ul>
    {% for question in latest_question_list %}
    <li>
        <a href="{% url 'detail' question.id %}">
            {{ question.question_text }}
        </a>
    </li>
    {% endfor %}
</ul>
{% else %}
<p>No polls are available</p>
{% endif %}
```
`polls/templates/polls/detail.html` <br/>
설문지 "상세" 페이지는 설문지와 관련된 선택들의 목록을 보여줄겁니다, 연결된 데이터가 없다면 for in 문이 루프를 돌지 않아 빈 화면이 출력되겠죠.
```python
<h1>{{ question.question_text }}</h1>
<ul>
{% for choice in question.choice_set.all %}
    <li>{{ choice.choice_text }}</li>
{% endfor %}
</ul>
```
이 Tempalte 들은 설정의 `DIRS` 또는 앱 내부 `tempates/` 경로에서 코드에서 지정한 템플릿 이름을 찾아 랜더링합니다.
이 연결 작업을 View에서 할 수 있죠.
<br/>

`polls/views.py`

장고에서는 편의 기능을 제공해서 간략화하는 기능들이 많습니다. <br/>
주석으로 동일한 기능을 적어뒀으니 참고하시면 됩니다.

```python
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse, Http404<br/>
from django.template import loader

from polls.models import Question


def index(request):
    # -pub_date 는 내림차순 pub_date는 오름차순
    latest_question_list = Question.objects.order_by('-pub_date')[:5]

    # 딕셔너리화화
    context = {"latest_question_list": latest_question_list}

    # template + return을 render로 간략화 가능
    # template = loader.get_template('polls/index.html')
    # return HttpResponse(template.render(context, request))
    return render(request, 'polls/index.html', context)

def detail(request, question_id):
    # 아래 예외 처리를 다음 코드로 간략화 가능
    # try:
    #    question = Question.objects.get(pk=question_id)
    # except Question.DoesNotExist:
    #    raise Http404("Question does not exist")
    question = get_object_or_404(Question, pk=question_id)

    return render(request, 'polls/detail.html', {'question': question})

def results(request, question_id):
    response = "You're  looking at the results of question %s." % question_id
    return HttpResponse(response)

def vote(request, question_id):
    return HttpResponse("You're voting on question %s." % question_id)
```

여기까지 구현했다면
`http://127.0.0.1:8000/polls/`를 접속해서 설문지 목록을 볼 수 있고, 설문지를 클릭하면 관련된 선택들으 볼 수 있을 겁니다.

마지막으로 현재는 앱이 `polls` 하나 뿐이라 상관이 없지만 후에 여럿 앱이 추가될 경우 URLconf에서 정한 `name`이 중복될 수 있습니다.

### Namespace 지정
그럴 때는 Namespace를 지정해서 해결할 수 있습니다. <br/>
`polls/urls.py`
```python
from . import views
from django.urls import path

# namespace를 polls로 지정
app_name = 'polls'
urlpatterns = [
    # /polls/
    path("", views.index, name="index"),
    # /polls/:id
    path("<int:question_id>/", views.detail, name="detail"),
    # /polls/:id/results
    path("<int:question_id>/results/", views.results, name="results"),
    # /polls/5/vote
    path("<int:question_id>/vote/", views.vote, name="vote"),
]
```

`namespace`가 지정되었으니 urls의 name을 사용한 곳을 바꿔줍니다. <br/>
`polls/templates/polls/index.html`
```html
...
        <a href="{% url 'polls:detail' question.id %}">
            {{ question.question_text }}
        </a>
...
```

## part 4
## part 5
## part 6
## part 7
## part 8
