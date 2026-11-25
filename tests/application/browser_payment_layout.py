"""Real Chromium acceptance for payment layout and shared dialog windows.

Run through run_payment_layout_browser.py, which supplies isolated fixtures.
Reference geometry: user BP screenshot 1661x589, not pixel identity.
"""
from urllib.parse import urlsplit
import browser_business_partners as bp
import run_business_partner_proof as runner
from playwright.sync_api import expect

class PaymentLayout(bp.BusinessPartnerBrowserTests):
    def payments(self):
        status, company = self.case.root.request('/api/data/companies?tenantId='+self.case.tenant_id, 'POST', {'name':'Layout proof company'})
        self.assertEqual(status, 201, company)
        self.login()
        self.page.locator('nav').get_by_role('button', name='Pagamenti', exact=True).click()
        w = self.page.locator('[data-payments-workspace]')
        expect(w).to_be_visible()
        w.locator('#payment-company').click()
        self.page.get_by_role('option', name='Layout proof company', exact=True).click()
        return w

    def screenshot(self, name):
        self.page.screenshot(path=str(runner.EVIDENCE / (name+'.png')), full_page=True)

    def test_select_label_spacing(self):
        w = self.payments()
        def verify(ids):
            self.page.evaluate('''async () => {
                await Promise.all(document.getAnimations().map(animation => animation.finished.catch(() => {})));
            }''')
            for field_id in ids:
                label = self.page.locator(f'label[for="{field_id}"]')
                control = self.page.locator(f'#{field_id}')
                expect(label).to_be_visible(); expect(control).to_be_visible()
                l, c = label.bounding_box(), control.bounding_box()
                self.assertGreaterEqual(c['y'] - (l['y'] + l['height']), 7, field_id)
        w.get_by_role('button', name='Nuovo', exact=True).click()
        verify(['pm-category', 'pm-direction', 'pm-fiscal'])
        self.page.get_by_role('dialog').get_by_role('button', name='Annulla', exact=True).click()
        w.get_by_role('button', name='Condizioni di pagamento', exact=True).click()
        w.get_by_role('button', name='Nuovo', exact=True).click()
        verify(['pt-reference', 'pt-method'])
        self.page.get_by_role('dialog').get_by_role('button', name='Annulla', exact=True).click()
        w.get_by_role('button', name='Impostazioni aziendali', exact=True).click()
        verify(['defaultSalesTermId', 'defaultPurchaseTermId', 'defaultSalesMethodId', 'defaultPurchaseMethodId'])

    def test_installments_compact_table(self):
        w = self.payments()
        w.get_by_role('button', name='Condizioni di pagamento', exact=True).click()
        w.get_by_role('button', name='Nuovo', exact=True).click()
        dialog = self.page.get_by_role('dialog')
        expect(dialog.get_by_role('tab', name='Generale')).to_have_attribute('aria-selected', 'true')
        expect(dialog.locator('#preview-amount')).to_have_count(0)
        dialog.get_by_role('tab', name='Rate', exact=True).click()
        table = dialog.locator('[data-installments-table]')
        expect(table).to_be_visible()
        expect(table.locator('tbody tr')).to_have_count(1)
        for width, height, label in ((1440, 900, 'desktop'), (390, 844, 'mobile')):
            self.page.set_viewport_size({'width': width, 'height': height})
            table.scroll_into_view_if_needed()
            self.page.wait_for_timeout(200)
            metrics = table.evaluate('''e => {
                const t = e.querySelector('table');
                return {viewport: e.clientWidth, scroll: e.scrollWidth, table: t.getBoundingClientRect().width,
                  columns: Array.from(t.querySelectorAll('thead th'), th => {
                    const r = document.createRange(); r.selectNodeContents(th);
                    const box = b => ({left:b.left, right:b.right, top:b.top, bottom:b.bottom});
                    return {text: th.textContent, width: th.getBoundingClientRect().width,
                      cell: box(th.getBoundingClientRect()), textRects: Array.from(r.getClientRects(), box)};
                  }), wrapperHeight: e.getBoundingClientRect().height, tableHeight: t.getBoundingClientRect().height,
                  css: {wrapper: getComputedStyle(t.parentElement).width, table: getComputedStyle(t).width, layout: getComputedStyle(t).tableLayout}};
            }''')
            print('INSTALLMENTS GEOMETRY', label, metrics, flush=True)
            self.screenshot('installments-'+label)
            self.assertEqual(len(metrics['columns']), 9)
            with self.subTest(viewport=label, check='wrapper height'):
                self.assertLessEqual(metrics['wrapperHeight'] - metrics['tableHeight'], 3, metrics)
            for column in metrics['columns']:
                with self.subTest(viewport=label, header=column['text']):
                    self.assertTrue(column['textRects'], column)
                    for rect in column['textRects']:
                        self.assertGreaterEqual(rect['left'], column['cell']['left'] - 0.5, column)
                        self.assertLessEqual(rect['right'], column['cell']['right'] + 0.5, column)
                        self.assertGreaterEqual(rect['top'], column['cell']['top'] - 0.5, column)
                        self.assertLessEqual(rect['bottom'], column['cell']['bottom'] + 0.5, column)
            for column in metrics['columns']:
                self.assertGreaterEqual(column['width'], 40, (label, metrics))
                self.assertLessEqual(column['width'], 220, (label, metrics))
            self.assertLessEqual(metrics['table'], 1200, (label, metrics))
            self.assertLessEqual(metrics['scroll'] - metrics['table'], 2, (label, metrics))
        first = table.locator('tbody tr').first.bounding_box()
        self.assertLess(first['height'], 70)
        dialog.get_by_role('button', name='Aggiungi', exact=True).click()
        expect(table.locator('tbody tr')).to_have_count(2)
        dialog.locator('#percent-0').fill('60')
        dialog.locator('#percent-1').fill('40')
        expect(dialog.get_by_role('button', name='Salva', exact=True)).to_be_enabled()

        self.page.set_viewport_size({'width':390,'height':844})
        expect(table).to_be_visible()
        dimensions = table.evaluate('(e) => ({width:e.clientWidth, scroll:e.scrollWidth})')
        self.assertGreater(dimensions['scroll'], dimensions['width'])
        dialog_box, table_box = dialog.bounding_box(), table.bounding_box()
        self.assertLessEqual(table_box['x'] + table_box['width'], dialog_box['x'] + dialog_box['width'])
        self.assertLessEqual(dialog_box['x'] + dialog_box['width'], 391)
        table.evaluate('(e) => { e.scrollLeft = e.scrollWidth; }')
        self.assertGreater(table.evaluate('(e) => e.scrollLeft'), 0)
        last_control = table.get_by_role('button', name='Rimuovi 2', exact=True)
        expect(last_control).to_be_visible()
        self.assertLessEqual(last_control.bounding_box()['x'] + last_control.bounding_box()['width'], table_box['x'] + table_box['width'])
        expect(dialog.locator('#percent-1')).to_have_value('40')
        # Required general fields are unmounted on Rate; submitting must not write.
        dialog.get_by_role('button', name='Salva', exact=True).click()
        expect(dialog.get_by_role('tab', name='Generale')).to_have_attribute('aria-selected', 'true')
        dialog.locator('#pt-code').fill('LAYOUT'); dialog.locator('#pt-name').fill('Layout term')
        dialog.get_by_role('tab', name='Rate', exact=True).click()
        dialog.locator('#preview-date').fill('2026-11-19')
        dialog.locator('#preview-currency').click(); self.page.get_by_role('option', name='EUR · Euro', exact=True).click()
        with self.page.expect_response(lambda r: r.request.method == 'POST' and '/payment-schedule/preview' in r.url) as preview:
            dialog.get_by_role('button', name='Calcola', exact=True).click()
        self.assertEqual(preview.value.status, 200, preview.value.text())
        expect(dialog.locator('table')).to_have_count(2)
        preview_table = dialog.locator('table').nth(1)
        expect(preview_table.locator('tbody tr')).to_have_count(2)
        for width, height, label in ((1440, 900, 'desktop'), (390, 844, 'mobile')):
            self.page.set_viewport_size({'width': width, 'height': height})
            preview_table.scroll_into_view_if_needed()
            self.page.evaluate('''async () => {
                await Promise.all(document.getAnimations().map(a => a.finished.catch(() => {})));
            }''')
            geometry = preview_table.evaluate('''table => {
                const text = element => {
                    const range = document.createRange(); range.selectNodeContents(element);
                    const rect = range.getBoundingClientRect();
                    return {text: element.textContent, left: rect.left, right: rect.right};
                };
                return {headers: Array.from(table.querySelectorAll('thead th'), text),
                    rows: Array.from(table.querySelectorAll('tbody tr'), row => Array.from(row.cells, text))};
            }''')
            print('PREVIEW TEXT GEOMETRY', label, geometry, flush=True)
            self.assertEqual(len(geometry['headers']), 3)
            self.assertEqual(len(geometry['rows']), 2)
            for row in geometry['rows']:
                self.assertEqual(len(row), 3)
                for header, cell in zip(geometry['headers'], row):
                    self.assertTrue(header['text'] and cell['text'], geometry)
                    self.assertLessEqual(abs(header['left'] - cell['left']), 1, (label, header, cell))
        dialog.locator('#days-0').fill('5')
        expect(dialog.locator('table')).to_have_count(1)
        with self.page.expect_response(lambda r: r.request.method == 'POST' and '/payment-terms' in r.url) as saved:
            dialog.get_by_role('button', name='Salva', exact=True).click()
        self.assertEqual(saved.value.status, 201, saved.value.text())
        payload = saved.value.request.post_data_json
        self.assertEqual((payload['code'], payload['name']), ('LAYOUT', 'Layout term'))
        self.assertEqual([i['percentage'] for i in payload['installments']], [60, 40])
        self.assertEqual(payload['installments'][0]['offsetDays'], 5)
        expect(w.get_by_text('Layout term', exact=True)).to_be_visible()
        company_id = self.case.root.request('/api/data/companies?tenantId='+self.case.tenant_id)[1]['items'][0]['id']
        status, result = self.case.root.request('/api/companies/'+company_id+'/payment-terms?tenantId='+self.case.tenant_id)
        self.assertEqual(status, 200, result)
        persisted = next(x for x in result['items'] if x['id'] == saved.value.json()['id'])
        self.assertEqual((persisted['code'], persisted['name']), ('LAYOUT', 'Layout term'))
        self.assertEqual([i['percentage'] for i in persisted['installments']], [60, 40])
        self.assertEqual(persisted['installments'][0]['offsetDays'], 5)

    def test_list_geometry_methods_and_terms(self):
        w = self.payments()
        for section in ('Metodi di pagamento', 'Condizioni di pagamento'):
            with self.subTest(section=section):
                w.get_by_role('button', name=section, exact=True).click()
                self.screenshot('layout-'+section.replace(' ', '-'))
                table = w.locator('table').first
                expect(table).to_be_visible()
                card = table.locator('xpath=ancestor::*[@data-slot="card"][1]')
                expect(card).to_be_visible()
                search = w.locator('#payments-filter')
                title = self.page.get_by_role('heading', name='Pagamenti', exact=True)
                new = self.page.get_by_role('button', name='Nuovo', exact=True)
                expect(title).to_be_visible()
                tb, nb, cb, sb, wb = [x.bounding_box() for x in (title, new, card, search, w)]
                self.assertLess(abs((tb['y']+tb['height']/2)-(nb['y']+nb['height']/2)), 10, 'title/new must share row')
                self.assertLessEqual(cb['x'], sb['x']); self.assertLessEqual(sb['x']+sb['width'], cb['x']+cb['width'])
                self.assertLessEqual(cb['y'], sb['y']); self.assertGreater(sb['width'], cb['width']*.55)
                self.assertGreater(cb['width'], wb['width']*.90)
                refresh = card.get_by_role('button', name='Aggiorna')
                expect(refresh).to_be_visible()
                expect(card.get_by_text('Pagina', exact=False)).to_be_visible()
                expect(card.get_by_role('button', name='Precedente', exact=True)).to_be_visible()
                expect(card.get_by_role('button', name='Successiva', exact=True)).to_be_visible()
                headers = table.locator('thead th')
                expect(headers).to_have_count(4)
                action_header = headers.last
                expect(action_header).to_have_text('Azioni')
                expect(action_header).to_be_visible()
                action = action_header.bounding_box()
                self.assertLess(action['width'], cb['width']*.2)
                print('GEOMETRY', section, {'title':tb,'new':nb,'card':cb,'search':sb,'action':action}, flush=True)

    def exercise_window(self, dialog, field, name):
        expect(dialog).to_be_visible()
        field.fill('UNSAVED-PROOF')
        self.page.wait_for_timeout(300)
        before = dialog.bounding_box()
        title = dialog.locator('[data-slot=dialog-title]')
        t = title.bounding_box()
        self.page.mouse.move(t['x']+min(30,t['width']/2), t['y']+t['height']/2)
        self.page.mouse.down(); self.page.mouse.move(t['x']+min(30,t['width']/2)+70, t['y']+t['height']/2+45, steps=8); self.page.mouse.up()
        self.page.wait_for_timeout(250)
        moved = dialog.bounding_box()
        self.screenshot(name+'-moved')
        self.assertGreater(abs(moved['x']-before['x'])+abs(moved['y']-before['y']), 20, (before,moved))
        expect(field).to_have_value('UNSAVED-PROOF')
        handle = dialog.locator('[data-dialog-resize]')
        expect(handle).to_be_visible()
        h = handle.bounding_box()
        self.page.mouse.move(h['x']+h['width']/2,h['y']+h['height']/2)
        self.page.mouse.down(); self.page.mouse.move(h['x']+h['width']/2-80,h['y']+h['height']/2-45,steps=8); self.page.mouse.up()
        self.page.wait_for_timeout(250)
        resized = dialog.bounding_box()
        self.screenshot(name+'-resized')
        self.assertGreater(abs(resized['width']-moved['width'])+abs(resized['height']-moved['height']), 20, (moved,resized))
        expect(field).to_have_value('UNSAVED-PROOF')
        dialog.get_by_role('button', name='Annulla', exact=True).click()
        expect(dialog).to_have_count(0)
        print('WINDOW',name,before,moved,resized,flush=True)

    def test_method_window(self):
        w=self.payments(); w.get_by_role('button',name='Nuovo',exact=True).click()
        self.exercise_window(self.page.get_by_role('dialog'),self.page.locator('#pm-code'),'method')
        w.get_by_role('button',name='Nuovo',exact=True).click()
        expect(self.page.locator('#pm-code')).to_have_value('')

    def test_term_window(self):
        w=self.payments(); w.get_by_role('button',name='Condizioni di pagamento',exact=True).click(); w.get_by_role('button',name='Nuovo',exact=True).click()
        self.exercise_window(self.page.get_by_role('dialog'),self.page.locator('#pt-code'),'term')
        w.get_by_role('button',name='Nuovo',exact=True).click()
        expect(self.page.locator('#pt-code')).to_have_value('')

    def test_shared_window(self):
        self.login(); self.page.locator('nav').get_by_role('button',name='Impostazioni',exact=True).click()
        self.page.get_by_role('button',name='Sistema',exact=True).click()
        self.page.get_by_role('button',name='Valute',exact=True).click()
        self.page.get_by_role('button',name='Nuovo',exact=True).click()
        dialog=self.page.get_by_role('dialog')
        self.exercise_window(dialog,dialog.locator('input').first,'shared-currency')

    def test_mobile_window_bounds(self):
        w=self.payments(); self.page.set_viewport_size({'width':390,'height':844})
        w.get_by_role('button',name='Nuovo',exact=True).click()
        dialog=self.page.get_by_role('dialog'); expect(dialog).to_be_visible()
        self.screenshot('mobile-method')
        box=dialog.bounding_box()
        self.assertGreaterEqual(box['x'],-1); self.assertGreaterEqual(box['y'],-1)
        self.assertLessEqual(box['x']+box['width'],391); self.assertLessEqual(box['y']+box['height'],845)
        field=dialog.locator('#pm-code'); field.fill('TOUCH-PROOF')
        title=dialog.locator('[data-slot=dialog-title]').bounding_box()
        x=title['x']+20; y=title['y']+title['height']/2
        cdp=self.context.new_cdp_session(self.page)
        cdp.send('Emulation.setTouchEmulationEnabled', {'enabled':True, 'maxTouchPoints':1})
        cdp.send('Input.dispatchTouchEvent', {'type':'touchStart','touchPoints':[{'x':x,'y':y}]})
        cdp.send('Input.dispatchTouchEvent', {'type':'touchMove','touchPoints':[{'x':x+15,'y':y+40}]})
        cdp.send('Input.dispatchTouchEvent', {'type':'touchEnd','touchPoints':[]})
        self.page.wait_for_timeout(250)
        moved=dialog.bounding_box(); self.screenshot('mobile-method-touch')
        self.assertGreater(abs(moved['x']-box['x'])+abs(moved['y']-box['y']), 10, (box,moved))
        expect(field).to_have_value('TOUCH-PROOF')
        dialog.get_by_role('button',name='Annulla',exact=True).click()
        expect(dialog).to_have_count(0)
        print('MOBILE TOUCH',box,moved,flush=True)

    def test_overflow_grip_and_touch(self):
        w=self.payments(); self.page.set_viewport_size({'width':390,'height':600})
        w.get_by_role('button',name='Condizioni di pagamento',exact=True).click()
        w.get_by_role('button',name='Nuovo',exact=True).click()
        dialog=self.page.get_by_role('dialog'); expect(dialog).to_be_visible()
        field=dialog.locator('#pt-code'); field.fill('SCROLL-TOUCH')
        dialog.get_by_role('tab',name='Rate',exact=True).click()
        initial=dialog.evaluate('(e) => ({scroll:e.scrollTop, height:e.clientHeight, content:e.scrollHeight})')
        self.assertGreater(initial['content'],initial['height'])
        grip=dialog.locator('[data-dialog-resize]'); box=dialog.bounding_box(); g=grip.bounding_box()
        hit=self.page.evaluate('([x,y]) => document.elementFromPoint(x,y)?.closest("[data-dialog-resize]") !== null',[g['x']+g['width']-5,g['y']+g['height']-5])
        self.assertTrue(hit, (box,g,initial))
        dialog.hover(position={'x':box['width']/2,'y':box['height']/2}); self.page.mouse.wheel(0,250)
        self.page.wait_for_timeout(200)
        self.assertGreater(dialog.evaluate('(e) => e.scrollTop'),0)
        g=grip.bounding_box(); box=dialog.bounding_box()
        self.assertLess(abs((g['y']+g['height'])-(box['y']+box['height'])), 8, (box,g))
        self.assertTrue(self.page.evaluate('([x,y]) => document.elementFromPoint(x,y)?.closest("[data-dialog-resize]") !== null',[g['x']+g['width']-5,g['y']+g['height']-5]), (box,g))
        cdp=self.context.new_cdp_session(self.page); cdp.send('Emulation.setTouchEmulationEnabled', {'enabled':True,'maxTouchPoints':1})
        x=g['x']+g['width']-5; y=g['y']+g['height']-5
        for typ,pts in [('touchStart',[{'x':x,'y':y}]),('touchMove',[{'x':x-50,'y':y-60}]),('touchEnd',[])]:
            cdp.send('Input.dispatchTouchEvent', {'type':typ,'touchPoints':pts})
        self.page.wait_for_timeout(200); resized=dialog.bounding_box()
        self.assertGreater(abs(resized['height']-box['height']),20,(box,resized))
        dialog.get_by_role('tab',name='Generale',exact=True).click()
        expect(field).to_have_value('SCROLL-TOUCH')
        print('OVERFLOW TOUCH',initial,box,g,resized,flush=True)

    def test_payment_switch_persistence(self):
        w = self.payments()
        company_id = self.case.root.request('/api/data/companies?tenantId='+self.case.tenant_id)[1]['items'][0]['id']
        base = '/api/companies/'+company_id
        suffix = '?tenantId='+self.case.tenant_id
        def switch(dialog, selector, checked):
            control = dialog.locator(selector)
            expect(control).to_have_attribute('role', 'switch')
            expect(control).to_have_attribute('data-slot', 'switch')
            expect(control).to_have_attribute('aria-checked', str(checked).lower())
            return control
        def save(dialog, verb, path, expected, version=None):
            with self.page.expect_response(lambda r:r.request.method == verb and path in r.url) as result:
                dialog.get_by_role('button', name='Salva', exact=True).click()
            response = result.value
            self.assertIn(response.status, (200, 201), response.text())
            payload = response.request.post_data_json
            for key,value in expected.items(): self.assertEqual(payload[key], value, payload)
            if version is not None: self.assertEqual(payload['expectedVersion'], version)
            print('SWITCH WRITE', verb, path, expected, 'expectedVersion', payload.get('expectedVersion'), 'status', response.status, flush=True)
            return response.json()
        def read(path, item, expected):
            status, result = self.case.root.request(base+path+suffix)
            self.assertEqual(status, 200, result)
            actual = next(x for x in result['items'] if x['id'] == item['id'])
            for key,value in expected.items(): self.assertEqual(actual[key], value, actual)
            self.assertEqual(actual['version'], item['version'])
            print('SWITCH READ', path, expected, 'version',actual['version'],flush=True)
        w.get_by_role('button',name='Nuovo',exact=True).click()
        d=self.page.get_by_role('dialog'); d.locator('#pm-code').fill('SWITCHM'); d.locator('#pm-name').fill('Switch method')
        bank=switch(d,'#pm-bank',False); active=switch(d,'#pm-active',True)
        bank.click(); active.focus(); active.press('Space')
        switch(d,'#pm-bank',True); switch(d,'#pm-active',False)
        method=save(d,'POST','/payment-methods',{'requiresBankAccount':True,'isActive':False})
        expect(w.get_by_text('Switch method',exact=False)).to_be_visible()
        read('/payment-methods',method,{'requiresBankAccount':True,'isActive':False})
        w.get_by_role('button',name='Modifica Switch method',exact=True).click(); d=self.page.get_by_role('dialog')
        bank=switch(d,'#pm-bank',True); active=switch(d,'#pm-active',False)
        bank.focus(); bank.press('Space'); active.click()
        switch(d,'#pm-bank',False); switch(d,'#pm-active',True)
        method2=save(d,'PATCH','/payment-methods/',{'requiresBankAccount':False,'isActive':True},method['version'])
        expect(w.get_by_text('Switch method',exact=False)).to_be_visible()
        read('/payment-methods',method2,{'requiresBankAccount':False,'isActive':True})
        w.get_by_role('button',name='Condizioni di pagamento',exact=True).click()
        w.get_by_role('button',name='Nuovo',exact=True).click(); d=self.page.get_by_role('dialog')
        d.locator('#pt-code').fill('SWITCHT'); d.locator('#pt-name').fill('Switch term')
        active=switch(d,'#pt-active',True); active.click(); switch(d,'#pt-active',False)
        term=save(d,'POST','/payment-terms',{'isActive':False})
        expect(w.get_by_text('Switch term',exact=False)).to_be_visible()
        read('/payment-terms',term,{'isActive':False})
        w.get_by_role('button',name='Modifica Switch term',exact=True).click(); d=self.page.get_by_role('dialog')
        active=switch(d,'#pt-active',False); active.focus(); active.press('Space'); switch(d,'#pt-active',True)
        term2=save(d,'PUT','/payment-terms/',{'isActive':True},term['version'])
        expect(w.get_by_text('Switch term',exact=False)).to_be_visible()
        read('/payment-terms',term2,{'isActive':True})
