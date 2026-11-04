import json,re,os,collections,glob
S=os.path.expanduser('~/.local/state/eranos-worker')
import os
N=os.environ['TELEION_NOTES']
tasks={}
def add(tid,title,prompt,src):
    if not tid: return
    r=tasks.setdefault(tid,{'title':'','prompt':'','src':set()})
    if title and len(title)>len(r['title']): r['title']=title
    if prompt and len(prompt)>len(r['prompt']): r['prompt']=prompt
    r['src'].add(src)
def walk(x,src):
    if isinstance(x,dict):
        tid=x.get('task_id')
        if isinstance(tid,str) and (x.get('title') or x.get('prompt') or x.get('description')):
            add(tid,str(x.get('title') or ''),str(x.get('prompt') or x.get('description') or ''),src)
        for v in x.values(): walk(v,src)
    elif isinstance(x,list):
        for v in x: walk(v,src)
for f in glob.glob(S+'/*.jsonl')+[N+'/work-2026-11-03/sizing/records/outcomes.jsonl']:
    for l in open(f,errors='replace'):
        try: j=json.loads(l)
        except: continue
        walk(j,os.path.basename(f))
        if isinstance(j,dict) and isinstance(j.get('input_sanitized'),str):
            s=j['input_sanitized']
            try: walk(json.loads(s),'traces')
            except:
                m=re.search(r'THE TASK THAT WAS ASKED FOR:\s*(\{.*?\})\s*(?:\n|$)',s,re.S)
                if m:
                    try:
                        d=json.loads(m.group(1)); add(j.get('task_id'),d.get('title',''),d.get('prompt') or d.get('description') or '','check')
                    except: pass
print(len(tasks),collections.Counter(s for t in tasks.values() for s in t['src']).most_common())
print('with prompt',sum(1 for t in tasks.values() if len(t['prompt'])>40),'index',sum(1 for k in tasks if k.startswith('verb_index_enrich')))
dec=[json.loads(l) for l in open(N+'/work-2026-11-03/meta-live/records/decisions.jsonl')]
print('decisions with text',sum(1 for d in dec if d['task_id'] in tasks),len(dec))
ft=[json.loads(l) for l in open(N+'/work-2026-11-03/sizing/records/fine-tune.jsonl')]
print('ft answers',[ (a.get('task_id') in tasks) for a in ft if a.get('event')=='answer'])
json.dump({k:{**v,'src':sorted(v['src'])} for k,v in tasks.items()},open('snapshot/tasks-local.json','w'))
obj=json.load(open(N+'/work-2026-11-03/search-eval/corpus/objects-raw.json'))[0]['results']
keys={o['k'] for o in obj}
rx=re.compile(r'[A-Za-z0-9][A-Za-z0-9_.:-]{9,}')
ref=collections.Counter(); pairs=[]
for o in obj:
    for m in set(rx.findall(o['s'] or ''))&keys:
        if m!=o['k']: pairs.append((o['k'],m))
print('obj-names-obj pairs',len(pairs),'distinct sources',len({a for a,b in pairs}))
tp=[]
for k,t in tasks.items():
    if k.startswith('verb_index'): continue
    for m in set(rx.findall(t['title']+' '+t['prompt']))&keys: tp.append((k,m))
print('task-names-obj pairs',len(tp),'tasks',len({a for a,b in tp}))
print(collections.Counter(re.sub(r'[_-]?(muse|v\d+|\d{6,}).*','',k)[:18] for k in keys).most_common(15))
print([o['k'] for o in obj if 'ed_trial' in o['k']][:20]); print([o['s'][:200] for o in obj if 'ed_trial' in o['s']][:6])
print('marked',sum(bool(re.search(r'(?i)\binvented|made.?up|fabricat|refuted',o['s'] or '')) for o in obj))
