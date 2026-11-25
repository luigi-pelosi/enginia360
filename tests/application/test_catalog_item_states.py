"""Accettazione HTTP mirata del ciclo ACTIVE/SUSPENDED/ARCHIVED su fixture isolata."""
from test_catalog_items_http import CatalogItemsHttp

HTTP_CASES = (
    'test_required_fields_are_identical_on_create_and_update',
    'test_existing_incomplete_record_requires_completion_without_silent_backfill',
    'test_active_default_for_goods_and_services_and_required_references',
    'test_only_current_statuses_and_no_archived_creation',
    'test_suspend_reactivate_archive_with_atomic_general_values',
    'test_initial_suspension_permissions_and_code_until_first_activation',
    'test_exact_transition_permissions_stale_versions_and_terminal_archive',
    'test_failed_archive_audit_rolls_back_general_status_and_physical_data',
)


class CatalogItemStateHttp(CatalogItemsHttp):
    def test_existing_incomplete_record_requires_completion_without_silent_backfill(self):
        from catalog_items_helpers import fixture_sql
        row = self.save(status='SUSPENDED')
        fixture_sql(f"UPDATE masterdata.catalog_item SET category_id=NULL,version=version+1 WHERE id='{row['id']}' AND tenant_id='{self.tenant_id}'")
        legacy = self.req('items', row['id'])
        self.assertIsNone(legacy['category_id'])
        self.save(legacy, {'description': 'Cannot preserve an incomplete general record'}, expected=400)
        for status in ('ACTIVE', 'ARCHIVED'):
            self.req('items', row['id'] + '/status', 'PUT', {'status': status, 'expectedVersion': legacy['version']}, 400)
        self.assertEqual(self.req('items', row['id']), legacy)
        fixed = self.save(legacy, {'category_id': self.category['id']})
        self.assertEqual(fixed['status'], 'SUSPENDED')
        self.assertEqual(fixed['version'], legacy['version'] + 1)

    def test_required_fields_are_identical_on_create_and_update(self):
        for kind in (self.good, self.service):
            for status in ('ACTIVE', 'SUSPENDED'):
                values = self.values(item_type_id=kind['id'])
                row = self.save(values=values, status=status)
                counter = self.req('numbering', kind=row['kind'])
                for field in ('name', 'item_type_id', 'category_id', 'base_uom_id'):
                    for invalid in (None, ''):
                        create_status, create_error = self.root.request(self.path('items'), 'POST', {'values': values | {field: invalid}, 'status': status})
                        update_status, update_error = self.root.request(self.path('items', row['id']), 'PUT', {'values': {field: invalid}, 'expectedVersion': row['version']})
                        self.assertEqual((create_status, update_status), (400, 400), field)
                        self.assertEqual(create_error, update_error, field)
                        self.assertEqual(create_error.get('field'), field)
                self.assertEqual(self.req('items', row['id']), row)
                self.assertEqual(self.req('numbering', kind=row['kind']), counter)
                saved = self.save(row, {'description': 'Partial update retains mandatory references'})
                self.assertEqual(saved['category_id'], row['category_id'])
                self.assertEqual(saved['base_uom_id'], row['base_uom_id'])

    def save(self, row=None, values=None, status=None, expected=200, **extra):
        body = {'values': values if values is not None else self.values(), **extra}
        if row is not None:
            body['expectedVersion'] = row['version']
        if status is not None:
            body['status'] = status
        return self.req('items', row['id'] if row else None, 'PUT' if row else 'POST', body,
                        expected if row else (201 if expected == 200 else expected))

    def test_active_default_for_goods_and_services_and_required_references(self):
        for kind in (self.good, self.service):
            row = self.save(values=self.values(item_type_id=kind['id']))
            self.full(row)
            self.assertEqual(row['status'], 'ACTIVE')
            self.assertIsNotNone(row['activated_at'])
        before = self.req('numbering', kind='GOOD')
        self.save(values={'name': 'Incomplete', 'item_type_id': self.good['id']}, expected=400)
        self.assertEqual(self.req('numbering', kind='GOOD'), before)

    def test_only_current_statuses_and_no_archived_creation(self):
        before = self.req('numbering', kind='GOOD')
        for status in ('DRAFT', 'INACTIVE', 'ARCHIVED'):
            self.save(status=status, expected=400)
        self.assertEqual(self.req('numbering', kind='GOOD'), before)
        for status in ('DRAFT', 'INACTIVE'):
            self.req('items', status=status, expected=400)
        row = self.save(status='SUSPENDED')
        self.assertIsNone(row['activated_at'])
        for status in ('DRAFT', 'INACTIVE'):
            self.save(row, {'name': 'Rejected'}, status, expected=400)
            self.req('items', row['id'] + '/status', 'PUT', {'status': status, 'expectedVersion': row['version']}, 400)
        self.assertEqual(self.req('items', row['id']), row)

    def test_suspend_reactivate_archive_with_atomic_general_values(self):
        row = self.save()
        activated = row['activated_at']
        self.save(row, {'category_id': None}, 'SUSPENDED', expected=400, physicalData=self.physical())
        self.assertEqual(self.req('items', row['id']), row)
        row = self.save(row, {'name': 'Suspended edited'}, 'SUSPENDED', physicalData=self.physical())
        self.assertEqual((row['status'], row['name'], row['activated_at']), ('SUSPENDED', 'Suspended edited', activated))
        self.assertIsNotNone(row['physicalData'])
        self.assertEqual(row['category_id'], self.category['id'])
        preserved = self.save(row, {'description': 'No status supplied'})
        self.assertEqual(preserved['status'], 'SUSPENDED')
        self.save(preserved, {'category_id': None}, 'ACTIVE', expected=400)
        self.assertEqual(self.req('items', row['id']), preserved)
        row = self.save(preserved, {'name': 'Reactivated', 'category_id': self.category['id']}, 'ACTIVE')
        self.assertEqual(row['activated_at'], activated)
        before = row
        self.save(row, {'category_id': None}, 'ARCHIVED', expected=400, physicalData=None)
        self.assertEqual(self.req('items', row['id']), row)
        row = self.save(row, {'description': 'Archived atomically'}, 'ARCHIVED', physicalData=None)
        self.assertEqual(row['version'], before['version'] + 1)
        self.assertEqual(row['status'], 'ARCHIVED')
        self.assertIsNone(row['physicalData'])
        self.assertEqual(row['category_id'], self.category['id'])
        self.assertEqual(row['description'], 'Archived atomically')
        self.save(row, {'name': 'Forbidden'}, 'ACTIVE', expected=409)
        self.assertEqual(self.req('items', row['id']), row)

    def test_initial_suspension_permissions_and_code_until_first_activation(self):
        self.manual()
        actor, _, _ = self.actor(['catalog-items.read', 'catalog-items.create'])
        body = {'values': self.values(code='NOACTIVATE')}
        self.assertEqual(actor.request(self.path('items'), 'POST', body)[0], 403)
        body['status'] = 'SUSPENDED'
        code, row = actor.request(self.path('items'), 'POST', body)
        self.assertEqual(code, 201, row)
        self.assertEqual(row['status'], 'SUSPENDED')
        self.assertIsNone(row['activated_at'])
        row = self.save(row, {'code': 'BEFOREFIRSTACTIVATION'})
        row = self.save(row, {'name': 'First activation'}, 'ACTIVE')
        self.assertIsNotNone(row['activated_at'])
        row = self.save(row, {'description': 'Suspend again'}, 'SUSPENDED')
        self.save(row, {'code': 'MUST-NOT-CHANGE'}, expected=409)
        self.assertEqual(self.req('items', row['id']), row)

    def test_exact_transition_permissions_stale_versions_and_terminal_archive(self):
        row = self.save()
        updater, _, _ = self.actor(['catalog-items.read', 'catalog-items.update'])
        payload = {'values': {'name': 'No transition grant'}, 'status': 'SUSPENDED', 'expectedVersion': row['version']}
        self.assertEqual(updater.request(self.path('items', row['id']), 'PUT', payload)[0], 403)
        self.assertEqual(self.req('items', row['id']), row)
        changed = self.save(row, {'name': 'Winner'}, 'SUSPENDED')
        self.save(row, {'name': 'Stale'}, 'ARCHIVED', expected=409)
        self.assertEqual(self.req('items', row['id']), changed)
        archived = self.save(changed, {'name': 'Final'}, 'ARCHIVED')
        for target in ('ACTIVE', 'SUSPENDED'):
            self.save(archived, {'name': 'Cannot reactivate'}, target, expected=409)
            self.req('items', archived['id'] + '/status', 'PUT', {'status': target, 'expectedVersion': archived['version']}, 409)
        self.child(archived, 'identifiers', self.identifier('Forbidden'), expected=409)
        self.assertEqual(self.req('items', archived['id']), archived)

    def test_failed_archive_audit_rolls_back_general_status_and_physical_data(self):
        from catalog_items_helpers import fixture_sql
        row = self.save(physicalData=self.physical())
        fixture_sql("CREATE FUNCTION foundation.reject_item_state_audit() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN "
                    f"IF NEW.tenant_id='{self.tenant_id}'::uuid AND NEW.action='archive' THEN RAISE EXCEPTION 'state audit proof'; END IF; RETURN NEW; END $$; "
                    "CREATE CONSTRAINT TRIGGER reject_item_state_audit AFTER INSERT ON foundation.audit_event DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION foundation.reject_item_state_audit();")
        try:
            self.save(row, {'name': 'Must roll back'}, 'ARCHIVED', expected=500, physicalData=None)
            self.assertEqual(self.req('items', row['id']), row)
        finally:
            fixture_sql('DROP TRIGGER reject_item_state_audit ON foundation.audit_event; DROP FUNCTION foundation.reject_item_state_audit();')
        archived = self.save(row, {'name': 'Recovered'}, 'ARCHIVED')
        self.assertEqual(archived['status'], 'ARCHIVED')
