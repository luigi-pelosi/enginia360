"""Verifiche locali dello schema foundation su PostgreSQL reale."""

import os
import subprocess
import unittest
from pathlib import Path

from dbbaseline import CONTAINER, sql as baseline_sql
ROOT = Path(__file__).resolve().parents[2]
TABLES = (
    "tenant", "company", "site", "warehouse_type", "warehouse",
    "warehouse_location", "user", "user_group", "role",
    "permission", "user_group_member", "user_role", "user_group_role",
    "role_permission", "login_limit", "audit_event",
    "sales_organization", "purchasing_organization",
    "purchasing_organization_company", "purchasing_organization_site",
    "country", "city",
    "business_partner", "business_partner_tax_identifier", "business_partner_address",
    "business_partner_address_usage", "business_partner_contact_channel",
    "numbering_series", "numbering_counter",
    "company_business_partner", "company_business_partner_role", "role_company",
    "currency", "payment_methods", "payment_terms", "payment_term_installments",
    "company_payment_settings", "business_partner_payment_defaults", "fatturapa_payment_codes",
    "catalog_unit_of_measure", "catalog_category", "catalog_item_type",
    "catalog_brand", "catalog_item", "catalog_item_code", "catalog_item_identifier",
    "catalog_item_unit", "catalog_item_physical_data", "catalog_item_company",
    "tax_types", "tax_nature_codes", "tax_codes", "tax_code_versions", "tax_audit_events",
    "item_tax_classifications", "partner_tax_classifications", "item_tax_profiles", "partner_tax_profiles",
    "tax_regimes", "company_tax_configurations", "company_tax_registrations", "company_tax_regime_profiles",
    "tax_rules", "tax_rule_versions", "tax_rule_conditions",
)

def table_schema(name):
    if name.startswith(('tax_', 'company_tax_')) or name in ('item_tax_classifications', 'partner_tax_classifications', 'item_tax_profiles', 'partner_tax_profiles'):
        return 'taxmanagement'
    return 'masterdata' if name.startswith(('business_partner', 'company_business_partner', 'catalog_', 'payment_')) or name in ('company_payment_settings', 'fatturapa_payment_codes') else 'foundation'


def query(sql):
    result = baseline_sql(sql)
    return result.stdout.strip()


def uid(number):
    return f"'00000000-0000-0000-0000-{number:012d}'"


def fixture():
    statements = []
    for number in (1, 2):
        tenant = uid(number)
        statements.extend([
            f"INSERT INTO foundation.tenant (id, code, name) VALUES ({tenant}, 't{number}', 'Cliente');",
            f"INSERT INTO foundation.company (id, tenant_id, code, name) VALUES ({tenant}, {tenant}, 'main', 'Società');",
            f"INSERT INTO foundation.site (id, tenant_id, company_id, code, name, site_type, address, city, province, postal_code, country_code) VALUES ({tenant}, {tenant}, {tenant}, 'hq', 'Sede legale', 'LEGAL', 'Via prova 1', 'Roma', 'RM', '00100', 'IT');",
            f"INSERT INTO foundation.warehouse_type (id, tenant_id, code, name) VALUES ({tenant}, {tenant}, 'main', 'Principale');",
            f"INSERT INTO foundation.warehouse (id, tenant_id, site_id, warehouse_type_id, code, name) VALUES ({tenant}, {tenant}, {tenant}, {tenant}, 'main', 'Magazzino');",
            f"INSERT INTO foundation.warehouse_location (id, tenant_id, warehouse_id, code, name) VALUES ({tenant}, {tenant}, {tenant}, 'a1', 'Scaffale');",
            f"INSERT INTO foundation.\"user\" (id, tenant_id, username, first_name, last_name, email) VALUES ({tenant}, {tenant}, 'mario', 'Mario', 'Rossi', 'mario@example.invalid');",
        ])
        for table in ('user_group', 'role', 'permission'):
            statements.append(
                f"INSERT INTO foundation.{table} (id, tenant_id, code, name) VALUES ({tenant}, {tenant}, 'sample', 'Esempio');"
            )
    statements.extend([
        f"INSERT INTO foundation.company (id, tenant_id, code, name) VALUES ({uid(3)}, {uid(1)}, 'second', 'Altra società');",
        f"INSERT INTO foundation.site (id, tenant_id, company_id, code, name, address, city, province, postal_code, country_code) VALUES ({uid(3)}, {uid(1)}, {uid(3)}, 'hq', 'Altra sede', 'Via prova 1', 'Roma', 'RM', '00100', 'IT');",
    ])
    return '\n'.join(statements)


class FoundationTests(unittest.TestCase):
    def exercise(self, statements):
        return query('BEGIN;\n' + fixture() + '\n' + statements + '\nROLLBACK;')

    def rejects(self, statement, sqlstate):
        self.exercise(
            f"DO $test$ BEGIN {statement}; "
            "RAISE EXCEPTION 'Operazione non valida accettata'; "
            f"EXCEPTION WHEN SQLSTATE '{sqlstate}' THEN NULL; END $test$;"
        )

    def test_valid_organization_and_tenant_rbac(self):
        tenant = uid(1)
        statements = []
        for table, left, right in (
            ('user_group_member', 'user_group_id', 'user_id'),
            ('user_role', 'user_id', 'role_id'),
            ('user_group_role', 'user_group_id', 'role_id'),
            ('role_permission', 'role_id', 'permission_id'),
        ):
            statements.append(
                f"INSERT INTO foundation.{table} (tenant_id, {left}, {right}) VALUES ({tenant}, {tenant}, {tenant});"
            )
        statements.append(f'SELECT count(*) FROM foundation.role_permission WHERE tenant_id = {tenant};')
        self.assertEqual(self.exercise('\n'.join(statements)), '1')

    def test_cross_tenant_links_are_rejected(self):
        first, second = uid(1), uid(2)
        statements = [
            f"INSERT INTO foundation.company (tenant_id, code, name) VALUES ({uid(99)}, 'x', 'X')",
            f"INSERT INTO foundation.site (tenant_id, company_id, code, name, address, city, province, postal_code, country_code) VALUES ({first}, {second}, 'x', 'X', 'Via prova', 'Roma', 'RM', '00100', 'IT')",
            f"INSERT INTO foundation.warehouse (tenant_id, site_id, warehouse_type_id, code, name) VALUES ({first}, {second}, {first}, 'x', 'X')",
            f"INSERT INTO foundation.warehouse (tenant_id, site_id, warehouse_type_id, code, name) VALUES ({first}, {first}, {second}, 'x', 'X')",
            f"INSERT INTO foundation.warehouse_location (tenant_id, warehouse_id, code, name) VALUES ({first}, {second}, 'x', 'X')",
            f"INSERT INTO foundation.\"user\" (tenant_id, username, first_name, last_name, email) VALUES ({uid(99)}, 'x', 'Nome', 'Cognome', 'x@example.invalid')",
        ]
        for table, left, right in (
            ('user_group_member', 'user_group_id', 'user_id'),
            ('user_role', 'user_id', 'role_id'),
            ('user_group_role', 'user_group_id', 'role_id'),
            ('role_permission', 'role_id', 'permission_id'),
        ):
            for left_id, right_id in ((first, second), (second, first)):
                statements.append(
                    f"INSERT INTO foundation.{table} (tenant_id, {left}, {right}) VALUES ({first}, {left_id}, {right_id})"
                )
        for statement in statements:
            with self.subTest(statement=statement):
                self.rejects(statement, '23503')

    def test_setting_is_not_an_installed_resource(self):
        self.assertEqual(query("SELECT to_regclass('foundation.setting') IS NULL"), 't')

    def test_codes_are_unique_in_their_own_scope(self):
        tenant = uid(1)
        statements = [
            "INSERT INTO foundation.tenant (code, name) VALUES ('t1', 'Duplicato')",
            f"INSERT INTO foundation.company (tenant_id, code, name) VALUES ({tenant}, 'main', 'Duplicato')",
            f"INSERT INTO foundation.site (tenant_id, company_id, code, name, address, city, province, postal_code, country_code) VALUES ({tenant}, {tenant}, 'hq', 'Duplicato', 'Via prova', 'Roma', 'RM', '00100', 'IT')",
            f"INSERT INTO foundation.warehouse_type (tenant_id, code, name) VALUES ({tenant}, 'main', 'Duplicato')",
            f"INSERT INTO foundation.warehouse (tenant_id, site_id, warehouse_type_id, code, name) VALUES ({tenant}, {tenant}, {tenant}, 'main', 'Duplicato')",
            f"INSERT INTO foundation.warehouse_location (tenant_id, warehouse_id, code, name) VALUES ({tenant}, {tenant}, 'a1', 'Duplicato')",
            f"INSERT INTO foundation.\"user\" (tenant_id, username, first_name, last_name, email) VALUES ({tenant}, 'MARIO', 'Mario', 'Duplicato', 'other@example.invalid')",
        ]
        for table in ('user_group', 'role', 'permission'):
            statements.append(f"INSERT INTO foundation.{table} (tenant_id, code, name) VALUES ({tenant}, 'sample', 'Duplicato')")
        for statement in statements:
            with self.subTest(statement=statement):
                self.rejects(statement, '23505')

    def test_duplicate_rbac_associations_are_rejected(self):
        tenant = uid(1)
        for table, left, right in (
            ('user_group_member', 'user_group_id', 'user_id'),
            ('user_role', 'user_id', 'role_id'),
            ('user_group_role', 'user_group_id', 'role_id'),
            ('role_permission', 'role_id', 'permission_id'),
        ):
            statement = f"INSERT INTO foundation.{table} (tenant_id, {left}, {right}) VALUES ({tenant}, {tenant}, {tenant})"
            with self.subTest(table=table):
                self.rejects(statement + '; ' + statement, '23505')

    def test_customer_can_create_additional_warehouse_types(self):
        tenant = uid(1)
        self.assertEqual(self.exercise(
            f"INSERT INTO foundation.warehouse_type (tenant_id, code, name) VALUES ({tenant}, 'returns', 'Resi'), ({tenant}, 'remanufactured', 'Rigenerati'); "
            f"SELECT count(*) FROM foundation.warehouse_type WHERE tenant_id = {tenant};"
        ), '3')

    def test_referenced_parents_cannot_be_deleted(self):
        self.rejects(f"DELETE FROM foundation.company WHERE id = {uid(1)}", '23503')

    def test_updated_at_is_refreshed(self):
        self.assertEqual(self.exercise(
            f"UPDATE foundation.company SET updated_at = '2000-01-01' WHERE id = {uid(1)}; "
            f"SELECT updated_at > '2000-01-01'::timestamptz FROM foundation.company WHERE id = {uid(1)};"
        ), 't')

    def test_blank_codes_and_names_are_rejected(self):
        for code, name in (("' '", "'Cliente'"), ("'valid'", "' '")):
            with self.subTest(code=code, name=name):
                self.rejects(f"INSERT INTO foundation.tenant (code, name) VALUES ({code}, {name})", '23514')

    def test_required_tables_exist(self):
        for table in TABLES:
            with self.subTest(table=table):
                self.assertEqual(
                    query(f"SELECT to_regclass('{table_schema(table)}.\"{table}\"') IS NOT NULL;"),
                    "t",
                )


if __name__ == "__main__":
    unittest.main()
