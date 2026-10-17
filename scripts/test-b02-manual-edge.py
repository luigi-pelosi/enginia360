#!/usr/bin/env python3
"""Exercise the manual nginx diagnostic boundary, never the direct API.

Usage: python3 scripts/test-b02-manual-edge.py [base-url]
"""
import sys
import unittest
import urllib.error
import urllib.request

BASE_URL = (sys.argv.pop(1) if len(sys.argv) > 1 else "http://127.0.0.1:18082").rstrip("/")


class ManualDiagnosticBoundaryTests(unittest.TestCase):
    def test_diagnostic_variants_are_nginx_404_not_backend_responses(self):
        paths = (
            "/api/v1/organization/database-session",
            "/api/v1/organization/Database-session",
            "/API/V1/ORGANIZATION/DATABASE-SESSION",
            "/api/v1/organization/DATABASE-SESSION",
        )
        for path in paths:
            for suffix in ("", "/", "/nested"):
                with self.subTest(path=path + suffix):
                    try:
                        response = urllib.request.urlopen(BASE_URL + path + suffix, timeout=10)
                    except urllib.error.HTTPError as error:
                        response = error
                    with response:
                        body = response.read().decode()
                        self.assertEqual(response.code, 404, "must be denied at nginx, not backend 401")
                        self.assertIn("text/html", response.headers.get("Content-Type", ""))
                        self.assertIn("<center>nginx</center>", body)
                        self.assertIsNone(response.headers.get("X-Correlation-ID"))


if __name__ == "__main__":
    unittest.main()
