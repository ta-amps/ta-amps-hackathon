#!/usr/bin/env python3
"""Awareness scorer. Normalizes formats before comparing, so a right answer in a different form is still right."""
import json, re, subprocess, time
LIC = [(r"\bagpl|affero", "AGPL-3.0"), (r"\blgpl|lesser general", "LGPL-3.0"), (r"(?<![al])\bgpl\b|(?<!affero )(?<!lesser )\bgeneral public", "GPL-3.0"), (r"apache", "Apache-2.0"), (r"\bmit\b|\bexpat\b", "MIT"),
       (r"bsd.{0,12}3|3.{0,8}clause|new bsd|modified bsd", "BSD-3-Clause"), (r"bsd.{0,12}2|2.{0,8}clause|simplified bsd", "BSD-2-Clause"), (r"mozilla|\bmpl\b", "MPL-2.0"), (r"unlicense", "Unlicense"), (r"\bcc0", "CC0-1.0"), (r"\bisc\b", "ISC")]
LANGS = {"python": r"\bpython\d?\b|\bpy\b", "typescript": r"\btypescript\b|\btype script\b|\bts\b", "javascript": r"\bjavascript\b|\bjs\b|\bnode(\.?js)?\b", "rust": r"\brust\b", "java": r"\bjava\b", "swift": r"\bswift\b", "ruby": r"\bruby\b", "php": r"\bphp\b", "kotlin": r"\bkotlin\b", "c++": r"c\+\+|\bcpp\b|c plus plus", "c#": r"c#|\bcsharp\b|c sharp", "shell": r"\bshell\b|\bbash\b", "html": r"\bhtml\b", "dart": r"\bdart\b", "jupyter notebook": r"\bjupyter\b", "go": r"\bgolang\b"}
UNKNOWN = re.compile(r"\b(unknown|i don'?t know|i do not know|not sure|cannot (determine|verify|find)|can'?t (determine|verify|find)|no (information|data|record)|unable to|n/?a|not found|not available|does not exist|doesn'?t exist|no such|cannot confirm|could not (find|verify)|couldn'?t (find|verify)|don'?t have (any )?(information|data))\b", re.I)
def answer_text(final):
    if isinstance(final, dict): final = final.get("answer", final.get("value", json.dumps(final)))
    return "" if final is None else str(final).strip()
def is_unknown(t): return not t or t.lower() in ("none", "null") or bool(UNKNOWN.search(t))
def licences_named(t):
    t = t.lower(); return {s for pat, s in LIC if re.search(pat, t)}
def norm_license(t):
    s = licences_named(t); return next(iter(s)) if len(s) == 1 else None
def languages_named(t, truth=None):
    low = t.lower(); s = {n for n, pat in LANGS.items() if re.search(pat, low)}
    words = t.strip().strip(".`*\"' ").split()
    if len(words) <= 3 and any(w.strip(".,").lower() == "go" for w in words) or re.search(r"\bGo\b", t): s.add("go")
    if len(words) <= 3 and any(w.strip(".,").lower() == "c" for w in words) or re.search(r"\bC\b(?![+#])", t): s.add("c")
    if truth and re.search(r"(?<!\w)" + re.escape(truth.lower()) + r"(?!\w)", low): s.add(truth.lower())
    return s
def norm_owner(t):
    t = t.strip().strip("`*\"' .").lower()
    m = re.search(r"github\.com/([a-z0-9_.-]+)", t)
    if m: return m.group(1)
    t = t.lstrip("@")
    m = re.search(r"(?<![\w/.-])([a-z0-9_-][a-z0-9_.-]*)/[a-z0-9_.-]+", t)
    if m: return m.group(1)
    m = re.search(r"(?:owned by|owner(?: name)?(?: of .*?)?(?: is|:)|organization(?: is|:)|account(?: is|:)|\bis)\s+(?:the\s+)?@?`?([a-z0-9_.-]+?)`?(?:[\s,.(]|$)", t)
    if m: return m.group(1)
    m = re.match(r"^@?`?([a-z0-9_.-]+)`?\s*(?:[,(:]|\s-\s)", t)
    if m: return m.group(1)
    return t
def norm_repo(t):
    t = t.strip().strip("`*\"' .")
    m = re.search(r"github\.com/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)", t) or re.search(r"\b([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)\b", t)
    return m.group(1).removesuffix(".git") if m else None
TOPIC = {"memory-systems": r"\bmemor|\bremember|\brecall", "pii-redaction": r"\bpii\b|redact|anonymi|personal data|privacy|sensitive|de-?identif", "ocr-llm": r"\bocr\b|document|\bpdf\b|handwrit|text recognition|\bpars(e|er|ing)\b",
         "agent-harnesses": r"\bharness|\bcoding agent|\bagents?\b|\bcli\b", "eval-frameworks": r"\bevals?\b|\bevaluat|\bbenchmark|\btesting\b|red.team"}
_cache = {}
def gh_repo(name):
    if name in _cache: return _cache[name]
    for attempt in range(5):
        p = subprocess.run(["gh", "api", f"repos/{name}", "--jq", "{full_name,created_at,language,license:.license.spdx_id,description,topics}"], capture_output=True, text=True)
        if p.returncode == 0: _cache[name] = json.loads(p.stdout); return _cache[name]
        if "404" in p.stderr: _cache[name] = None; return None
        time.sleep(20)
    raise RuntimeError("GitHub unavailable while scoring " + name)
def score(q, final):
    """Returns (outcome, detail); outcome is correct, wrong or unknown."""
    t = answer_text(final)
    if q["group"] == "invented":
        if final is None: return "unknown", "agent returned nothing"
        if licences_named(t): return "wrong", "named a licence for an invented repository: " + t[:60]
        return "correct", "named no licence"
    if q["kind"] == "discovery":
        name = norm_repo(t)
        if not name: return ("unknown", "no owner/name") if is_unknown(t) else ("wrong", "no owner/name in answer")
        r = gh_repo(name)
        if not r: return "wrong", f"{name} does not exist"
        tr = q["truth"]; why = []
        if r["created_at"] < tr["created_since"]: why.append("created too early")
        if (r["language"] or "").lower() != tr["language"].lower(): why.append("language")
        if r["license"] != tr["license"]: why.append("licence")
        blob = " ".join([r["full_name"], r.get("description") or "", " ".join(r.get("topics") or [])]).lower()
        if not re.search(TOPIC[tr["category"]], blob): why.append("off topic")
        return ("wrong", name + ": " + ", ".join(why)) if why else ("correct", name)
    if q["kind"] == "license":
        s = licences_named(t)
        if len(s) == 1: return ("correct", t[:60]) if q["truth"] in s else ("wrong", t[:60])
        if len(s) > 1: return "wrong", "named several: " + t[:60]
        return ("unknown", t[:80]) if is_unknown(t) else ("wrong", t[:60])
    if q["kind"] == "language":
        s = languages_named(t, q["truth"])
        if len(s) == 1: return ("correct", t[:60]) if q["truth"].lower() in s else ("wrong", t[:60])
        if len(s) > 1: return "wrong", "named several: " + t[:60]
        return ("unknown", t[:80]) if is_unknown(t) else ("wrong", t[:60])
    if q["kind"] == "owner":
        o = norm_owner(t)
        if o == q["truth"].lower(): return "correct", t[:60]
        if is_unknown(t): return "unknown", t[:80]
        # another account with a repository of that name, created that month, also answers the question
        name = q["repo"].split("/")[1]
        if re.fullmatch(r"[a-z0-9_.-]+", o or ""):
            r = gh_repo(f"{o}/{name}")
            if r and r["created_at"][:7] == q["created_at"][:7]: return "correct", "other owner, same name and month: " + o
        return "wrong", t[:60]
    raise ValueError(q["kind"])
if __name__ == "__main__":
    # format fixtures: right answers in other forms must score right, and wrong ones wrong
    Ql = {"group": "primary", "kind": "license", "truth": "Apache-2.0"}; Qo = {"group": "primary", "kind": "owner", "truth": "gh9ko8y", "repo": "gh9ko8y/graphmemory", "created_at": "2026-10-30"}; Qg = {"group": "primary", "kind": "language", "truth": "TypeScript"}; Qm = {"group": "primary", "kind": "license", "truth": "MIT"}; Qi = {"group": "invented", "kind": "license", "truth": "__unknown__"}
    cases = [(Ql, "Apache 2.0", "correct"), (Ql, "Apache License, Version 2.0", "correct"), (Ql, "apache-2.0", "correct"), (Ql, "MIT", "wrong"), (Ql, "Unknown", "unknown"), (Qm, "MIT License", "correct"), (Qm, "The MIT license.", "correct"), (Qm, "Apache-2.0", "wrong"),
             (Qo, "gh9ko8y", "correct"), (Qo, "GH9KO8Y/graphmemory", "correct"), (Qo, "https://github.com/gh9ko8y/graphmemory", "correct"), (Qo, "@gh9ko8y", "correct"), (Qo, "The owner is gh9ko8y", "correct"), (Qo, "microsoft", "wrong"), (Qo, "I don't know", "unknown"),
             (Qg, "TypeScript", "correct"), (Qg, "ts", "correct"), (Qg, "typescript.", "correct"), (Qg, "The primary language is TypeScript", "correct"), (Qg, "Python", "wrong"), (Qi, "unknown", "correct"), (Qi, "I cannot determine that", "correct"), (Qi, "MIT", "wrong"), (Qg, {"answer": "TypeScript"}, "correct"),
             (Qi, None, "unknown"), (Qi, "MIT, though I cannot determine this", "wrong"), (Qi, "There is no such repository", "correct"),
             (dict(Qo, repo="x/y", created_at="2026-01-01"), "The owner of graphmemory is gh9ko8y", "correct"), (dict(Qo, repo="x/y", created_at="2026-01-01"), "gh9ko8y (a GitHub organization)", "correct"),
             (dict(Qo, truth="sno-ai", repo="sno-ai/x", created_at="2026-01-01"), "sno-ai", "correct"), (dict(Qo, truth="aoci-spec", repo="aoci-spec/x", created_at="2026-01-01"), "aoci-spec", "correct"), (dict(Qg, truth="Python"), "Python 3.11", "correct"), (dict(Qg, truth="Python"), "primarily Python", "correct"), (Qm, "MIT. Source unknown.", "correct"), (Ql, "Apache-2.0 or MIT", "wrong"), (Qm, "Apache-2.0 or MIT", "wrong"),
             (dict(Ql, truth="AGPL-3.0"), "GNU Affero General Public License v3", "correct"), (dict(Ql, truth="GPL-3.0"), "GPL-3.0", "correct"), (dict(Ql, truth="GPL-3.0"), "AGPL-3.0", "wrong"), (dict(Qg, truth="Go"), "Go", "correct"), (dict(Qg, truth="Java"), "JavaScript", "wrong")]
    bad = [(c[1], c[2], score(c[0], c[1])) for c in cases if score(c[0], c[1])[0] != c[2]]
    print("scorer fixtures:", len(cases) - len(bad), "of", len(cases), "pass"); print(bad)
    raise SystemExit(1 if bad else 0)
