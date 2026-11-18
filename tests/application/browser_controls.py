"""Verifica dei controlli shadcn su database e account isolati."""

import json
import os
from pathlib import Path
import secrets
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright, expect

BASE = os.environ['ENGINIA360_BROWSER_BASE']
SECRET = Path(os.environ['ENGINIA360_TEST_CREDENTIALS'])
EVIDENCE = Path(os.environ['ENGINIA360_EVIDENCE'])
credentials = json.loads(SECRET.read_text())
records = json.loads((EVIDENCE / 'browser-created.json').read_text())
tenant_id = next(record['id'] for record in records if record['resource'] == 'tenants')

with sync_playwright() as p:
    browser = p.chromium.launch(
        executable_path='/root/.hermes/tools/chromium-1208/chrome-linux64/chrome',
        headless=True, args=['--no-sandbox'],
    )
    admin_context = browser.new_context(locale='it-IT', viewport={'width': 1440, 'height': 1000})
    page = admin_context.new_page()
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto(BASE, wait_until='networkidle')
    page.locator('#username').fill(credentials['username'])
    page.locator('#password').fill(credentials['password'])
    page.get_by_role('button', name='Accedi', exact=True).click()
    expect(page.locator('[data-slot=sidebar-wrapper]')).to_be_visible()
    page.locator('#tenant-select').click()
    page.get_by_role('option', name='Organizzazione verifica', exact=True).click()

    page.locator('nav').get_by_role('button', name='Sedi', exact=True).click()
    page.get_by_role('button', name='Nuovo', exact=True).first.click()
    dialog = page.get_by_role('dialog')
    dialog.locator('#field-code').fill('not-saved')
    dialog.locator('#field-name').fill('Sede non salvata')
    expect(dialog.get_by_role('button', name='Salva', exact=True)).to_be_disabled()
    dialog.locator('#field-company_id').click()
    page.get_by_role('option', name='Società aggiornata', exact=True).press('Enter')
    expect(dialog.get_by_role('button', name='Salva', exact=True)).to_be_enabled()
    dialog.get_by_role('button', name='Annulla', exact=True).click()

    page.locator('nav').get_by_role('button', name='Tipi di magazzino', exact=True).click()
    page.get_by_role('button', name='Nuovo', exact=True).first.click()
    dialog = page.get_by_role('dialog')
    dialog.locator('#field-code').fill('delete-check')
    dialog.locator('#field-name').fill('Da eliminare')
    dialog.get_by_role('switch').uncheck()
    with page.expect_response(lambda response: urlparse(response.url).path == '/api/data/warehouse-types' and response.request.method == 'POST') as created:
        dialog.get_by_role('button', name='Salva', exact=True).click()
    assert created.value.status == 201 and created.value.json()['is_enabled'] is False
    expect(page.get_by_role('dialog')).to_have_count(0)
    expect(page.locator('tbody tr').filter(has_text='Da eliminare')).to_contain_text('Disattivo')
    page.get_by_role('button', name='Elimina Da eliminare', exact=True).click()
    alert = page.get_by_role('alertdialog')
    alert.get_by_role('button', name='Annulla', exact=True).click()
    expect(page.locator('tbody')).to_contain_text('Da eliminare')
    page.get_by_role('button', name='Elimina Da eliminare', exact=True).click()
    with page.expect_response(lambda response: '/api/data/warehouse-types/' in response.url and response.request.method == 'DELETE') as deleted:
        page.get_by_role('alertdialog').get_by_role('button', name='Elimina', exact=True).click()
    assert deleted.value.status == 204
    expect(page.get_by_role('alertdialog')).to_have_count(0)
    expect(page.locator('tbody')).not_to_contain_text('Da eliminare')

    page.locator('nav').get_by_role('button', name='Impostazioni', exact=True).click()
    page.get_by_role('button', name='Modifica language', exact=True).click()
    dialog = page.get_by_role('dialog')
    dialog.locator('#field-company_id').click()
    page.get_by_role('option', name='—', exact=True).click()
    expect(dialog.locator('#field-site_id')).to_contain_text('—')
    with page.expect_response(lambda response: '/api/data/settings/' in response.url and response.request.method == 'PUT') as changed:
        dialog.get_by_role('button', name='Salva', exact=True).click()
    assert changed.value.status == 200
    assert changed.value.json()['company_id'] is None and changed.value.json()['site_id'] is None

    page.locator('nav').get_by_role('button', name='Utenti', exact=True).click()
    page.get_by_role('button', name='Imposta password Operatore verifica', exact=True).click()
    dialog = page.get_by_role('dialog')
    initial_password = secrets.token_urlsafe(24)
    dialog.locator('#new-password').fill(initial_password)
    dialog.locator('#confirm-password').fill(initial_password)
    with page.expect_response(lambda response: '/api/users/' in response.url and response.request.method == 'PUT') as password_reset:
        dialog.get_by_role('button', name='Salva', exact=True).click()
    assert password_reset.value.status == 204
    expect(page.get_by_role('dialog')).to_have_count(0)
    tenant_response = admin_context.request.get(BASE + '/api/data/tenants?pageSize=100')
    tenant_code = next(item['code'] for item in tenant_response.json()['items'] if item['id'] == tenant_id)

    limited_context = browser.new_context(locale='it-IT', viewport={'width': 1280, 'height': 800})
    limited = limited_context.new_page()
    limited.on('pageerror', lambda error: errors.append(str(error)))
    limited.goto(BASE, wait_until='networkidle')
    limited.locator('#username').fill('operator')
    limited.locator('#password').fill(initial_password)
    limited.locator('#tenant-code').fill(tenant_code)
    limited.get_by_role('button', name='Accedi', exact=True).click()
    expect(limited.locator('#current-password')).to_be_visible()
    next_password = secrets.token_urlsafe(24)
    limited.locator('#current-password').fill(initial_password)
    limited.locator('#new-password').fill(next_password)
    limited.locator('#confirm-password').fill(next_password)
    limited.get_by_role('button', name='Salva', exact=True).click()
    expect(limited.locator('nav').get_by_role('button', name='Aziende', exact=True)).to_be_visible()
    expect(limited.locator('nav').get_by_role('button')).to_have_count(1)
    expect(limited.get_by_role('button', name='Nuovo', exact=True)).to_have_count(0)
    expect(limited.locator('tbody')).to_contain_text('Società aggiornata')
    limited.screenshot(path=str(EVIDENCE / 'workspace-readonly.png'), full_page=True)
    limited.get_by_role('button', name='Esci', exact=True).click()
    expect(limited.locator('#username')).to_be_visible()
    assert not errors, errors
    limited_context.close()
    admin_context.close()
    browser.close()
    print(json.dumps({'required_reference_guard': True, 'keyboard_select': True, 'switch_boolean': True, 'alertdialog_cancel_delete': True, 'optional_scope_clear': True, 'ui_password_reset_and_change': True, 'readonly_navigation_and_actions': True, 'javascript_errors': errors}))
