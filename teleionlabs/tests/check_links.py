#!/usr/bin/env python3
"""Link check for the built site.

Internal links (href/src) must resolve to a file in dist/ and every #fragment must exist on its page.
External links, and every URL inside a code sample or llms.txt, must answer: 2xx/3xx for links,
and for code-sample and llms.txt URLs any answer except 404/410/5xx (POST-only endpoints answer 405
to a GET, which shows they exist). mailto: links need a well-formed address. Requests are GET,
read-only, one at a time.

Usage: python3 tests/check_links.py [DIST]. Exit 1 on any broken link. Stdlib only.
"""
from __future__ import annotations

import re
import sys
import urllib.error
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

HERE = Path(__file__).resolve().parent.parent
DIST = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "dist"
URL = re.compile(r"https?://[^\s'\"<>()\\`$]+")  # stops at template-literal parts such as ${path}
OWN_HOST = "teleionlabs.com"
WORKER_ROUTES = {"/api/status", "/api/network", "/products", "/products/", "/tessera", "/tessera/", "/video", "/film", "/film/"}  # answered by worker/lib.js, not a file in dist/
EMAIL = re.compile(r"^mailto:[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")


class Links(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links: list[str] = []
        self.ids: set[str] = set()
        self.code: list[str] = []
        self.in_pre = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if a.get("id"):
            self.ids.add(a["id"])
        for k in ("href", "src", "poster"):
            if a.get(k) and not (tag == "link" and a.get("rel") in ("canonical",)) and not (tag == "meta"):
                self.links.append(a[k])
        if tag == "pre":
            self.in_pre += 1

    def handle_endtag(self, tag):
        if tag == "pre" and self.in_pre:
            self.in_pre -= 1

    def handle_data(self, data):
        if self.in_pre:
            self.code.append(data)


def target_file(path: str) -> Path:
    p = DIST / path.lstrip("/")
    if path.endswith("/"):
        p = p / "index.html"
    return p


def fetch(url: str) -> int:
    req = urllib.request.Request(url, headers={"User-Agent": "teleionlabs-link-check/1", "Accept": "*/*"})
    try:
        with urllib.request.urlopen(req, timeout=20) as res:
            return res.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return 0


def main() -> int:
    pages = {}
    for p in sorted(DIST.rglob("*.html")):
        parser = Links()
        parser.feed(p.read_text(encoding="utf-8"))
        pages[p] = parser
    bad: list[str] = []
    external: dict[str, set[str]] = {}
    code_urls: dict[str, set[str]] = {}
    internal = 0
    for p, parser in pages.items():
        rel = str(p.relative_to(DIST))
        for href in parser.links:
            if href.startswith("mailto:"):
                if not EMAIL.match(href):
                    bad.append(f"{rel}: malformed {href}")
                continue
            parts = urlsplit(href)
            if parts.scheme in ("http", "https"):
                external.setdefault(href, set()).add(rel)
                continue
            internal += 1
            if parts.path in WORKER_ROUTES:
                continue
            path = parts.path or "/" + rel
            f = target_file(path) if parts.path else p
            if not f.is_file():
                bad.append(f"{rel}: {href} -> missing {f.relative_to(DIST) if f.is_relative_to(DIST) else f}")
                continue
            if parts.fragment:
                ids = pages[f].ids if f in pages else set()
                if parts.fragment not in ids:
                    bad.append(f"{rel}: {href} -> no #{parts.fragment} on that page")
        for block in parser.code:
            for u in URL.findall(block):
                code_urls.setdefault(u.rstrip(".,;"), set()).add(rel)
    llms = (DIST / "llms.txt").read_text(encoding="utf-8")
    for u in URL.findall(llms):
        u = u.rstrip(".,;")
        if "<" in u or u.endswith("..."):
            continue
        code_urls.setdefault(u, set()).add("llms.txt")

    # This site's own absolute URLs resolve against the build: the live host may still serve the old site.
    for url in [u for u in code_urls if urlsplit(u).hostname == OWN_HOST]:
        where = code_urls.pop(url)
        path = urlsplit(url).path or "/"
        if path not in WORKER_ROUTES and not target_file(path).is_file():
            bad.append(f"{', '.join(sorted(where))}: {url} -> not in the build")
    for url, where in sorted(external.items()):
        status = fetch(url)
        if not 200 <= status < 400:
            bad.append(f"{', '.join(sorted(where))}: {url} -> {status}")
    for url, where in sorted(code_urls.items()):
        if url in external:
            continue
        status = fetch(url)
        if status == 0 or status in (404, 410) or status >= 500:
            bad.append(f"{', '.join(sorted(where))}: {url} -> {status}")

    print(f"checked {internal} internal links, {len(external)} external links and {len(code_urls)} code-sample/llms.txt URLs across {len(pages)} pages")
    if bad:
        print(f"FAIL {len(bad)}")
        for b in bad:
            print(f"  {b}")
        return 1
    print("PASS no broken links")
    return 0


if __name__ == "__main__":
    sys.exit(main())
