#!/usr/bin/env python3
"""Builds data.js from the stored run records only. Every number on screen comes from a field read here."""
import json, glob, os, re
R=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def run(i): return json.load(open(f'{R}/records/{i}.json'))['payload']
A=run('20261103t011822z'); B=run('20261103t131829z')
def tok(p): t=p['counts']['tokens']; k=p['check']['tokens']; return t['input']+t['output']+k['input']+k['output']
def part(p):
    c=p['counts']; ch=p['check']
    return dict(det=c['deterministic']['dropped_license'], seen=c['deterministic']['seen'], ans=c['reuse']['answered_no_model'], rej=c['reuse']['already_rejected_unchanged'],
      sent=c['model']['items_sent'], by=c['model']['by_model'], calls=c['model']['attempts'], audited=len(ch['verdicts']), pub=ch['published']['sent'], status=ch['published']['status'],
      batch=p['batch_size_used'], tuner=p['tuner_version_used'], spec=p['spec_version'], mix=p['mix_used'], secs=p['seconds'], tok=tok(p), gh=p['github']['calls'],
      acc=c['hybrid']['rule_accepted'], back=c['hybrid']['rule_rejected'], effort=p['attempts'][0]['reasoning_effort'])
a=part(A); b=part(B)
assert a['det']+a['ans']+a['rej']+a['sent']==a['seen']==24 and b['det']+b['ans']+b['rej']+b['sent']==b['seen']==24
fails=sorted({f for i in A['items'] for f in i.get('rule_failures',[])})
sp=lambda m:m.split('-')[1].capitalize()
at=A['attempts']; aud=A['check']['attempts']; bt=B['attempts'][0]; bd=B['check']['attempts'][0]
# t, kind (-1 plain, 0 Settings, 1 Deterministic, 2 Reuse, 3 Models, 4 Harness), full, short, tiny, side (L/R), mv
def L(t,k,full,short=None,tiny=None,side='L',mv=None,opt=False,cmd=False):
    return dict(t=t,k=k,full=full,short=short or full,tiny=tiny or short or full,side=side,mv=mv,opt=opt,cmd=cmd)
idA=A['run_id']; idB=B['run_id']
LOG=[
 L(.20,-1,'$ GET stored run record',cmd=True),
 L(.55,-1,f"omninode_feed_run_{idA.lower()}",f"run {idA}",f"run {idA}"),
 L(.85,4,f"{A['maker_worker']} claimed {A['task_id']}",f"{A['maker_worker']} claimed the Task","feed-maker claimed the Task",mv='TF'),
 L(1.25,4,f"node {A['node']}, spec v{a['spec']}",f"node feed-maintenance, spec v{a['spec']}",f"feed-maintenance, spec v{a['spec']}"),
 L(2.00,1,f"GitHub search: {a['gh']} calls, public API, no model",f"GitHub search: {a['gh']} calls, no model",f"GitHub: {a['gh']} calls, no model"),
 L(2.40,1,f"items seen by code: {a['seen']}"),
 L(2.70,1,f"  dropped by license rule: {a['det']}",f"  license rule dropped {a['det']}"),
 L(3.10,2,f"reuse check: {a['ans']} answered, no model call",f"reuse: {a['ans']} answered, no model call",f"reuse: {a['ans']} answered, no model",side='R',mv='OF'),
 L(3.40,2,f"  {a['rej']} already rejected, unchanged",f"  {a['rej']} already rejected",side='R'),
 L(3.70,0,f"settings: batch {a['batch']}, effort {a['effort']}, tuner v{a['tuner']}",f"batch {a['batch']}, effort {a['effort']}, tuner v{a['tuner']}"),
 L(4.00,3,f"label {at[0]['model']}: {len(at[0]['item_keys'])} items"),
 L(4.30,3,f"{at[0]['model']} answered in {at[0]['seconds']} s, {at[0]['output_tokens']} output tokens",f"{at[0]['model']}: {at[0]['seconds']} s, {at[0]['output_tokens']} tokens",f"{sp(at[0]['model'])}: {at[0]['seconds']} s, {at[0]['output_tokens']} tokens"),
 L(4.60,3,f"label {at[1]['model']}: {len(at[1]['item_keys'])} item"),
 L(4.85,3,f"{at[1]['model']} answered in {at[1]['seconds']} s, {at[1]['output_tokens']} output tokens",f"{at[1]['model']}: {at[1]['seconds']} s, {at[1]['output_tokens']} tokens",f"{sp(at[1]['model'])}: {at[1]['seconds']} s, {at[1]['output_tokens']} tokens"),
 L(5.15,1,f"rule check accepted {a['acc']}, sent back {a['back']}",None,f"rules accepted {a['acc']}, sent back {a['back']}"),
 L(5.45,4,f"audit by {A['check']['by_worker']}, a separate worker","audit: a separate worker","audit: a separate worker",side='R'),
 L(5.80,4,f"published {a['pub']} Task Objects, status {a['status']}",f"published {a['pub']} Task Objects, {a['status']}",f"published {a['pub']} Task Objects",side='R',mv='FO'),
 L(6.35,-1,f"status: checked, {a['secs']} s, {a['tok']} tokens",f"checked, {a['secs']} s, {a['tok']} tokens",f"{a['secs']} s, {a['tok']} tokens",side='R'),
 L(6.85,-1,f"$ GET later run {idB.lower()}",f"$ GET run {idB.lower()}",f"$ run {idB}",cmd=True),
 L(7.10,4,f"same node, spec v{b['spec']}, tuner v{b['tuner']}, batch {b['batch']}",f"spec v{b['spec']}, tuner v{b['tuner']}, batch {b['batch']}",mv='TF'),
 L(7.40,1,f"items seen by code: {b['seen']}, license rule dropped {b['det']}",f"seen {b['seen']}, license rule dropped {b['det']}"),
 L(7.70,2,f"reuse check: {b['ans']} answered, {b['rej']} already rejected",f"reuse: {b['ans']} answered, {b['rej']} rejected",side='R',mv='OF'),
 L(8.05,3,f"label {bt['model']}: {len(bt['item_keys'])} item"),
 L(8.35,3,f"{bt['model']} answered in {bt['seconds']} s, {bt['output_tokens']} output tokens",f"{bt['model']}: {bt['seconds']} s, {bt['output_tokens']} tokens",f"{sp(bt['model'])}: {bt['seconds']} s, {bt['output_tokens']} tokens"),
 L(8.70,4,f"audit {bd['model']}: {len(bd['item_keys'])} item, a separate worker",f"audit {bd['model']}: {len(bd['item_keys'])} item",f"audit {sp(bd['model'])}: {len(bd['item_keys'])} item",side='R'),
 L(9.00,4,f"published {b['pub']} Task Object, status {b['status']}",f"published {b['pub']} Task Object, {b['status']}",f"published {b['pub']} Task Object",side='R',mv='FO'),
 L(9.30,-1,f"status: checked, {b['secs']} s, {b['tok']} tokens (was {a['tok']})",f"checked, {b['secs']} s, {b['tok']} tokens",f"{b['secs']} s, {b['tok']} tokens",side='R'),
]
def mixs(m): return f"{round(m['label-muse-spark']*100)} / {round(m['label-muse-wonder']*100)}"
def models(x): return ', '.join(f"{sp(k)} {v}" for k,v in x['by'].items())
def choices(x):
    return {1:dict(v=x['det'],c=f"{x['det']} dropped before any model",s=f"{x['det']} dropped",why='license rule'),
            2:dict(v=x['ans']+x['rej'],c=f"{x['ans']} answered, {x['rej']} already rejected",s=f"{x['ans']+x['rej']} from stored work",why='no model call'),
            3:dict(v=x['sent'],c=f"{x['sent']} item{'s' if x['sent']!=1 else ''}: {models(x)}",s=models(x),why=f"share {mixs(x['mix'])}"),
            0:dict(v=x['calls'],c=f"batch {x['batch']}, effort {x['effort']}",s=f"batch {x['batch']}, {x['effort']}",why=f"tuner v{x['tuner']}"),
            4:dict(v=x['audited'],c=f"separate worker audits {x['audited']}",s=f"{x['audited']} audited",why=f"spec v{x['spec']}")}
ALL=[]
for f in sorted(glob.glob(f'{R}/records/2026*.json')):
    p=json.load(open(f))['payload']; ALL.append(dict(id=p['run_id'],tok=tok(p),sent=p['counts']['model']['items_sent'],reuse=p['counts']['reuse']['answered_no_model']))
D=dict(LOG=LOG,A=choices(a),B=choices(b),tokA=a['tok'],tokB=b['tok'],secsA=a['secs'],secsB=b['secs'],pubA=a['pub'],pubB=b['pub'],runs=ALL,fails=fails)
open(f'{R}/data.js','w').write('window.LAB='+json.dumps(D,ensure_ascii=False)+';\n')
print(json.dumps(ALL)); print(fails); print(a); print(b)
