"""Percorso browser reale della foundation con account temporaneo dedicato."""

import json
import os
from pathlib import Path
import secrets
import uuid
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright, expect

BASE = os.environ.get('ENGINIA360_BROWSER_BASE', 'https://vmi3659251.tailfcced0.ts.net:8080')
SECRET = Path(os.environ['ENGINIA360_TEST_CREDENTIALS'])
EVIDENCE = Path(os.environ.get('ENGINIA360_EVIDENCE', '/root/.hermes/cache/scratch/enginia360-app-evidence'))
EVIDENCE.mkdir(parents=True, exist_ok=True)
credentials = json.loads(SECRET.read_text())
created = []
errors = []

with sync_playwright() as p:
    browser = p.chromium.launch(
        executable_path=os.environ.get('ENGINIA360_CHROMIUM', '/root/.hermes/tools/chromium-1208/chrome-linux64/chrome'),
        headless=True, args=['--no-sandbox'],
    )
    context = browser.new_context(viewport={'width': 1440, 'height': 1000}, locale='it-IT')
    page = context.new_page()
    page.on('pageerror', lambda error: errors.append(str(error)))
    try:
        page.goto(BASE, wait_until='networkidle')
        expect(page.get_by_role('heading', name='Accedi', exact=True)).to_be_visible()
        page.locator('#username').fill(credentials['username'])
        page.locator('#password').fill(credentials['password'])
        page.get_by_role('button', name='Accedi', exact=True).click()
        page.wait_for_function("document.querySelector('#current-password') || document.querySelector('.app-shell, [data-slot=sidebar-wrapper]')")
        if page.locator('#current-password').count():
            new_password = secrets.token_urlsafe(24)
            page.locator('#current-password').fill(credentials['password'])
            page.locator('#new-password').fill(new_password)
            page.locator('#confirm-password').fill(new_password)
            page.get_by_role('button', name='Salva', exact=True).click()
            expect(page.locator('.app-shell, [data-slot=sidebar-wrapper]')).to_be_visible()
            credentials['password'] = new_password
            SECRET.write_text(json.dumps(credentials))
        expect(page.locator('.app-shell, [data-slot=sidebar-wrapper]')).to_be_visible()
        page.screenshot(path=str(EVIDENCE / 'workspace-empty.png'), full_page=True)

        labels = {}

        def choose(control, value=None, label=None):
            expect(control).to_be_enabled()
            if control.evaluate('(node) => node.tagName') == 'SELECT':
                control.select_option(value=value) if value is not None else control.select_option(label=label)
            else:
                control.click()
                page.get_by_role('option', name=label or labels[value], exact=True).click()

        def create(resource, label, values):
            page.locator('nav').get_by_role('button', name=label, exact=True).click()
            page.get_by_role('button', name='Nuovo', exact=True).first.click()
            dialog = page.get_by_role('dialog')
            expect(dialog).to_be_visible()
            for field, value in values.items():
                control = dialog.locator('#field-' + field)
                if control.evaluate('(node) => node.tagName') == 'SELECT' or control.get_attribute('role') == 'combobox':
                    choose(control, value=value)
                else:
                    control.fill(value)
            with page.expect_response(lambda response: urlparse(response.url).path == '/api/data/' + resource and response.request.method == 'POST') as response_info:
                dialog.get_by_role('button', name='Salva', exact=True).click()
            response = response_info.value
            assert response.status == 201, (resource, response.status)
            record = response.json()
            labels[record['id']] = str(record.get('name') or ' '.join(str(record.get(key) or '') for key in ('first_name', 'last_name')).strip() or record.get('username') or record.get('key') or record.get('code') or record['id'])
            created.append({'resource': resource, 'id': record['id']})
            (EVIDENCE / 'browser-created.json').write_text(json.dumps(created))
            expect(page.get_by_role('dialog')).to_have_count(0)
            return record['id']

        code = 'qa-ui-' + uuid.uuid4().hex[:10]
        tenant = create('tenants', 'Organizzazioni', {'code': code, 'name': 'Organizzazione verifica'})
        tenant_select = page.locator('#tenant-select')
        if tenant_select.evaluate('(node) => node.tagName') == 'SELECT':
            expect(tenant_select).to_have_value(tenant)
        else:
            expect(tenant_select).to_contain_text(labels[tenant])
        company = create('companies', 'Aziende', {'code': 'main', 'name': 'Società verifica'})
        site = create('sites', 'Sedi', {'company_id': company, 'code': 'hq', 'name': 'Sede legale', 'site_type': 'LEGAL', 'address': 'Via QA 1', 'city': 'Roma', 'province': 'RM', 'postal_code': '00100', 'country_code': 'IT'})
        kind = create('warehouse-types', 'Tipi di magazzino', {'code': 'returns', 'name': 'Resi'})
        warehouse = create('warehouses', 'Magazzini', {'site_id': site, 'warehouse_type_id': kind, 'code': 'main', 'name': 'Magazzino resi'})
        create('warehouse-locations', 'Ubicazioni', {'warehouse_id': warehouse, 'code': 'a1', 'name': 'Scaffale A1'})
        user = create('users', 'Utenti', {'username': 'operator', 'first_name': 'Operatore', 'last_name': 'verifica', 'email': 'operator@example.invalid'})
        group = create('groups', 'Gruppi', {'code': 'operators', 'name': 'Operatori verifica'})
        role = create('roles', 'Ruoli', {'code': 'reader', 'name': 'Lettura società'})
        permission = create('permissions', 'Permessi', {'code': 'companies.read', 'name': 'Lettura società'})

        for label, record_name, relation_label, target_name in (
            ('Ruoli', 'Lettura società', 'Permessi del ruolo', 'Lettura società'),
            ('Gruppi', 'Operatori verifica', 'Utenti del gruppo', 'Operatore verifica'),
            ('Gruppi', 'Operatori verifica', 'Ruoli del gruppo', 'Lettura società'),
            ('Utenti', 'Operatore verifica', 'Ruoli utente', 'Lettura società'),
        ):
            page.locator('nav').get_by_role('button', name=label, exact=True).click()
            page.get_by_role('button', name='Modifica ' + record_name, exact=True).click()
            dialog = page.get_by_role('dialog')
            section = dialog.locator('section').filter(has=page.get_by_role('heading', name=relation_label, exact=True))
            section.get_by_role('checkbox', name=target_name, exact=False).check()
            with page.expect_response(lambda response: '/api/links/' in response.url and response.request.method == 'PUT') as response_info:
                section.get_by_role('button', name='Salva · ' + relation_label, exact=True).click()
            assert response_info.value.status == 204
            dialog.get_by_role('button', name='Annulla', exact=True).click()

        page.locator('nav').get_by_role('button', name='Aziende', exact=True).click()
        page.get_by_role('button', name='Modifica Società verifica', exact=True).click()
        dialog = page.get_by_role('dialog')
        dialog.locator('#field-name').fill('Società aggiornata')
        with page.expect_response(lambda response: '/api/data/companies/' in response.url and response.request.method == 'PUT') as response_info:
            dialog.get_by_role('button', name='Salva', exact=True).click()
        assert response_info.value.status == 200
        expect(page.get_by_role('dialog')).to_have_count(0)
        expect(page.locator('tbody')).to_contain_text('Società aggiornata')
        page.reload(wait_until='networkidle')
        choose(page.locator('#tenant-select'), value=tenant)
        page.locator('nav').get_by_role('button', name='Aziende', exact=True).click()
        expect(page.locator('tbody')).to_contain_text('Società aggiornata')
        page.screenshot(path=str(EVIDENCE / 'workspace-desktop.png'), full_page=True)
        choose(page.get_by_role('combobox', name='Lingua', exact=True), label='English')
        expect(page.locator('html')).to_have_attribute('lang', 'en')
        expect(page.locator('nav').get_by_role('button', name='Companies', exact=True)).to_be_visible()
        page.set_viewport_size({'width': 390, 'height': 844})
        page.get_by_role('button', name='Menu', exact=True).click()
        expect(page.locator('nav').get_by_role('button', name='Users', exact=True)).to_be_visible()
        if page.get_by_role('dialog').count():
            page.keyboard.press('Escape')
            expect(page.get_by_role('dialog')).to_have_count(0)
        else:
            page.locator('aside').get_by_role('button', name='Close', exact=True).click()
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        page.screenshot(path=str(EVIDENCE / 'workspace-mobile.png'), full_page=True)
        page.get_by_role('button', name='Sign out', exact=True).click()
        expect(page.locator('#username')).to_be_visible()
        assert not errors, errors
        print(json.dumps({'browser': 'Chromium', 'origin': BASE, 'created_resources': len(created), 'relation_editors': 4, 'update_persisted': True, 'locales': ['it', 'en'], 'mobile_overflow': False, 'javascript_errors': errors}))
    except Exception:
        page.screenshot(path=str(EVIDENCE / 'browser-failure.png'), full_page=True)
        raise
    finally:
        context.close()
        browser.close()
