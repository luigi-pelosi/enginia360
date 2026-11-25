"""Run finite Catalog ITEMS acceptance against candidate images in tmpfs only."""
import argparse
import json
import unittest
from catalog_items_helpers import fixture, start, install_transport, require_fixture

HTTP_CASES = (
    'test_item_type_filter_pagination_and_isolation',
    'test_inline_status_create_and_update_atomic',
    'test_inline_status_guards_and_rollback',
    'test_atomic_create_full_root_and_child_version_identity',
    'test_numbering_manual_reservations_and_cross_kind_collision',
    'test_numbering_auto_concurrent_and_rollback_counter',
    'test_lifecycle_activation_nature_base_and_terminal_archive',
    'test_inactive_reference_grace_activation_revalidation',
    'test_identifiers_checksum_canonical_uniqueness_primary_search',
    'test_tenant_child_and_reference_isolation',
    'test_item_units_exact_contextual_conversion_and_universal_consistency',
    'test_physical_validation_good_only_and_versioned_removal',
    'test_exact_crud_permissions_options_grants_revocation_and_bypass',
    'test_exact_status_permissions_grants_revocation_separate_from_update',
    'test_csrf_origin_and_all_mutations_require_version',
    'test_deferred_audit_failure_rolls_back_root_children_codes_and_status',
    'test_sql_crossrefs_invariants_append_only_and_runtime_privileges',
)

def parser(browser=False):
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument('--backend-image', default='enginia360-backend:catalog-items-proof')
    result.add_argument('--frontend-image', default='enginia360-frontend:catalog-items-proof' if browser else None)
    result.add_argument('--schema', default=str(fixture.ROOT / 'database/foundation.sql'))
    result.add_argument('--migration', action='append', default=[], help='Ordered SQL; only exact canonical includes expanded')
    result.add_argument('--keep', action='store_true')
    result.add_argument('--reuse', action='store_true')
    result.add_argument('--cleanup', action='store_true')
    return result


def run(browser=False):
    args = parser(browser).parse_args()
    if args.cleanup:
        fixture.cleanup()
        return 0
    summary = {'scope': fixture.SCOPE, 'browser': browser, 'acceptance': 'NONPASS',
               'testsRun': 0, 'skipped': 0, 'tlsProved': False}
    fixture.EVIDENCE.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        state = json.loads((fixture.EVIDENCE / 'state.json').read_text()) if args.reuse else start(args)
        install_transport(state)
        require_fixture(browser)
        if browser:
            from browser_catalog_items_proof import CatalogItemsBrowser, BROWSER_CASES
            case_class, cases = CatalogItemsBrowser, BROWSER_CASES
        else:
            from test_catalog_items_http import CatalogItemsHttp
            case_class, cases = CatalogItemsHttp, HTTP_CASES
        # Explicit names, never module discovery or inherited acceptance cases.
        suite = unittest.TestSuite(case_class(name) for name in cases)
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        passed = result.testsRun == len(cases) and result.wasSuccessful() and not result.skipped
        summary.update(testsRun=result.testsRun, failures=len(result.failures), errors=len(result.errors),
                       skipped=len(result.skipped), cases=list(cases), acceptance='PASS' if passed else 'NONPASS')
        return 0 if passed else 1
    except Exception as error:
        summary['blocker'] = type(error).__name__ + ': ' + str(error)
        raise
    finally:
        (fixture.EVIDENCE / ('browser-result.json' if browser else 'http-result.json')).write_text(json.dumps(summary, indent=2))
        if fixture.verify_target(fixture.API):
            log = fixture.docker('logs', fixture.API, check=False)
            (fixture.EVIDENCE / ('browser-api.log' if browser else 'http-api.log')).write_text(log.stdout + log.stderr)
        if not args.keep:
            fixture.cleanup()


if __name__ == '__main__':
    raise SystemExit(run())
