#!/usr/bin/env python3
"""mine.py [ROUND ...]: where real bots got stuck. Reads swarm/transcripts (OpenCode JSON) and prints per-run step counts plus every non-happy reply, grouped."""
import collections, json, pathlib, re, sys
D = pathlib.Path(__import__('os').environ['TELEION_NOTES']) / 'work-2026-11-03/agent-prompt/swarm'
rounds = sys.argv[1:] or ['A1','A5','A20']
kinds = collections.Counter(); ex = {}; per=[]
PAT = [
 ('claim_no_task', r'no task|NO_TASK|"task":\s*null|no_claimable|nothing to claim'),
 ('bad_json', r'invalid.json|not valid JSON|invalid_json|Unexpected token|bad json'),
 ('fence', r'expected_fencing_token|lost.{0,20}lease|LEASE_LOST|stale.?fenc|FENCE|fencing_token_mismatch'),
 ('409', r'\b409\b'), ('503', r'\b503\b'), ('429', r'\b429\b'), ('403', r'\b403\b|error code: 1010'), ('404', r'\b404\b'), ('400', r'\b400\b'), ('422', r'\b422\b'),
 ('expired', r'expired'), ('released', r'RELEASED|"released"'), ('refused', r'refused|rejected|REJECT|policy_violation'),
]
for rnd in rounds:
  for f in sorted((D/'transcripts').glob(f'{rnd}-*.jsonl')):
    r = collections.Counter(); seq=[]; last=''
    for l in f.read_text(errors='replace').splitlines():
      try: e=json.loads(l)
      except Exception: continue
      p=e.get('part',{})
      if e.get('type')=='text': last=p.get('text','')
      if e.get('type')!='tool_use': continue
      st=p.get('state',{}); inp=json.dumps(st.get('input',{})); out=str(st.get('output') or st.get('error') or '')
      m=re.search(r'/q/([a-z_-]+)',inp); route=m.group(1) if m else p.get('tool')
      seq.append(route); r[route]+=1
      if '/q/' in inp:
        for k,pt in PAT:
          if re.search(pt,out[:2500]):
            key=(route,k); kinds[key]+=1
            ex.setdefault(key,(f.name[:30],inp[:160],out[:300].replace('\n',' ')))
    per.append((f.name.replace('.jsonl',''),len(seq),dict(r),' '.join(seq)[:300],last[:160].replace('\n',' ')))
for x in per: print(x[0],x[1],x[3]); print('    END:',x[4])
print()
for k,v in kinds.most_common(40):
  print(v,k); print('   ',ex[k])
