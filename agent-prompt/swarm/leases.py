#!/usr/bin/env python3
"""leases.py ROUND...: real leases from transcripts. A lease counts only if the answer says LEASED or holds a lease object. Double = same Task and same fence for two bots, or two bots' submits both accepted on one Task."""
import collections, glob, json, re, sys
for rnd in sys.argv[1:]:
    L = []; none = collections.Counter(); subs = collections.defaultdict(list); rel = 0; lost = []; hb = 0; ret = 0; codes = collections.Counter(); sizes = []
    for f in sorted(glob.glob(f'transcripts/{rnd}-*.jsonl')):
        bot = re.match(rf'transcripts/{rnd}-(.+)-\d+\.jsonl', f).group(1); prev = None
        for l in open(f, errors='replace'):
            try: e = json.loads(l)
            except Exception: continue
            if e.get('type') == 'tool_use':
                s = e['part'].get('state', {}); i = json.dumps(s.get('input', {})); o = str(s.get('output') or s.get('error') or ''); ts = e.get('timestamp', 0)
            elif e.get('type') == 'item.completed' and e.get('item', {}).get('type') == 'command_execution':
                it = e['item']; i = it.get('command', ''); o = it.get('aggregated_output', ''); ts = 0
            else: continue
            for code in re.findall(r'\bHTTP/\S+ (\d{3})\b|"status":\s*(429|50[0-9])\b', o): codes[code[0] or code[1]] += 1
            ii = i.replace('\\', '')
            if '/q/claim/' in ii or ('/q/claim' in ii and 'task_id' in ii):
                m = re.search(r'task_id[=":\s]+([\w.-]+)', ii); t = m.group(1) if m else None
                leased = 'LEASED PRIORITIZED' in o or re.search(r'"lease":\s*\{', o)
                f2 = re.search(r'FENCING_TOKEN[:=\s]+(\d+)|"fencing_token":\s*(\d+)', o)
                tm = re.search(r'TASK_ID:\s+(\S+)', o)
                if leased and f2: L.append((tm.group(1) if tm else t, bot, f2.group(1) or f2.group(2), ts))
                else:
                    r = re.search(r'NO READY[A-Z ]*|"reason":\s*"([^"]{0,60})|(field|needs_people)[^"]{0,40}', o); none[(r.group(0)[:50] if r else 'other/' + o[:30].replace('\n', ' '))] += 1
            if '/q/submit' in ii and 'q/submit' in ii[:800]:
                ok = bool(re.search(r'verification_code', o)); 
                m = re.search(r'"task_id"\s*:\s*"([\w.-]+)"', o) or re.search(r'task_id[":\s]+([\w.-]+)', ii)
                if ok and m: subs[m.group(1)].append(bot)
                if '409' in o[:400] or 'stale' in o[:300].lower(): lost.append((bot, o[:120]))
            if '/q/release/' in ii: rel += 1
            if '/q/heartbeat' in ii: hb += 1
    by = collections.defaultdict(list)
    for t, b, f, ts in L: by[t].append((b, f))
    samef = {t: v for t, v in by.items() if len({x[1] for x in v}) < len({x[0] for x in v})}
    two = {t: sorted(set(v)) for t, v in subs.items() if len(set(v)) > 1}
    print(f'== {rnd}: leases {len(L)} on {len(by)} Tasks; same fence two bots {samef}; accepted submits by 2 bots {two}; re-leased after release/expiry {sum(1 for v in by.values() if len(v) > 1)}; no-lease {sum(none.values())}: {none.most_common(4)}; releases {rel}; heartbeats {hb}; 409/stale {len(lost)} {lost[:2]}; error codes in bodies {dict(codes)}')
