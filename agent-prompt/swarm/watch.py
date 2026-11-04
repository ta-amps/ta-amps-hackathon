#!/usr/bin/env python3
"""Prints a line only when something needs eyes: 429, Cloudflare limit errors, 5xx bursts, a shared Meta day near the stop, the pulse kill switch. Also writes logs/pulse.jsonl and page samples."""
import glob, json, os, pathlib, re, time, urllib.request
D = pathlib.Path(__file__).resolve().parent; seen = {}; said = set()
PAT = re.compile(r'\b(429|1027)\b.{0,80}|Too Many Requests|exceeded.{0,30}limit|Worker exceeded', re.I)
PAGES = ['https://eranosforgood.org/', 'https://teleionlabs.com/', 'https://shim.teleionlabs.com/q/pulse']
while not (D/'WATCHSTOP').exists():
    for f in glob.glob(str(D/'transcripts/*.jsonl')):
        if '/smoke' in f: continue
        n = os.path.getsize(f)
        if n == seen.get(f): continue
        with open(f, errors='replace') as h:
            h.seek(seen.get(f, 0)); new = h.read(); seen[f] = n
        for l in new.splitlines():
            try: d = json.loads(l)
            except Exception: continue
            st = d.get('part', {}).get('state', {})
            if d.get('type') == 'tool_use':
                e = str(st.get('error') or '')
                o = str(st.get('output') or '')[:300]
                if st.get('status') == 'error' and re.search(r'\b(429|5\d\d|1027)\b', e) or re.search(r'error code: 1\d{3}|HTTP/\S+ (429|5\d\d)|^\s*(error code|Too Many)', o):
                    print('ALARM', os.path.basename(f), (e or o)[:140].replace('\n', ' '), flush=True)
    rec = {'ts': time.time()}
    for u in PAGES:
        t0 = time.time()
        try:
            r = urllib.request.urlopen(urllib.request.Request(u, headers={'user-agent': 'swarm-watch'}), timeout=30); b = r.read(); rec[u] = [r.status, round(time.time()-t0, 3)]
            if 'pulse' in u: q = json.loads(b); rec['q'] = q.get('queue_counts_by_tier'); rec['kill'] = q.get('kill_switch_active')
        except urllib.error.HTTPError as e:
            rec[u] = [e.code, round(time.time()-t0, 3)]
            if e.code in (429,) or (e.code >= 500): print('PAGE', u, e.code, flush=True)
        except Exception as e:
            rec[u] = [0, type(e).__name__]; print('PAGE', u, type(e).__name__, flush=True)
    with open(D/'logs/pulse.jsonl', 'a') as f: f.write(json.dumps(rec)+'\n')
    if rec.get('kill'): print('KILL SWITCH ON', flush=True)
    try:
        day = json.loads((pathlib.Path.home()/'.local/state/eranos-worker/meta-spend.json').read_text())['days'][time.strftime('%Y-%m-%d', time.gmtime())]
        for lim in (15, 18, 20):
            if day >= lim and lim not in said: said.add(lim); print('SPEND day', day, flush=True)
    except Exception: pass
    time.sleep(45)
