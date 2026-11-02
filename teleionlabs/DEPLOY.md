# Deploying teleionlabs.com

The apex moved to this Worker on 2026-11-02 at 03:19 UTC (`a557998`); the first plain deploy was `51135c3` at 05:28 UTC
(version `df7420ac-f552-4c47-87e8-afb854f609e2`). Every deploy is a plain one:
lock, gates, deploy, verify, guard, release. The first move's record and the emergency domain rollback are at the end.

**The domains today:** `teleionlabs.com` is bound to `teleionlabs`; `www.teleionlabs.com` is bound to
`www-canonical-redirect`, which answers 301 to the apex with path and query kept. This Worker owns the apex only.

Run every block in one shell, in order. Any failure stops the shell (`set -e`). If that happens before step 3, nothing was
deployed: release with `python3 "$LOCK" release teleionlabs "$WHO" unchanged "$LIVE" --note "stopped before deploy"`, so
the log keeps the commit that is really live, and stop.

## 0. Set up (prints no secret)

```bash
set -euo pipefail
cd ~/meta_hacakthon/notes/claude-work-2026-11-01/teleionlabs-site/teleionlabs
REVIEWED=<the 7-character commit the reviewer approved>
WHO=claude
W=~/meta_hacakthon/notes/portal-worker/node_modules/.bin/wrangler       # wrangler 4.154.0
LOCK=~/meta_hacakthon/notes/coordination-2026-10-31/deploy-locks/deploy_lock.py
GUARD=~/meta_hacakthon/notes/claude-work-2026-11-01/light-guard
REC=~/meta_hacakthon/notes/claude-work-2026-11-01/teleionlabs-deploy && mkdir -p "$REC"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
$W whoami >/dev/null 2>&1      # refreshes the OAuth token if it has expired
CF_TOKEN="$(python3 -c 'import os,tomllib;print(tomllib.load(open(os.path.expanduser("~/.config/.wrangler/config/default.toml"),"rb"))["oauth_token"])')"
ACCOUNT_ID="$(jq -r .account_id ~/meta_hacakthon/notes/work-2026-11-01/cloudflare-startup-and-email-kit/live_domains_and_email_receipt.json)"
CF="https://api.cloudflare.com/client/v4/accounts/$ACCOUNT_ID/workers/domains"
# The token goes to curl on stdin, never in argv, a file or the screen.
api() { printf 'Authorization: Bearer %s\n' "$CF_TOKEN" | curl -sS -H @- "$@"; }
```

## 1. Lock, the reviewed commit, and the gates (rule 15)

```bash
python3 "$LOCK" acquire teleionlabs "$WHO" "$REVIEWED" --minutes 30 --note "plain deploy of $REVIEWED"
LIVE="$(python3 "$LOCK" live teleionlabs)"; echo "live commit: $LIVE"
git merge-base --is-ancestor "$LIVE" HEAD                          # build on what is live
$W deployments list --name teleionlabs > "$REC/deployments-$STAMP.txt"
head -20 "$REC/deployments-$STAMP.txt"                            # note the current version id for a rollback

test -z "$(git status --porcelain -- .)"                           # a clean tree ...
test "$(git rev-parse --short=7 HEAD)" = "$REVIEWED"               # ... at the reviewed commit

# wrangler's build step also runs `python3 build.py && python3 tests/check_words.py` (wrangler.jsonc), so neither a
# stale dist/ nor a stale generated word list can ship. The build reads the shared banned-words list (rule 16).
make check                                                         # build, Worker tests, word gate, link check
PORT="$(python3 -c 'import socket; s = socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1]); s.close()')"
$W dev --local --port "$PORT" --ip 127.0.0.1 --show-interactive-dev-session=false >"$REC/dev-$STAMP.log" 2>&1 &
DEV=$!
until curl -s -o /dev/null "http://127.0.0.1:$PORT/"; do kill -0 "$DEV" 2>/dev/null || { echo "dev server exited"; exit 1; }; sleep 1; done
node tests/check_site.mjs --base "http://127.0.0.1:$PORT"          # light (both schemes), layout, axe
kill "$DEV"
```

## 2. Record the bindings (read-only); keep the first move's record

```bash
# domains-before.json is the record of the first move (apex on agora); keep it under its own name.
[ -f "$REC/domains-before.json" ] && [ ! -f "$REC/domains-first-move.json" ] && cp "$REC/domains-before.json" "$REC/domains-first-move.json"
api "$CF" > "$REC/domains-$STAMP.json"
test "$(jq -r '.result[] | select(.hostname == "teleionlabs.com") | .service' "$REC/domains-$STAMP.json")" = "teleionlabs"
test "$(jq -r '.result[] | select(.hostname == "www.teleionlabs.com") | .service' "$REC/domains-$STAMP.json")" = "www-canonical-redirect"
```

## 3. Deploy

```bash
$W deploy --tag "$REVIEWED" --message "source $REVIEWED" | tee "$REC/deploy-$STAMP.log"
VERSION_ID="$(grep -oE 'Current Version ID: [0-9a-f-]+' "$REC/deploy-$STAMP.log" | awk '{print $4}' || true)"; echo "version: ${VERSION_ID:-see deploy log}"
```

## 4. Verify

```bash
curl -s https://teleionlabs.com/ | grep -o '<title>[^<]*</title>'
#   <title>Tessera · infrastructure for agent work · Teleion Labs</title>
curl -s -o /dev/null -w '%{http_code} %{redirect_url}\n' 'https://www.teleionlabs.com/free/?a=1'
#   301 https://teleionlabs.com/free/?a=1
curl -sI https://teleionlabs.com/ | grep -iE '^(content-security-policy|strict-transport-security|x-content-type-options|cache-control)'
#   cache-control includes no-transform (no injected beacon for the CSP to block)
curl -sI https://teleionlabs.com/api/status | grep -i '^cache-control'     #   no-store
curl -s https://teleionlabs.com/api/status                                 #   three services, each "state":"up"
curl -s https://teleionlabs.com/.well-known/security.txt | head -3
node tests/check_site.mjs --base https://teleionlabs.com                   #   includes "no console errors"
```

If `/api/status` shows a service as `down` while its own health address answers, the service binding and the public
fetch both failed; check `wrangler tail teleionlabs`.

## 5. Guard once for this site (rule 16)

First make sure the watchdog entry lists every page this deploy serves (it adds what's missing and changes nothing else):

```bash
python3 - "$GUARD/routes.json" <<'PY'
import json, sys
path = sys.argv[1]
data = json.load(open(path))
entry = next(s for s in data["sites"] if s["site"] == "teleionlabs")
for route in ["/", "/tessera/", "/free/", "/docs/", "/status/", "/security/", "/privacy/", "/terms/", "/company/"]:
    if route not in entry["routes"]:
        entry["routes"].append(route)
with open(path, "w") as f:
    json.dump(data, f, indent=2)
    f.write("\n")
PY
python3 "$GUARD/light_guard.py" --site teleionlabs --no-versions --out "$REC/light-guard-$STAMP.json"
```

`watchdog.py` has no per-site option and would alert on every site, so run the guard for this site only and post its
result.

## 6. Release and record

```bash
python3 "$LOCK" release teleionlabs "$WHO" "${VERSION_ID:-unknown}" "$REVIEWED" --note "plain deploy; guard: $REC/light-guard-$STAMP.json"
```

Then one line in `notes/COORDINATION-2026-10-31.md`: the version, the commit and the guard result.

## Rollback of a bad deploy

```bash
$W rollback <the previous version id from $REC/deployments-$STAMP.txt> --message "rollback to source $LIVE" -y
curl -s https://teleionlabs.com/ | grep -o '<title>[^<]*</title>'
python3 "$LOCK" release teleionlabs "$WHO" rolled-back "$LIVE" --note "rolled back from $REVIEWED"
```

Log the rollback in COORDINATION.

## Emergency only: put the apex back on agora

The first move's record is `$REC/domains-first-move.json` (the apex on `agora`). From a fresh shell, run step 0, take the
`teleionlabs` and `agora` locks, then:

```bash
FIRST="$REC/domains-first-move.json"
for h in teleionlabs.com; do
  svc=$(jq -r --arg h "$h" '.result[] | select(.hostname == $h) | .service' "$FIRST")
  zone=$(jq -r --arg h "$h" '.result[] | select(.hostname == $h) | .zone_id' "$FIRST")
  id=$(api "$CF" | jq -r --arg h "$h" '.result[] | select(.hostname == $h) | .id')
  [ -n "$id" ] && api -X DELETE "$CF/$id" | jq -c '{success, errors}'
  api -X PUT "$CF" -H 'Content-Type: application/json' \
    -d "$(jq -nc --arg h "$h" --arg s "$svc" --arg z "$zone" '{environment: "production", hostname: $h, service: $s, zone_id: $z}')" \
    | jq -c --arg h "$h" '{hostname: $h, success, errors}'
done
curl -s https://teleionlabs.com/ | grep -o '<title>[^<]*</title>'      # the Agora title again
```

Then set the `teleionlabs` entry in `light-guard/routes.json` back to `"worker": "agora"`, release both locks (version
`rolled-back`) and log it in COORDINATION. `www` never moved. `wrangler.jsonc` still declares the apex, so the next
`wrangler deploy` of `teleionlabs` takes it back.
