#!/usr/bin/env python3
"""verdicts.py: for every object key the bots reported, read it live and tally the checker's latest verdict by round. Also lists rationale of REFUTED."""
import collections, glob, json, re, urllib.request as u
def get(p): return json.load(u.urlopen(u.Request('https://shim.teleionlabs.com'+p, headers={'user-agent': 'swarm-analyze'}), timeout=30))
keys = {}
for f in glob.glob('transcripts/*.jsonl'):
    m = re.match(r'transcripts/(A1|A5|A20|A50|C1m|D1)-(.+)-\d+\.jsonl', f)
    if not m: continue
    s = open(f, errors='replace').read()
    for k in set(re.findall(r'[A-Za-z0-9][\w.-]*_(?:opencode-(?:mix-)?muse-\d+|codex-muse-\d+)_\d{8}_v\d+', s)):
        if m.group(2) in k: keys[k] = m.group(1)
tally = collections.defaultdict(collections.Counter); ref = []; rows = {}; miss = 0
for k, rnd in sorted(keys.items()):
    try: o = get('/q/object/' + k)
    except Exception: miss += 1; tally[rnd]['not_stored'] += 1; continue
    if o.get('producer_agent', '') not in k: tally[rnd]['other_producer'] += 1; continue
    ev = [e for e in (o.get('evaluations') or []) if 'checker' in str(e.get('evaluator_agent_id'))]
    v = ev[-1].get('verification_verdict') if ev else 'NOT_CHECKED'
    tally[rnd][v] += 1; rows[k] = {'round': rnd, 'verdict': v, 'rationale': (ev[-1].get('rationale') if ev else '')}
    if v == 'REFUTED': ref.append((k[:60], rows[k]['rationale'].replace("The maker's model isn't known, so this is a different worker and possibly the same model. ", '')[:260]))
json.dump(rows, open('logs/verdicts.json', 'w'), indent=1)
print('objects', len(keys), 'not stored', miss)
for r, c in sorted(tally.items()): print(r, dict(c))
print('all', dict(sum(tally.values(), collections.Counter())))
for x in ref: print(x)
