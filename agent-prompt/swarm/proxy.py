#!/usr/bin/env python3
"""Local recording proxy for the swarm test. Bots never hold a key.

  /b/<bot>/<round>/meta/v1/...   -> Meta API, key added here, cost recorded on both shared ledgers
  /b/<bot>/<round>/local/v1/...  -> the local model server, no cost, timing recorded

Every attempt is written to logs/model.jsonl, failures too. New Meta calls are refused once the shared day passes STOP_DAY_USD.
No credential is printed or logged."""
import datetime, fcntl, http.client, http.server, json, os, pathlib, re, ssl, sys, threading, time
D = pathlib.Path(__file__).resolve().parent
PORT = int(os.environ.get('SWARM_PROXY_PORT', 8911))
STOP_DAY_USD = float(os.environ.get('STOP_DAY_USD', 20))
IN, OUT = 0.10, 0.20
LOG = D / 'logs/model.jsonl'
LEDGER = D.parents[2] / 'coordination-2026-10-31/compute-ledger.jsonl'
SHARED = pathlib.Path.home() / '.local/state/eranos-worker/meta-spend.json'
lock = threading.Lock()
def now(): return datetime.datetime.now(datetime.UTC).isoformat()
def key():
    for l in (pathlib.Path.home() / '.config/ta-amps/eranos-worker/meta.env').read_text().splitlines():
        if l.startswith('META_API_KEY='): return l.split('=', 1)[1].strip().strip('"\'')
    raise SystemExit('no key')
def append(path, rec):
    with lock:
        with open(path, 'a') as f: f.write(json.dumps(rec, ensure_ascii=False) + '\n')
def shared(delta=0.0):
    """Same lock, same format as SharedSpendLedger. Returns today's total."""
    day = time.strftime('%Y-%m-%d', time.gmtime())
    fd = os.open(str(SHARED) + '.lock', os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        data = json.loads(SHARED.read_text() or '{}')
        if delta:
            data.setdefault('days', {})[day] = round(float(data['days'].get(day, 0)) + delta, 6)
            data['total_usd'] = round(float(data.get('total_usd', 0)) + delta, 6)
            tmp = SHARED.with_name(f'.{SHARED.name}.{os.getpid()}.{threading.get_ident()}.tmp')
            with open(os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), 'w') as f:
                f.write(json.dumps(data, sort_keys=True)); f.flush(); os.fsync(f.fileno())
            os.replace(tmp, SHARED)
        return float(data.get('days', {}).get(day, 0))
    finally:
        os.close(fd)
class H(http.server.BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    def log_message(self, *a): pass
    def do_GET(self):
        self.send_response(200); b = b'{"data":[]}'; self.send_header('content-length', str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_POST(self):
        m = re.match(r'/b/([\w.-]+)/([\w.-]+)/(meta|local)(/v1/.*)$', self.path)
        n = int(self.headers.get('content-length') or 0); raw = self.rfile.read(n)
        if not m:
            self.send_response(404); self.send_header('content-length', '0'); self.end_headers(); return
        bot, rnd, up, path = m.groups(); t0 = time.time()
        try: body = json.loads(raw)
        except Exception: body = {}
        rec = {'ts': now(), 'round': rnd, 'bot': bot, 'up': up, 'model': body.get('model'), 'stream': bool(body.get('stream')), 'req_bytes': n, 'msgs': len(body.get('messages') or []), 'tools': len(body.get('tools') or [])}
        if up == 'meta':
            today = shared()
            if today >= STOP_DAY_USD:
                rec.update(status=-1, error=f'stopped: shared day at ${today:.2f}'); append(LOG, rec)
                b = json.dumps({'error': {'message': 'swarm test stopped: day budget'}}).encode()
                self.send_response(503); self.send_header('content-type', 'application/json'); self.send_header('content-length', str(len(b))); self.end_headers(); self.wfile.write(b); return
            if body.get('stream') and path.endswith('chat/completions'):
                body.setdefault('stream_options', {})['include_usage'] = True
            data = json.dumps(body).encode()
            c = http.client.HTTPSConnection('api.meta.ai', timeout=300, context=ssl.create_default_context())
            hd = {'authorization': 'Bearer ' + key(), 'content-type': 'application/json', 'user-agent': 'swarm-test/1'}
        else:
            data = raw
            c = http.client.HTTPConnection('127.0.0.1', 11434, timeout=1800)
            hd = {'content-type': 'application/json'}
        tail = b''; usage = None; finish = None; tcalls = {}; text = 0
        try:
            c.request('POST', path, body=data, headers=hd)
            r = c.getresponse(); st = r.status; ct = r.getheader('content-type') or 'application/json'
            self.send_response(st); self.send_header('content-type', ct); self.send_header('transfer-encoding', 'chunked'); self.send_header('connection', 'close')
            ra = r.getheader('retry-after')
            if ra: self.send_header('retry-after', ra)
            self.end_headers(); ttfb = None; buf = b''; alive = True
            while True:
                ch = r.read1(65536)
                if not ch: break
                if ttfb is None: ttfb = round(time.time() - t0, 2)
                if alive:
                    try: self.wfile.write(b'%x\r\n%s\r\n' % (len(ch), ch)); self.wfile.flush()
                    except OSError: alive = False; rec['client_gone'] = True
                tail = (tail + ch)[-3000:]
                buf += ch
                while b'\n' in buf:
                    line, buf = buf.split(b'\n', 1)
                    if line.startswith(b'data:') and b'[DONE]' not in line:
                        try: d = json.loads(line[5:])
                        except Exception: continue
                        usage = d.get('usage') or (d.get('response') or {}).get('usage') or usage
                        for x in d.get('choices') or []:
                            finish = x.get('finish_reason') or finish
                            dl = x.get('delta') or {}
                            text += len(dl.get('content') or '')
                            for tc in dl.get('tool_calls') or []:
                                nm = (tc.get('function') or {}).get('name')
                                if nm: tcalls[tc.get('index', len(tcalls))] = nm
            if not body.get('stream') and st == 200:
                try:
                    d = json.loads(buf.decode() or tail.decode()); usage = d.get('usage'); ch0 = d['choices'][0]; finish = ch0.get('finish_reason')
                    tcalls = {i: t['function']['name'] for i, t in enumerate(ch0['message'].get('tool_calls') or [])}; text = len(ch0['message'].get('content') or '')
                except Exception: pass
            if alive:
                try: self.wfile.write(b'0\r\n\r\n'); self.wfile.flush()
                except OSError: pass
            self.close_connection = True
            rec.update(status=st, s=round(time.time() - t0, 2), ttfb=ttfb, finish=finish, tool_calls=list(tcalls.values()), text_chars=text)
            if usage: rec.update(prompt_tokens=usage.get('prompt_tokens', usage.get('input_tokens')), completion_tokens=usage.get('completion_tokens', usage.get('output_tokens')))
            if st != 200: rec['error'] = tail.decode('utf-8', 'replace')[:400]
        except Exception as e:
            rec.update(status=0, s=round(time.time() - t0, 2), error=f'{type(e).__name__}: {e}'[:300])
            self.close_connection = True
            try:
                if 'st' not in dir(): self.send_response(502); self.send_header('content-length', '0'); self.end_headers()
            except OSError: pass
        usd = 0.0
        if up == 'meta':
            pt, ct2 = rec.get('prompt_tokens') or 0, rec.get('completion_tokens') or 0
            if rec.get('status') == 200 and not usage: rec['usage_missing'] = True; pt, ct2 = n // 4, text // 4  # estimate so the ledger never undercounts to zero
            usd = (pt * IN + ct2 * OUT) / 1e6
            rec['usd'] = round(usd, 6)
            if usd: shared(usd)
            append(LEDGER, {'ts': rec['ts'], 'provider': 'meta', 'model': rec['model'], 'tier': 'contributor', 'who': 'claude', 'job': f'swarm-real/{rnd}/{bot}', 'status': rec.get('status'), 'prompt_tokens': pt, 'completion_tokens': ct2, 'cost_usd': round(usd, 6)})
        append(LOG, rec)
http.server.ThreadingHTTPServer.daemon_threads = True
print('proxy on', PORT, flush=True)
http.server.ThreadingHTTPServer(('127.0.0.1', PORT), H).serve_forever()
