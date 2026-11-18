"""Regressione browser: il Super Admin vede la propria utenza senza azioni tenant."""
import json
from pathlib import Path
import uuid
from playwright.sync_api import sync_playwright, expect

ORIGIN = 'https://vmi3659251.tailfcced0.ts.net:8080'
PRIVATE = Path('/root/.config/enginia360/self-visible')
EVIDENCE = Path('/root/.hermes/cache/scratch/enginia360-self-visible')
credentials = json.loads((PRIVATE / 'bootstrap.json').read_text())
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path='/root/.hermes/tools/chromium-1208/chrome-linux64/chrome',headless=True,args=['--no-sandbox'])
    context = browser.new_context(locale='it-IT',viewport={'width':1440,'height':1000})
    def forward(route):
        from urllib.parse import urlsplit
        url = urlsplit(route.request.url)
        assert url.netloc == 'vmi3659251.tailfcced0.ts.net:8080'
        target = 'http://127.0.0.1:18082' if url.path.startswith('/api/') else 'http://127.0.0.1:18083'
        response = route.fetch(url=target+url.path+('?' + url.query if url.query else ''),headers={**route.request.all_headers(),'host':url.netloc})
        route.fulfill(response=response)
    context.route(ORIGIN+'/**',forward)
    page=context.new_page();errors=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto(ORIGIN,wait_until='networkidle')
    page.locator('#username').fill(credentials['username']);page.locator('#password').fill(credentials['password'])
    page.get_by_role('button',name='Accedi',exact=True).click()
    expect(page.locator('[data-slot=sidebar-wrapper]')).to_be_visible()
    page.locator('.tenant-bar').get_by_role('button',name='Crea organizzazione',exact=True).click()
    dialog=page.get_by_role('dialog');dialog.locator('#field-code').fill('visible-ui-'+uuid.uuid4().hex[:10]);dialog.locator('#field-name').fill('Verifica visibilità')
    dialog.get_by_role('button',name='Salva',exact=True).click();expect(page.get_by_role('dialog')).to_have_count(0)
    page.locator('nav').get_by_role('button',name='Utenti',exact=True).click()
    expect(page.locator('tbody')).to_contain_text('visibility-verification')
    expect(page.locator('.table-count')).to_contain_text('1 elemento')
    full_name='Verifica Visibilità'
    assert page.get_by_role('button',name='Elimina '+full_name,exact=True).count()==0
    assert page.get_by_role('button',name='Imposta password '+full_name,exact=True).count()==0
    page.get_by_role('button',name='Dettagli '+full_name,exact=True).click()
    dialog=page.get_by_role('dialog')
    expect(dialog.locator('#field-first_name')).to_have_value('Verifica')
    expect(dialog.locator('#field-first_name')).to_be_disabled()
    assert dialog.get_by_role('button',name='Salva',exact=True).count()==0
    assert dialog.get_by_role('heading',name='Ruoli utente',exact=True).count()==0
    dialog.get_by_role('button',name='Annulla',exact=True).click()
    page.screenshot(path=str(EVIDENCE/'global-user-visible.png'),full_page=True)
    page.get_by_role('button',name='Nuovo',exact=True).first.click()
    dialog=page.get_by_role('dialog')
    for field,value in {'username':'operator-ui','first_name':'Operatore','last_name':'Test','email':'operator-ui@example.invalid'}.items():dialog.locator('#field-'+field).fill(value)
    dialog.get_by_role('button',name='Salva',exact=True).click();expect(page.get_by_role('dialog')).to_have_count(0)
    expect(page.get_by_role('button',name='Modifica Operatore Test',exact=True)).to_be_visible()
    page.locator('nav').get_by_role('button',name='Gruppi',exact=True).click();page.get_by_role('button',name='Nuovo',exact=True).first.click()
    dialog=page.get_by_role('dialog');dialog.locator('#field-code').fill('operators');dialog.locator('#field-name').fill('Operatori')
    dialog.get_by_role('button',name='Salva',exact=True).click();expect(page.get_by_role('dialog')).to_have_count(0)
    page.get_by_role('button',name='Modifica Operatori',exact=True).click();dialog=page.get_by_role('dialog')
    section=dialog.locator('section').filter(has=page.get_by_role('heading',name='Utenti del gruppo',exact=True))
    expect(section.get_by_role('checkbox',name='Operatore Test',exact=True)).to_be_visible()
    assert section.get_by_role('checkbox',name=full_name,exact=True).count()==0
    section.get_by_role('checkbox',name='Operatore Test',exact=True).check()
    section.get_by_role('button',name='Salva · Utenti del gruppo',exact=True).click()
    expect(section.get_by_role('checkbox',name='Operatore Test',exact=True)).to_be_checked()
    assert not errors,errors
    report={'own_global_user_visible':True,'correct_count':True,'global_details_read_only':True,'tenant_user_still_editable':True,'global_excluded_from_group_choices':True,'normal_group_assignment':True,'javascript_errors':errors}
    (EVIDENCE/'browser-verification.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
    browser.close()
