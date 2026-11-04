#!/usr/bin/env python3
"""compare.py ROUND...: per-round numbers from transcripts and the proxy log. Prompt tokens per run, no-lease replies, calls, finish, reuse (builds_on), helper looks, releases, runs that ended idle or stopped, wall time."""
import collections, json, pathlib, re, statistics as st, sys, urllib.request
D = pathlib.Path(__import__('os').environ['TELEION_NOTES']) / 'work-2026-11-03/agent-prompt/swarm'
M = [json.loads(l) for l in (D/'logs/model.jsonl').open()]
R = [json.loads(l) for l in (D/'logs/runs.jsonl').open() if '"exit"' in l]
rows = {}
for rnd in [a for a in sys.argv[1:] if not a.startswith('-')]:
    files = sorted((D/'transcripts').glob(f'{rnd}-*.jsonl'))
    n = len(files); out = collections.Counter(); per = []
    usd = sum(m.get('usd') or 0 for m in M if m.get('round') == rnd)
    pt = sum(m.get('prompt_tokens') or 0 for m in M if m.get('round') == rnd); ct = sum(m.get('completion_tokens') or 0 for m in M if m.get('round') == rnd)
    secs = [r['s'] for r in R if r['round'] == rnd]
    for f in files:
        c = collections.Counter(); done = False; last = ''; kit = False; bo = 0; hl = False; lens = 0
        for l in f.read_text(errors='replace').splitlines():
            try: e = json.loads(l)
            except Exception: continue
            p = e.get('part', {})
            if e.get('type') == 'text': last = p.get('text', '')
            if e.get('type') != 'tool_use': continue
            s = p.get('state', {}); inp = json.dumps(s.get('input', {})); o = str(s.get('output') or s.get('error') or '')
            c['calls'] += 1; lens += len(o)
            if 'fabric_worker' in inp: kit = True
            if re.search(r'q/claim|fabric_worker\S* .*claim| claim ', inp):
                c['claims'] += 1
                if re.search(r'"lease": null|NO LEASE|NO READY MATCHING|No lease', o): c['no_lease'] += 1
            if re.search(r'q/find|q/repos|helpers| find ', inp): hl = True
            if re.search(r'q/release|give-back', inp) and re.search(r'released|GAVE BACK', o): c['released'] += 1
            if re.search(r'q/submit| submit ', inp):
                c['submits'] += 1
                if re.search(r'verification_code|VERIFICATION_CODE', o) and not re.search(r'"verification_code": null', o): done = True
                if re.search(r'error code: 1010|"ok": false|invalid_json|REFUSED|HTTP Error', o[:800]): c['submit_refused'] += 1
                m = re.search(r'builds_on\W+\[([^\]]*)\]', inp) or re.search(r'--builds-on\W+([\w.,:-]+)', inp)
                if m and m.group(1).strip(): bo = 1
            if re.search(r'error code: 1010', o): c['e1010'] += 1
            if re.search(r'\b503\b|Service Unavailable', o[:300]): c['e503'] += 1
        if '--live' in sys.argv and done:
            m = re.search(r'object.keys?\W+([\w.:-]+)', last, re.I)
            if m:
                try:
                    o = json.load(urllib.request.urlopen(urllib.request.Request('https://shim.teleionlabs.com/q/object/' + m.group(1), headers={'user-agent': 'kit-analyze'}), timeout=30))
                    bo = 1 if o.get('builds_on') else 0
                except Exception: pass
        per.append({'bot': f.name[:-6], 'calls': c['calls'], 'done': done, 'no_lease': c['no_lease'], 'claims': c['claims'], 'released': c['released'], 'looked': hl, 'cited': bo, 'kit': kit, 'submit_refused': c['submit_refused'], 'e1010': c['e1010'], 'e503': c['e503'], 'out_chars': lens, 'end': last[:120].replace('\n', ' ')})
    d = {'runs': n, 'finished_a_task': sum(x['done'] for x in per), 'idle_or_stopped': sum(not x['done'] for x in per), 'used_kit': sum(x['kit'] for x in per), 'calls_median': st.median([x['calls'] for x in per] or [0]), 'claims': sum(x['claims'] for x in per), 'no_lease': sum(x['no_lease'] for x in per), 'gave_back': sum(x['released'] for x in per), 'looked_for_help': sum(x['looked'] for x in per), 'cited_builds_on': sum(x['cited'] for x in per), 'submit_refused': sum(x['submit_refused'] for x in per), 'e1010': sum(x['e1010'] for x in per), 'e503': sum(x['e503'] for x in per), 'prompt_tokens_per_run': round(pt/max(n, 1)), 'completion_tokens_per_run': round(ct/max(n, 1)), 'usd': round(usd, 4), 'usd_per_finished': round(usd/max(sum(x['done'] for x in per), 1), 4), 'seconds_median': st.median(secs or [0]), 'tool_output_chars_median': st.median([x['out_chars'] for x in per] or [0])}
    rows[rnd] = d; print(rnd, json.dumps(d))
    if '-v' in sys.argv: [print('  ', x) for x in per]
json.dump(rows, open(pathlib.Path(__file__).parent/'compare-last.json', 'w'), indent=1)
