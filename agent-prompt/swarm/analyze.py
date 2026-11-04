#!/usr/bin/env python3
"""analyze.py ROUND...: numbers for each round, from OpenCode transcripts, the curl log, the proxy log; --live re-reads objects and Tasks (few requests)."""
import collections, json, pathlib, re, sys, urllib.request, urllib.error
D = pathlib.Path(__file__).resolve().parent; A = [a for a in sys.argv[1:] if not a.startswith('--')]; LIVE = '--live' in sys.argv
BASE = 'https://shim.teleionlabs.com'
def pct(v, q):
    v = sorted(v); return v[min(len(v)-1, int(len(v)*q))] if v else None
ROWS = {}
for rnd in A:
    M = [json.loads(l) for l in (D/'logs/model.jsonl').open()]; M = [m for m in M if m.get('round') == rnd]
    R = [json.loads(l) for l in (D/'logs/runs.jsonl').open()] if (D/'logs/runs.jsonl').exists() else []; R = [r for r in R if r.get('round') == rnd and 'exit' in r]
    C = []
    for f in (D/'logs').glob(f'curl-{rnd}-*.log'):
        for l in f.read_text(errors='replace').splitlines():
            p = l.split(' ', 3)
            if len(p) == 4: C.append({'code': p[0], 't': float(p[1]), 'method': p[2], 'url': p[3], 'bot': f.stem})
    run = []; tools = collections.Counter(); toolerr = collections.Counter(); ends = []; webst = collections.Counter(); webroutes = collections.Counter()
    for f in sorted((D/'transcripts').glob(f'{rnd}-*.jsonl')):
        ev = []
        for l in f.read_text(errors='replace').splitlines():
            try: ev.append(json.loads(l))
            except Exception: pass
        res = {'file': f.name, 'tools': 0, 'claims': [], 'submits': [], 'release': 0, 'keys': [], 'tasks': [], 'code': None, 'idle': False}
        last = ''
        for e in ev:
            p = e.get('part', {})
            if e.get('type') == 'text': last = p.get('text', '')
            if e.get('type') == 'tool_use':
                st = p.get('state', {}); tool = p.get('tool'); tools[tool] += 1; res['tools'] += 1
                if st.get('status') == 'error': toolerr[tool] += 1
                inp = json.dumps(st.get('input', {})); out = str(st.get('output') or st.get('error') or '')
                if '/q/claim/' in inp:
                    m = re.search(r'task_id=([\w-]+)', inp); f2 = re.search(r'FENCING_TOKEN[:=\s]+(\d+)|"fencing_token":\s*(\d+)', out)
                    res['claims'].append({'task': m and m.group(1), 'fence': f2 and (f2.group(1) or f2.group(2))})
                if '/q/submit' in inp:
                    code = re.search(r'verification_code"?[:=\s]+"?([\w-]+)', out, re.I)
                    res['submits'].append({'ok': bool(code), 'head': out[:200]})
                    res['keys'] += re.findall(r'/c/([\w.:-]+)', out) + re.findall(r'"object_key"\s*:\s*"([\w.:-]+)', out)
                if '/q/release/' in inp: res['release'] += 1
                hs = re.findall(r'status(?: code)?[:\s]+(\d{3})|error code:? ?(1\d{3})', str(st.get('error') or '')[:400])
                for a, b in hs: webst[a or b] += 1
                if tool == 'webfetch':
                    m = re.search(r'/q/(\w+)', inp); webroutes[m.group(1) if m else 'other'] += 1
        fk = re.search(r'object.keys?\W+(.+)', last, re.I)
        if fk: res['keys'] = re.findall(r'[A-Za-z0-9][\w.:-]*_v\d+[\w.:-]*', fk.group(1))
        ft = re.search(r'task_id\W+(\S+)', last)
        res['task_final'] = ft.group(1) if ft else None
        res['idle'] = bool(re.search(r'\bidle\b', last, re.I)); res['final'] = last[:300]
        run.append(res)
    ctr = collections.Counter(c['code'] for c in C); routes = collections.Counter()
    for c in C:
        m = re.search(r'/q/(\w+)', c['url']); routes[(m.group(1) if m else 'other', c['code'])] += 1
    got = collections.Counter(); 
    for r in run:
        for c in r['claims']:
            if c['fence']: got[c['task']] += 1
    ms = [m for m in M if m.get('status') == 200]
    print(f'== {rnd}: runs {len(R)} exit {collections.Counter(str(r["exit"]) for r in R)} p50 {pct([r["s"] for r in R],.5)} s max {max([r["s"] for r in R] or [0])}')
    print(f'   model attempts {len(M)} status {collections.Counter(m.get("status") for m in M)} tokens in {sum(m.get("prompt_tokens") or 0 for m in M)} out {sum(m.get("completion_tokens") or 0 for m in M)} usd {round(sum(m.get("usd") or 0 for m in M),4)} p50 {pct([m["s"] for m in ms],.5)} s; finish {collections.Counter(m.get("finish") for m in ms)}; with real tool calls {sum(1 for m in ms if m.get("tool_calls"))}')
    print(f'   curl calls {len(C)} {dict(ctr)}; 5xx/429 by route {dict((k,v) for k,v in routes.items() if k[1][0]=="5" or k[1]=="429")}')
    print(f'   tools {dict(tools)} errors {dict(toolerr)}; webfetch routes {dict(webroutes)} error statuses {dict(webst)}')
    print(f'   claims with fence {sum(got.values())} on {len(got)} Tasks; same Task 2+ {[k for k,v in got.items() if v>1]}; submit tries {sum(len(r["submits"]) for r in run)} ok {sum(1 for r in run for s in r["submits"] if s["ok"])}; runs with a submit ok {sum(1 for r in run if any(s["ok"] for s in r["submits"]))}; releases {sum(r["release"] for r in run)}; idle {sum(r["idle"] for r in run)}; no tool at all {sum(1 for r in run if not r["tools"])}')
    if LIVE:
        ok = bad = 0
        for r in run:
            for k in dict.fromkeys(r['keys']):
                try:
                    urllib.request.urlopen(urllib.request.Request(BASE+'/q/object/'+k, headers={'user-agent':'swarm-analyze'}), timeout=30).read(); ok += 1
                except Exception: bad += 1; print('   not readable', k)
        print(f'   read back {ok} ok, {bad} not')
    ROWS[rnd] = run
(D/'logs/analysis.json').write_text(json.dumps(ROWS, indent=1)[:5000000])
