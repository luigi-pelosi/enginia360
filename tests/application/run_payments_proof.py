"""Run payments over real HTTP against a disposable PostgreSQL/API fixture.

Requires an already-built backend image. Logical HTTPS uses loopback HTTP, not TLS.
"""
import argparse, http.client, json, os, sys, unittest, urllib.request
from pathlib import Path
import run_business_partner_proof as fixture

fixture.SCOPE='enginia360-payments-http-proof'
fixture.DB=fixture.SCOPE+'-db'
fixture.API=fixture.SCOPE+'-api'
fixture.WEB=fixture.SCOPE+'-web'
fixture.NETWORK=fixture.SCOPE
fixture.INGRESS=fixture.SCOPE+'-ingress'
fixture.EVIDENCE=Path(os.environ.get('TMPDIR','/root/.hermes/cache/scratch'))/fixture.SCOPE

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--backend-image',required=True)
    args=parser.parse_args()
    args.schema=str(fixture.ROOT/'database/foundation.sql'); args.migration=[]; args.frontend_image=None
    try:
        state=fixture.start(args)
        os.environ.update(ENGINIA360_PAYMENTS_PROOF='1',ENGINIA360_TEST_BASE=fixture.ORIGIN,ENGINIA360_TEST_ORIGIN=fixture.ORIGIN,ENGINIA360_TEST_CREDENTIALS=state['credentials'])
        class Local(urllib.request.HTTPSHandler):
            def https_open(self,request):
                if request.host!='business-partner.invalid': raise RuntimeError('non-fixture host')
                return self.do_open(lambda host,**kw:http.client.HTTPConnection('127.0.0.1',state['apiPort'],**kw),request)
        original=urllib.request.build_opener
        urllib.request.build_opener=lambda *handlers:original(Local(),*handlers)
        result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromName('test_payments_http'))
        return 0 if result.wasSuccessful() and not result.skipped else 1
    finally:
        fixture.cleanup()

if __name__=='__main__': raise SystemExit(main())
