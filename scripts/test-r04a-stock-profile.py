#!/usr/bin/env python3
"""Offline stock setup input is explicit, company-scoped, closed, and not counterparties authority."""

import importlib.util
from pathlib import Path
import unittest
import uuid

ROOT = Path(__file__).resolve().parents[1]


class StockProfileInputTests(unittest.TestCase):
    def test_owner_setup_has_a_company_scoped_closed_input_without_implicit_local_profile(
        self,
    ):
        path = ROOT / "scripts/owner-stock-profile.py"
        self.assertTrue(path.exists(), "owner-only stock setup entrypoint is missing")
        spec = importlib.util.spec_from_file_location("stock_owner", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        value = {
            k: str(uuid.uuid4())
            for k in (
                "commandId",
                "tenantId",
                "legalEntityId",
                "actorMembershipId",
                "verificationReference",
                "sourceId",
                "profileId",
            )
        }
        value.update(
            domain="stock", direction="Enginia360ToExternal", expectedVersion=0
        )
        self.assertEqual(module.validate(value), value)
        for change in (
            {"domain": "counterparties"},
            {"domain": "inventory"},
            {"expectedVersion": 1},
            {"expectedVersion": True},
            {"direction": None},
            {"direction": "both"},
            {"legalEntityId": str(uuid.UUID(int=0))},
            {"companyIds": [value["legalEntityId"]]},
            {"legalEntityId": value["legalEntityId"].upper()},
        ):
            with self.subTest(change=change), self.assertRaises(ValueError):
                module.validate({**value, **change})
        for key in value:
            with self.subTest(missing=key), self.assertRaises(ValueError):
                module.validate({k: v for k, v in value.items() if k != key})


if __name__ == "__main__":
    unittest.main()
