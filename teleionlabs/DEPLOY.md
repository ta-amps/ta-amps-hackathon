# Deploying teleionlabs.com

The lead runs this after review. The author ran only the read-only checks and `wrangler deploy --dry-run`.

**The domains today** (read-only API check, 2026-11-02 about 02:10 UTC):
- `teleionlabs.com` is bound to `agora` and shows the Agora title;
- `www.teleionlabs.com` is bound to `www-canonical-redirect`, which answers 301 to the apex with path and query kept.

This Worker, `teleionlabs` (`wrangler.jsonc`), takes **the apex only**; `www` stays where it already works. It serves the
static pages from `dist/`, security headers with a CSP of `'self'` only, GET and HEAD only, and `GET /api/status` (cached
60 s). Its alias is `teleionlabs.ta-amps.workers.dev`, which serves the same pages with `X-Robots-Tag: noindex`.

Run every block in one shell, in order. Steps 3 and 4 run back to back: between the detach and the deploy the apex has
no Worker.

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
$W whoami >/dev/null 2>&1      # refreshes the OAuth token if it has expired
CF_TOKEN="$(python3 -c 'import os,tomllib;print(tomllib.load(open(os.path.expanduser("~/.config/.wrangler/config/default.toml"),"rb"))["oauth_token"])')"
ACCOUNT_ID="$(jq -r .account_id ~/meta_hacakthon/notes/work-2026-11-01/cloudflare-startup-and-email-kit/live_domains_and_email_receipt.json)"
CF="https://api.cloudflare.com/client/v4/accounts/$ACCOUNT_ID/workers/domains"
# The token goes to curl on stdin, never in argv, a file or the screen.
api() { printf 'Authorization: Bearer %s\n' "$CF_TOKEN" | curl -sS -H @- "$@"; }
```

The token's scopes include `workers:write`, `workers_scripts:write` and `zone:read`, which the domain calls need.

## 1. Locks, the reviewed commit, and the gates (rule 15)

```bash
# Locks: this Worker, and agora, whose domain moves (another session may deploy agora meanwhile).
AGORA_LIVE="$(python3 "$LOCK" live agora)"; echo "agora live commit: ${AGORA_LIVE:-none logged}"
$W deployments list --name agora > "$REC/agora-deployments.txt"  # read-only: agora's current version
head -20 "$REC/agora-deployments.txt"
python3 "$LOCK" acquire teleionlabs "$WHO" "$REVIEWED" --minutes 45 --note "first deploy; takes teleionlabs.com from agora"
python3 "$LOCK" acquire agora "$WHO" "${AGORA_LIVE:-unknown}" --minutes 45 --note "teleionlabs.com moves to teleionlabs; no agora deploy"

# Deploy only the reviewed commit, from a clean tree (dist/ and worker/banned.generated.js are rebuilt by the build).
test -z "$(git status --porcelain -- .)"
test "$(git rev-parse --short=7 HEAD)" = "$REVIEWED"

# Gates. wrangler's build step runs `python3 build.py && python3 tests/check_words.py` on every deploy (wrangler.jsonc);
# the build reads the shared banned-words list (rule 16) from outside this repo and fails without it.
make check                                                        # build, Worker tests, word gate, link check
$W dev --local --port 8799 --ip 127.0.0.1 --show-interactive-dev-session=false >"$REC/dev.log" 2>&1 &
DEV=$!; until curl -s -o /dev/null http://127.0.0.1:8799/; do sleep 1; done
node tests/check_site.mjs --base http://127.0.0.1:8799            # light (both schemes), layout, axe
kill "$DEV"
```

Any failure stops the shell (`set -e`): release both locks (see "Release" below, with version `none`) and stop.

## 2. Record the current bindings (read-only)

```bash
api "$CF" > "$REC/domains-before.json"
jq -r '.result[] | select(.hostname | endswith("teleionlabs.com")) | [.id, .hostname, .service] | @tsv' "$REC/domains-before.json"
# Expect exactly this picture, or stop:
test "$(jq -r '.result[] | select(.hostname == "teleionlabs.com") | .service' "$REC/domains-before.json")" = "agora"
test "$(jq -r '.result[] | select(.hostname == "www.teleionlabs.com") | .service' "$REC/domains-before.json")" = "www-canonical-redirect"
```

## 3. Detach the apex (its service read from the record)

```bash
APEX_ID="$(jq -r '.result[] | select(.hostname == "teleionlabs.com") | .id' "$REC/domains-before.json")"
api -X DELETE "$CF/$APEX_ID" | jq -c '{hostname: "teleionlabs.com", success, errors}'
```

## 4. Deploy, which attaches the apex (straight after step 3)

```bash
$W deploy --tag "$REVIEWED" --message "source $REVIEWED" | tee "$REC/deploy.log"
VERSION_ID="$(grep -oE 'Current Version ID: [0-9a-f-]+' "$REC/deploy.log" | awk '{print $4}' || true)"; echo "version: ${VERSION_ID:-see deploy.log}"
```

If wrangler reports that the domain is still bound to another Worker, answer no and run the rollback.

## 5. Verify

```bash
curl -s https://teleionlabs.com/ | grep -o '<title>[^<]*</title>'
#   <title>Tessera · infrastructure for agent work · Teleion Labs</title>
curl -s -o /dev/null -w '%{http_code} %{redirect_url}\n' 'https://www.teleionlabs.com/free/?a=1'
#   301 https://teleionlabs.com/free/?a=1   (www is untouched and still redirects)
curl -sI https://teleionlabs.com/ | grep -iE '^(content-security-policy|strict-transport-security|x-content-type-options)'
curl -s https://teleionlabs.com/.well-known/security.txt | head -3
curl -s https://teleionlabs.com/api/status        # three services, each "state":"up"
api "$CF" | jq -r '.result[] | select(.hostname | endswith("teleionlabs.com")) | [.hostname, .service] | @tsv'
#   teleionlabs.com -> teleionlabs; www.teleionlabs.com -> www-canonical-redirect; the rest unchanged
node tests/check_site.mjs --base https://teleionlabs.com
```

If `/api/status` shows a service as `down` while its own health address answers, the service binding and the public
fetch both failed; check `wrangler tail teleionlabs`.

## 6. The watchdog entry and one guard run (rule 16)

`light-guard/routes.json` already has a `teleionlabs` entry (it now says `agora`, the Worker that served the apex). Point
it at the new Worker and its pages, then run the guard once for this site only (`watchdog.py` has no per-site option and
would alert on every site):

```bash
python3 - "$GUARD/routes.json" teleionlabs <<'PY'
import json, sys
path, worker = sys.argv[1], sys.argv[2]
data = json.load(open(path))
entry = next(s for s in data["sites"] if s["site"] == "teleionlabs")
entry["worker"] = worker
entry["routes"] = ["/", "/tessera/", "/free/", "/docs/", "/status/", "/security/", "/company/"]
with open(path, "w") as f:
    json.dump(data, f, indent=2)
    f.write("\n")
PY
python3 "$GUARD/light_guard.py" --site teleionlabs --no-versions --out "$REC/light-guard.json"
```

## 7. Release and record

```bash
python3 "$LOCK" release teleionlabs "$WHO" "${VERSION_ID:-unknown}" "$REVIEWED" --note "first deploy; apex moved from agora; guard: see $REC/light-guard.json"
python3 "$LOCK" release agora "$WHO" "unchanged" "${AGORA_LIVE:-unknown}" --note "teleionlabs.com detached; no agora deploy"
```

Then one line in `notes/COORDINATION-2026-10-31.md`: the version, the commit, the hosts and the guard result.

## Rollback: put the apex back from the record

From a fresh shell, re-run step 0 first (`REC` holds `domains-before.json`).

```bash
for h in teleionlabs.com; do
  svc=$(jq -r --arg h "$h" '.result[] | select(.hostname == $h) | .service' "$REC/domains-before.json")
  zone=$(jq -r --arg h "$h" '.result[] | select(.hostname == $h) | .zone_id' "$REC/domains-before.json")
  id=$(api "$CF" | jq -r --arg h "$h" '.result[] | select(.hostname == $h) | .id')
  [ -n "$id" ] && api -X DELETE "$CF/$id" | jq -c '{success, errors}'
  api -X PUT "$CF" -H 'Content-Type: application/json' \
    -d "$(jq -nc --arg h "$h" --arg s "$svc" --arg z "$zone" '{environment: "production", hostname: $h, service: $s, zone_id: $z}')" \
    | jq -c --arg h "$h" '{hostname: $h, success, errors}'
done
curl -s https://teleionlabs.com/ | grep -o '<title>[^<]*</title>'      # the Agora title again
```

Then put the watchdog entry back with the step 6 snippet, passing `agora` instead of `teleionlabs`, release both locks
(version `rolled-back`) and log the rollback in COORDINATION. `www` was never moved, so it needs nothing.

`wrangler.jsonc` still declares the apex, so the next `wrangler deploy` of `teleionlabs` takes it back.
