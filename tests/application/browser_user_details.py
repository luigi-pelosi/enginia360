"""Verifica browser dell'anagrafica e della lingua salvata dell'utente."""

import json
import os
from pathlib import Path
import secrets
import uuid
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright, expect

BASE = os.environ['ENGINIA360_BROWSER_BASE']
EVIDENCE = Path(os.environ['ENGINIA360_EVIDENCE'])
credentials = json.loads(Path(os.environ['ENGINIA360_TEST_CREDENTIALS']).read_text())
errors = []
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path='/root/.hermes/tools/chromium-1208/chrome-linux64/chrome',
                                headless=True, args=['--no-sandbox'])
    context = browser.new_context(locale='it-IT', viewport={'width': 1440, 'height': 1000})
    page = context.new_page()
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto(BASE, wait_until='networkidle')
    page.locator('#username').fill(credentials['username'])
    page.locator('#password').fill(credentials['password'])
    page.get_by_role('button', name='Accedi', exact=True).click()
    expect(page.locator('[data-slot=sidebar-wrapper]')).to_be_visible()
    code = 'profile-ui-' + uuid.uuid4().hex[:10]
    page.locator('.tenant-bar').get_by_role('button', name='Crea organizzazione', exact=True).click()
    dialog = page.get_by_role('dialog')
    dialog.locator('#field-code').fill(code)
    dialog.locator('#field-name').fill('Verifica anagrafica browser')
    dialog.get_by_role('button', name='Salva', exact=True).click()
    expect(page.get_by_role('dialog')).to_have_count(0)
    page.locator('nav').get_by_role('button', name='Utenti', exact=True).click()
    page.get_by_role('button', name='Nuovo', exact=True).first.click()
    dialog = page.get_by_role('dialog')
    assert dialog.locator('#field-display_name').count() == 0
    for field in ['first_name', 'last_name', 'email']:
        assert dialog.locator('#field-' + field).evaluate('(el) => el.required')
    assert dialog.locator('#field-date_of_birth').get_attribute('type') == 'date'
    assert dialog.locator('#field-phone_number').get_attribute('type') == 'tel'
    expect(dialog.locator('#field-preferred_language')).to_contain_text('Italiano')
    dialog.locator('#field-username').fill('profile-browser')
    dialog.locator('#field-first_name').fill('Élodie')
    dialog.locator('#field-last_name').fill("D'Amico")
    dialog.locator('#field-email').fill('profile-browser@example.invalid')
    dialog.locator('#field-date_of_birth').fill('2000-02-29')
    dialog.locator('#field-phone_number').fill('+39 (06) 1234 5678')
    dialog.locator('#field-preferred_language').click()
    page.get_by_role('option', name='Inglese', exact=True).click()
    with page.expect_response(lambda r: urlsplit(r.url).path == '/api/data/users' and r.request.method == 'POST') as info:
        dialog.get_by_role('button', name='Salva', exact=True).click()
    assert info.value.status == 201
    record = info.value.json()
    assert record['date_of_birth'] == '2000-02-29' and record['preferred_language'] == 'en'
    assert 'display_name' not in record
    expect(page.get_by_role('dialog')).to_have_count(0)
    name = "Élodie D'Amico"
    page.get_by_role('button', name='Modifica ' + name, exact=True).click()
    dialog = page.get_by_role('dialog')
    expect(dialog.locator('#field-date_of_birth')).to_have_value('2000-02-29')
    expect(dialog.locator('#field-phone_number')).to_have_value('+39 (06) 1234 5678')
    expect(dialog.locator('#field-preferred_language')).to_contain_text('Inglese')
    page.screenshot(path=str(EVIDENCE / 'user-profile-form.png'), full_page=True)
    dialog.get_by_role('button', name='Annulla', exact=True).click()
    password = secrets.token_urlsafe(24)
    page.get_by_role('button', name='Imposta password ' + name, exact=True).click()
    dialog = page.get_by_role('dialog')
    dialog.locator('#new-password').fill(password)
    dialog.locator('#confirm-password').fill(password)
    dialog.get_by_role('button', name='Salva', exact=True).click()
    expect(page.get_by_role('dialog')).to_have_count(0)
    page.get_by_role('button', name='Esci', exact=True).click()
    expect(page.locator('#username')).to_be_visible()
    page.locator('#username').fill('profile-browser')
    page.locator('#password').fill(password)
    page.locator('#tenant-code').fill(code)
    page.get_by_role('button', name='Accedi', exact=True).click()
    expect(page.locator('html')).to_have_attribute('lang', 'en')
    expect(page.get_by_role('heading', name='Change password', exact=True)).to_be_visible()
    changed = secrets.token_urlsafe(24)
    page.locator('#current-password').fill(password)
    page.locator('#new-password').fill(changed)
    page.locator('#confirm-password').fill(changed)
    page.get_by_role('button', name='Save', exact=True).click()
    expect(page.locator('[data-slot=sidebar-wrapper]')).to_be_visible()
    expect(page.get_by_text(name, exact=True).first).to_be_visible()
    assert not errors, errors
    report = {'required_names_email': True, 'display_name_removed': True, 'date_and_phone_persisted': True,
              'language_default_it': True, 'saved_english_applied_on_login': True,
              'full_name_derived': True, 'javascript_errors': errors}
    (EVIDENCE / 'browser-profile.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report))
    browser.close()
