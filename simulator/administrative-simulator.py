#!/usr/bin/env python3
"""Deterministic simulated external administrative system, contract v1. Synthetic tests only.

State is in memory by design: it represents the remote system, not Enginia360 persistence.
Acquisition ("Received") is distinct from completed processing ("Completed" with a stable
external reference) and from a business refusal ("Rejected"), as decided in D40.
"""
import json
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

UUID = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
MODES = {'complete', 'receive', 'reject', 'unavailable', 'lost-response', 'hold-response'}
lock = threading.Lock()
state = {'mode': 'complete', 'sequence': 0, 'requests': {}, 'rejected_posts': 0}


def reply(handler, status, body):
    data = json.dumps(body).encode()
    handler.send_response(status)
    handler.send_header('Content-Type', 'application/json')
    handler.send_header('Content-Length', str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def outcome(entry):
    body = {'requestId': entry['requestId'], 'status': entry['status']}
    if entry['status'] == 'Completed': return 200, body | {'externalReference': entry['externalReference']}
    if entry['status'] == 'Rejected': return 422, body | {'code': entry['code']}
    return 202, body


def complete(entry):
    state['sequence'] += 1
    entry['status'], entry['externalReference'] = 'Completed', 'AMM-SIM-%06d' % state['sequence']


class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def log_message(self, *args):
        pass  # No request payloads in logs.

    def body(self):
        length = int(self.headers.get('Content-Length') or 0)
        if length <= 0 or length > 65536: return None
        try: return json.loads(self.rfile.read(length))
        except ValueError: return None

    def do_GET(self):
        if self.path == '/health': return reply(self, 200, {'status': 'ok'})
        if self.path == '/control/inflight': return reply(self, 200, {'requestId': state.get('inflight')})
        if self.path == '/control/requests':
            with lock: return reply(self, 200, {'mode': state['mode'], 'requests': list(state['requests'].values())})
        match = re.fullmatch(r'/v1/administrative-requests/([0-9a-f-]{36})', self.path)
        if not match: return reply(self, 404, {'status': 'NotFound'})
        with lock:
            if state['mode'] == 'unavailable': return reply(self, 503, {'status': 'Unavailable'})
            entry = state['requests'].get(match.group(1))
            if entry is None: return reply(self, 404, {'requestId': match.group(1), 'status': 'NotFound'})
            entry['statusQueries'] += 1
            return reply(self, *outcome(entry))

    def do_POST(self):
        payload = self.body()
        if self.path == '/control/mode':
            if not isinstance(payload, dict) or payload.get('mode') not in MODES: return reply(self, 400, {'status': 'Invalid'})
            with lock: state['mode'] = payload['mode']
            return reply(self, 200, {'mode': payload['mode']})
        match = re.fullmatch(r'/control/(complete|reject)/([0-9a-f-]{36})', self.path)
        if match:
            with lock:
                entry = state['requests'].get(match.group(2))
                if entry is None or entry['status'] != 'Received': return reply(self, 409, {'status': 'Conflict'})
                if match.group(1) == 'complete': complete(entry)
                else: entry['status'], entry['code'] = 'Rejected', 'synthetic_refusal'
                return reply(self, *outcome(entry))
        if self.path != '/v1/administrative-requests': return reply(self, 404, {'status': 'NotFound'})
        if not isinstance(payload, dict) or payload.get('contractVersion') != 1 or not UUID.match(str(payload.get('requestId', ''))) \
                or self.headers.get('Idempotency-Key') != payload['requestId']:
            return reply(self, 400, {'status': 'Invalid'})
        with lock:
            if state['mode'] == 'unavailable':
                state['rejected_posts'] += 1
                return reply(self, 503, {'status': 'Unavailable'})
            entry = state['requests'].get(payload['requestId'])
            if entry is not None:
                # Receiver-side deduplication: an identical retry returns the original outcome, never a second effect.
                entry['posts'] += 1
                if entry['payload'] != payload: return reply(self, 409, {'requestId': payload['requestId'], 'status': 'Conflict'})
                return reply(self, *outcome(entry))
            entry = {'requestId': payload['requestId'], 'payload': payload, 'posts': 1, 'statusQueries': 0, 'status': 'Received'}
            state['requests'][payload['requestId']] = entry
            if state['mode'] in {'complete', 'lost-response', 'hold-response'}: complete(entry)
            elif state['mode'] == 'reject': entry['status'], entry['code'] = 'Rejected', 'synthetic_refusal'
            if state['mode'] == 'hold-response':
                state['inflight'] = entry['requestId']
                threading.Event().wait(12)  # Fault boundary: receiver committed, sender can be killed before response.
                self.close_connection = True
                return
            if state['mode'] == 'lost-response':
                # Deterministic T06 fault: business effect committed, response lost before any bytes.
                import socket
                self.close_connection = True
                self.connection.shutdown(socket.SHUT_RDWR)
                return
            return reply(self, *outcome(entry))


if __name__ == '__main__':
    ThreadingHTTPServer(('0.0.0.0', 8080), Handler).serve_forever()
