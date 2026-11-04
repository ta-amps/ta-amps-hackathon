#!/usr/bin/env python3
"""breakdown.py ROUND: no-lease claims by Task, why, and Tasks let go repeatedly. A few reads of /q/task."""
import collections, json, pathlib, re, sys, urllib.request as u
D = pathlib.Path(__import__('os').environ['TELEION_NOTES']) / 'work-2026-11-03/agent-prompt/swarm/transcripts'
PH = ["field team","field-team","field partner","field test","live block","live trial","gloved trial","40-trial","consented sites","collect genuine","recruit a","live two-pair run","recruit ","real non-specialist","real reader","real-reader","real-site","gloved 20","physical eyes-closed","bare-arm block","the 5-user","live facilitator","field-print","field-test the three-blob","field trial","coordinator pairs","survivor-advocate"]
nl = collections.Counter(); bots = collections.defaultdict(set); rel = collections.defaultdict(set); runs = 0; stuck = 0; calls_after = []
for f in D.glob(sys.argv[1] + '-*.jsonl'):
    runs += 1; nlr = 0
    for l in f.read_text(errors='replace').splitlines():
        try: e = json.loads(l)
        except Exception: continue
        if e.get('type') != 'tool_use': continue
        s = e['part'].get('state', {}); i = json.dumps(s.get('input', {})); o = str(s.get('output') or s.get('error') or '')
        if '/q/claim' in i and re.search(r'"lease": null|NO READY MATCHING', o):
            for t in set(re.findall(r'task_id[=\\": ]+(verb_[\w.-]+)', i)) or {'(no id)'}:
                nl[t] += 1; bots[t].add(f.name); nlr += 1
        m = re.search(r'/q/release/[\w.-]+/(verb_[\w.-]+)/', i)
        if m and 'released' in o: rel[m.group(1)].add(f.name)
    stuck += nlr >= 2
print('runs', runs, 'runs with 2+ no-lease claims', stuck, 'no-lease claims', sum(nl.values()), 'on', len(nl), 'Tasks')
ph = cnt = 0
for t, n in nl.most_common(30):
    try: title = json.load(u.urlopen(u.Request('https://shim.teleionlabs.com/q/task/' + t, headers={'user-agent': 'kit-analyze'}), timeout=20))['task']['title']
    except Exception: title = '?'
    fw = any(p in title.lower() for p in PH); cnt += n; ph += n if fw else 0
    print(n, len(bots[t]), 'bots', 'FIELD' if fw else 'other', t, title[:90])
print('of top 30 Tasks,', ph, 'of', cnt, 'no-lease claims hit the silent field-work filter')
print('let go by 2+ runs:', {k: len(v) for k, v in rel.items() if len(v) >= 2})
