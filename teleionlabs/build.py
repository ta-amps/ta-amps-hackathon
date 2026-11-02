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

SHARED_WORDS = Path(os.environ.get("BANNED_WORDS") or HERE.parents[2] / "coordination-2026-10-31" / "rules" / "banned-words.json")
WORD_CATEGORIES = ("always", "visible_text", "agent_apps_outside_models_page")
WORKER_WORDS = HERE / "worker" / "banned.generated.js"

PAGES = ["home", "start", "fabric", "video", "benchmarks", "methodology", "free", "docs", "status", "security", "privacy", "terms", "company", "errors"]
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

    def banner(self) -> str:
        noun = req(self.site, "banner", "site")
        for k in BANNER_FIELDS:
            req(noun, k, "site/banner")
        value = {"schema_version": 1, "kind": "instructions", "key": "agent-banner", **{k: noun[k] for k in BANNER_FIELDS}}
        blob = json.dumps(value, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
        return (f'<ta-agent-banner class="agent-banner"><script type="application/json">{blob}</script>'
                f'<p class="agent-fallback">{BANNER_ICON}<span class="agent-fallback-lead"><b>{esc(noun["lead_strong"])}</b> {esc(noun["lead"])}</span> '
                f'<a href="{esc(req(noun, "fallback_href", "site/banner"))}">{esc(noun["chip"])}</a></p></ta-agent-banner>')

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
        return f'<pre class="code" data-generated><code>{esc(text)}</code></pre>'

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
        if b.get("sub"):
            parts.append(f'<p class="hero__sub">{self.inline(b["sub"])}</p>')
        if b.get("actions"):
            parts.append('<div class="actions">' + "".join(self.button(a, where) for a in b["actions"]) + "</div>")
        if b.get("fixes"):
            fx = b["fixes"]
            pills = "".join(self.link(req(it, "label", where), req(it, "href", where), "hero__fix-pill")
                            for it in req(fx, "items", where))
            parts.append(f'<div class="hero__fixes"><span class="hero__fixes-label">{esc(req(fx, "label", where))}</span>{pills}</div>')
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
                f'<div class="callout__body"><h2 id="{sid}-title">{esc(req(b, "heading", where))}</h2>{paras}</div>{link}</div></div></section>')

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

    def b_problems(self, b, where):
        items = []
        for idx, it in enumerate(req(b, "items", where), start=1):
            pid = esc(it.get("id") or f"why-{idx}")
            bench = self.link(it["link"]["label"], it["link"]["href"], "problem__bench") if it.get("link") else ""
            items.append(
                f'<li class="problem" id="{pid}"><h3 class="problem__title">{esc(req(it, "problem", where))}</h3>'
                f'<p class="problem__text">{self.inline(req(it, "problem_text", where))}</p>'
                f'<div class="problem__fix"><p class="problem__label">{esc(req(b, "fix_label", where))}</p>'
                f'<p class="problem__fix-title">{esc(req(it, "fix", where))}</p>'
                f'<p class="problem__fix-text">{self.inline(req(it, "fix_text", where))}</p>{bench}</div></li>')
        fourth_html = ""
        if b.get("fourth"):
            f4 = b["fourth"]
            fid = esc(f4.get("id") or "why-4")
            flink = self.link(f4["link"]["label"], f4["link"]["href"], "problem__bench") if f4.get("link") else ""
            fourth_html = (
                f'<article class="problem-fourth" id="{fid}">'
                f'<div class="problem-fourth__main"><h3 class="problem__title">{esc(req(f4, "title", where))}</h3>'
                f'<p class="problem__fix-text">{self.inline(req(f4, "text", where))}</p></div>'
                f'{flink}</article>')
        under = f'<p class="problems__under">{self.inline(b["under"])}</p>' if b.get("under") else ""
        return self._section(b, where, f'<ul class="problems">{"".join(items)}</ul>{fourth_html}{under}', "section section--problems")

    def b_metrics(self, b, where):
        cards = []
        for it in req(b, "items", where):
            rec = self.link(req(it["record"], "label", where), req(it["record"], "href", where), "metric-card__record") if it.get("record") else ""
            cards.append(
                f'<li class="metric-card">'
                f'<span class="metric-card__value">{esc(req(it, "value", where))}</span>'
                f'<p class="metric-card__text">{self.inline(req(it, "label", where))}</p>'
                f'<span class="metric-card__meta"><span>{esc(req(it, "meta", where))}</span>{rec}</span></li>')
        more = f'<p class="metrics-more">{self.link(b["link"]["label"], b["link"]["href"], "metrics-more__link")}</p>' if b.get("link") else ""
        return self._section(b, where, f'<ul class="metric-grid">{"".join(cards)}</ul>{more}', "section")

    def b_kits(self, b, where):
        sid = esc(req(b, "id", where))
        cards = []
        for k in req(b, "kits", where):
            bullets = "".join(f"<li>{self.inline(pt)}</li>" for pt in req(k, "points", where))
            klink = self.link(req(k["link"], "label", where), req(k["link"], "href", where), "btn btn--secondary btn--small kit-card__btn")
            cards.append(
                f'<article class="kit-card">'
                f'<span class="kit-card__id">{esc(req(k, "kit_id", where))}</span>'
                f'<h3>{esc(req(k, "title", where))}</h3>'
                f'<p>{self.inline(req(k, "text", where))}</p>'
                f'<ul class="kit-card__list">{bullets}</ul>'
                f'{klink}</article>')
        vet = req(b, "vetting", where)
        vsteps = "".join(
            f'<li><span class="kits-step-num" aria-hidden="true">{i}</span><span>{self.inline(s)}</span></li>'
            for i, s in enumerate(req(vet, "steps", where), start=1))
        reuse = req(b, "reuse", where)
        pills = "".join(f'<li class="kits-pill">{esc(p)}</li>' for p in req(reuse, "parts", where))
        lib_link = self.link(req(reuse["link"], "label", where), req(reuse["link"], "href", where), "feature__link")
        cmd = self.code(req(b, "code", where))
        inner = (
            f'<p class="section__intro">{self.inline(req(b, "intro", where))}</p>'
            f'<div class="kit-grid">{"".join(cards)}</div>'
            f'<div class="kits-subgrid">'
            f'<div class="kits-col"><h3>{esc(req(vet, "heading", where))}</h3><ol class="kits-steps">{vsteps}</ol></div>'
            f'<div class="kits-col"><h3>{esc(req(reuse, "heading", where))}</h3><p>{self.inline(req(reuse, "text", where))}</p>'
            f'<ul class="kits-pills">{pills}</ul><p class="kits-safety">{self.inline(req(reuse, "safety", where))}</p>{lib_link}</div>'
            f'</div>'
            f'<div class="kits-cmd"><h3 class="feature__label">{esc(self.labels["how"])}</h3><p>{self.inline(req(b, "how", where))}</p>{cmd}</div>'
        )
        return (f'<section class="section section--kits" id="{sid}" aria-labelledby="{sid}-title"><div class="wrap">'
                f'{self.chip(b.get("chip"))}<h2 id="{sid}-title">{esc(req(b, "heading", where))}</h2>{inner}</div></section>')

    def b_benchmarks(self, b, where):
        method = req(b, "method", where)
        m_items = "".join(f"<li>{self.inline(x)}</li>" for x in req(method, "items", where))
        head_html = (
            f'<section class="page-head bench-head" aria-labelledby="page-title"><div class="wrap bench-head__grid">'
            f'<div><p class="eyebrow">{esc(req(b, "eyebrow", where))}</p>'
            f'<h1 id="page-title">{esc(req(b, "title", where))}</h1>'
            f'<p class="lead">{self.inline(req(b, "lead", where))}</p></div>'
            f'<aside class="bench-method" aria-labelledby="bench-method-title">'
            f'<h2 id="bench-method-title" class="bench-method__title">{esc(req(method, "heading", where))}</h2>'
            f'<ul class="bench-method__list">{m_items}</ul></aside></div></section>'
        )
        groups = req(b, "groups", where)
        chips = []
        for g in groups:
            key = req(g, "key", where)
            pressed = "true" if key == "all" else "false"
            chips.append(
                f'<button type="button" class="bench-chip" aria-pressed="{pressed}" data-bench-filter="{esc(key)}">'
                f'{esc(req(g, "label", where))}</button>')
        entries = req(b, "entries", where)
        sections = []
        for g in groups:
            key = req(g, "key", where)
            if key == "all":
                continue
            g_entries = [e for e in entries if e.get("group") == key]
            cards = []
            for e in g_entries:
                val = e.get("value")
                if val:
                    rec = (
                        self.link(req(b, "record_label", where), e["record_href"], "metric-card__record")
                        if e.get("record_href") and b.get("record_label")
                        else ""
                    )
                    meta = f'{esc(req(e, "setup", where))}<span aria-hidden="true"> · </span>{esc(req(e, "date", where))}'
                    cards.append(
                        f'<article class="metric-card">'
                        f'<span class="metric-card__value">{esc(val)}</span>'
                        f'<p class="metric-card__text">{self.inline(req(e, "label", where))}</p>'
                        f'<span class="metric-card__meta"><span>{meta}</span>{rec}</span></article>')
                else:
                    cards.append(
                        f'<article class="metric-card metric-card--pending">'
                        f'<span class="metric-card__pending">{esc(req(b, "pending_label", where))}</span>'
                        f'<p class="metric-card__text">{self.inline(req(e, "label", where))}</p>'
                        f'<p class="metric-card__note">{self.inline(req(b, "pending_note", where))}</p>'
                        f'<span class="metric-card__meta"><span>{esc(req(e, "setup", where))}</span></span></article>')
            sections.append(
                f'<section class="bench-group" id="bench-{esc(key)}" aria-labelledby="bench-{esc(key)}-title" data-bench-group="{esc(key)}">'
                f'<h2 id="bench-{esc(key)}-title">{esc(req(g, "label", where))}</h2>'
                f'<div class="metric-grid">{"".join(cards)}</div></section>')
        rerun = req(b, "rerun", where)
        body_html = (
            f'<div class="section bench-body" data-benchmarks><div class="wrap">'
            f'<div class="bench-filters" role="group" aria-label="{esc(req(b, "filter_label", where))}" data-needs-js>{"".join(chips)}</div>'
            f'{"".join(sections)}'
            f'<section class="bench-rerun" aria-labelledby="bench-rerun-title">'
            f'<h2 id="bench-rerun-title">{esc(req(rerun, "heading", where))}</h2>'
            f'<p>{self.inline(req(rerun, "text", where))}</p></section>'
            f'</div></div>'
        )
        return head_html + body_html

    def b_video_teaser(self, b, where):
        sid = esc(req(b, "id", where))
        actions = "".join(self.button(a, where) for a in req(b, "actions", where))
        meta = "".join(f'<span class="video-pill">{esc(m)}</span>' for m in req(b, "meta", where))
        poster = req(b, "poster", where)
        poster_href = req(b, "poster_href", where)
        poster_alt = req(b, "poster_alt", where)
        return (
            f'<section class="section video-teaser" id="{sid}" aria-labelledby="{sid}-title"><div class="wrap video-teaser__grid">'
            f'<div class="video-teaser__text">'
            f'<p class="eyebrow">{esc(req(b, "eyebrow", where))}</p>'
            f'<h2 id="{sid}-title">{esc(req(b, "heading", where))}</h2>'
            f'<p>{self.inline(req(b, "text", where))}</p>'
            f'<div class="video-pills">{meta}</div>'
            f'<div class="actions">{actions}</div>'
            f'</div>'
            f'<a class="video-teaser__frame" href="{esc(poster_href)}">'
            f'<img src="{esc(poster)}" alt="{esc(poster_alt)}" width="960" height="540" loading="lazy">'
            f'</a></div></section>'
        )

    def b_video(self, b, where):
        meta = "".join(f'<span class="video-pill">{esc(m)}</span>' for m in req(b, "meta", where))
        actions = "".join(self.button(a, where) for a in req(b, "actions", where))
        player = req(b, "player", where)
        head_html = (
            f'<section class="page-head" aria-labelledby="page-title"><div class="wrap">'
            f'<p class="eyebrow">{esc(req(b, "eyebrow", where))}</p>'
            f'<h1 id="page-title">{esc(req(b, "title", where))}</h1>'
            f'<p class="lead">{self.inline(req(b, "lead", where))}</p>'
            f'<div class="video-pills">{meta}</div>'
            f'<div class="actions">{actions}</div>'
            f'</div></section>'
        )
        player_html = (
            f'<section class="section video-stage" id="watch" aria-labelledby="watch-title"><div class="wrap">'
            f'<h2 id="watch-title" class="video-stage__title">{esc(req(player, "heading", where))}</h2>'
            f'<div class="video-card">'
            f'<video class="video-card__media" controls preload="none" playsinline poster="{esc(req(player, "poster", where))}">'
            f'<source src="{esc(req(player, "mp4", where))}" type="video/mp4">'
            f'<track kind="captions" src="{esc(req(player, "vtt", where))}" srclang="en" label="{esc(req(player, "captions_label", where))}" default>'
            f'</video>'
            f'<div class="video-card__bar">'
            f'<span class="video-card__meta">{esc(req(player, "caption", where))}</span>'
            f'<a class="btn btn--secondary btn--small" href="{esc(req(player, "mp4", where))}" download>{esc(req(player, "download_label", where))}</a>'
            f'</div></div>'
        )
        short_html = ""
        if b.get("short"):
            sh = b["short"]
            short_html = (
                f'<details class="video-short" id="short-cut">'
                f'<summary>{esc(req(sh, "summary", where))}</summary>'
                f'<div class="video-short__body">'
                f'<p>{self.inline(req(sh, "text", where))}</p>'
                f'<div class="video-card">'
                f'<video class="video-card__media" controls preload="none" playsinline poster="{esc(req(sh, "poster", where))}">'
                f'<source src="{esc(req(sh, "mp4", where))}" type="video/mp4">'
                f'<track kind="captions" src="{esc(req(sh, "vtt", where))}" srclang="en" label="{esc(req(sh, "captions_label", where))}" default>'
                f'</video>'
                f'<div class="video-card__bar">'
                f'<span class="video-card__meta">{esc(req(sh, "caption", where))}</span>'
                f'<a class="btn btn--secondary btn--small" href="{esc(req(sh, "mp4", where))}" download>{esc(req(sh, "download_label", where))}</a>'
                f'</div></div></div></details>'
            )
        stage_end = f'{short_html}</div></section>'
        tr = req(b, "transcript", where)
        t_rows = "".join(
            f'<li class="transcript-row"><span class="transcript-row__time">{esc(req(r, "time", where))}</span>'
            f'<span class="transcript-row__scene">{esc(req(r, "scene", where))}</span>'
            f'<p class="transcript-row__text">{self.inline(req(r, "text", where))}</p></li>'
            for r in req(tr, "items", where)
        )
        tr_html = (
            f'<section class="section" id="transcript" aria-labelledby="transcript-title"><div class="wrap">'
            f'<h2 id="transcript-title">{esc(req(tr, "heading", where))}</h2>'
            f'<p class="section__intro">{self.inline(req(tr, "intro", where))}</p>'
            f'<ol class="transcript-list">{t_rows}</ol></div></section>'
        )
        ev = req(b, "evidence", where)
        ev_items = "".join(
            f'<li>{self.link(req(it, "label", where), req(it, "href", where), "ref__link")}'
            f'<span class="ref__text">{self.inline(req(it, "text", where))}</span></li>'
            for it in req(ev, "items", where)
        )
        ev_html = (
            f'<section class="section" id="evidence" aria-labelledby="evidence-title"><div class="wrap">'
            f'<h2 id="evidence-title">{esc(req(ev, "heading", where))}</h2>'
            f'<p class="section__intro">{self.inline(req(ev, "intro", where))}</p>'
            f'<ul class="refs">{ev_items}</ul></div></section>'
        )
        next_btns = "".join(self.button(a, where) for a in req(b, "next_actions", where))
        next_html = f'<div class="wrap"><div class="actions actions--page">{next_btns}</div></div>'
        return head_html + player_html + stage_end + tr_html + ev_html + next_html

    def b_band(self, b, where):
        sid = esc(req(b, "id", where))
        paras = "".join(f"<p>{self.inline(p)}</p>" for p in b.get("paragraphs", []))
        facts = "".join(f"<li>{self.inline(x)}</li>" for x in b.get("facts", []))
        facts = f'<ul class="facts">{facts}</ul>' if facts else ""
        links = "".join(self.link(l["label"], l["href"], "band__link") for l in b.get("links", []))
        links = f'<p class="band__links">{links}</p>' if links else ""
        if b.get("diagram"):
            aside = self.diagram(b["diagram"], f"{where}/diagram", sid)
        elif b.get("code"):
            cap = f'<figcaption class="band__caption">{self.inline(b["code_caption"])}</figcaption>' if b.get("code_caption") else ""
            aside = (f'<figure class="band__figure band__figure--code">{cap}'
                     f'<pre class="code code--band" tabindex="0" aria-label="{esc(req(b, "code_label", where))}" data-generated><code>{esc(b["code"])}</code></pre></figure>')
        else:
            raise BuildError(f"{where}: a band needs a diagram or code")
        return (f'<section class="section band" id="{sid}" aria-labelledby="{sid}-title"><div class="wrap band__grid">'
                f'<div class="band__text">{self.chip(b.get("chip"))}<h2 id="{sid}-title">{esc(req(b, "heading", where))}</h2>'
                f'{paras}{facts}{links}</div>{aside}</div></section>')

    TONES = ("task", "object", "check", "plain", "muted")

    def diagram(self, d: dict, where: str, sid: str) -> str:
        w, h = int(req(d, "width", where)), int(req(d, "height", where))
        nodes = {}
        for n in req(d, "nodes", where):
            tone = n.get("tone", "plain")
            if tone not in self.TONES:
                raise BuildError(f"{where}: unknown tone '{tone}'")
            nodes[req(n, "id", where)] = n
        out = [f'<figure class="band__figure"><svg class="diagram" viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" '
               f'aria-labelledby="{sid}-dt {sid}-dd" focusable="false"><title id="{sid}-dt">{esc(req(d, "title", where))}</title>'
               f'<desc id="{sid}-dd">{esc(req(d, "desc", where))}</desc>'
               f'<defs><marker id="{sid}-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
               f'<path d="M0 0L10 5L0 10z" class="diagram__head"/></marker></defs>']
        for g in d.get("groups", []):
            x, y, gw, gh = (int(g[k]) for k in ("x", "y", "w", "h"))
            out.append(f'<g class="diagram__group diagram__group--{esc(g.get("tone", "plain"))}"><rect x="{x}" y="{y}" width="{gw}" height="{gh}" rx="14"/>'
                       f'<text class="diagram__group-label" x="{x + 14}" y="{y + 24}">{esc(req(g, "label", where))}</text></g>')
        for e in d.get("edges", []):
            a, z = nodes[req(e, "from", where)], nodes[req(e, "to", where)]
            pts = self._route(a, z, e)
            path = "M" + " L".join(f"{px} {py}" for px, py in pts)
            dashed = " diagram__edge--refused" if e.get("refused") else ""
            out.append(f'<g class="diagram__edge{dashed}"><path d="{path}" marker-end="url(#{sid}-arrow)"/>'
                       + ("" if e.get("refused") else f'<path class="diagram__flow" d="{path}"/>'))
            if e.get("label"):
                lx, ly, auto = self._mid(pts)
                if e.get("label_at"):
                    lx, ly = e["label_at"]
                anchor = e.get("anchor", auto)
                out.append(f'<text class="diagram__label" x="{lx}" y="{ly}" text-anchor="{esc(anchor)}">{esc(e["label"])}</text>')
            out.append("</g>")
        for n in nodes.values():
            x, y, nw, nh = (int(n[k]) for k in ("x", "y", "w", "h"))
            sub = n.get("sub")
            ty = y + nh / 2 + (-4 if sub else 6)
            out.append(f'<g class="diagram__node diagram__node--{esc(n.get("tone", "plain"))}"><rect x="{x}" y="{y}" width="{nw}" height="{nh}" rx="10"/>'
                       f'<text class="diagram__title" x="{x + nw / 2:g}" y="{ty:g}" text-anchor="middle">{esc(req(n, "title", where))}</text>')
            if sub:
                out.append(f'<text class="diagram__sub" x="{x + nw / 2:g}" y="{ty + 20:g}" text-anchor="middle">{esc(sub)}</text>')
            out.append("</g>")
        out.append("</svg>")
        if d.get("caption"):
            out.append(f'<figcaption class="band__caption">{self.inline(d["caption"])}</figcaption>')
        out.append("</figure>")
        return "".join(out)

    @staticmethod
    def _side(n: dict, side: str) -> tuple[float, float]:
        x, y, w, h = (int(n[k]) for k in ("x", "y", "w", "h"))
        return {"right": (x + w, y + h / 2), "left": (x, y + h / 2), "top": (x + w / 2, y), "bottom": (x + w / 2, y + h)}[side]

    def _route(self, a: dict, z: dict, e: dict) -> list[tuple[float, float]]:
        if e.get("points"):
            return [tuple(p) for p in e["points"]]
        ax, ay = int(a["x"]) + int(a["w"]) / 2, int(a["y"]) + int(a["h"]) / 2
        zx, zy = int(z["x"]) + int(z["w"]) / 2, int(z["y"]) + int(z["h"]) / 2
        horizontal = abs(zx - ax) >= abs(zy - ay)
        s = e.get("from_side") or (("right" if zx > ax else "left") if horizontal else ("bottom" if zy > ay else "top"))
        t = e.get("to_side") or (("left" if zx > ax else "right") if horizontal else ("top" if zy > ay else "bottom"))
        p0, p1 = self._side(a, s), self._side(z, t)
        if p0[0] == p1[0] or p0[1] == p1[1]:
            return [p0, p1]
        if s in ("left", "right") and t in ("left", "right"):
            mx = (p0[0] + p1[0]) / 2
            return [p0, (mx, p0[1]), (mx, p1[1]), p1]
        if s in ("top", "bottom") and t in ("top", "bottom"):
            my = (p0[1] + p1[1]) / 2
            return [p0, (p0[0], my), (p1[0], my), p1]
        return [p0, (p1[0], p0[1]), p1] if s in ("left", "right") else [p0, (p0[0], p1[1]), p1]

    @staticmethod
    def _mid(pts: list[tuple[float, float]]) -> tuple[float, float, str]:
        best = max(zip(pts, pts[1:]), key=lambda s: abs(s[1][0] - s[0][0]) + abs(s[1][1] - s[0][1]))
        (x0, y0), (x1, y1) = best
        if y0 == y1:
            return ((x0 + x1) / 2, y0 - 8, "middle")
        return (x0 + 8, (y0 + y1) / 2 + 5, "start")

    def b_setup(self, b, where):
        sid = esc(req(b, "id", where))
        values, fields = {}, []
        for ch in req(b, "choices", where):
            name = req(ch, "name", where)
            values[name] = req(ch, "default", where)
            opts = "".join(
                f'<label class="choice"><input type="radio" name="{esc(name)}" value="{esc(req(o, "value", where))}"'
                f'{" checked" if o["value"] == ch["default"] else ""} data-setup-input><span>{esc(req(o, "label", where))}</span></label>'
                for o in req(ch, "options", where))
            fields.append(f'<fieldset class="setup__group"><legend>{esc(req(ch, "legend", where))}</legend>{opts}</fieldset>')
        adv = req(b, "advanced", where)
        extra = []
        for f in req(adv, "fields", where):
            name, kind = req(f, "name", where), req(f, "kind", where)
            fid = f"{sid}-{esc(name)}"
            hint = f'<span class="setup__hint" id="{fid}-hint">{self.inline(f["hint"])}</span>' if f.get("hint") else ""
            described = f' aria-describedby="{fid}-hint"' if f.get("hint") else ""
            if kind == "text":
                values[name] = req(f, "default", where)
                extra.append(f'<div class="setup__field"><label for="{fid}">{esc(req(f, "label", where))}</label>'
                             f'<input id="{fid}" name="{esc(name)}" type="text" value="{esc(f["default"])}" maxlength="64" '
                             f'autocomplete="off" spellcheck="false" data-setup-input{described}>{hint}</div>')
            elif kind == "select":
                values[name] = req(f, "default", where)
                opts = "".join(f'<option value="{esc(o["value"])}"{" selected" if o["value"] == f["default"] else ""}>{esc(o["label"])}</option>'
                               for o in req(f, "options", where))
                extra.append(f'<div class="setup__field"><label for="{fid}">{esc(req(f, "label", where))}</label>'
                             f'<select id="{fid}" name="{esc(name)}" data-setup-input{described}>{opts}</select>{hint}</div>')
            elif kind == "checkbox":
                values[name] = bool(f.get("default"))
                extra.append(f'<div class="setup__field setup__field--check"><label class="choice"><input id="{fid}" name="{esc(name)}" type="checkbox"'
                             f'{" checked" if f.get("default") else ""} data-setup-input{described}><span>{esc(req(f, "label", where))}</span></label>{hint}</div>')
            else:
                raise BuildError(f"{where}: unknown field kind '{kind}'")
        show = req(b, "show", where)
        values["show"] = req(show, "default", where)
        tabs = "".join(
            f'<label class="choice choice--tab"><input type="radio" name="show" value="{esc(o["value"])}"'
            f'{" checked" if o["value"] == show["default"] else ""} data-setup-input><span>{esc(o["label"])}</span></label>'
            for o in req(show, "options", where))
        data = {k: b[k] for k in ("templates", "tokens")}
        data["copy"] = req(b, "copy", where)
        for key in data["templates"]:
            if len(key.split(".")) != 3:
                raise BuildError(f"{where}: template key '{key}' is not goal.via.show")
        default = setup_text(data, values)
        blob = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
        copy = data["copy"]
        return (
            f'<section class="section band band--setup" id="{sid}" aria-labelledby="{sid}-title"><div class="wrap">'
            f'<div class="setup" data-setup><div class="setup__choices"><h2 id="{sid}-title">{esc(req(b, "heading", where))}</h2>'
            f'<div class="setup__inputs" data-needs-js>{"".join(fields)}'
            f'<details class="setup__more"><summary>{esc(req(adv, "summary", where))}</summary><div class="setup__fields">{"".join(extra)}</div></details></div>'
            f'<p class="setup__note">{self.inline(req(b, "note", where))}</p>'
            f'<noscript><p class="setup__note">{esc(req(b, "noscript", where))}</p></noscript></div>'
            f'<div class="setup__out"><fieldset class="setup__tabs" data-needs-js><legend>{esc(req(show, "legend", where))}</legend>{tabs}</fieldset>'
            f'<pre class="code setup__code" tabindex="0" aria-label="{esc(req(b, "output_label", where))}" data-generated><code data-setup-output>{esc(default)}</code></pre>'
            f'<div class="setup__actions" data-needs-js><button type="button" class="btn btn--secondary btn--small" data-setup-copy>{esc(copy["label"])}</button>'
            f'<span class="setup__status" role="status" aria-live="polite" data-setup-status></span></div></div></div>'
            f'<script type="application/json" id="setup-data">{blob}</script></div></section>')

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
        scripts = '<script src="/assets/agent-banner.js" defer></script>\n'
        kinds = {b.get("type") for b in page["blocks"]}
        if "status" in kinds:
            scripts += '<script src="/assets/status.js" defer></script>\n'
        if "setup" in kinds:
            scripts += '<script src="/assets/start.js" defer></script>\n'
        if "benchmarks" in kinds:
            scripts += '<script src="/assets/benchmarks.js" defer></script>\n'
        if kinds & {"status", "setup", "benchmarks"}:
            scripts += '<noscript><link rel="stylesheet" href="/assets/noscript.css"></noscript>\n'

        noindex = page.get("noindex", False)
        canonical = self.origin + ("/" if noindex else route)
        banner = self.banner()
        values = {
            "lang": req(site, "lang", "site"),
            "title": req(page, "title", where),
            "description": req(page, "description", where),
            "robots": '<meta name="robots" content="noindex">\n' if noindex else "",
            "canonical": canonical,
            "site_name": req(site["brand"], "name", "site/brand"),
            "og_image": req(site, "og_image", "site"),
            "scripts": scripts,
            "skip_link": req(site, "skip_link", "site"),
            "home_label": req(site["brand"], "home_label", "site/brand"),
            "brand": req(site["brand"], "name", "site/brand"),
            "nav_label": req(nav, "label", "site/nav"),
            "cta_href": req(nav["cta"], "href", "site/nav/cta"),
            "cta_label": req(nav["cta"], "label", "site/nav/cta"),
            "footer_label": req(footer, "label", "site/footer"),
            "footer_line": req(footer, "line", "site/footer"),
        }
        raw = {
            "banner": banner,
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


BANNER_FIELDS = ("label", "lead_strong", "lead", "lead_short", "chip", "copy_text", "copy", "copy_short", "copied", "copied_status",
                 "copy_failed", "more", "less", "panel_title", "panel_note", "panel_line", "can_title", "can", "rules_title", "rules", "links")
BANNER_ICON = ('<svg class="agent-fallback-icon" viewBox="0 0 40 40" width="18" height="18" aria-hidden="true" focusable="false">'
               '<circle cx="20" cy="20" r="17" fill="none" stroke="currentColor" stroke-width="2.6"/>'
               '<path d="M20 12v-3h-3" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round"/>'
               '<rect x="12" y="14" width="16" height="12" rx="3" fill="none" stroke="currentColor" stroke-width="2.6"/>'
               '<path d="M17 19v2M23 19v2" stroke="currentColor" stroke-width="2.6" stroke-linecap="round"/></svg>')


def setup_text(data: dict, values: dict) -> str:
    key = f"{values['goal']}.{values['via']}.{values['show']}"
    if key not in data["templates"]:
        raise BuildError(f"setup: no template '{key}'")
    agent = re.sub(r"[^a-zA-Z0-9 ._:-]", "", str(values["agent"]))[:64] or "agent"
    swap = {"agent": agent, "queue": values["queue"], "map": data["tokens"]["map_on" if values["map"] else "map_off"]}
    return re.sub(r"\{(agent|queue|map)\}", lambda m: swap[m.group(1)], data["templates"][key])


def render_llms(llms: dict) -> str:
    lines = [f"# {req(llms, 'title', 'llms')}", "", f"> {req(llms, 'summary', 'llms')}", ""]
    for sec in req(llms, "sections", "llms"):
        lines.append(f"## {req(sec, 'heading', 'llms/section')}")
        lines.extend(f"- {line}" for line in req(sec, "lines", "llms/section"))
        lines.append("")
    return "\n".join(lines)


def shared_words() -> tuple[list[str], list[str]]:
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
