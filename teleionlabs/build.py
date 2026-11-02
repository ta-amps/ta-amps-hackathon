#!/usr/bin/env python3
"""Build teleionlabs.com from its content Task Objects.

Every visible string lives in content/*.json (Task Objects, MUST-FOLLOW rule 12). This script and
templates/ hold markup only. The build fails when a content file or a required field is missing.

Usage: python3 build.py [--out dist]
Stdlib only.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import shutil
import sys
from pathlib import Path
from urllib.parse import urlsplit

HERE = Path(__file__).resolve().parent
CONTENT = HERE / "content"
TEMPLATES = HERE / "templates"
STATIC = HERE / "static"

# Rule 16: the ONE shared banned-words list. It lives outside this public repo (it names private words), so the
# build reads it from the workspace and writes a gitignored module the Worker bundles. No list, no build.
SHARED_WORDS = Path(os.environ.get("BANNED_WORDS") or HERE.parents[2] / "coordination-2026-10-31" / "rules" / "banned-words.json")
WORD_CATEGORIES = ("always", "visible_text", "agent_apps_outside_models_page")
WORKER_WORDS = HERE / "worker" / "banned.generated.js"

PAGES = ["home", "tessera", "free", "docs", "status", "security", "company", "errors"]
REQUIRED = ["site", "llms", *PAGES]


class BuildError(Exception):
    pass


def load(name: str) -> dict:
    path = CONTENT / f"{name}.json"
    if not path.is_file():
        raise BuildError(f"missing content Task Object: {path.relative_to(HERE)}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("kind") != "task_object" or not str(data.get("id", "")).startswith("teleion.instructions/"):
        raise BuildError(f"{path.name}: not a teleion.instructions Task Object")
    return data


def req(obj: dict, key: str, where: str):
    if key not in obj or obj[key] in (None, "", []):
        raise BuildError(f"{where}: missing '{key}'")
    return obj[key]


def esc(text: str) -> str:
    return html.escape(str(text), quote=True)


class Renderer:
    def __init__(self, site: dict):
        self.site = site
        self.origin = req(site, "origin", "site")
        self.host = urlsplit(self.origin).hostname
        self.mark = (TEMPLATES / "mark.svg").read_text(encoding="utf-8").strip()
        self.chips = req(site, "chips", "site")
        self.labels = req(site, "labels", "site")

    # Links and inline text
    def is_external(self, href: str) -> bool:
        parts = urlsplit(href)
        return bool(parts.scheme in ("http", "https") and parts.hostname and parts.hostname != self.host)

    def link(self, label: str, href: str, cls: str = "") -> str:
        mark = esc(self.site["external_mark"]) if self.is_external(href) else ""
        klass = f' class="{cls}"' if cls else ""
        return f'<a{klass} href="{esc(href)}">{esc(label)}{mark}</a>'

    INLINE = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)|`([^`]+)`")

    def inline(self, text: str) -> str:
        out, pos = [], 0
        for m in self.INLINE.finditer(text):
            out.append(esc(text[pos:m.start()]))
            if m.group(1) is not None:
                out.append(self.link(m.group(1), m.group(2)))
            else:
                out.append(f"<code>{esc(m.group(3))}</code>")
            pos = m.end()
        out.append(esc(text[pos:]))
        return "".join(out)

    def chip(self, key: str | None) -> str:
        if not key:
            return ""
        if key not in self.chips:
            raise BuildError(f"unknown chip '{key}'")
        return f'<span class="chip chip--{esc(key)}">{esc(self.chips[key])}</span>'

    def button(self, item: dict, where: str) -> str:
        style = item.get("style", "secondary")
        return self.link(req(item, "label", where), req(item, "href", where), f"btn btn--{esc(style)}")

    def code(self, text: str) -> str:
        return f'<pre class="code"><code>{esc(text)}</code></pre>'

    # Blocks
    def block(self, b: dict, where: str) -> str:
        kind = req(b, "type", where)
        fn = getattr(self, f"b_{kind}", None)
        if fn is None:
            raise BuildError(f"{where}: unknown block type '{kind}'")
        return fn(b, f"{where}/{b.get('id', kind)}")

    def _head(self, b: dict, where: str, cls: str) -> str:
        parts = [f'<section class="{cls}" aria-labelledby="page-title"><div class="wrap">']
        if b.get("eyebrow"):
            parts.append(f'<p class="eyebrow">{esc(b["eyebrow"])}</p>')
        parts.append(f'<h1 id="page-title">{esc(req(b, "title", where))}</h1>')
        if b.get("lead"):
            parts.append(f'<p class="lead">{self.inline(b["lead"])}</p>')
        if b.get("actions"):
            parts.append('<div class="actions">' + "".join(self.button(a, where) for a in b["actions"]) + "</div>")
        if b.get("note"):
            parts.append(f'<p class="hero__note">{self.inline(b["note"])}</p>')
        parts.append("</div></section>")
        return "".join(parts)

    def b_hero(self, b, where):
        return self._head(b, where, "hero")

    def b_page_head(self, b, where):
        return self._head(b, where, "page-head")

    def _section(self, b: dict, where: str, inner: str, cls: str = "section") -> str:
        sid = esc(req(b, "id", where))
        intro = f'<p class="section__intro">{self.inline(b["intro"])}</p>' if b.get("intro") else ""
        return (f'<section class="{cls}" id="{sid}" aria-labelledby="{sid}-title"><div class="wrap">'
                f'<h2 id="{sid}-title">{esc(req(b, "heading", where))}</h2>{intro}{inner}</div></section>')

    def b_flow(self, b, where):
        steps = "".join(
            f'<li class="flow__step">{self.chip(s.get("chip"))}<h3>{esc(req(s, "title", where))}</h3>'
            f'<p>{self.inline(req(s, "text", where))}</p></li>' for s in req(b, "steps", where))
        return self._section(b, where, f'<ol class="flow">{steps}</ol>')

    def b_cards(self, b, where):
        items = []
        for it in req(b, "items", where):
            link = self.link(it["link"]["label"], it["link"]["href"], "card__link") if it.get("link") else ""
            items.append(f'<li class="card">{self.chip(it.get("chip"))}<h3>{esc(req(it, "title", where))}</h3>'
                         f'<p>{self.inline(req(it, "text", where))}</p>{link}</li>')
        return self._section(b, where, f'<ul class="cards">{"".join(items)}</ul>')

    def b_status(self, b, where):
        attrs = " ".join(f'data-{k}="{esc(req(b, k, where))}"' for k in ("up", "down", "unknown", "checked", "failed"))
        items = []
        for it in req(b, "items", where):
            items.append(
                f'<li class="status-item" data-service="{esc(req(it, "id", where))}" data-state="checking">'
                f'<span class="status-item__name">{esc(req(it, "name", where))}</span>'
                f'<span class="status-item__state" data-state-text>{esc(req(b, "initial", where))}</span>'
                f'<span class="status-item__text">{self.inline(req(it, "text", where))}</span>'
                f'{self.link(req(it, "host", where), req(it, "href", where), "status-item__host")}</li>')
        inner = (f'<ul class="status-list" data-status-src="{esc(req(b, "endpoint", where))}" {attrs}>{"".join(items)}</ul>'
                 f'<p class="status-note" data-checked-note aria-live="polite"></p>'
                 f'<noscript><p class="status-note">{esc(req(b, "noscript", where))}</p></noscript>')
        return self._section(b, where, inner)

    def b_feature(self, b, where):
        sid = esc(req(b, "id", where))
        what = "".join(f"<p>{self.inline(p)}</p>" for p in req(b, "what", where))
        limits = "".join(f"<li>{self.inline(x)}</li>" for x in req(b, "limits", where))
        link = self.link(b["link"]["label"], b["link"]["href"], "feature__link") if b.get("link") else ""
        return (f'<section class="section feature" id="{sid}" aria-labelledby="{sid}-title"><div class="wrap feature__grid">'
                f'<div class="feature__text">{self.chip(b.get("chip"))}<h2 id="{sid}-title">{esc(req(b, "heading", where))}</h2>{what}</div>'
                f'<div class="feature__side"><h3 class="feature__label">{esc(self.labels["how"])}</h3>'
                f'<p>{self.inline(req(b, "how", where))}</p>{self.code(req(b, "code", where))}'
                f'<h3 class="feature__label">{esc(self.labels["limits"])}</h3><ul class="limits">{limits}</ul>{link}</div>'
                f'</div></section>')

    def b_table(self, b, where):
        cols = req(b, "columns", where)
        head = "".join(f'<th scope="col">{esc(c)}</th>' for c in cols)
        rows = []
        for r in req(b, "rows", where):
            if len(r) != len(cols):
                raise BuildError(f"{where}: row has {len(r)} cells, expected {len(cols)}")
            rows.append(f'<tr><th scope="row">{self.inline(r[0])}</th>' + "".join(f"<td>{self.inline(c)}</td>" for c in r[1:]) + "</tr>")
        notes = "".join(f'<p class="table-note">{self.inline(n)}</p>' for n in b.get("notes", []))
        table = f'<table class="limits-table"><thead><tr>{head}</tr></thead><tbody>{"".join(rows)}</tbody></table>{notes}'
        return self._section(b, where, table)

    def b_prose(self, b, where):
        paras = "".join(f"<p>{self.inline(p)}</p>" for p in req(b, "paragraphs", where))
        return self._section(b, where, f'<div class="prose">{paras}</div>')

    def b_steps(self, b, where):
        items = []
        for it in req(b, "items", where):
            code = self.code(it["code"]) if it.get("code") else ""
            items.append(f'<li class="step"><h3>{esc(req(it, "title", where))}</h3><p>{self.inline(req(it, "text", where))}</p>{code}</li>')
        return self._section(b, where, f'<ol class="steps">{"".join(items)}</ol>')

    def b_callout(self, b, where):
        sid = esc(req(b, "id", where))
        paras = "".join(f"<p>{self.inline(p)}</p>" for p in req(b, "paragraphs", where))
        link = self.button({"label": b["link"]["label"], "href": b["link"]["href"]}, where) if b.get("link") else ""
        return (f'<section class="section" id="{sid}" aria-labelledby="{sid}-title"><div class="wrap"><div class="callout">'
                f'<h2 id="{sid}-title">{esc(req(b, "heading", where))}</h2>{paras}{link}</div></div></section>')

    def b_contact(self, b, where):
        email = req(b, "email", where)
        inner = (f'<div class="prose"><p>{self.inline(req(b, "text", where))}</p>'
                 f'<p class="contact__email"><a href="mailto:{esc(email)}">{esc(email)}</a></p>'
                 f'<p class="contact__note">{self.inline(req(b, "note", where))}</p></div>')
        return self._section(b, where, inner)

    def b_links(self, b, where):
        items = "".join(f'<li>{self.link(req(it, "label", where), req(it, "href", where), "ref__link")}'
                        f'<span class="ref__text">{self.inline(req(it, "text", where))}</span></li>' for it in req(b, "items", where))
        return self._section(b, where, f'<ul class="refs">{items}</ul>')

    def b_actions(self, b, where):
        return '<div class="wrap"><div class="actions actions--page">' + "".join(self.button(a, where) for a in req(b, "items", where)) + "</div></div>"

    # Page
    def page(self, page: dict, layout: str) -> str:
        where = page["id"]
        route = req(page, "route", where)
        site = self.site
        nav = req(site, "nav", "site")
        nav_items = []
        for it in req(nav, "items", "site/nav"):
            current = ' aria-current="page"' if it["href"] == route else ""
            nav_items.append(f'        <li><a href="{esc(it["href"])}"{current}>{esc(it["label"])}</a></li>')
        footer = req(site, "footer", "site")
        footer_items = "\n".join(f"        <li>{self.link(it['label'], it['href'])}</li>" for it in req(footer, "links", "site/footer"))
        scripts = ""
        if any(b.get("type") == "status" for b in page["blocks"]):
            scripts = ('<script src="/assets/status.js" defer></script>\n'
                       '<noscript><link rel="stylesheet" href="/assets/noscript.css"></noscript>\n')
        noindex = page.get("noindex", False)
        canonical = self.origin + ("/" if noindex else route)
        banner = req(site, "banner", "site")
        values = {
            "lang": req(site, "lang", "site"),
            "title": req(page, "title", where),
            "description": req(page, "description", where),
            "robots": '<meta name="robots" content="noindex">\n' if noindex else "",
            "canonical": canonical,
            "scripts": scripts,
            "skip_link": req(site, "skip_link", "site"),
            "banner_label": req(banner, "label", "site/banner"),
            "banner_before": req(banner, "before", "site/banner"),
            "banner_href": req(banner, "href", "site/banner"),
            "banner_url": req(banner, "url", "site/banner"),
            "banner_after": req(banner, "after", "site/banner"),
            "home_label": req(site["brand"], "home_label", "site/brand"),
            "brand": req(site["brand"], "name", "site/brand"),
            "nav_label": req(nav, "label", "site/nav"),
            "cta_href": req(nav["cta"], "href", "site/nav/cta"),
            "cta_label": req(nav["cta"], "label", "site/nav/cta"),
            "footer_label": req(footer, "label", "site/footer"),
            "footer_line": req(footer, "line", "site/footer"),
        }
        raw = {
            "mark": self.mark,
            "nav_items": "\n".join(nav_items),
            "footer_items": footer_items,
            "blocks": "\n".join(self.block(b, where) for b in req(page, "blocks", where)),
            "robots": values.pop("robots"),
            "scripts": values.pop("scripts"),
        }

        def fill(m: re.Match) -> str:
            key = m.group(1)
            if key in raw:
                return raw[key]
            if key in values:
                return esc(values[key])
            raise BuildError(f"template placeholder '{key}' has no value")

        return re.sub(r"\{\{(\w+)\}\}", fill, layout)


def render_llms(llms: dict) -> str:
    lines = [f"# {req(llms, 'title', 'llms')}", "", f"> {req(llms, 'summary', 'llms')}", ""]
    for sec in req(llms, "sections", "llms"):
        lines.append(f"## {req(sec, 'heading', 'llms/section')}")
        lines.extend(f"- {line}" for line in req(sec, "lines", "llms/section"))
        lines.append("")
    return "\n".join(lines)


def shared_words() -> tuple[list[str], list[str]]:
    """The shared list's regex patterns and its private-name hashes (matched per lowercase word token)."""
    if not SHARED_WORDS.is_file():
        raise BuildError(f"the shared banned-words list is missing: {SHARED_WORDS} (set BANNED_WORDS to its path)")
    words = json.loads(SHARED_WORDS.read_text(encoding="utf-8"))
    patterns = []
    for cat in WORD_CATEGORIES:
        found = words.get(cat, {}).get("patterns")
        if not found:
            raise BuildError(f"the shared banned-words list has no '{cat}' patterns")
        for pat in found:
            re.compile(pat)
            patterns.append(pat)
    hashes = words.get("private_names", {}).get("sha256") or []
    if not hashes or not all(re.fullmatch(r"[0-9a-f]{64}", h) for h in hashes):
        raise BuildError("the shared banned-words list has no valid private_names.sha256 hashes")
    return patterns, hashes


def write_worker_words(patterns: list[str], hashes: list[str]) -> None:
    pats = ",\n  ".join(json.dumps(p) for p in patterns)
    hexes = ",\n  ".join(json.dumps(h) for h in hashes)
    WORKER_WORDS.write_text(
        "// Generated by build.py from the shared banned-words list (rule 16). Gitignored: never commit it.\n"
        f"export const BANNED_PATTERNS = [\n  {pats},\n];\n"
        f"export const PRIVATE_SHA256 = [\n  {hexes},\n];\n", encoding="utf-8")


def build(out: Path) -> list[str]:
    write_worker_words(*shared_words())
    data = {name: load(name) for name in REQUIRED}
    site = data["site"]
    r = Renderer(site)
    layout = (TEMPLATES / "layout.html").read_text(encoding="utf-8")
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(STATIC, out)
    written = []
    sitemap = []
    for name in PAGES:
        page = data[name]
        target = out / req(page, "output", page["id"])
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(r.page(page, layout), encoding="utf-8")
        written.append(str(target.relative_to(out)))
        if not page.get("noindex"):
            sitemap.append(r.origin + page["route"])
    (out / "llms.txt").write_text(render_llms(data["llms"]), encoding="utf-8")
    found: dict[str, str] = {}
    for name in PAGES:
        for b in data[name]["blocks"]:
            if b.get("type") != "status":
                continue
            for it in b["items"]:
                if found.setdefault(it["id"], it["health"]) != it["health"]:
                    raise BuildError(f"{name}: status item '{it['id']}' names a different health address on another page")
    if not found:
        raise BuildError("no page has a status block with health sources")
    sources = [{"id": k, "url": v} for k, v in found.items()]
    (out / "status.sources.json").write_text(json.dumps(sources, indent=2) + "\n", encoding="utf-8")
    (out / "robots.txt").write_text(f"User-agent: *\nAllow: /\n\nSitemap: {r.origin}/sitemap.xml\n", encoding="utf-8")
    urls = "".join(f"  <url><loc>{esc(u)}</loc></url>\n" for u in sitemap)
    (out / "sitemap.xml").write_text(
        f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{urls}</urlset>\n',
        encoding="utf-8")
    sec = req(data["security"], "security_txt", "security")
    lines = [f"Contact: {c}" for c in req(sec, "contact", "security_txt")]
    lines += [f"Expires: {req(sec, 'expires', 'security_txt')}",
              f"Preferred-Languages: {req(sec, 'preferred_languages', 'security_txt')}",
              f"Canonical: {req(sec, 'canonical', 'security_txt')}",
              f"Policy: {req(sec, 'policy', 'security_txt')}"]
    (out / ".well-known").mkdir(exist_ok=True)
    (out / ".well-known" / "security.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    written += ["llms.txt", "status.sources.json", "robots.txt", "sitemap.xml", ".well-known/security.txt"]
    return written


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=str(HERE / "dist"))
    args = ap.parse_args()
    try:
        files = build(Path(args.out))
    except (BuildError, json.JSONDecodeError) as exc:
        print(f"build failed: {exc}", file=sys.stderr)
        return 1
    print(f"built {len(files)} files into {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
