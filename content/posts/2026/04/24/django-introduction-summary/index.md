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
첫 번째 장고 앱 작성하기, part 1
첫 번째 장고 앱 작성하기, part 2
첫 번째 장고 앱 작성하기, part 3
첫 번째 장고 앱 작성하기, part 4
첫 번째 장고 앱 작성하기, part 5
첫 번째 장고 앱 작성하기, part 6
첫 번째 장고 앱 작성하기, part 7
첫 번째 Django 앱 작성하기, part 8
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
```cmd
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
