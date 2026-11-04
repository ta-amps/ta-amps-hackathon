#!/usr/bin/env python3
"""How far can the local model get with its hand held? Read-only: one exact command, then report the ids. Reported ids are compared to the real output."""
import json, pathlib, re, shutil, subprocess, time
D = pathlib.Path(__file__).parent
PROMPT = "Use the shell tool to run exactly this command: curl -s 'https://shim.teleionlabs.com/q/tasks?state=ready&tier=ngo_priority&limit=3&offset=0' . Then write only the task_id values from its output, one per line."
out = []
for i in range(8):
    d = D/'clean'/f'hh-{i}'; shutil.rmtree(d, ignore_errors=True); (d/'.home').mkdir(parents=True)
    (d/'opencode.json').write_text(json.dumps({"provider": {"local": {"npm": "@ai-sdk/openai-compatible", "name": "local", "options": {"baseURL": f"http://127.0.0.1:8911/b/opencode-local-hh{i}/B4/local/v1", "apiKey": "none"}, "models": {"meta-open-small-32k": {"name": "s", "tool_call": True}}}}}))
    t0 = time.time()
    try: o = subprocess.run([str(D/'sandbox.sh'), str(d.resolve()), 'opencode.exe', 'run', '--standalone', '--auto', '--format', 'json', '-m', 'local/meta-open-small-32k', PROMPT], stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=200).stdout
    except subprocess.TimeoutExpired: o = ''
    ev = []
    for l in o.splitlines():
        try: ev.append(json.loads(l))
        except Exception: pass
    ran = [e['part'] for e in ev if e['type'] == 'tool_use' and 'curl' in json.dumps(e['part'].get('state', {}).get('input', {}))]
    real = re.findall(r'verb_\w+', ' '.join(str(p['state'].get('output')) for p in ran))
    tx = ' '.join(e['part'].get('text', '') for e in ev if e['type'] == 'text')
    said = set(re.findall(r'verb_\w+', tx))
    r = {'i': i, 's': round(time.time()-t0, 1), 'ran_curl': bool(ran), 'ids_said': len(said), 'said_in_real': len(said & set(real)), 'invented_ids': sorted(said-set(real))[:3], 'text': tx[:120]}
    out.append(r); print(json.dumps(r), flush=True)
(D/'logs/handheld.json').write_text(json.dumps(out, indent=1))
