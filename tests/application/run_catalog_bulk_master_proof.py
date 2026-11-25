"""Runner limitato alle prove di filtri adattivi e tabelle condivise su fixture possedute."""
import json,os,unittest
from catalog_items_helpers import fixture,start,install_transport,require_fixture
from run_catalog_items_proof import parser

def main():
    cli=parser(browser=True);cli.add_argument('--browser',action='store_true',default=True)
    cli.set_defaults(backend_image='enginia360-backend:catalog-bulk-tables-proof',frontend_image='enginia360-frontend:catalog-bulk-master-proof')
    args=cli.parse_args()
    if args.cleanup:fixture.cleanup();return 0
    if not args.browser:args.frontend_image=None
    fixture.EVIDENCE.mkdir(mode=0o700,parents=True,exist_ok=True)
    report={'acceptance':'NONPASS','testsRun':0,'tlsProved':False}
    try:
        state=json.loads((fixture.EVIDENCE/'state.json').read_text()) if args.reuse else start(args)
        install_transport(state);require_fixture(browser=args.browser)
        images={}
        for name,tag in ((fixture.API,args.backend_image),*([(fixture.WEB,args.frontend_image)] if args.browser else [])):
            actual=fixture.docker('inspect','--format','{{.Image}}',name).stdout.strip();expected=fixture.docker('image','inspect','--format','{{.Id}}',tag).stdout.strip()
            if actual!=expected:raise RuntimeError('Candidate/fixture image mismatch: '+name)
            images[name]=actual
        if args.browser:
            os.environ['CATALOG_BROWSER_BACKEND_IMAGE']=args.backend_image;os.environ['CATALOG_BROWSER_FRONTEND_IMAGE']=args.frontend_image
            from browser_catalog_bulk_master import CatalogBulkMasterBrowser as Case,BROWSER_CASES as cases

        result=unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(Case(name) for name in cases))
        passed=result.testsRun==len(cases) and result.wasSuccessful() and not result.skipped
        report.update(acceptance='PASS' if passed else 'NONPASS',testsRun=result.testsRun,skipped=len(result.skipped),failures=len(result.failures),errors=len(result.errors),cases=cases,images=images)
        return 0 if passed else 1
    finally:
        (fixture.EVIDENCE/'bulk-master-browser.json').write_text(json.dumps(report,indent=2))
        if not args.keep:fixture.cleanup()

if __name__=='__main__':raise SystemExit(main())
