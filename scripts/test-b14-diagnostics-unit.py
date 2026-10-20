#!/usr/bin/env python3
"""Unit mutations of the log validator; these are not runtime evidence."""
import json
import os
import subprocess
import sys
import unittest

class DiagnosticsValidatorTests(unittest.TestCase):
    def validate(self, mutation=None):
        rows = [dict(EventId=e, State={}, Scopes=[dict(CorrelationId='c'+str(n), TraceId='a'*32, SpanId='b'*16)])
                for n,e in enumerate([404,312,313,314,314,314,314])]
        if mutation:
            mutation(rows)
        return subprocess.run([sys.executable,'scripts/test-b14-diagnostics.py'],
            input='\n'.join(json.dumps(row) for row in rows), text=True, capture_output=True,
            env=os.environ | {'B02_DB_PASSWORD':'ephemeral-validator-secret'}).returncode
    def test_valid_technical_diagnostics(self):
        self.assertEqual(0,self.validate())
    def test_rejects_credentials(self):
        self.assertNotEqual(0,self.validate(lambda r:r[0].update(Message='ephemeral-validator-secret')))
    def test_rejects_business_payload_in_audit(self):
        self.assertNotEqual(0,self.validate(lambda r:r[0]['State'].update(AccountCode='120100',Amount='200.69')))
    def test_rejects_absent_trace(self):
        self.assertNotEqual(0,self.validate(lambda r:[x.update(Scopes=[dict(CorrelationId='c'+str(n))]) for n,x in enumerate(r)]))
if __name__=='__main__':
    unittest.main()
