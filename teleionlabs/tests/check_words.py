#!/usr/bin/env python3
"""Word gate and copy check for teleionlabs.com (rule 16 + brand contract T1-T11).

1. The ONE shared banned-words list, read from outside this repo (never copied into it): its regex
   patterns and its private names, which exist only as SHA-256 hashes of lowercase word tokens.
     - visible text, text attributes and agent-readable files in dist/, and every content string:
       all patterns and the private-name hashes;
     - this site's own source files (everything git would commit under teleionlabs/): the 'always'
       patterns and the private-name hashes, so no banned or private word lands in the public repo.
2. Site rules (owner, Nov 1: "simplify anything that could potentially be confusing", plus brand T7):
   teleionlabs.com names only Tessera, Teleion Labs, Meta's Muse models and Eranos; the model shim's
   own name appears at most once per page and once in llms.txt, as its address. The owner’s Nov 2
   slide-site direction permits a clearly proposed human-payment handoff on /story only. Percentage
   comparisons may appear there and on /benchmarks/ with linked technical evidence.
3. No hard-coded copy: every visible text node and text attribute in dist/*.html appears in a content
   Task Object. Code and setup blocks marked data-generated are built from content/*.json, so they pass
   the word gate without plain-text stripping mismatches.

Usage: python3 tests/check_words.py [DIST]   (BANNED_WORDS=path overrides the shared list's location)
Exit 1 on any hit, 2 when the shared list can't be read. Stdlib only.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from html import unescape
from html.parser import HTMLParser
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
DIST = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "dist"
CONTENT = HERE / "content"
SHARED = Path(os.environ.get("BANNED_WORDS") or HERE.parents[2] / "coordination-2026-10-31" / "rules" / "banned-words.json")

# Site rules. None of these is a banned word; they keep this site to its four names and its own facts.
SITE_RULES = [
    ("other surface and project names", r"\bagora\b|ta-amps"),
    ("one product name: Teleion Fabric", r"\btessera\b|\bherma\b"),
    ("an alias host on the canonical site", r"workers\.dev"),
    ("agent apps", r"muse code|openclaw|\bopencode\b|\bhermes\b"),
    ("stamp", r"not ready yet"),
    ("hash", r"\bhash(es|ed)?\b"),
    ("brand T7 (misspelling)", r"tel[e]on"),
    ("unverified numbers from other sessions", r"28\.6|99\.85|40\+"),
]
COMMERCE_RULE = re.compile(r"\bprice\b|\bpricing\b|\bcheckout\b|\bbilling\b|\bpayments?\b", re.I)
PERCENT_RULE = re.compile(r"%")
ALLOWED_NAMES = "Teleion Fabric, Teleion Labs, Meta's Muse models, Eranos"
SHIM = re.compile(r"herma", re.I)
TEXT_ATTRS = ("aria-label", "title", "alt", "placeholder")
META_TEXT = ("description", "og:title", "og:description")
DATA_ATTRS_SKIP = {
    "data-status-src", "data-service", "data-state", "data-state-text",
    "data-checked-note", "data-bench-filter", "data-bench-group", "data-benchmarks",
    "data-act", "data-mode", "data-source", "data-state-chip",
    "data-scene", "data-start", "data-end", "data-go",
    "data-duration", "data-story-scene", "data-story-go", "data-seconds", "data-c", "data-film", "data-svc", "data-on", "data-off",
}
AGENT_FILES = ("llms.txt", "robots.txt", "sitemap.xml", "status.sources.json", ".well-known/security.txt")
BINARY = {".woff2", ".woff", ".png", ".jpg", ".ico", ".mp4", ".webm"}
TOKEN = re.compile(r"[^\W_]+")
ESCAPE = re.compile(r"\\[a-z]")


class Shared:
    def __init__(self, path: Path):
        data = json.loads(path.read_text(encoding="utf-8"))
        self.always = [re.compile(p, re.I) for p in data["always"]["patterns"]]
        self.visible = [re.compile(p, re.I) for p in data["visible_text"]["patterns"]]
        self.visible += [re.compile(p, re.I) for p in data["agent_apps_outside_models_page"]["patterns"]]
        self.visible += [re.compile(p, re.I) for p in data.get("marketing_voice", {}).get("patterns", [])]
        self.private = set(data["private_names"]["sha256"])
        if not (self.always and self.visible and self.private):
            raise ValueError("the shared list is missing a category")

    def private_hits(self, text: str) -> int:
        # Strip regex and string escapes first: a literal like "\\bname\\b" must not hide as the token "bname".
        text = ESCAPE.sub(" ", text.lower())
        return sum(1 for tok in TOKEN.findall(text) if hashlib.sha256(tok.encode()).hexdigest() in self.private)


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.text: list[str] = []
        self.attrs: list[str] = []
        self.generated: list[str] = []
        self.skip = 0
        self.gen: str | None = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ("script", "style"):
            self.skip += 1
        if "data-generated" in a and self.gen is None:
            self.gen = tag
        for k in TEXT_ATTRS:
            if a.get(k):
                self.attrs.append(a[k])
        for k, v in a.items():
            if k.startswith("data-") and v and k not in DATA_ATTRS_SKIP:
                self.attrs.append(v)
        if tag == "meta" and (a.get("name") in META_TEXT or a.get("property") in META_TEXT) and a.get("content"):
            self.attrs.append(a["content"])

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self.skip:
            self.skip -= 1
        if tag == self.gen:
            self.gen = None

    def handle_data(self, data):
        if not self.skip and data.strip():
            (self.generated if self.gen else self.text).append(data.strip())


def content_strings_by_file(include_notes: bool) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    notes = ("sources", "why", "kind", "id", "status", "updated", "version", "owner")

    def walk(fname: str, o, key=""):
        if not include_notes and key in notes:
            return
        if isinstance(o, str):
            out.append((fname, o))
        elif isinstance(o, list):
            for x in o:
                walk(fname, x, key)
        elif isinstance(o, dict):
            for k, v in o.items():
                walk(fname, v, k)

    for p in sorted(CONTENT.glob("*.json")):
        walk(p.name, json.loads(p.read_text(encoding="utf-8")))
    return out


def plain(s: str) -> str:
    return re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", r"\1", s).replace("`", "")


def source_files() -> list[Path]:
    """Files git would commit under teleionlabs/: tracked plus untracked, minus ignored ones."""
    try:
        out = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z", "."],
                             cwd=HERE, capture_output=True, check=True).stdout.decode()
        return [HERE / f for f in out.split("\0") if f]
    except (OSError, subprocess.CalledProcessError):
        return [p for p in HERE.rglob("*") if p.is_file() and "dist" not in p.parts and ".wrangler" not in p.parts]


def check_benchmarks_contract(hits: list[str]) -> None:
    bench_path = CONTENT / "benchmarks.json"
    if not bench_path.is_file():
        hits.append("content/benchmarks.json: missing")
        return
    data = json.loads(bench_path.read_text(encoding="utf-8"))
    entries = []
    has_methodology_link = False
    for b in data.get("blocks", []):
        if b.get("type") == "benchmarks":
            entries.extend(b.get("entries", []))
            if "/benchmarks/methodology/" in (b.get("rerun", {}).get("text") or ""):
                has_methodology_link = True
    meth_path = CONTENT / "methodology.json"
    has_methodology_records = False
    if has_methodology_link and meth_path.is_file():
        mdata = json.loads(meth_path.read_text(encoding="utf-8"))
        for b in mdata.get("blocks", []):
            if b.get("type") == "links":
                if any(str(it.get("href", "")).startswith("/records/") for it in b.get("items", [])):
                    has_methodology_records = True
    if not entries:
        hits.append("content/benchmarks.json: no benchmark entries")
        return
    for e in entries:
        lbl = e.get("label", "<unnamed>")[:40]
        if e.get("value") is not None:
            if not e.get("date") or not (e.get("record_href") or has_methodology_records):
                hits.append(f"benchmarks.json ({lbl}): measured entry lacks date or linked methodology records")
        else:
            if e.get("record_href") is not None:
                hits.append(f"benchmarks.json ({lbl}): pending entry should have null record_href")


def main() -> int:
    try:
        shared = Shared(SHARED)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"cannot read the shared banned-words list at {SHARED}: {exc}", file=sys.stderr)
        return 2
    hits: list[str] = []
    site_rules = [(label, re.compile(p, re.I)) for label, p in SITE_RULES]

    def gate(where: str, text: str, full: bool = True, allow_percent: bool = False, allow_handoff: bool = False):
        groups = [("shared list", shared.always)]
        if full:
            groups += [("shared list", shared.visible)]
        for label, pats in groups:
            for rx in pats:
                for m in rx.finditer(text):
                    hits.append(f"{where}: {label} pattern #{pats.index(rx) + 1}: {mask(text, m)}")
        n = shared.private_hits(text)
        if n:
            hits.append(f"{where}: {n} private-name token(s) (shared list, hashed)")
        if full:
            for label, rx in site_rules:
                for m in rx.finditer(text):
                    hits.append(f"{where}: {label}: {mask(text, m)}")
            if not allow_handoff:
                for m in COMMERCE_RULE.finditer(text):
                    hits.append(f"{where}: commerce copy outside the proposed story: {mask(text, m)}")
            if not allow_percent:
                for m in PERCENT_RULE.finditer(text):
                    hits.append(f"{where}: percent sign outside /benchmarks/: {mask(text, m)}")

    def mask(text: str, m: re.Match) -> str:
        before = text[max(0, m.start() - 25): m.start()].replace("\n", " ")
        after = text[m.end(): m.end() + 25].replace("\n", " ")
        return f"...{before}[{len(m.group(0))} masked chars]{after}..."

    check_benchmarks_contract(hits)
    vis_pairs = content_strings_by_file(include_notes=False)
    vis_set = {s for _, s in vis_pairs}
    corpus = "\n".join(unescape(plain(s)) for _, s in vis_pairs)
    mark = json.loads((CONTENT / "site.json").read_text(encoding="utf-8"))["external_mark"].strip()

    pages = sorted(DIST.rglob("*.html"))
    for p in pages:
        parser = Page()
        raw_html = p.read_text(encoding="utf-8")
        parser.feed(raw_html)
        rel = str(p.relative_to(DIST))
        allow_pct = rel.startswith(("benchmarks/", "video-gallery/")) or rel in ("index.html",) or rel == "judges/index.html"
        allow_handoff = rel == "story/index.html"
        gate(rel, "\n".join(parser.text + parser.attrs + parser.generated), allow_percent=allow_pct, allow_handoff=allow_handoff)
        # Also verify raw HTML carries zero T7 banned strings (including hrefs and metadata).
        for m in re.finditer(r"ta-amps|tel[e]on" + ("" if allow_handoff else r"|\bprice\b|\bpricing\b|\bcheckout\b|\bbilling\b|\bpayments?\b"), raw_html, re.I):
            hits.append(f"{rel} (raw html): T7 hit: {mask(raw_html, m)}")
        shim = len(SHIM.findall("\n".join(parser.text)))
        if shim > 1:
            hits.append(f"{rel}: the shim's name appears {shim} times in visible text (at most once, as its address)")
        for t in parser.text + parser.attrs:
            frag = t.replace(mark, "").strip()
            # The review gallery's words live in tools/gallery.json and its films' own sources. The word gate above still reads them.
            if frag and frag not in corpus and not rel.startswith("video-gallery/"):
                hits.append(f"{rel}: text not found in any content Task Object: {frag[:80]!r}")
    for name in AGENT_FILES:
        p = DIST / name
        if not p.is_file():
            hits.append(f"{name}: missing from the build")
            continue
        text = p.read_text(encoding="utf-8")
        gate(name, text)
        if name == "llms.txt" and len(SHIM.findall(text)) > 1:
            hits.append("llms.txt: the shim's name appears more than once")
    for rec in sorted((DIST / "records").glob("*.json")):
        rtext = rec.read_text(encoding="utf-8")
        gate(f"record {rec.name}", rtext, full=False)
        for m in re.finditer(r"ta-amps|tel[e]on|\bprice\b|\bpricing\b|\bcheckout\b|\bbilling\b|\bpayments?\b", rtext, re.I):
            hits.append(f"record {rec.name}: T7 hit: {mask(rtext, m)}")
    media_dir = DIST / "media"
    if media_dir.is_dir():
        for vtt in sorted(media_dir.glob("*.vtt")):
            vtext = vtt.read_text(encoding="utf-8")
            gate(f"captions {vtt.name}", vtext, allow_percent=False)
            for m in re.finditer(r"ta-amps|tel[e]on|\bprice\b|\bpricing\b|\bcheckout\b|\bbilling\b|\bpayments?\b", vtext, re.I):
                hits.append(f"captions {vtt.name}: T7 hit: {mask(vtext, m)}")
    for fname, s in content_strings_by_file(include_notes=True):
        gate(f"content/{fname}", s, full=s in vis_set, allow_percent=(fname in ("benchmarks.json", "methodology.json", "home.json", "judges.json")), allow_handoff=fname == "story.json")
    sources = [p for p in source_files() if p.suffix not in BINARY and p.is_file()]
    for p in sources:
        gate(f"source {p.relative_to(HERE)}", p.read_text(encoding="utf-8", errors="replace"), full=False)

    print(f"checked {len(pages)} pages, {len(AGENT_FILES)} agent-readable files, {len(vis_pairs)} content strings and "
          f"{len(sources)} source files against the shared list (v{json.loads(SHARED.read_text())['version']}); "
          f"names allowed: {ALLOWED_NAMES}")
    if hits:
        print(f"FAIL {len(hits)}")
        for h in hits:
            print(f"  {h}")
        return 1
    print("PASS shared banned words 0, private names 0, T7 brand gate 0, cited benchmarks, shim name at most once, no hard-coded copy")
    return 0


if __name__ == "__main__":
    sys.exit(main())
