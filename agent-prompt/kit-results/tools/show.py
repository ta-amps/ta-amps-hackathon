#!/usr/bin/env python3
"""show.py FILE-STEM [route-regex] [outchars]: tool calls of one run, cut short."""
import json,re,sys,pathlib
D=pathlib.Path(__import__('os').environ['TELEION_NOTES']) / 'work-2026-11-03/agent-prompt/swarm/transcripts'
pat=sys.argv[2] if len(sys.argv)>2 else '.'; n=int(sys.argv[3]) if len(sys.argv)>3 else 300
i=0
for l in (D/(sys.argv[1]+'.jsonl')).read_text(errors='replace').splitlines():
    try:e=json.loads(l)
    except: continue
    p=e.get('part',{})
    if e.get('type')=='text': print('TEXT',p.get('text','')[:n].replace('\n',' '))
    if e.get('type')=='tool_use':
        st=p.get('state',{});inp=json.dumps(st.get('input',{}));out=str(st.get('output') or st.get('error') or '')
        i+=1
        if re.search(pat,inp): print(i,p.get('tool'),st.get('status'),'IN',inp[:n]);print('   OUT',len(out),out[:n].replace('\n',' '))
