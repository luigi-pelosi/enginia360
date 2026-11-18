"""Contratto ristretto per la sola baseline di nuove installazioni."""
from pathlib import Path
import unittest
import dbbaseline

ROOT = Path(__file__).resolve().parents[2]


class PortableBaselineTests(unittest.TestCase):
    def test_baseline_has_no_personal_role(self):
        source = (ROOT / 'database/foundation.sql').read_text()
        self.assertNotIn('luigi_pelosi', source)
        self.assertIn("current_user <> 'postgres'", source)
        self.assertIn("rolname = 'enginia360_app'", source)

    def test_only_exact_personal_grants_are_removed(self):
        grants = ('GRANT USAGE ON SCHEMA foundation TO luigi_pelosi;\n'
                  'GRANT SELECT ON TABLE foundation.audit_event TO luigi_pelosi;\n')
        kept = ('-- ACL luigi_pelosi must not be hidden\n'
                'GRANT SELECT ON TABLE foundation.tenant TO enginia360_app;\n'
                'GRANT SELECT ON TABLE foundation.tenant TO PUBLIC;\n'
                'GRANT SELECT ON TABLE foundation.tenant TO luigi_pelosi_extra;\n'
                'GRANT SELECT ON TABLE foundation.tenant TO luigi_pelosi, other;\n'
                'GRANT SELECT ON TABLE other.tenant TO luigi_pelosi;\n'
                'ALTER TABLE foundation.tenant OWNER TO luigi_pelosi;\n'
                'REVOKE SELECT ON TABLE foundation.tenant FROM luigi_pelosi;\n'
                "COMMENT ON TABLE foundation.tenant IS 'TO luigi_pelosi;';\n")
        self.assertEqual(dbbaseline.normalize_product_dump(grants + kept), kept)
        self.assertEqual(dbbaseline.normalize_dump(grants + kept), grants + kept)
        for mutation in (kept.replace('TO enginia360_app', 'TO other'),
                         kept.replace('OWNER TO luigi_pelosi', 'OWNER TO postgres'),
                         kept.replace('SELECT', 'ALL'),
                         kept.replace('-- ACL luigi_pelosi must not be hidden\n', '')):
            self.assertNotEqual(dbbaseline.normalize_product_dump(kept),
                                dbbaseline.normalize_product_dump(mutation))


if __name__ == '__main__':
    unittest.main(verbosity=2)
