# Deploying teleionlabs.com

The lead runs this after review. Nothing here was run by the author except the read-only checks and
`wrangler deploy --dry-run`. Today (2026-11-02 UTC) `teleionlabs.com` and `www.teleionlabs.com` are bound to the
`agora` Worker, and `www.teleionlabs.com` answers HTTP 530.

The Worker is `teleionlabs` (`wrangler.jsonc`): static pages from `dist/`, `www` → apex (301 for GET/HEAD, 308
otherwise), security headers with a CSP of `'self'` only, and `GET /api/status` (cached 60 s) for the live strip. Its
alias is `teleionlabs.ta-amps.workers.dev`, which serves the same pages with `X-Robots-Tag: noindex`.

## 0. Set up (prints no secret)

```bash
cd ~/meta_hacakthon/notes/claude-work-2026-11-01/teleionlabs-site/teleionlabs
W=~/meta_hacakthon/notes/portal-worker/node_modules/.bin/wrangler     # wrangler 4.154.0
REC=~/meta_hacakthon/notes/claude-work-2026-11-01/teleionlabs-deploy && mkdir -p "$REC"
$W whoami >/dev/null 2>&1      # refreshes the OAuth token if it has expired
CF_TOKEN="$(python3 -c 'import os,tomllib;print(tomllib.load(open(os.path.expanduser("~/.config/.wrangler/config/default.toml"),"rb"))["oauth_token"])')"
ACCOUNT_ID="$(jq -r .account_id ~/meta_hacakthon/notes/work-2026-11-01/cloudflare-startup-and-email-kit/live_domains_and_email_receipt.json)"
CF="https://api.cloudflare.com/client/v4/accounts/$ACCOUNT_ID/workers/domains"
# The token goes to curl on stdin, never in argv, a file or the screen.
api() { printf 'Authorization: Bearer %s\n' "$CF_TOKEN" | curl -sS -H @- "$@"; }
```

The token's scopes include `workers:write`, `workers_scripts:write` and `zone:read`, which the domain calls need.

## 1. Build and check

The build reads the shared banned-words list (rule 16) from
`~/meta_hacakthon/notes/coordination-2026-10-31/rules/banned-words.json`, outside this repo, and writes
`worker/banned.generated.js`, which is gitignored and bundled into the Worker. Without the list the build fails.

```bash
make check                                   # build, Worker unit tests, word gate, link check
$W dev --local --port 8799 --ip 127.0.0.1 --show-interactive-dev-session=false &
node tests/check_site.mjs --base http://127.0.0.1:8799    # light (both schemes), layout, axe
kill %1
```

## 2. Record the current bindings (read-only)

```bash
api "$CF" > "$REC/domains-before.json"
jq -r '.result[] | select(.hostname | endswith("teleionlabs.com")) | [.id, .hostname, .service] | @tsv' "$REC/domains-before.json"
# Expect teleionlabs.com and www.teleionlabs.com -> agora. Stop if either is bound elsewhere.
ZONE_ID="$(jq -r '.result[] | select(.hostname == "teleionlabs.com") | .zone_id' "$REC/domains-before.json")"
```

## 3. Detach both from agora

```bash
for h in teleionlabs.com www.teleionlabs.com; do
  id="$(jq -r --arg h "$h" '.result[] | select(.hostname == $h and .service == "agora") | .id' "$REC/domains-before.json")"
  [ -n "$id" ] && api -X DELETE "$CF/$id" | jq -c --arg h "$h" '{hostname: $h, success, errors}'
done
```

## 4. Deploy, which attaches both custom domains

```bash
make build
$W deploy --tag "$(git rev-parse --short HEAD)" --message "Teleion Labs site $(git rev-parse --short HEAD)" | tee "$REC/deploy.log"
```

If wrangler asks to take over a domain that is still bound to another Worker, answer no and go back to step 3.

## 5. Verify

```bash
for u in https://teleionlabs.com/ https://www.teleionlabs.com/ https://teleionlabs.ta-amps.workers.dev/; do
  printf '%s ' "$u"; curl -s -o /dev/null -w '%{http_code} %{redirect_url}\n' "$u"
done
curl -s https://teleionlabs.com/ | grep -o '<title>[^<]*</title>'
# <title>Tessera · infrastructure for agent work · Teleion Labs</title>
curl -s -o /dev/null -w '%{http_code} %{redirect_url}\n' 'https://www.teleionlabs.com/free/?a=1'
# 301 https://teleionlabs.com/free/?a=1
curl -sI https://teleionlabs.com/ | grep -iE '^(content-security-policy|strict-transport-security|x-content-type-options)'
curl -s https://teleionlabs.com/api/status       # three services, each "state":"up"
api "$CF" | jq -r '.result[] | select(.hostname | endswith("teleionlabs.com")) | [.hostname, .service] | @tsv'
node tests/check_site.mjs --base https://teleionlabs.com
```

Then run the live watchdog once for teleionlabs.com. Add this entry to the `sites` list in
`~/meta_hacakthon/notes/claude-work-2026-11-01/light-guard/routes.json`:

```json
{"site": "teleionlabs", "worker": "teleionlabs", "base_url": "https://teleionlabs.com",
 "routes": ["/", "/tessera/", "/free/", "/plans/", "/docs/", "/status/", "/security/", "/company/"]}
```

```bash
cd ~/meta_hacakthon/notes/claude-work-2026-11-01/light-guard
python3 light_guard.py --site teleionlabs --no-versions --out "$REC/light-guard.json"   # observes only
python3 watchdog.py                                                                    # one watchdog cycle
```

The entry above covers `https://teleionlabs.com/` and its pages `/tessera/`, `/free/`, `/plans/`, `/docs/`, `/status/`,
`/security/` and `/company/`, so the watchdog keeps checking them.
`curl -s https://teleionlabs.com/.well-known/security.txt` should show the two Contact lines and an Expires date.

If `/api/status` shows a service as `down` while its own health address answers, the service binding and the
public fetch both failed; check `wrangler tail teleionlabs`.

## Rollback: reattach to agora

```bash
for h in teleionlabs.com www.teleionlabs.com; do
  id="$(api "$CF" | jq -r --arg h "$h" '.result[] | select(.hostname == $h) | .id')"
  [ -n "$id" ] && api -X DELETE "$CF/$id" | jq -c '{success, errors}'
  api -X PUT "$CF" -H 'Content-Type: application/json' \
    -d "{\"environment\":\"production\",\"hostname\":\"$h\",\"service\":\"agora\",\"zone_id\":\"$ZONE_ID\"}" \
    | jq -c --arg h "$h" '{hostname: $h, success, errors}'
done
curl -s https://teleionlabs.com/ | grep -o '<title>[^<]*</title>'      # the Agora title again
```

`wrangler.jsonc` still declares both domains, so the next `wrangler deploy` of `teleionlabs` takes them back.
