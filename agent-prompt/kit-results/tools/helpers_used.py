#!/usr/bin/env python3
"""helpers_used.py ROUND...: per run, the helpers shown on the claim, whether the bot read or cited one, and what it cited that the Task did not name."""
import json, pathlib, re, sys
D = pathlib.Path(__import__('os').environ['TELEION_NOTES']) / 'work-2026-11-03/agent-prompt/swarm/transcripts'
det = json.load(open(pathlib.Path(__file__).parent / 'detail-last.json'))
for rnd in sys.argv[1:]:
    shown = runs = read = cited = 0; types = {}; rows = []
    for f in sorted(D.glob(f'{rnd}-*.jsonl')):
        runs += 1; ids = []; reads = set()
        for l in f.read_text(errors='replace').splitlines():
            try: e = json.loads(l)
            except Exception: continue
            if e.get('type') != 'tool_use': continue
            s = e['part'].get('state', {}); o = str(s.get('output') or ''); i = json.dumps(s.get('input', {}))
            if re.search(r'q/claim|fabric_worker\S* --id \S+ claim', i):
                ids += re.findall(r'^- ([\w./:-]+): ', o, re.M) + re.findall(r'^HELPER \[([^\]]+)\] (\S+):', o, re.M)
                try:
                    ids += [(h.get('type') or '?', h['id']) for h in json.loads(o).get('helpers', [])]
                except Exception:
                    ids += [('?', x) for x in re.findall(r'"ref": "\w+:([^"]+)"', o)]
            reads |= set(re.findall(r'q/object/([\w.:-]+)', i)) | set(re.findall(r'--id \S+ read ([\w.:-]+)', i))
        names = [x[1] if isinstance(x, tuple) else x for x in ids]
        for x in ids:
            if isinstance(x, tuple): types[x[0].split(',')[0]] = types.get(x[0].split(',')[0], 0) + 1
        shown += bool(names); rd = reads & set(names); read += bool(rd)
        d = next((x for x in det.get(rnd, []) if x['bot'] == f.stem), {})
        bo = set(d.get('found', []) + d.get('named', [])); c = bo & set(names); cited += bool(c)
        rows.append((f.stem[-10:], len(names), sorted(rd)[:2], sorted(c)[:2], str(d.get('title'))[52:90]))
    print(rnd, 'runs', runs, 'helpers shown on claim', shown, 'read one', read, 'cited one', cited, types)
    if '-v' in sys.argv:
        for r in rows: print('  ', r)
