#!/usr/bin/env bash
# Rebuild the gallery from its sources and the inbox, stop on any failed check, deploy under the lock, verify and log.
set -euo pipefail
export NODE_OPTIONS=--network-family-autoselection-attempt-timeout=3000
cd "$(dirname "$0")/.."; N=${TELEION_NOTES:?set TELEION_NOTES to the local working notes}; L=$N/coordination-2026-10-31/deploy-locks/deploy_lock.py; W=$N/portal-worker/node_modules/.bin/wrangler; T=$(mktemp -d)
F=$(python3 -c 'import json;print(json.load(open("content/site.json"))["main_film"])'); [ "$(stat -c %s "static/media/$F.mp4")" -gt 1048576 ] || { echo "the real film is missing: copy it into static/media (see MEDIA.md)"; exit 1; }
python3 build.py >/dev/null; python3 tools/make_gallery.py | tail -3 | cut -c1-140; python3 build.py >/dev/null
python3 tests/check_words.py >"$T/w" 2>&1 || { tail -4 "$T/w" | cut -c1-220; echo STOP words; exit 1; }
make test >"$T/t" 2>&1 || { grep -E '^not ok' "$T/t" | cut -c1-110; echo STOP tests; exit 1; }
python3 tests/check_links.py >"$T/l" 2>&1 || { tail -4 "$T/l" | cut -c1-200; echo STOP links; exit 1; }
git add -A content static/assets tools tests worker static/video-gallery static/video-gallery.txt; git diff --cached --quiet || git commit -qm "teleionlabs: gallery update [skip ci]"; R=$(git rev-parse --short=7 HEAD)
LIVE=$(python3 "$L" live teleionlabs); git merge-base --is-ancestor "$LIVE" "$R" || { echo "STOP live $LIVE is not in this build; merge it first"; exit 1; }
python3 "$L" acquire teleionlabs claude "$R" --minutes 15 --note "gallery" >/dev/null
if ! timeout 3000 "$W" deploy --tag "$R" --message "source $R" >"$T/d" 2>&1; then tail -5 "$T/d" | cut -c1-200; echo STOP deploy, lock still held; exit 1; fi
V=$(grep -oE 'Current Version ID: [0-9a-f-]+' "$T/d" | awk '{print $4}'); [ -n "$V" ] || { echo STOP no version, lock still held; exit 1; }
python3 "$L" release teleionlabs claude "$V" "$R" --note "gallery" >/dev/null; sleep 6
# A cold read of a large film can hang for 47 s and fail at one Cloudflare location; requests from here land on more than one, so warm it several times. It only warms the locations reached from here.
FILM=$(python3 -c "import json;print(json.load(open('content/site.json'))['main_film'])"); for i in 1 2 3 4 5 6 7 8; do curl -s -o /dev/null -m 60 -w "warm %{http_code} %{time_starttransfer}s %header{cf-ray}\n" "https://teleionlabs.com/media/$FILM.mp4" | cut -c1-70 || true; done
curl -sf -o /dev/null https://teleionlabs.com/video-gallery/items.json; N_ITEMS=$(curl -s https://teleionlabs.com/video-gallery/items.json | python3 -c "import json,sys;print(len(json.load(sys.stdin)['items']))")
(cd "$N/claude-work-2026-11-01/light-guard"; rc=0; timeout 500 python3 light_guard.py --site teleionlabs --quiet >/dev/null 2>&1 || rc=$?; echo "watchdog exit $rc")
printf -- '- %s Claude: teleionlabs %s (source %s): gallery update, %s items.\n' "$(date -u +%FT%TZ)" "$V" "$R" "$N_ITEMS" >>"$N/COORDINATION-2026-10-31.md"; echo "LIVE $V $R items=$N_ITEMS"
