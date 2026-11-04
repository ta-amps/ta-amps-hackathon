#!/usr/bin/env python3
"""readout.py ROUND [i ...]: Task title+prompt, final object, tools that ran. For reading outputs by hand."""
import json,sys,urllib.request as u,re
r=json.load(open('logs/analysis.json'))[sys.argv[1]]
idx=[int(x) for x in sys.argv[2:]] or range(len(r))
def get(p): return json.load(u.urlopen(u.Request('https://shim.teleionlabs.com'+p,headers={'user-agent':'swarm-analyze'}),timeout=30))
for i in idx:
    x=r[i]; print('=====',i,x['file'],'tools',x['tools'])
    if x.get('task_final'):
        t=get('/q/task/'+x['task_final']); t=t.get('task',t); print('TITLE',t.get('title')); print('PROMPT',(t.get('prompt') or '')[:700])
    for k in x['keys'][:1]:
        o=get('/q/object/'+k); print('SUMMARY',(o.get('summary') or '')[:300]); print('PAYLOAD',json.dumps(o.get('payload'),ensure_ascii=False)[:1500])
