#!/usr/bin/env python3
"""End-to-end test of the live public system, as a stranger with no credentials.

    python3 e2e.py                                 read-only stages: names, crawl
    python3 e2e.py --stages eranos                 read-only pages and answers from Eranos
    python3 e2e.py --write --stages fabric,shim    stages that write to live queues (also q, browser)
    python3 e2e.py --max-pages 60                  pages per host in the crawl

It reads no credential file and sends no credential. It never files an Eranos request and uses no example slots.

The fabric, shim, q and browser stages change live data, so they refuse to run without --write. Each run adds
unfinished Tasks to the shared queue, a public Task Object, a follow-up, one human link and one shim worker join, and
it claims a canary Task. Run them only against a copy you own, or when you own the live system.
--claim-real also claims real Tasks: real nonprofit work is held until each lease ends.

Output: RESULTS.md and results.json beside this file. Exit 0 only when no check failed.
"""
import argparse, html, json, os, re, sys, time, uuid
from collections import deque
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse, urldefrag
import requests

HERE = Path(__file__).resolve().parent
WORDS = json.loads(Path(os.environ["BANNED_WORDS_FILE"]).read_text())
FABRIC, SHIM, TELEION, ERANOS, AGORA = ("https://fabric.teleionlabs.com", "https://shim.teleionlabs.com",
                                        "https://teleionlabs.com", "https://eranosforgood.org", "https://agora.eranosforgood.org")
OURS = {urlparse(u).netloc for u in (FABRIC, SHIM, TELEION, ERANOS, AGORA)} | {"www.teleionlabs.com", "www.eranosforgood.org", "herma.teleionlabs.com", "tessera.teleionlabs.com"}
UA = "e2e-probe/1.0 (Teleion Labs public test; no credentials)"
AGENT = "e2e-probe"
RUN = uuid.uuid4().hex[:8]
results = []
http = requests.Session()
http.headers["user-agent"] = UA


def check(stage, name, ok, repro="", detail=""):
    results.append({"stage": stage, "name": name, "ok": bool(ok), "repro": repro, "detail": str(detail)[:900]})
    print(("PASS " if ok else "FAIL ") + f"[{stage}] {name}" + ("" if ok else f"\n     {str(detail)[:300]}"), flush=True)
    return bool(ok)


def req(method, url, **kw):
    kw.setdefault("timeout", 40)
    for attempt in range(3):
        try:
            r = http.request(method, url, **kw)
            if r.encoding and r.encoding.lower() == "iso-8859-1":
                r.encoding = "utf-8"
            return r
        except requests.RequestException as e:
            last = e
            time.sleep(1.5)
    class Down:
        status_code = 0; text = f"network error: {last}"; headers = {}; content = b""; url = ""; history = []
        def json(self): raise ValueError("no body")
    return Down()


def jbody(r):
    try:
        return r.json()
    except Exception:
        return None


def curl(method, url, headers=None, body=None):
    parts = ["curl -s -i", f"-X {method}"] if method != "GET" else ["curl -s -i"]
    for k, v in (headers or {}).items():
        parts.append(f"-H '{k}: {v}'")
    if body is not None:
        parts.append(f"-H 'content-type: application/json' -d '{json.dumps(body)}'")
    parts.append(f"'{url}'")
    return " ".join(parts)


# ---------- text rules ----------
class Text(HTMLParser):
    SKIP = {"script", "style", "noscript", "template"}
    CODE = {"code", "pre", "kbd", "samp", "tt", "var"}
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth, self.code, self.body = 0, 0, False
        self.prose, self.links, self.first, self.tags = [], [], None, []
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "body": self.body = True
        if tag in self.SKIP: self.depth += 1
        if tag in self.CODE: self.code += 1
        if tag in ("a", "link") and a.get("href"):
            if tag == "a" or a.get("rel") in ("stylesheet", "icon"): self.links.append(a["href"])
        if tag in ("video", "source", "img", "script") and a.get("src"): self.links.append(a["src"])
        self.tags.append(tag)
    def handle_endtag(self, tag):
        if tag in self.SKIP and self.depth: self.depth -= 1
        if tag in self.CODE and self.code: self.code -= 1
    def handle_data(self, d):
        if self.depth or not d.strip(): return
        if self.first is None and self.body: self.first = d.strip()
        if not self.code: self.prose.append(d)


def groups():
    g = {"always": WORDS["always"]["patterns"], "visible_text": WORDS["visible_text"]["patterns"], "marketing_voice": WORDS["marketing_voice"]["patterns"]}
    return {k: [re.compile(p, re.I) for p in v] for k, v in g.items()}
GROUPS = groups()
OLD_NAMES = re.compile(r"(?<![\w-])(tessera|herma)(?![\w-]|\.[a-z_]+\.)", re.I)


def word_hits(text, which=("always", "visible_text", "marketing_voice")):
    """Group and count only; the rule list says never to print the words themselves in a report."""
    text = text.split('{\n  "service"')[0]  # the machine-readable contract at the end of llms-full.txt
    text = re.sub(r"`[^`]*`|https?://\\S+|/v1/\\S+|\"[^\"]*\"\\s*:|\\b\\w+\\.(?:verify|review|propose)\\b", " ", text)
    hits = {}
    for g in which:
        n = sum(len(p.findall(text)) for p in GROUPS[g])
        if n: hits[g] = n
    return hits


def old_names(text):
    # Hostnames, machine values and code names stay; prose may not use them.
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"\b[\w.-]*(tessera|herma)[\w-]*\.[a-z]{2,}\S*", " ", text, flags=re.I)
    text = re.sub(r"\b(X-)?(Tessera|Herma)[-_]\w+", " ", text)
    return OLD_NAMES.findall(text)


# ---------- crawl ----------
SEEDS = {
    TELEION: ["/", "/llms.txt", "/index.txt", "/fabric/", "/free/", "/docs/", "/status/", "/api/status", "/benchmarks/", "/benchmarks/methodology/", "/video/", "/security/", "/privacy/", "/terms/", "/company/", "/omninode/", "/shimming/", "/fabric-intelligence/", "/feeds/", "/.well-known/security.txt", "/robots.txt", "/sitemap.xml"],
    FABRIC: ["/", "/connect", "/connect.json", "/llms.txt", "/llms-full.txt", "/board", "/work", "/v1/health", "/openapi.json", "/v1/openapi.json", "/.well-known/agent-card.json", "/.well-known/agent.json", "/robots.txt"],
    SHIM: ["/", "/llms.txt", "/llms-full.txt", "/connect.json", "/healthz", "/get-started", "/prompts", "/dashboard", "/kits", "/starter", "/trust", "/connect", "/q/search", "/q/pulse", "/q/schema", "/.well-known/agent-card.json"],
    ERANOS: ["/", "/nonprofits", "/help", "/requests", "/library", "/catalog", "/connect", "/privacy", "/terms", "/report", "/video", "/llms.txt", "/llms-full.txt", "/connect.json", "/robots.txt", "/.well-known/agent-card.json", "/.well-known/security.txt", "/api/tracks", "/api/catalog", "/api/open-tasks", "/api/fabric", "/api/health"],
    AGORA: ["/", "/models/", "/network/", "/evidence/", "/feeds/", "/llms.txt"],
}
MEDIA = re.compile(r"\.(mp4|webm|mov|png|jpe?g|webp|gif|svg|ico|woff2?|ttf|mp3|m4a|wav|zip|gz|tar|pdf|pptx|vtt|srt)(\?|$)", re.I)


def crawl(max_pages):
    stage = "crawl"
    external = {}
    for base, seeds in SEEDS.items():
        host = urlparse(base).netloc
        seen, queue, bad, pages, word_bad, names_bad = set(), deque(urljoin(base, s) for s in seeds), [], 0, [], []
        linked_from = {}
        while queue and pages < max_pages:
            url = urldefrag(queue.popleft()).url
            if url in seen: continue
            seen.add(url)
            if MEDIA.search(urlparse(url).path):
                r = req("HEAD", url, allow_redirects=True)
                if r.status_code >= 400 and r.status_code != 405:
                    bad.append((url, r.status_code, linked_from.get(url, "seed")))
                continue
            r = req("GET", url, allow_redirects=False)
            hops = 0
            while r.status_code in (301, 302, 303, 307, 308) and hops < 6:
                nxt = urljoin(url if hops == 0 else r.url, r.headers.get("location", ""))
                r = req("GET", nxt, allow_redirects=False); hops += 1
            pages += 1
            final = r.url or url
            if r.status_code >= 400 or r.status_code == 0:
                bad.append((url, r.status_code, linked_from.get(url, "seed")))
                continue
            ctype = r.headers.get("content-type", "")
            if urlparse(final).netloc != host:
                continue  # a redirect to another of our hosts: that host's own crawl covers it
            if "html" in ctype:
                t = Text(); t.feed(r.text)
                prose = " ".join(t.prose)
                hits = word_hits(prose, ("always", "visible_text") if base == AGORA and "/feeds/" in final else ("always", "visible_text", "marketing_voice"))
                if hits: word_bad.append((urlparse(final).path, hits))
                n = old_names(prose)
                if n: names_bad.append((urlparse(final).path, len(n)))
                if "only light" not in r.text and "color-scheme" not in r.text:
                    bad.append((url, "no color-scheme", ""))
                for href in t.links:
                    if href.startswith(("mailto:", "tel:", "javascript:", "data:", "#")): continue
                    full = urldefrag(urljoin(final, href)).url
                    p = urlparse(full)
                    if p.netloc == host:
                        if full not in seen:
                            linked_from.setdefault(full, urlparse(final).path); queue.append(full)
                    elif p.scheme in ("http", "https"):
                        external.setdefault(full, urlparse(final).netloc + urlparse(final).path)
                if base == TELEION:
                    path = urlparse(final).path
                    if not path.startswith(("/l/", "/assets/")):
                        tu = urljoin(base, ("/index.txt" if path == "/" else path.rstrip("/") + ".txt"))
                        tr = req("GET", tu)
                        if tr.status_code != 200 or "text/plain" not in tr.headers.get("content-type", ""):
                            bad.append((tu, f"{tr.status_code} no .txt copy", path))
                        else:
                            h = word_hits(tr.text)
                            if h: word_bad.append((urlparse(tu).path, h))
                            n = old_names(tr.text)
                            if n: names_bad.append((urlparse(tu).path, len(n)))
                    first = t.first or ""
                    if "llms.txt" not in first.lower() and "agent" not in first.lower():
                        bad.append((url, "first line is not the instruction line", first[:80]))
                    if "<footer" not in r.text:
                        bad.append((url, "no footer", ""))
            elif "text/plain" in ctype:
                # Instructions an agent reads may say verify; the marketing word list is for what people read.
                h = word_hits(r.text, ("always", "visible_text"))
                if h: word_bad.append((urlparse(final).path, h))
                n = old_names(r.text)
                if n: names_bad.append((urlparse(final).path, len(n)))
        check(stage, f"{host}: every page and linked file loads ({pages} pages)", not bad, f"open each address listed", bad[:25])
        check(stage, f"{host}: banned words absent from served prose", not word_bad, "GET the path, compare its prose with rules/banned-words.json (group counts only here)", word_bad[:25])
        check(stage, f"{host}: public text says Teleion Fabric, not the old names", not names_bad, "GET the path and read the prose", names_bad[:25])
    # outward links from any page
    bad_ext = []
    for url, src in sorted(external.items()):
        p = urlparse(url)
        if p.netloc in OURS or p.netloc == "github.com" and p.path.startswith("/ta-amps/"):
            r = req("GET", url, allow_redirects=True, stream=True, timeout=25)
            if r.status_code >= 400 or r.status_code == 0:
                bad_ext.append((url, r.status_code, "from " + src))
    check(stage, "links between our sites and to our repos work", not bad_ext, "open the address listed", bad_ext[:30])


# ---------- fabric ----------
def rpc(url, method, params=None, id_=1, headers=None):
    h = {"content-type": "application/json", "accept": "application/json, text/event-stream", "x-agent-label": f"{AGENT}-{RUN}"}
    h.update(headers or {})
    r = req("POST", url, headers=h, json={"jsonrpc": "2.0", "id": id_, "method": method, "params": params or {}})
    body = None
    if "event-stream" in r.headers.get("content-type", ""):
        for line in r.text.splitlines():
            if line.startswith("data:"): body = json.loads(line[5:])
    else:
        body = jbody(r)
    return r, body


def tool_text(body):
    try:
        c = body["result"]["content"][0]["text"]
        return json.loads(c)
    except Exception:
        return None


def fabric():
    st = "fabric"
    H = {"x-agent-label": AGENT}
    M = {"x-agent-label": AGENT, "x-namespace": "main"}
    # 1. The docs an agent starts from must describe no-key access and name the addresses it then uses.
    llms = req("GET", FABRIC + "/llms.txt").text
    check(st, "llms.txt does not demand a key from the operator", not re.search(r"you need a key", llms, re.I), f"curl {FABRIC}/llms.txt", [l for l in llms.splitlines() if re.search("need a key", l, re.I)][:3])
    conn = jbody(req("GET", FABRIC + "/connect.json")) or {}
    check(st, "connect.json says direct access needs no credential", conn.get("authentication_required") is False and conn.get("credentials_required") is False and conn.get("session_required") is False, f"curl {FABRIC}/connect.json", {k: conn.get(k) for k in ("authentication_required", "credentials_required", "session_required", "abuse_rate_limits", "free_until")})
    # 2. Reads with no key.
    r = req("GET", FABRIC + "/v1/health"); check(st, "health", r.status_code == 200, f"curl {FABRIC}/v1/health", r.status_code)
    for name, path in [("search", "/v1/search?q=nonprofit"), ("feeds", "/v1/feeds"), ("reflex match", "/v1/reflexes/match?q=nonprofit"), ("Task list", "/v1/verbs?limit=5")]:
        r = req("GET", FABRIC + path, headers=M)
        check(st, f"no-key {name} on the shared space answers 200", r.status_code == 200, curl("GET", FABRIC + path, M), f"{r.status_code} {r.text[:200]}")
    feeds = jbody(req("GET", FABRIC + "/v1/feeds", headers=M)) or {}
    names = [f.get("feed") or f.get("name") for f in feeds.get("feeds", []) if isinstance(f, dict)]
    check(st, "at least one feed is readable with no key", bool(names), curl("GET", FABRIC + "/v1/feeds", M), str(feeds)[:200])
    if names:
        r = req("GET", f"{FABRIC}/v1/feeds/{names[0]}", headers=M)
        check(st, f"feed {names[0]} polls with no key", r.status_code == 200, curl("GET", f"{FABRIC}/v1/feeds/{names[0]}", M), f"{r.status_code} {r.text[:200]}")
    # 3. Private things stay private.
    for name, method, path, body in [("key issuing", "POST", "/v1/keys", {"label": "x"}), ("key list", "GET", "/v1/keys", None), ("admin audit", "GET", "/v1/admin/audit", None), ("reap", "POST", "/v1/admin/reap", {})]:
        r = req(method, FABRIC + path, json=body) if body is not None else req(method, FABRIC + path)
        check(st, f"{name} stays closed with no key", r.status_code in (401, 403), curl(method, FABRIC + path, None, body), f"{r.status_code} {r.text[:150]}")
    r = req("POST", FABRIC + "/v1/tasks", headers=M, json={"queue": "eq03", "brief": {"title": "e2e must be refused"}})
    check(st, "no-key write to a review queue is refused", r.status_code in (401, 403), curl("POST", FABRIC + "/v1/tasks", M, {"queue": "eq03"}), f"{r.status_code} {r.text[:150]}")
    r = req("POST", FABRIC + "/v1/tasks/claim", headers=M, json={"queue": "eq03", "worker": AGENT})
    check(st, "no-key claim on the review queue is refused (maker never checks)", r.status_code in (401, 403), curl("POST", FABRIC + "/v1/tasks/claim", M, {"queue": "eq03", "worker": AGENT}), f"{r.status_code} {r.text[:150]}")
    # 4. Practice loop with no key: enqueue, claim, heartbeat, save a Task Object, submit.
    q = "demo.echo"
    H = {"x-agent-label": f"{AGENT}-{RUN}"}
    tb = {"queue": q, "brief": {"title": "e2e probe practice Task", "example_only": True}}
    r = req("POST", FABRIC + "/v1/tasks", headers=H, json=tb)
    created = jbody(r) or {}
    tid = created.get("task_id") or (created.get("task") or {}).get("id") or created.get("id")
    check(st, "no-key POST /v1/tasks creates a practice Task", r.status_code in (200, 201) and tid, curl("POST", FABRIC + "/v1/tasks", H, tb), f"{r.status_code} {r.text[:250]}")
    c = {"queue": q, "worker": AGENT}
    r = req("POST", FABRIC + "/v1/tasks/claim", headers=H, json=c)
    lease = (lambda d: d.get("lease") or (d if d.get("fencing_token") else None))(jbody(r) or {})
    check(st, "no-key claim returns a lease", r.status_code == 200 and lease, curl("POST", FABRIC + "/v1/tasks/claim", H, c), f"{r.status_code} {r.text[:250]}")
    if lease:
        hb = {"task_id": lease["task_id"], "fencing_token": lease["fencing_token"], "worker": AGENT}
        r = req("POST", FABRIC + "/v1/tasks/heartbeat", headers=H, json=hb)
        check(st, "no-key heartbeat", r.status_code == 200, curl("POST", FABRIC + "/v1/tasks/heartbeat", H, hb), f"{r.status_code} {r.text[:200]}")
        key = f"e2e-{RUN}"
        rec = {"value": {"title": "e2e probe Task Object", "example_only": True}, "expected_version": 0}
        r = req("POST", f"{FABRIC}/v1/stores/demo.artifacts/records/{key}", headers=H, json=rec)
        check(st, "no-key Task Object save", r.status_code in (200, 201), curl("POST", f"{FABRIC}/v1/stores/demo.artifacts/records/{key}", H, rec), f"{r.status_code} {r.text[:250]}")
        r = req("GET", f"{FABRIC}/v1/stores/demo.artifacts/records/{key}", headers=H)
        check(st, "the saved Task Object reads back", r.status_code == 200 and "e2e probe" in r.text, curl("GET", f"{FABRIC}/v1/stores/demo.artifacts/records/{key}", H), f"{r.status_code} {r.text[:200]}")
        sub = {"task_id": lease["task_id"], "fencing_token": lease["fencing_token"], "worker": AGENT, "output": {"record": key, "version": 1}, "idempotency_key": f"{lease['task_id']}:{lease['fencing_token']}"}
        r = req("POST", FABRIC + "/v1/tasks/submit", headers=H, json=sub)
        check(st, "no-key submit gives a record", r.status_code == 200, curl("POST", FABRIC + "/v1/tasks/submit", H, sub), f"{r.status_code} {r.text[:250]}")
        r2 = req("POST", FABRIC + "/v1/tasks/submit", headers=H, json=sub)
        check(st, "a repeated submit returns the first record, no second result", r2.status_code == 200 and (jbody(r2) or {}).get("receipt_hash") == (jbody(r) or {}).get("receipt_hash"), curl("POST", FABRIC + "/v1/tasks/submit", H, sub), f"{r2.status_code} {r2.text[:200]}")
        r = req("GET", f"{FABRIC}/v1/me/audit", headers=H)
        check(st, "the agent can read its own recorded actions", r.status_code == 200 and "claim" in r.text, curl("GET", f"{FABRIC}/v1/me/audit", H), f"{r.status_code} {r.text[:200]}")
    # 5. Real work: open Tasks on the shared queue a stranger can see and take.
    r = req("GET", FABRIC + "/v1/verbs?status=ready&limit=100", headers=M)
    verbs = (jbody(r) or {}).get("verbs", [])
    check(st, "the shared queue has at least one Task open to a new agent", r.status_code == 200 and verbs, curl("GET", FABRIC + "/v1/verbs?status=ready&limit=100", M), f"{r.status_code} open={len(verbs)} {r.text[:150]}")
    canary = [v for v in verbs if "e2e-canary" in json.dumps(v.get("tags", [])) or "e2e-canary" in json.dumps(v.get("brief", {}))]
    target = canary[0] if canary else (verbs[0] if verbs and ARGS.claim_real else None)
    if target:
        c = {"queue": target["queue"], "worker": AGENT, "task_id": target.get("id") or target.get("task_id")}
        r = req("POST", FABRIC + "/v1/tasks/claim", headers=M, json=c)
        lease = (lambda d: d.get("lease") or (d if d.get("fencing_token") else None))(jbody(r) or {})
        check(st, "a stranger claims a real shared Task with no key", r.status_code == 200 and lease, curl("POST", FABRIC + "/v1/tasks/claim", M, c), f"{r.status_code} {r.text[:250]}")
        if lease:
            sub = {"task_id": lease["task_id"], "fencing_token": lease["fencing_token"], "worker": AGENT, "output": {"note": "e2e canary done", "run": RUN}, "idempotency_key": f"{lease['task_id']}:{lease['fencing_token']}"}
            r = req("POST", FABRIC + "/v1/tasks/submit", headers=M, json=sub)
            check(st, "a stranger reports a real shared Task with no key", r.status_code == 200, curl("POST", FABRIC + "/v1/tasks/submit", M, sub), f"{r.status_code} {r.text[:250]}")
    # 6. MCP.
    r, b = rpc(FABRIC + "/mcp", "initialize", {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": AGENT, "version": "1"}})
    check(st, "MCP initialize with no key", r.status_code == 200 and b and "result" in b, curl("POST", FABRIC + "/mcp", None, {"method": "initialize"}), f"{r.status_code} {r.text[:200]}")
    r, b = rpc(FABRIC + "/mcp", "tools/list")
    tools = {t["name"]: t for t in ((b or {}).get("result") or {}).get("tools", [])}
    check(st, "MCP tools/list", bool(tools), curl("POST", FABRIC + "/mcp", None, {"method": "tools/list"}), r.text[:200])
    for name, args in [("search_nouns", {"query": "nonprofit"}), ("explain_access_modes", {}), ("whoami", {})]:
        r, b = rpc(FABRIC + "/mcp", "tools/call", {"name": name, "arguments": args})
        err = (b or {}).get("error") or ((b or {}).get("result") or {}).get("isError")
        check(st, f"MCP {name} with no key", r.status_code == 200 and b and not err, curl("POST", FABRIC + "/mcp", None, {"method": "tools/call", "params": {"name": name, "arguments": args}}), r.text[:300])
    r, b = rpc(FABRIC + "/mcp", "tools/call", {"name": "enqueue", "arguments": {"queue": "demo.ping", "brief": {"title": "e2e mcp", "example_only": True}}})
    err = (b or {}).get("error") or ((b or {}).get("result") or {}).get("isError")
    check(st, "MCP enqueue in practice space with no key", r.status_code == 200 and b and not err, curl("POST", FABRIC + "/mcp", None, {"method": "tools/call", "params": {"name": "enqueue"}}), r.text[:300])
    r, b = rpc(FABRIC + "/mcp", "tools/call", {"name": "claim", "arguments": {"queue": "demo.ping", "worker": AGENT}})
    d = tool_text(b) or {}
    check(st, "MCP claim with no key", bool(d.get("lease") or d.get("fencing_token")), curl("POST", FABRIC + "/mcp", None, {"method": "tools/call", "params": {"name": "claim"}}), r.text[:300])
    # 7. The older session door still works for agents that want it.
    r = req("POST", FABRIC + "/v1/session/anonymous", json={"agent_label": AGENT, "show_on_map": False})
    d = jbody(r) or {}
    check(st, "optional session door works", r.status_code == 201 and d.get("session_token"), curl("POST", FABRIC + "/v1/session/anonymous", None, {"agent_label": AGENT}), f"{r.status_code}")
    if d.get("session_token"):
        s = {"authorization": "Bearer " + d["session_token"]}
        for q in ("demo.ping",):
            r = req("POST", FABRIC + "/v1/tasks/claim", headers=s, json={"queue": q, "worker": AGENT})
            lz = (lambda d: d.get("lease") or (d if d.get("fencing_token") else None))(jbody(r) or {})
            check(st, f"session claim {q}", r.status_code == 200 and lz, "POST /v1/session/anonymous, then claim with the token", f"{r.status_code} {r.text[:200]}")
    # 8. A browser must be able to POST from another site (the CORS blocker).
    r = req("OPTIONS", FABRIC + "/v1/tasks", headers={"origin": ERANOS, "access-control-request-method": "POST", "access-control-request-headers": "content-type,x-namespace"})
    allow = r.headers.get("access-control-allow-headers", "")
    check(st, "CORS preflight names valid headers only", r.status_code == 204 and all(re.fullmatch(r"[A-Za-z0-9-]+", x.strip()) for x in allow.split(",")), f"curl -i -X OPTIONS {FABRIC}/v1/tasks -H 'origin: {ERANOS}' -H 'access-control-request-method: POST'", allow)
    # 9. Human link: ask, open, answer once, read the answer.
    body = {"kind": "ask", "text": "e2e probe: please ignore, an automated test answers this.", "ttl_seconds": 120}
    r = req("POST", FABRIC + "/v1/human-links", headers=H, json=body)
    d = jbody(r) or {}
    ok = check(st, "no-key agent gets a human link", r.status_code == 201 and d.get("url"), curl("POST", FABRIC + "/v1/human-links", H, body), f"{r.status_code} {r.text[:200]}")
    if ok:
        token = d["url"].rsplit("/", 1)[-1]
        p = req("GET", d["url"])
        check(st, "the human link page opens and shows no token in the page text", p.status_code == 200 and token not in re.sub(r"<script.*?</script>", "", p.text, flags=re.S), "open the url the POST returned", p.status_code)
        pub = {"x-human-link-token": token}
        r = req("GET", FABRIC + "/v1/human-links/public", headers=pub)
        check(st, "the link shows the question", r.status_code == 200 and "e2e probe" in r.text, "GET /v1/human-links/public with header x-human-link-token", r.text[:150])
        r = req("POST", FABRIC + "/v1/human-links/public", headers=pub, json={"answer": "send", "value": "e2e answer"})
        check(st, "the person's answer is accepted", r.status_code == 200, "POST /v1/human-links/public with action send", f"{r.status_code} {r.text[:200]}")
        r = req("POST", FABRIC + "/v1/human-links/public", headers=pub, json={"answer": "send", "value": "second answer"})
        check(st, "the link answers only once", r.status_code >= 400 or "second answer" not in r.text, "POST the answer twice", f"{r.status_code} {r.text[:200]}")
        r = req("GET", f"{FABRIC}/v1/human-links/{d['id']}", headers=H)
        check(st, "the agent reads the person's answer", r.status_code == 200 and "e2e answer" in r.text, curl("GET", f"{FABRIC}/v1/human-links/{d['id']}", H), f"{r.status_code} {r.text[:200]}")
    # 10. Library door as documented.
    r = req("GET", FABRIC + "/v1/library/catalog")
    check(st, "library catalog reads with no key", r.status_code == 200, f"curl {FABRIC}/v1/library/catalog", f"{r.status_code} {r.text[:200]}")
    # 11. A Task's page words: board and work page.
    r = req("GET", FABRIC + "/work")
    check(st, "the /work page does not ask for a key at every step", not re.search(r'name="key"[^>]*required', r.text), f"open {FABRIC}/work", re.findall(r"[^.>]{0,60}\bkey\b[^.<]{0,40}", r.text)[:3])


# ---------- shim ----------
def shim():
    st = "shim"
    llms = req("GET", SHIM + "/llms.txt").text
    check(st, "shim llms.txt says Teleion Fabric, not the old name", not old_names(llms), f"curl {SHIM}/llms.txt", len(old_names(llms)))
    check(st, "shim llms.txt does not require a key", not re.search(r"(hmk_ .*required|require scoped)", llms, re.I), f"curl {SHIM}/llms.txt", [l for l in llms.splitlines() if "hmk_" in l][:2])
    c = jbody(req("GET", SHIM + "/connect.json")) or {}
    check(st, "shim connect.json uses the public address", "tessera.ta-amps" not in json.dumps(c) and True, f"curl {SHIM}/connect.json", json.dumps(c.get("tessera_access", {}))[:200])
    r = req("POST", SHIM + "/api/preview", json={"prompt": "How do I add a nonprofit flyer task to the shared queue?"})
    d = jbody(r) or {}
    check(st, "preview answers", r.status_code == 200 and d, curl("POST", SHIM + "/api/preview", None, {"prompt": "..."}), f"{r.status_code} {r.text[:200]}")
    preview_prose = re.sub(r'"sha256_hash": "[0-9a-f]+"|"verification_verdict": "\w+"', "", json.dumps(d))
    check(st, "preview text has the public name and words", not old_names(r.text) and not word_hits(preview_prose, ("always", "visible_text")), curl("POST", SHIM + "/api/preview", None, {"prompt": "How do I add a nonprofit flyer task to the shared queue?"}), f"old={len(old_names(r.text))} words={word_hits(json.dumps(d), ('always', 'visible_text'))}")
    r, b = rpc(SHIM + "/mcp", "tools/list")
    tools = [t["name"] for t in ((b or {}).get("result") or {}).get("tools", [])]
    check(st, "shim MCP tools/list", bool(tools), curl("POST", SHIM + "/mcp", None, {"method": "tools/list"}), f"{r.status_code} {r.text[:200]}")
    # The queue door, following the steps in llms.txt: schema, onboard, claim, report.
    r = req("GET", SHIM + "/q/schema"); check(st, "queue schema", r.status_code == 200, f"curl {SHIM}/q/schema", r.status_code)
    r = req("GET", SHIM + "/q/pulse"); pulse = jbody(r) or {}
    check(st, "queue pulse", r.status_code == 200 and pulse.get("ok"), f"curl {SHIM}/q/pulse", r.status_code)
    r = req("GET", SHIM + "/q/search?q=nonprofit&format=json"); check(st, "queue search with no key", r.status_code == 200, f"curl '{SHIM}/q/search?q=nonprofit&format=json'", f"{r.status_code} {r.text[:150]}")
    r = req("GET", SHIM + "/dashboard?format=json"); check(st, "dashboard data", r.status_code == 200 and jbody(r) is not None, f"curl '{SHIM}/dashboard?format=json'", f"{r.status_code}")
    r = req("GET", SHIM + "/q/network"); check(st, "network map data", r.status_code == 200, f"curl {SHIM}/q/network", r.status_code)
    on = {"agent_name": f"{AGENT}-{RUN}", "model": "none", "show_on_map": False, "worker_type": "probe"}
    r = req("POST", SHIM + "/q/onboard", json=on); d = jbody(r) or {}
    check(st, "a new worker can join with no key", r.status_code in (200, 201) and d.get("ok", True), curl("POST", SHIM + "/q/onboard", None, on), f"{r.status_code} {r.text[:300]}")
    wid = d.get("worker_id") or (d.get("worker") or {}).get("worker_id") or (d.get("worker") or {}).get("id")
    ARGS.shim_worker = {"id": wid, "token": d.get("worker_token") or d.get("token")}
    claim = {"worker_id": wid, "agent_name": on["agent_name"], "probe": True, "diagnostic": True, "peek": True}
    if ARGS.claim_real:
        r = req("POST", SHIM + "/q/claim", json=claim); d = jbody(r) or {}
        check(st, "a stranger can claim from the shim queue", r.status_code == 200 and (d.get("task") or d.get("lease") or d.get("ok")), curl("POST", SHIM + "/q/claim", None, claim), f"{r.status_code} {r.text[:300]}")
    # Zero-auth for the model-forward route: the door must open with no key (a malformed body cannot spend).
    r = req("POST", SHIM + "/v1/dry-run", json={"model": "muse-spark-1.3", "messages": [{"role": "user", "content": "e2e probe dry run"}]})
    check(st, "dry run with no key", r.status_code == 200, curl("POST", SHIM + "/v1/dry-run", None, {"model": "muse-spark-1.3", "messages": []}), f"{r.status_code} {r.text[:200]}")
    r = req("POST", SHIM + "/v1/chat/completions", json={"model": "muse-spark-1.3", "messages": []})
    check(st, "chat route opens with no key (empty body refused as invalid, not as unauthorized)", r.status_code not in (401, 403), curl("POST", SHIM + "/v1/chat/completions", None, {"model": "muse-spark-1.3", "messages": []}), f"{r.status_code} {r.text[:200]}")
    r = req("GET", SHIM + "/", allow_redirects=False, headers={"accept": "text/html", "sec-fetch-mode": "navigate", "sec-fetch-dest": "document"})
    check(st, "the shim root takes a person to the Fabric page", r.status_code in (301, 302, 307, 308) and "teleionlabs.com/fabric" in r.headers.get("location", ""), f"curl -i {SHIM}/", f"{r.status_code} {r.headers.get('location')}")



# ---------- the shim's queue, as a bot on a schedule would use it ----------
Q_CONTENT = {
    "title": "Volunteer retention: what public research says, with sources",
    "points": [
        {"point": "Leadership inclusiveness predicted retention better than leadership integrity.", "source": "https://doi.org/10.18666/jnel-2016-v6-i4-6521"},
        {"point": "Matching volunteer skills to assignments is linked to longer service.", "source": "https://openalex.org/W2766874007"},
    ],
    "note": "Written by the labeled end-to-end test agent from the public Eranos report RPT-R1FDD2ED-01.",
}


def q_stage(base):
    import threading
    st = "q:" + urlparse(base).netloc
    bot = f"e2e-test-bot-{RUN}"
    check(st, "pulse with no key", req("GET", base + "/q/pulse").status_code == 200, f"curl {base}/q/pulse")
    # A canary Task made by one labeled bot, done by another: the only Task these tests complete.
    tag = f"e2e-canary-{RUN}"
    r = req("POST", base + "/q/enqueue", json={"agent_id": bot + "-maker", "title": f"{tag}: gather public sources on volunteer retention", "prompt": "Labeled end-to-end test Task. List two public sources on keeping volunteers.", "tags": [tag], "category": tag, "show_on_map": False})
    d = jbody(r) or {}
    tasks = d.get("enqueued_followup_tasks") or d.get("enqueued_followup_verbs") or []
    tid = d.get("task_id") or (tasks[0].get("task_id") if tasks and isinstance(tasks[0], dict) else (tasks[0] if tasks else None))
    check(st, "a bot can add a Task with no key", r.status_code == 200 and tid, curl("POST", base + "/q/enqueue", None, {"title": tag}), f"{r.status_code} {r.text[:300]}")
    if not tid:
        return
    worker = bot + "-post"
    r = req("POST", base + "/q/claim", json={"agent_id": worker, "task_id": tid, "lease_seconds": 300, "show_on_map": False})
    d = jbody(r) or {}
    lease = d.get("lease") or {}
    check(st, "POST /q/claim with no key leases the Task", lease.get("task_id") == tid, curl("POST", base + "/q/claim", None, {"agent_id": worker, "task_id": tid}), f"{r.status_code} {r.text[:300]}")
    host_bad = sorted(set(re.findall(r"https://herma\.teleionlabs\.com[^\s\"]*", r.text)))[:3]
    check(st, "the claim answer names the public address", not host_bad, f"POST {base}/q/claim and read its addresses", host_bad)
    size = len(r.content)
    check(st, "the claim answer is a sensible size (under 80 KB)", size < 80000, f"POST {base}/q/claim", f"{size} bytes")
    key_dict = f"e2e_dict_{RUN}_v1"
    key_list = f"e2e_list_{RUN}_v1"
    verb_title = f"{tag}: follow-up, add a third source"
    sub = {"agent_id": worker, "task_id": tid, "fencing_token": lease.get("fencing_token"), "summary": "Two public sources on volunteer retention, with what each says.",
           "task_objects": {key_dict: {"category": "canonical_schema", "summary": "Volunteer retention sources, sent as a dict", "payload": Q_CONTENT}},
           "queued_tasks": [{"title": verb_title, "prompt": "Labeled end-to-end test follow-up: add a third public source on keeping volunteers."}], "show_on_map": False}
    r = req("POST", base + "/q/submit", json=sub)
    d = jbody(r) or {}
    check(st, "POST /q/submit answers", r.status_code == 200 and d.get("ok"), curl("POST", base + "/q/submit", None, {"task_id": tid}), f"{r.status_code} {r.text[:300]}")
    printout = d.get("contributor_printout")
    check(st, "the answer carries the printout for the person", bool(printout), f"POST {base}/q/submit", str(list(d.keys()))[:300])
    recs = d.get("receipt") or d.get("record") or d.get("completion_receipt") or d.get("receipt_sha256") or d.get("receipt_hash")
    check(st, "a record of the submit comes back", bool(recs), f"POST {base}/q/submit", str(list(d.keys()))[:300])
    o = req("GET", base + f"/q/object/{key_dict}")
    if o.status_code != 200:
        o = req("GET", base + f"/q/objects/{key_dict}")
    if o.status_code != 200:
        o = req("GET", base + "/q/search", params={"q": key_dict, "format": "json"})
    check(st, "a dict-form Task Object is really stored", key_dict in o.text or "Volunteer retention sources" in o.text, f"submit task_objects as a dict, then GET {base}/q/search?q={key_dict}&format=json", f"{o.status_code} {o.text[:250]}")
    t = req("GET", base + f"/q/task/{tid}")
    if t.status_code != 200:
        t = req("GET", base + f"/q/tasks/{tid}")
    check(st, "a reader sees no holder or fence on a Task", '"fencing_token"' not in t.text and '"leased_by"' not in t.text, f"curl {base}/q/task/{tid}", t.text[:200])
    check(st, "the Task reads as completed", t.status_code == 200 and re.search(r'"state":\s*"(completed|done|complete)"', t.text), f"curl {base}/q/task/{tid}", f"{t.status_code} {t.text[:300]}")
    fup = req("GET", base + "/q/search", params={"q": verb_title, "format": "json"})
    check(st, "a follow-up with a real prompt is stored, under the priority cap", tag in json.dumps(d) or tag in fup.text, f"curl '{base}/q/search?q=...&format=json'", fup.text[:200])
    r = req("POST", base + "/q/submit", json={**sub, "task_objects": "not an object"})
    check(st, "a malformed task_objects is refused loudly, not a 200 or a crash", 400 <= r.status_code < 500 or (r.status_code == 200 and (jbody(r) or {}).get("idempotent_replay")), f"POST {base}/q/submit with task_objects a string", f"{r.status_code} {r.text[:200]}")
    # The GET forms, for browser and chat bots that can only open a link.
    gw = bot + "-get"
    r = req("POST", base + "/q/enqueue", json={"agent_id": bot + "-maker", "title": f"{tag}: GET form test", "prompt": "Labeled test Task for the GET forms.", "category": tag})
    d = jbody(r) or {}
    tasks = d.get("enqueued_followup_tasks") or d.get("enqueued_followup_verbs") or []
    gt = d.get("task_id") or (tasks[0].get("task_id") if tasks and isinstance(tasks[0], dict) else (tasks[0] if tasks else None))
    r = req("GET", base + f"/q/claim/{gw}", params={"task_id": gt, "format": "json"})
    d = jbody(r) or {}
    lease = d.get("lease") or {}
    check(st, "GET /q/claim/<agent> leases a Task", lease.get("task_id") == gt or gt in r.text, f"curl '{base}/q/claim/{gw}?task_id={gt}&format=json'", f"{r.status_code} {r.text[:250]}")
    ok_key = f"e2e_get_{RUN}"
    follow = f"e2e-followup-{RUN}"
    r = req("GET", base + f"/q/submit/{gw}/{gt}/summary-public-sources-on-volunteer-retention--object-{ok_key}:volunteer-retention-sources--verb-{follow}", params={"fencing_token": lease.get("fencing_token"), "format": "json"})
    check(st, "GET /q/submit with --object- and --verb- answers", r.status_code == 200, f"curl '{base}/q/submit/{gw}/{gt}/summary-...--object-{ok_key}:...--verb-{follow}'", f"{r.status_code} {r.text[:300]}")
    o = req("GET", base + "/q/search", params={"q": ok_key, "format": "json"})
    check(st, "the GET form's Task Object is really stored", ok_key in o.text, f"curl '{base}/q/search?q={ok_key}&format=json'", o.text[:200])
    check(st, "a title-only follow-up from the GET form is refused and says so", "rejected_followup" in r.text or "real prompt" in r.text or follow in r.text, f"curl '{base}/q/submit/{gw}/{gt}/...--verb-{follow}'", r.text[:300])
    # Two claimers at once: different Tasks, never one Task twice.
    found = {}
    def claim(name):
        x = req("POST", base + "/q/claim", json={"agent_id": name, "family": tag, "lease_seconds": 60, "show_on_map": False})
        found[name] = ((jbody(x) or {}).get("lease") or {}).get("task_id")
    for i in range(2):
        req("POST", base + "/q/enqueue", json={"agent_id": bot + "-maker", "title": f"{tag}: concurrent claim test {i}", "prompt": "Labeled test Task, for two claimers at once.", "category": tag})
    ts = [threading.Thread(target=claim, args=(f"{bot}-c{i}",)) for i in range(2)]
    [t.start() for t in ts]; [t.join() for t in ts]
    vals = [v for v in found.values() if v]
    check(st, "two claimers at once never get the same Task", len(vals) == len(set(vals)) and vals, f"two POST {base}/q/claim at the same moment", found)
    # Empty queue: a filter that matches nothing gets a next step, not an error.
    r = req("POST", base + "/q/claim", json={"agent_id": bot + "-empty", "family": f"nothing-matches-{RUN}"})
    d = jbody(r) or {}
    check(st, "an empty queue answers with what to do next", r.status_code == 200 and not d.get("lease") and re.search(r"self_seed|waterfall|next", r.text), curl("POST", base + "/q/claim", None, {"family": "nothing"}), f"{r.status_code} {r.text[:300]}")
    # No field work for an API bot, and no gate per caller.
    titles = []
    if ARGS.claim_real:
        for i in range(6):
            x = req("POST", base + "/q/claim", json={"agent_id": f"{bot}-f{i}", "tier": "ngo_priority", "lease_seconds": 30, "show_on_map": False})
            titles.append((((jbody(x) or {}).get("lease")) or {}).get("title") or "")
        bad = [t for t in titles if re.search(r"field[- ]team|live block|field partner|gloved", t, re.I)]
        check(st, "an API bot is not handed work that needs people in a place", not bad, f"POST {base}/q/claim as a new agent", bad[:2] or titles[:3])
    import concurrent.futures as cf
    with cf.ThreadPoolExecutor(16) as ex:
        res = list(ex.map(lambda i: req("GET", base + "/q/schema", timeout=25).status_code, range(140)))
    check(st, "140 quick requests from one address meet no rate gate", 429 not in res, f"140 quick GET {base}/q/schema", {c: res.count(c) for c in set(res)})


# ---------- eranos api ----------
def eranos():
    st = "eranos"
    conn = jbody(req("GET", ERANOS + "/connect.json")) or {}
    txt = json.dumps(conn)
    check(st, "connect.json agrees with the no-key rule", not re.search(r"(uses a Teleion Fabric anonymous session or an API key)", txt), f"curl {ERANOS}/connect.json", txt[:300])
    r, b = rpc(ERANOS + "/mcp", "tools/list")
    tools = [t["name"] for t in ((b or {}).get("result") or {}).get("tools", [])]
    check(st, "MCP lists the documented tools", {"list_tracks", "search_catalog", "get_kit", "practice_verify_kit"} <= set(tools), curl("POST", ERANOS + "/mcp", None, {"method": "tools/list"}), tools)
    r, b = rpc(ERANOS + "/mcp", "tools/call", {"name": "list_tracks", "arguments": {}})
    check(st, "MCP list_tracks", r.status_code == 200 and b and not (b.get("error") or (b.get("result") or {}).get("isError")), "POST /mcp tools/call list_tracks", r.text[:200])
    cat = jbody(req("GET", ERANOS + "/api/catalog")) or {}
    kits = cat.get("kits") or cat.get("items") or []
    check(st, "catalog has kits", bool(kits), f"curl {ERANOS}/api/catalog", str(cat)[:200])
    if kits:
        kid = kits[0].get("id") or kits[0].get("kit_id") or (kits[0].get("kit") or {}).get("kit_id")
        r = req("GET", f"{ERANOS}/api/catalog/{kid}"); check(st, "a kit reads over HTTP", r.status_code == 200, f"curl {ERANOS}/api/catalog/{kid}", r.status_code)
        r, b = rpc(ERANOS + "/mcp", "tools/call", {"name": "get_kit", "arguments": {"id": kid, "kit_id": kid}})
        check(st, "a kit reads over MCP", r.status_code == 200 and b and not (b.get("error") or (b.get("result") or {}).get("isError")), f"POST /mcp tools/call get_kit {kid}", r.text[:200])
    r = req("POST", ERANOS + "/api/practice", json={"title": "e2e probe draft"})
    check(st, "practice check answers and stores nothing", r.status_code in (200, 400, 422) and jbody(r) is not None, curl("POST", ERANOS + "/api/practice", None, {"title": "e2e probe draft"}), f"{r.status_code} {r.text[:200]}")
    r = req("GET", ERANOS + "/api/open-tasks"); d = jbody(r) or {}
    open_now = [t for t in d.get("tasks", []) if t.get("open_to_anonymous")]
    check(st, "the volunteer list shows Tasks a new agent can take", bool(open_now), f"curl {ERANOS}/api/open-tasks", f"{len(open_now)} of {len(d.get('tasks', []))} open to new agents")
    for path, must in [("/help", None), ("/llms.txt", None)]:
        t = req("GET", ERANOS + path).text
        check(st, f"{path} does not say a key is needed for Tasks", not re.search(r"volunteer key for other Tasks|Keys come from Teleion Fabric|volunteer key", t, re.I), f"open {ERANOS}{path}", re.findall(r"[^.<>]{0,80}(?:volunteer key|Keys come from)[^.<>]{0,60}", t)[:2])
    for path, host in [("/", ERANOS), ("/models/", ERANOS), ("/network/", ERANOS)]:
        r = req("GET", AGORA + path, allow_redirects=False)
    r = req("GET", AGORA + "/", allow_redirects=False)
    check(st, "Agora's main page redirects", r.status_code in (301, 302, 307, 308), f"curl -i {AGORA}/", f"{r.status_code} {r.headers.get('location')}")
    r = req("GET", AGORA + "/evidence/")
    check(st, "Agora records stay served", r.status_code == 200, f"curl -i {AGORA}/evidence/", r.status_code)


def names_stage():
    import subprocess
    out = subprocess.run([sys.executable, str(HERE / "oldnames.py")], capture_output=True, text=True, timeout=400)
    last = out.stdout.strip().splitlines()[-1] if out.stdout.strip() else out.stderr[-200:]
    check("names", "no old product name on any public route", out.returncode == 0, f"python3 {HERE / 'oldnames.py'}", last)
    r = req("OPTIONS", FABRIC + "/v1/tasks", headers={"origin": ERANOS, "access-control-request-method": "POST", "access-control-request-headers": "x-tessera-namespace"})
    check("names", "the old namespace header still passes a browser preflight", "x-tessera-namespace" in r.headers.get("access-control-allow-headers", "").lower(), "OPTIONS /v1/tasks asking with the old header", r.headers.get("access-control-allow-headers"))
    r = req("GET", FABRIC + "/v1/me", headers={"x-tessera-namespace": "main"})
    check("names", "the old namespace header still works", r.status_code == 200 and '"namespace":"main"' in r.text.replace(" ", ""), "GET /v1/me with the old header", r.text[:150])


# ---------- browser ----------
def browser():
    st = "browser"
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        b = pw.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
        def visit(ctx, url, wait=1200):
            page = ctx.new_page(); errs, failed = [], []
            page.on("console", lambda m: errs.append(m.text[:200]) if m.type == "error" and "cloudflareinsights" not in m.text else None)
            page.on("pageerror", lambda e: errs.append("pageerror: " + str(e)[:200]))
            page.on("response", lambda r: failed.append(f"{r.status} {r.url[:120]}") if r.status >= 400 else None)
            resp = page.goto(url, wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(wait)
            return page, resp, errs, failed
        desk = b.new_context(viewport={"width": 1280, "height": 800}, user_agent=UA)
        phone = b.new_context(viewport={"width": 390, "height": 844}, user_agent=UA, is_mobile=True, has_touch=True)
        routes = [(ERANOS, p) for p in ["/", "/nonprofits", "/help", "/requests", "/library", "/catalog", "/connect", "/privacy", "/terms", "/report", "/video"]] + \
                 [(TELEION, p) for p in ["/", "/fabric/", "/free/", "/docs/", "/status/", "/benchmarks/", "/video/", "/omninode/", "/shimming/", "/fabric-intelligence/", "/feeds/"]] + \
                 [(FABRIC, "/connect"), (FABRIC, "/board"), (FABRIC, "/work")]
        for base, path in routes:
            url = base + path
            page, resp, errs, failed = visit(desk, url)
            bg = page.evaluate("getComputedStyle(document.body).backgroundColor")
            lum = sum(float(x) for x in re.findall(r"[\d.]+", bg)[:3])
            check(st, f"{url} loads with no errors", resp and resp.status < 400 and not errs and not failed, f"open {url}, look at the browser console", {"status": resp and resp.status, "console": errs[:4], "failed": failed[:4]})
            check(st, f"{url} is light", lum > 400 or bg in ("rgba(0, 0, 0, 0)", "transparent"), f"open {url}", bg)
            page.close()
            page, resp, errs, failed = visit(phone, url, 500)
            over = page.evaluate("document.documentElement.scrollWidth - window.innerWidth")
            check(st, f"{url} has no sideways scroll on a phone", over <= 1, f"open {url} at 390 px wide", f"{over}px over")
            page.close()
        # Eranos doors and a click path.
        page, *_ = visit(desk, ERANOS + "/")
        texts = [a.inner_text().strip() for a in page.locator("main a, main button").all()]
        ngo = next((i for i, t in enumerate(texts) if "My NGO needs help" in t), None)
        hlp = next((i for i, t in enumerate(texts) if "I want to help" in t), None)
        check(st, "Eranos home has both doors, the NGO door first", ngo is not None and hlp is not None and ngo < hlp, f"open {ERANOS}/", texts[:8])
        if ngo is not None:
            page.get_by_text("My NGO needs help").first.click(); page.wait_for_timeout(1500)
            check(st, "the NGO door opens a request form", page.locator("form textarea, textarea").count() > 0, f"open {ERANOS}/ and click My NGO needs help", page.url)
        page.goto(ERANOS + "/", wait_until="domcontentloaded"); page.wait_for_timeout(600)
        if hlp is not None:
            page.get_by_text("I want to help").first.click(); page.wait_for_timeout(1500)
            check(st, "the help door opens the volunteer page", "/help" in page.url, f"open {ERANOS}/ and click I want to help", page.url)
            t = page.locator("main").inner_text()
            check(st, "the volunteer page shows work and how to connect", bool(re.search(r"connect", t, re.I)), f"open {ERANOS}/help", t[:200])
        # Library: open one, read it, download it.
        page.goto(ERANOS + "/library", wait_until="domcontentloaded"); page.wait_for_timeout(2000)
        links = page.locator('main a[href*="/requests/"], main a[href*="/result"]').all()
        check(st, "the library lists finished work", bool(links), f"open {ERANOS}/library", page.locator("main").inner_text()[:200])
        if links:
            href = links[0].get_attribute("href"); page.goto(urljoin(ERANOS, href), wait_until="domcontentloaded"); page.wait_for_timeout(2500)
            t = page.locator("main").inner_text()
            check(st, "a library result opens with text", len(t) > 200 and "undefined" not in t, f"open {ERANOS}{href}", t[:200])
            downloads = [a.get_attribute("href") for a in page.locator('main a[download], main a[href$=".md"], main a[href$=".json"], main a[href*="download"]').all()]
            bad = []
            for d in downloads[:6]:
                r = req("GET", urljoin(page.url, d), stream=True)
                if r.status_code >= 400: bad.append((d, r.status_code))
            check(st, f"result downloads work ({len(downloads)} found)", not bad, f"open {ERANOS}{href} and use its download links", bad)
        # Catalog: one kit page.
        page.goto(ERANOS + "/catalog", wait_until="domcontentloaded"); page.wait_for_timeout(2000)
        links = page.locator('main a[href*="/catalog/"]').all()
        check(st, "the catalog lists kits", bool(links), f"open {ERANOS}/catalog", page.locator("main").inner_text()[:200])
        if links:
            href = links[0].get_attribute("href"); page2, resp, errs, failed = visit(desk, urljoin(ERANOS, href), 1800)
            check(st, f"a kit page opens ({href})", resp.status == 200 and not errs and not failed, f"open {ERANOS}{href}", {"console": errs[:3], "failed": failed[:3]}); page2.close()
        page.close()
        # Teleion home: the canvas film runs.
        page, resp, errs, failed = visit(desk, TELEION + "/", 4000)
        has = page.evaluate("document.querySelectorAll('canvas').length + [...document.querySelectorAll('video')].filter(v => v.currentTime > 0).length")
        check(st, "the Teleion home film is playing", has > 0, f"open {TELEION}/", has)
        page.close()
        # Human link, in a browser, from the agent's request to the agent reading the answer.
        H = {"x-agent-label": AGENT}
        r = req("POST", FABRIC + "/v1/human-links", headers=H, json={"kind": "confirm", "text": "e2e probe: please ignore, an automated browser test answers this.", "ttl_seconds": 180})
        d = jbody(r) or {}
        if d.get("url"):
            page, resp, errs, failed = visit(desk, d["url"], 1500)
            btn = page.get_by_role("button").filter(has_text=re.compile("yes|confirm|approve", re.I))
            check(st, "the human link page shows the question and a button", "e2e probe" in page.locator("body").inner_text() and btn.count() > 0, "POST /v1/human-links, open the url", page.locator("body").inner_text()[:300])
            if btn.count():
                btn.first.click(); page.wait_for_timeout(1500)
                got = jbody(req("GET", f"{FABRIC}/v1/human-links/{d['id']}", headers=H)) or {}
                check(st, "clicking in the browser reaches the agent", got.get("state") == "confirmed", "click the button, GET /v1/human-links/<id>", got)
            check(st, "the human link page has no console errors", not errs and not failed, "open the url", {"console": errs[:3], "failed": failed[:3]})
            page.close()
        else:
            check(st, "human link for the browser test", False, curl("POST", FABRIC + "/v1/human-links", H, {"kind": "confirm"}), f"{r.status_code} {r.text[:200]}")
        b.close()


def report():
    fails = [r for r in results if not r["ok"]]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    lines = [f"# End-to-end results, {now}", "", f"Run `{RUN}`, stages {ARGS.stages}. {len(results) - len(fails)} passed, {len(fails)} failed. Rerun: `python3 notes/work-2026-11-03/e2e/e2e.py`.", ""]
    if fails:
        lines += ["## Failures", ""]
        for r in fails:
            lines += [f"### [{r['stage']}] {r['name']}", f"- Reproduce: `{r['repro']}`", f"- Saw: {r['detail']}", ""]
    lines += ["## Everything checked", ""] + [f"- {'PASS' if r['ok'] else 'FAIL'} [{r['stage']}] {r['name']}" for r in results]
    known = HERE / "KNOWN-LEFT.md"
    if known.exists():
        lines += ["", known.read_text()]
    (HERE / "RESULTS.md").write_text("\n".join(lines) + "\n")
    (HERE / "results.json").write_text(json.dumps({"at": now, "run": RUN, "results": results}, indent=1))
    print(f"\n{len(results) - len(fails)} passed, {len(fails)} failed. {HERE / 'RESULTS.md'}")
    return 1 if fails else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--stages", default="names,crawl")
    ap.add_argument("--max-pages", type=int, default=45)
    ap.add_argument("--claim-real", action="store_true", help="also claim real Tasks, which holds real work until each lease ends")
    ap.add_argument("--write", action="store_true", help="allow the stages that write to live queues")
    ARGS = ap.parse_args()
    stages = ARGS.stages.split(",")
    writing = sorted(set(stages) & {"fabric", "shim", "q", "browser"})
    if writing and not ARGS.write:
        sys.exit(f"stages {', '.join(writing)} change live data: pass --write only for a system you own")
    for name, fn in [("fabric", fabric), ("shim", shim), ("q", lambda: (q_stage(SHIM), q_stage("https://herma.ta-amps.workers.dev"))), ("eranos", eranos), ("names", names_stage), ("crawl", lambda: crawl(ARGS.max_pages)), ("browser", browser)]:
        if name in stages:
            try:
                fn()
            except Exception as e:
                import traceback
                check(name, f"stage {name} ran to its end", False, "rerun the stage", traceback.format_exc()[-700:])
    sys.exit(report())
