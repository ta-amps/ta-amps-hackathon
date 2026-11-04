#!/usr/bin/env python3
"""test_kit.py [--base URL]: the whole client flow, both languages, against a queue with labeled test Tasks.

--base is required: local `wrangler dev`, or live. Makes its own labeled Tasks through /q/enqueue when --seed is given (local only).
Live runs use --live-task-less: read-only checks plus one give-back of nothing. Fault cases use a small local faulty proxy, no model calls."""
import argparse, http.server, json, os, pathlib, subprocess, sys, tempfile, threading, time, urllib.request
HERE = pathlib.Path(__file__).resolve().parents[2] / "static" / "kit"
sys.path.insert(0, str(HERE))
import fabric_worker as fw
ap = argparse.ArgumentParser(); ap.add_argument("--base", required=True); ap.add_argument("--seed", action="store_true"); A = ap.parse_args()
BASE = A.base.rstrip("/"); run = str(int(time.time()))[-7:]; ok = bad = 0
def check(name, cond, extra=""):
    global ok, bad
    print(("ok  " if cond else "FAIL"), name, extra if not cond else "")
    ok += bool(cond); bad += not cond
def post(path, body):
    return json.load(urllib.request.urlopen(urllib.request.Request(BASE + path, json.dumps(body).encode(), {"content-type": "application/json", "user-agent": "kit-test"})))
def enqueue(title):
    out = post("/enqueue", {"agent_id": f"kit-test-maker-{run}", "title": title, "prompt": "A labeled kit test Task. Write one line.", "tier": "ngo_priority", "category": "ngo_public_good"})
    made = out.get("enqueued_followup_tasks") or out.get("enqueued_followup_verbs") or []
    return made[0]["task_id"] if made and isinstance(made[0], dict) else (made[0] if made else out.get("completed_task_id"))
tmp = tempfile.mkdtemp(prefix="kit-test")
state = lambda n: os.path.join(tmp, n + ".json")
nosleep = lambda s: None

if A.seed:
    # Flow in Python
    t1 = enqueue(f"Kit test Task python {run}")
    w = fw.Worker(f"kit-test-py-{run}", bases=[BASE], state_file=state("py"))
    got = w.claim(t1)
    check("py claim leases and saves the fence", got.get("lease") and w.state["fence"] == got["lease"]["fencing_token"])
    check("py claim says what is next", got["next"]["action"] == "do_the_work")
    check("py heartbeat", w.heartbeat().get("ok") is True)
    out = w.submit("kit test, one line", {"line": "labeled kit test"}, builds_on=[])
    check("py submit stored", out.get("verification_code") and out.get("completed_task_id") == t1)
    # Give back; then skip list hides it
    t2 = enqueue(f"Kit test Task give back {run}")
    w2 = fw.Worker(f"kit-test-py2-{run}", bases=[BASE], state_file=state("py2"))
    assert w2.claim(t2).get("lease")
    rel = w2.give_back("kit-test")
    check("py give back frees the Task", rel.get("released") is True and rel["next"]["action"] == "find_other")
    ids = [t["task_id"] for t in w2.next(limit=10).get("tasks", [])]
    check("py next leaves out what I gave back", t2 not in ids)
    # Lost fence: the server's fence moved. Claim again, then resend.
    t3 = enqueue(f"Kit test Task fence {run}")
    w3 = fw.Worker(f"kit-test-py3-{run}", bases=[BASE], state_file=state("py3"))
    w3.claim(t3); real = w3.state["fence"]; w3.state["fence"] = real + 9
    out = w3.submit("kit test, fence recovered", {"line": "fence"})
    check("py lost fence recovers by claiming again", out.get("completed_task_id") == t3)
    # Taken by someone else: LeaseLost, nothing stored
    t4 = enqueue(f"Kit test Task taken {run}")
    a = fw.Worker(f"kit-test-pya-{run}", bases=[BASE], state_file=state("a")); b = fw.Worker(f"kit-test-pyb-{run}", bases=[BASE], state_file=state("b"))
    a.claim(t4); a.state["task_id"] = t4; b.state.update(task_id=t4, fence=99, title="x")
    try:
        b.submit("not mine", {"line": "x"}); check("py someone else's Task refused", False)
    except fw.LeaseLost as e:
        check("py someone else's Task raises LeaseLost", True)
    except fw.FabricError as e:
        check("py someone else's Task refused", e.status in (403, 409), str(e))
    # No-lease reason
    t5 = enqueue(f"Run a live trial with a field team, kit test {run}")
    got = w.claim(t5)
    check("py no lease has a reason", not got.get("lease") and got["no_lease"]["reason"] == "needs_people", str(got.get("no_lease")))
    # run_once with give-back and with a result
    t6 = enqueue(f"Kit test Task run once {run}")
    w6 = fw.Worker(f"kit-test-py6-{run}", bases=[BASE], state_file=state("py6"))
    r = w6.run_once(lambda task: None, pick=lambda ts: next((x for x in ts if x["task_id"] == t6), None))
    check("py run_once gives back on None", r["status"] in ("gave_back", "idle"), str(r))
    w6.state["skip"] = []
    r = w6.run_once(lambda task: {"summary": "kit test run once", "payload": {"line": "ok"}}, pick=lambda ts: next((x for x in ts if x["task_id"] == t6), None))
    check("py run_once finishes one Task", r["status"] in ("done", "idle"), str(r))
    # JS flow through its CLI
    t7 = enqueue(f"Kit test Task js {run}")
    env = {**os.environ, "FABRIC_BASES": BASE, "FABRIC_WORKER_STATE": state("js")}
    def js(*args, input=None):
        return subprocess.run(["node", str(HERE/"fabric_worker.mjs"), "--id", f"kit-test-js-{run}", *args], env=env, capture_output=True, text=True, input=input, cwd=tmp)
    c = js("claim", t7); check("js claim", c.returncode == 0 and "LEASE" in c.stdout, c.stdout + c.stderr)
    check("js heartbeat", '"ok": true' in js("heartbeat").stdout)
    work = pathlib.Path(tmp, "work.json"); work.write_text('{"line":"labeled kit test js"}')
    s = js("submit", "--summary", "kit test js", "--file", str(work)); check("js submit stored", "verification_code" in s.stdout and t7 in s.stdout, s.stdout + s.stderr)
    t8 = enqueue(f"Kit test Task js give back {run}")
    js("claim", t8); g = js("give-back", "kit-test"); check("js give back", "GAVE BACK" in g.stdout, g.stdout + g.stderr)
    t9 = enqueue(f"Run a live trial with a field team, kit test js {run}")
    n = js("claim", t9); check("js no lease has a reason", n.returncode == 2 and "needs_people" in n.stdout, n.stdout)

# Local checks that need no queue
class FakeH(fw.Worker):
    def __init__(self, *a, **k):
        super().__init__(*a, **k); self.sent = []
    def call(self, method, path, body=None):
        self.sent.append((method, path, body))
        if method == "POST": raise fw.FabricError(409, {"code": "lease_expired", "next": {"action": "claim_again_then_resend"}})
        if path.startswith("/claim/"): return {"lease": None, "next": {"action": "find_other"}, "no_lease": {"reason": "held_now"}}
        if path.startswith("/object/"): return {"ok": True}
        if path.startswith("/release/"): raise fw.FabricError(409, {"code": "stale_fencing_token", "next": {"action": "find_other"}})
        return {}
h = FakeH(f"kit-test-h-{run}", state_file=state("h"))
for fn, name in ((h.heartbeat, "heartbeat"), (h.give_back, "give back"), (lambda: h.submit("s", {"a": 1}), "submit")):
    try:
        fn(); check(f"{name} with no Task is a plain stop", False)
    except ValueError:
        check(f"{name} with no Task is a plain stop", True)
h.state.update(task_id="t1", fence=1, title="A title")
try:
    h.claim("t2"); check("a second claim does not orphan the first", False)
except ValueError:
    check("a second claim does not orphan the first", True)
for blank in ("", {}, {"result": ""}):
    try:
        h.submit("s", blank); check("empty work never closes a Task", False)
    except ValueError:
        check("empty work never closes a Task", True)
out = h.submit("s", {"a": 1}); check("a lost reply: already stored is reported, not lost", out.get("already_stored") is True and not h.state.get("task_id"), str(out))
keys = [b["task_objects"][0]["object_key"] for m, p, b in h.sent if m == "POST"]
check("the object name stays the same on a resend", len(set(keys)) == 1)
h.state.update(task_id="t3", fence=1); r = h.give_back("x"); check("a give back after the lease ended clears the state", not h.state.get("task_id") and r["task_id"] == "t3")
blank = pathlib.Path(tmp, "blank.json"); blank.write_text("  \n")
try:
    fw.read_work(str(blank)); check("a blank file is refused", False)
except ValueError:
    check("a blank file is refused", True)

# Read-only, live or local
w = fw.Worker(f"kit-test-ro-{run}", bases=[BASE], state_file=state("ro"))
n = w.next(limit=2); check("next answers", "next" in n and isinstance(n.get("tasks"), list))
check("find answers", "found" in w.find("grant deadline"))
for_kinds = w.find("grant deadline", kinds="kit"); check("find kinds is respected", all(h["kind"] == "kit" for h in for_kinds.get("hits", []) + for_kinds.get("maybe", [])))
if n.get("tasks"):
    h = w.find_helpers({"task_id": n["tasks"][0]["task_id"]}); check("find_helpers answers", h.get("ok") is True)
    check("helpers carry a type and a reviewed label", all("type" in x and "reviewed" in x for x in h.get("hits", []) + h.get("maybe", [])))

# Faults, through a local faulty stand-in: busy twice, then the real reply. No queue calls. Sleep is recorded, not waited.
class Faulty(http.server.BaseHTTPRequestHandler):
    seen = []
    def log_message(self, *a): pass
    def do_GET(self):
        Faulty.seen.append(self.path); k = len(Faulty.seen)
        body = {"ok": True, "tasks": [], "next": {"action": "stop"}} if k >= 3 else {"code": "busy_try_again", "next": {"action": "retry_same_call"}}
        b = json.dumps(body).encode(); self.send_response(200 if k >= 3 else 503); self.send_header("retry-after", "7"); self.send_header("content-length", str(len(b))); self.end_headers(); self.wfile.write(b)
srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Faulty); threading.Thread(target=srv.serve_forever, daemon=True).start()
waits = []; f = fw.Worker(f"kit-test-fault-{run}", bases=[f"http://127.0.0.1:{srv.server_port}"], state_file=state("f"), sleep=waits.append)
check("busy answers are retried, then the reply comes back", f.next().get("ok") is True and len(Faulty.seen) == 3)
check("the wait honors Retry-After and adds a random part", waits[0] >= 7 and waits[0] < 12 and waits[1] >= 20 and waits[1] < 40, str(waits))
srv.shutdown()
dead = fw.Worker(f"kit-test-dead-{run}", bases=["http://127.0.0.1:9"], state_file=state("d"), sleep=nosleep)
try:
    dead.next(); check("no connection is an error", False)
except fw.FabricError as e:
    check("no connection is a plain error", e.code == "no_connection", str(e))
secretish = open(HERE/"fabric_worker.py").read() + open(HERE/"fabric_worker.mjs").read()
check("no key or token handling in the kit", "worker_token" not in secretish and "authorization" not in secretish.lower() and "api_key" not in secretish.lower())
print(f"\n{ok} passed, {bad} failed")
sys.exit(1 if bad else 0)
