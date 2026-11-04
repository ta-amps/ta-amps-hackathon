#!/usr/bin/env python3
"""Does the local model make real tool calls through OpenCode? No queue contact; the target is example.com."""
import json, pathlib, shutil, subprocess, sys, time
D = pathlib.Path(__file__).parent
PROMPT = "Run the shell command: curl -s -o /dev/null -w '%{http_code}' https://example.com . Then tell me the number it printed."
def cfg(d, bot, tools):
    (d/'.home').mkdir(parents=True, exist_ok=True)
    c = {"provider": {"local": {"npm": "@ai-sdk/openai-compatible", "name": "local", "options": {"baseURL": f"http://127.0.0.1:8911/b/{bot}/toolcall-trial/local/v1", "apiKey": "none"}, "models": {"meta-open-small-32k": {"name": "s", "tool_call": True}}}}}
    if tools: c["tools"] = {t: False for t in tools}; 
    (d/'opencode.json').write_text(json.dumps(c))
OFF = ['read','write','edit','glob','grep','list','task','todowrite','todoread','skill','question','webfetch','websearch','patch','multiedit','lsp','codesearch','apply_patch']
out = []
for arm, tools in (('all-tools', None), ('bash-only', OFF)):
    for i in range(5):
        d = D/'clean'/f'tc-{arm}-{i}'; shutil.rmtree(d, ignore_errors=True); cfg(d, f'{arm}-{i}', tools); t0 = time.time()
        try:
            p = subprocess.run([str(D/'sandbox.sh'), str(d.resolve()), 'opencode.exe', 'run', '--standalone', '--auto', '--format', 'json', '-m', 'local/meta-open-small-32k', PROMPT], stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=400); o = p.stdout
        except subprocess.TimeoutExpired as e: o = (e.stdout or b'').decode() if e.stdout else ''
        ev = []
        for l in o.splitlines():
            try: ev.append(json.loads(l))
            except Exception: pass
        tu = [e['part'] for e in ev if e['type'] == 'tool_use']; tx = ' '.join(e['part'].get('text', '') for e in ev if e['type'] == 'text')
        r = {'arm': arm, 'i': i, 's': round(time.time()-t0, 1), 'tool_uses': [(u.get('tool'), u.get('state', {}).get('status')) for u in tu], 'said_200': '200' in tx, 'curl_log': (d/'.home/curl.log').read_text()[:60] if (d/'.home/curl.log').exists() else '', 'text': tx[:160]}
        out.append(r); print(json.dumps(r), flush=True)
(D/'logs/toolcall-trial.json').write_text(json.dumps(out, indent=1))
