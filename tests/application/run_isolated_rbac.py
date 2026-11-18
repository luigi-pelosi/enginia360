"""Runner locale: origine logica HTTPS, trasporto HTTP limitato alla copia isolata.

Non costituisce una prova TLS. L'ingresso HTTPS reale va verificato separatamente.
"""
import http.client
import json
import os
from pathlib import Path
import secrets
import sys
import unittest
import urllib.request

ORIGIN = 'https://vmi3659251.tailfcced0.ts.net:8080'
os.environ.update(ENGINIA360_TEST_BASE=ORIGIN, ENGINIA360_TEST_ORIGIN=ORIGIN,
                  ENGINIA360_TEST_CREDENTIALS='/root/.config/enginia360/rbac/bootstrap.json',
                  ENGINIA360_DB_CONTAINER='enginia360-rbac-db',
                  ENGINIA360_DB_DATABASE='enginia360_rbac_api')


class IsolatedTransport(urllib.request.HTTPSHandler):
    def https_open(self, request):
        if request.host != 'vmi3659251.tailfcced0.ts.net:8080':
            raise RuntimeError('Host esterno non ammesso dal runner isolato')
        return self.do_open(lambda host, **kwargs: http.client.HTTPConnection('127.0.0.1', 18082, **kwargs), request)


original = urllib.request.build_opener
urllib.request.build_opener = lambda *handlers: original(IsolatedTransport(), *handlers)
from test_api import Client

def main():
    credentials_path = Path(os.environ['ENGINIA360_TEST_CREDENTIALS'])
    credentials = json.loads(credentials_path.read_text())
    client = Client()
    status, session = client.login(credentials)
    if status != 200:
        raise RuntimeError('Autenticazione QA isolata fallita')
    if session['mustChangePassword']:
        updated = secrets.token_urlsafe(28)
        if client.request('/api/auth/password', 'PUT', {
            'currentPassword': credentials['password'], 'newPassword': updated,
        })[0] != 204:
            raise RuntimeError('Attivazione QA isolata fallita')
        credentials['password'] = updated
        credentials_path.write_text(json.dumps(credentials))

    names = sys.argv[1:] or ['test_granular_rbac']
    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(name) for name in names)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if result.skipped:
        raise RuntimeError('Una prova richiesta è stata saltata')
    return not result.wasSuccessful()


if __name__ == '__main__':
    raise SystemExit(main())
