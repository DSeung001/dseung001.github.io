"""배포 산출물의 사이트맵과 검색로봇 접근 설정을 검사한다."""

import sys
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit
from urllib.robotparser import RobotFileParser
from xml.etree import ElementTree as ET


class PageMetadata(HTMLParser):
    def __init__(self):
        super().__init__()
        self.canonical = None
        self.noindex = False
        self.redirect = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "link" and "canonical" in attrs.get("rel", "").lower().split():
            self.canonical = attrs.get("href")
        if tag == "meta":
            if attrs.get("name", "").lower() in ("robots", "googlebot"):
                directives = attrs.get("content", "").lower().replace(",", " ").split()
                self.noindex |= "noindex" in directives or "none" in directives
            self.redirect |= attrs.get("http-equiv", "").lower() == "refresh"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validate(destination, base_url):
    base_url = base_url.rstrip("/") + "/"
    base = urlsplit(base_url)
    require(base.scheme == "https" and base.netloc, "배포 주소는 HTTPS 절대 주소여야 합니다.")
    robots = RobotFileParser()
    robots.parse((destination / "robots.txt").read_text(encoding="utf-8").splitlines())
    require(base_url + "sitemap.xml" in (robots.site_maps() or []), "robots.txt에 기본 사이트맵 주소가 없습니다.")
    namespace = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
    expected_urls = None
    for filename in ("sitemap.xml", "sitemap/sitemap.xml"):
        raw = (destination / filename).read_bytes()
        require(raw.startswith(b"<?xml "), f"{filename}: XML 선언 앞에 다른 내용이 있습니다.")
        require(len(raw) <= 50 * 1024 * 1024, f"{filename}: 50MB 제한을 초과했습니다.")
        root = ET.fromstring(raw.decode("utf-8"))
        require(root.tag == namespace + "urlset", f"{filename}: 사이트맵 네임스페이스가 잘못되었습니다.")
        entries = root.findall(namespace + "url")
        require(0 < len(entries) <= 50000, f"{filename}: URL 수가 허용 범위를 벗어났습니다.")
        require(robots.can_fetch("Googlebot", base_url + filename), f"{filename}: Googlebot 접근이 차단되었습니다.")
        urls = set()
        for entry in entries:
            url = entry.findtext(namespace + "loc") or ""
            parsed = urlsplit(url)
            require(url.startswith(base_url) and parsed.netloc == base.netloc and not parsed.fragment and not parsed.query,
                    f"{filename}: 잘못된 사이트 주소 {url}")
            require(url not in urls, f"{filename}: 중복 주소 {url}")
            urls.add(url)
            require(robots.can_fetch("Googlebot", url), f"{filename}: 검색로봇 접근이 차단된 주소 {url}")
            relative = unquote(parsed.path[len(base.path):])
            target = (destination / relative).resolve()
            require(target.is_relative_to(destination.resolve()), f"{filename}: 배포 폴더 밖의 주소 {url}")
            if target.is_dir():
                target /= "index.html"
            require(target.is_file(), f"{filename}: 실제 페이지가 없는 주소 {url}")
            metadata = PageMetadata()
            metadata.feed(target.read_text(encoding="utf-8"))
            require(not metadata.noindex and not metadata.redirect, f"{filename}: 색인 제외 또는 이동 페이지 {url}")
            require(metadata.canonical == url, f"{filename}: 대표 주소가 일치하지 않습니다: {url}")
            lastmod = entry.findtext(namespace + "lastmod")
            if lastmod:
                datetime.fromisoformat(lastmod.replace("Z", "+00:00"))
        require(base_url in urls, f"{filename}: 홈페이지 주소가 없습니다.")
        require(expected_urls is None or urls == expected_urls, "기본 사이트맵과 기존 사이트맵의 주소 목록이 다릅니다.")
        expected_urls = urls
        print(f"{filename}: {len(urls)}개 URL, XML과 페이지 및 robots.txt 검사 통과")


if __name__ == "__main__":
    try:
        validate(Path(sys.argv[1]), sys.argv[2])
    except (ValueError, OSError, ET.ParseError) as error:
        sys.exit(f"사이트맵 검증 실패: {error}")
