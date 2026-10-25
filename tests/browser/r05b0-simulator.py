#!/usr/bin/env python3
"""Test-only traffic observer around the existing synthetic protocol; counts even failed/unknown paths."""
import runpy
import threading
from http.server import ThreadingHTTPServer
protocol = runpy.run_path('/simulator/administrative-simulator.py')
traffic = []
traffic_lock = threading.Lock()

class Observer(protocol['Handler']):
    def do_GET(self):
        if self.path == '/control/traffic':
            with traffic_lock:
                return protocol['reply'](self, 200, {'traffic': list(traffic)})
        if not self.path.startswith(('/control/', '/health')):
            with traffic_lock: traffic.append({'method': 'GET', 'path': self.path})
        return super().do_GET()

    def do_POST(self):
        if not self.path.startswith('/control/'):
            with traffic_lock: traffic.append({'method': 'POST', 'path': self.path})
        return super().do_POST()

ThreadingHTTPServer(('0.0.0.0', 8080), Observer).serve_forever()
