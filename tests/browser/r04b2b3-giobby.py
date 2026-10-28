#!/usr/bin/env python3
"""Private in-memory purchase-order replay fake over the owned R05.a.7 projections, not a Giobby compatibility assertion."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import copy
import json
import ssl
import threading
import time
import urllib.parse
CAPTURES = json.loads(Path('/captures/r05a7-owned-captures.json').read_text())
state = {'mode': 'complete', 'traffic': [], 'documents': {}, 'inflight': None}
lock = threading.RLock()
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args): pass
    def reply(self, body, status=200):
        data = json.dumps(body).encode()
        try:
            self.send_response(status); self.send_header('Content-Type', 'application/json'); self.send_header('Content-Length', str(len(data))); self.end_headers(); self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError): pass
    def do_POST(self): self.handle_request()
    def do_GET(self): self.handle_request()
    def handle_request(self):
        p = urllib.parse.urlsplit(self.path)
        raw = b''
        if self.command == 'POST':
            if self.headers.get('Transfer-Encoding') == 'chunked':
                while True:
                    size = int(self.rfile.readline().strip(), 16)
                    if size == 0: self.rfile.readline(); break
                    assert len(raw) + size <= 65536
                    raw += self.rfile.read(size); self.rfile.read(2)
            else: raw = self.rfile.read(min(65536, int(self.headers.get('Content-Length', '0'))))
        body = json.loads(raw) if raw else {}
        delay = 0
        with lock:
            if p.path == '/health': return self.reply({'healthy': True})
            if p.path == '/control/traffic': return self.reply({'traffic': state['traffic']})
            if p.path == '/control/requests': return self.reply({'requests': list(state['documents'].values())})
            if p.path == '/control/inflight': return self.reply({'requestId': state['inflight']})
            if p.path == '/control/mode': state['mode'] = body['mode']; return self.reply({'ok': True})
            auth = self.headers.get('Authorization', '') == 'Bearer synthetic-runtime-token' and self.headers.get('X-Giobby-Realm') == 'api-server'
            state['traffic'].append({'method': self.command, 'path': self.path, 'authVerified': auth})
            if not auth: return self.reply({'error': 'synthetic_auth_refused'}, 401)
            if p.path == '/loggeduser': return self.reply({'idCompany': 101, 'cid': 'SYNTH-CID-A'})
            mode = state['mode']
            if mode == 'redirect':
                self.send_response(307); self.send_header('Location', 'https://simulator-b:8443/purchases/orders'); self.send_header('Content-Length', '0'); self.end_headers(); return
            if self.command == 'POST' and p.path == '/purchases/orders' and p.query == 'simulation=false':
                assert body['idDocumentType'] == 2 and body['idContact'] is None and isinstance(body['idVendor'], str) and 'docNumber' not in body and 'Idempotency-Key' not in self.headers
                if mode == '500': return self.reply({'responseCode': 500, 'errorCode': 2121003}, 500)
                number = 300 + len(state['documents']) + 1
                document = copy.deepcopy(CAPTURES['po-readback'])
                d = document['document']; d.update(id=number, reference=body['reference'], idVendor=body['idVendor'], idBu=body['idBu'], idNumerator=body['idNumerator'])
                template = d['rows'][0]
                d['rows'] = [dict(copy.deepcopy(template), **row, idPos=i+1) for i, row in enumerate(body['rows'])]
                if mode == 'mismatch': d['rows'][0]['price'] = d['rows'][0]['price'] + 1
                state['documents'][number] = {'id': number, 'reference': body['reference'], 'document': document, 'body': body, 'posts': 1}
                state['inflight'] = body['reference']
                result = copy.deepcopy(CAPTURES['po-ack']); result['idDocument'] = number
                if mode in ('lost-response', 'lost-response-empty', 'hold-response'): delay = 10
            elif self.command == 'GET' and p.path == '/purchases/orders':
                result = copy.deepcopy(CAPTURES['po-lookup-vendor-name-status'])
                entries = [] if mode in ('empty', 'lost-response-empty') else sorted(state['documents'].values(), key=lambda e: -e['id'])
                result['documentsHeaders'] = []
                for entry in entries:
                    h = {k: v for k, v in entry['document']['document'].items() if k not in ('rows', 'idContact', 'payments', 'idBu', 'idNumerator', 'taxableAmount', 'vatAmount')}; h['idContact'] = None
                    result['documentsHeaders'].append(h)
                total = len(result['documentsHeaders']); result['documentsHeaders'] = result['documentsHeaders'][:5]
                result['metadata'].update(totalCount=total, offset=0, limit=5)
                return self.reply(result)
            elif self.command == 'GET' and p.path.startswith('/purchases/') and p.path.endswith('/orders'):
                entry = state['documents'].get(int(p.path.split('/')[2]))
                if entry is None: return self.reply({'errorCode': 404, 'responseCode': 404}, 404)
                return self.reply(entry['document'])
            else: return self.reply({'error': 'FORBIDDEN_ENDPOINT'}, 404)
        if delay: time.sleep(delay)
        self.reply(result)
http = ThreadingHTTPServer(('0.0.0.0', 8080), Handler)
threading.Thread(target=http.serve_forever, daemon=True).start()
https = ThreadingHTTPServer(('0.0.0.0', 8443), Handler)
ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
certs = list(Path('/run/giobby').glob('*.crt')); cert = next(p for p in certs if p.name != 'ca.crt')
ctx.load_cert_chain(str(cert), str(cert.with_suffix('.key')))
https.socket = ctx.wrap_socket(https.socket, server_side=True)
https.serve_forever()
