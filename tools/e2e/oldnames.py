#!/usr/bin/env python3
"""Fresh count of the old names on public routes. Prints route, count and short context; exit 1 if any name shows.
    oldnames.py [--context N] [--write]
Without --write it reads only: the POST probes that could register a worker or reach a queue are skipped.
"""
import re, sys, json, requests
F, S, T, E, A = "https://fabric.teleionlabs.com", "https://shim.teleionlabs.com", "https://teleionlabs.com", "https://eranosforgood.org", "https://agora.eranosforgood.org"
ROUTES = {
 F: ["/", "/connect", "/connect.json", "/llms.txt", "/llms-full.txt", "/board", "/work", "/v1/health", "/healthz", "/openapi.json", "/v1/openapi.json", "/.well-known/agent-card.json", "/.well-known/agent.json", "/robots.txt", "/v1/library", "/v1/library/catalog", "/v1/feeds", "/v1/verbs", "/v1/me", "/v1/search?q=practice", "/v1/public/activity"],
 S: ["/", "/shim", "/llms.txt", "/llms-full.txt", "/connect.json", "/connect", "/healthz", "/get-started", "/prompts", "/dashboard", "/dashboard?format=json", "/kits", "/starter", "/trust", "/q/pulse", "/q/help", "/q/schema", "/q/search?q=nonprofit&format=json", "/q/network", "/q/tasks?limit=5", "/q/objects?limit=5", "/q/workers?limit=5", "/q/seeds", "/q/runtimes", "/q/graph", "/q/demand", "/q/meta-telemetry", "/q/grid-robustness", "/q/embeddings-spec", "/q/lease-intelligence", "/q/affinity", "/q/experiments", "/.well-known/agent-card.json", "/prompts/raw/worker_loop", "/prompts/raw/scheduled_bounded_v6", "/prompts/raw/master_v3", "/help", "/status", "/chat"],
 T: ["/", "/index.txt", "/llms.txt", "/fabric/", "/fabric.txt", "/free/", "/docs/", "/status/", "/api/status", "/shimming/", "/omninode/", "/feeds/", "/fabric-intelligence/", "/benchmarks/", "/benchmarks/methodology/", "/video/", "/security/", "/privacy/", "/terms/", "/company/"],
 E: ["/", "/nonprofits", "/help", "/library", "/catalog", "/connect", "/connect.json", "/llms.txt", "/llms-full.txt", "/.well-known/agent-card.json", "/api/open-tasks", "/api/fabric", "/api/health", "/api/tracks", "/api/catalog"],
 A: ["/llms.txt", "/evidence/", "/models/", "/decks/", "/feeds/", "/decks/server-workers/"],
}
POST = [(S, "/api/preview", {"prompt": "How do I add a nonprofit flyer task to the shared queue?"}), (S, "/q/claim", {"agent_id": "e2e-names-probe", "family": "nothing-matches-names"}), (F, "/v1/tasks", {}), (S, "/mcp", {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}), (F, "/mcp", {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}), (E, "/mcp", {"jsonrpc": "2.0", "id": 1, "method": "tools/list"})]
if "--write" not in sys.argv:
    POST = [row for row in POST if isinstance(row[2], dict) and row[2].get("method") == "tools/list"]
PAT = re.compile(r"tessera(?!ct)|herma", re.I)  # tesseract is the OCR tool, not the old name
# What stays on purpose: repository addresses, kit and asset file paths, and
# ids an agent sends back (Task, object and agent ids), which must not change or a later call would not find them.
KEPT = re.compile(r"\b(?:noun|verb|detail|n|v):(?:tessera|herma)\.[\w.]+|github\.com/ta-amps/[\w.-]+|/assets/herma-[\w.?=-]+|/kits/herma[\w.-]*|data-herma-[\w-]+|herma-(?:pages|agent-kit)[\w.-]*|herma_shim\.py|[\w.-]*[\w-](?:herma|tessera)[\w-]*|(?:herma|tessera)[\w-]*-[\w-]*|(?:herma|tessera)_[a-z0-9_]*\w", re.I)
N = int(sys.argv[sys.argv.index("--context") + 1]) if "--context" in sys.argv else 45
total = 0
kept_total = 0


def show(label, r):
    global total
    text = r.text + " " + " ".join(f"{k}: {v}" for k, v in r.headers.items() if k.lower().startswith(("x-", "access-control", "link", "www-auth", "server")))
    global kept_total
    kept_total += sum(len(PAT.findall(m.group(0))) for m in KEPT.finditer(text))
    text = KEPT.sub(" ", text)
    hits = [m for m in PAT.finditer(text)]
    total += len(hits)
    if hits:
        print(f"{len(hits):5} {label} [{r.status_code}]")
        seen = {}
        for m in hits:
            c = text[max(0, m.start() - N):m.end() + N].replace("\n", " ")
            key = re.sub(r"\W+", "", c)[:50]
            if key not in seen and len(seen) < 6:
                seen[key] = 1
                print("        ", repr(c))


for base, paths in ROUTES.items():
    for p in paths:
        try:
            show(base.split("//")[1] + p, requests.get(base + p, timeout=40, allow_redirects=False, headers={"x-namespace": "main"} if "fabric" in base else {}))
        except requests.RequestException as e:
            print("ERR", base + p, str(e)[:80])
for base, p, body in POST:
    show("POST " + base.split("//")[1] + p, requests.post(base + p, json=body, timeout=40, headers={"accept": "application/json, text/event-stream"}))
print("TOTAL", total, "kept on purpose", kept_total)
sys.exit(1 if total else 0)
