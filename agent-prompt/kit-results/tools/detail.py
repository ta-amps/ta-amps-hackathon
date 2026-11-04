#!/usr/bin/env python3
"""detail.py ROUND...: per-run Task kind, tier, object key, builds_on split into keys the Task itself names vs found elsewhere. Reads /q/object and /q/task once per run."""
import json, pathlib, re, sys, urllib.request as u
D = pathlib.Path(__import__('os').environ['TELEION_NOTES']) / 'work-2026-11-03/agent-prompt/swarm/transcripts'
def get(p): return json.load(u.urlopen(u.Request('https://shim.teleionlabs.com' + p, headers={'user-agent': 'kit-analyze'}), timeout=30))
out = {}
for rnd in sys.argv[1:]:
    rows = []
    for f in sorted(D.glob(f'{rnd}-*.jsonl')):
        last = ''; submit = ''
        for l in f.read_text(errors='replace').splitlines():
            try: e = json.loads(l)
            except Exception: continue
            if e.get('type') == 'text': last = e['part'].get('text', '')
        mk = re.search(r'object.keys?\W+([\w.:-]+)', last, re.I); mt = re.search(r'task_id\W+([\w.:-]+)', last)
        r = {'bot': f.stem, 'task': mt and mt.group(1), 'key': mk and mk.group(1), 'end': last[:90].replace('\n', ' ')}
        if mk and mt:
            try:
                o = get('/q/object/' + mk.group(1)); t = get('/q/task/' + mt.group(1)); t = t.get('task', t)
                text = f"{t.get('title')} {t.get('prompt')}"; bo = o.get('builds_on') or []
                r.update(tier=t.get('tier'), kind=t.get('verb_kind'), title=str(t.get('title'))[:70], named=[b for b in bo if b in text], found=[b for b in bo if b not in text], size=len(json.dumps(o.get('payload'))))
            except Exception as ex: r['err'] = str(ex)[:80]
        rows.append(r)
    out[rnd] = rows
    ng = [x for x in rows if x.get('tier') == 'ngo_priority']
    print(rnd, 'runs', len(rows), 'read', sum('tier' in x for x in rows), 'ngo Tasks', len(ng), 'reviews', sum('review' in str(x.get('title')).lower() or x.get('kind') == 'eval_and_rank' for x in rows), 'cite something the Task did not name', sum(bool(x.get('found')) for x in rows), 'cite only named', sum(bool(x.get('named')) and not x.get('found') for x in rows), 'none', sum(not x.get('named') and not x.get('found') for x in rows), 'median payload', sorted(x.get('size', 0) for x in rows)[len(rows)//2])
json.dump(out, open(pathlib.Path(__file__).parent / 'detail-last.json', 'w'), indent=1)
