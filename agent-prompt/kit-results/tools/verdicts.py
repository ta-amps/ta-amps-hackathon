#!/usr/bin/env python3
"""verdicts.py [detail file]: the independent checker's verdict on each stored object, by arm."""
import collections, json, sys, urllib.request as u
d = json.load(open(sys.argv[1] if len(sys.argv) > 1 else 'detail-M.json'))
for r, rows in d.items():
    c = collections.Counter()
    for x in rows:
        if not x.get('key'): c['no object'] += 1; continue
        try: o = json.load(u.urlopen(u.Request('https://shim.teleionlabs.com/q/object/' + x['key'], headers={'user-agent': 'kit-analyze'}), timeout=20))
        except Exception: c['read failed'] += 1; continue
        x['verdict'] = o.get('verification_verdict'); c[o.get('verification_verdict')] += 1
    print(r, dict(c))
json.dump(d, open('verdicts-M.json', 'w'), indent=1)
