"""Authenticated Chromium geometry of the real shared searchable Select."""
import json
from playwright.sync_api import expect
from browser_payment_layout import PaymentLayout

class SelectGeometry(PaymentLayout):
    def test_selected_tick_geometry(self):
        long_name = 'Proof selected company with a long descriptive name for multiline mobile layout'
        for i in range(12):
            name = long_name if i == 11 else f'Proof company {i:02d}'
            status, result = self.case.root.request('/api/data/companies?tenantId='+self.case.tenant_id, 'POST', {'name': name})
            self.assertEqual(status, 201, result)
        w = self.payments()
        company_trigger = w.locator('#payment-company')
        for width, height in ((1440, 900), (390, 844)):
            self.page.set_viewport_size({'width': width, 'height': height})
            company_trigger.click()
            self.page.get_by_role('option', name=long_name, exact=True).click()
            company_trigger.click()
            options = self.page.locator('[data-slot="select-item"]')
            self.assertGreater(options.count(), 10)
            self.check_options(options, width, 'scrolled-long')
            self.page.locator('[data-slot="select-search"]').fill('multiline mobile')
            self.check_options(options, width, 'searched-long')
            self.page.keyboard.press('Escape')
        w.get_by_role('button', name='Nuovo', exact=True).click()
        trigger = self.page.locator('#pm-direction')
        for width, height in ((1440, 900), (390, 844)):
            self.page.set_viewport_size({'width': width, 'height': height})
            for index in (0, 1):
                trigger.click()
                options = self.page.locator('[data-slot="select-item"]')
                expect(options.first).to_be_visible()
                self.assertGreaterEqual(options.count(), 2)
                options.nth(index).click()
                trigger.click()
                chosen = options.nth(index)
                expect(chosen).to_have_attribute('aria-selected', 'true')
                self.check_options(options, width, 'all')
                text = chosen.inner_text().strip()
                self.page.locator('[data-slot="select-search"]').fill(text)
                expect(self.page.get_by_role('option', name=text, exact=True)).to_be_visible()
                self.check_options(options, width, 'search')
                self.page.keyboard.press('Escape')
                expect(trigger).to_be_focused()

    def check_options(self, options, width, phase):
        selected = 0
        for option in options.all():
            option.scroll_into_view_if_needed()
            is_selected = option.get_attribute('aria-selected') == 'true'
            icons = option.locator('svg')
            self.assertEqual(icons.count(), int(is_selected))
            if not is_selected:
                continue
            selected += 1
            metrics = option.evaluate('''e => {
              const icon=e.querySelector('svg').getBoundingClientRect();
              const r=document.createRange();
              const walker=document.createTreeWalker(e, NodeFilter.SHOW_TEXT);
              let n; const rects=[];
              while(n=walker.nextNode()) { if(n.textContent.trim()) {r.selectNodeContents(n); rects.push(...Array.from(r.getClientRects(), b=>({top:b.top,bottom:b.bottom})));} }
              const item=e.getBoundingClientRect();
              return {item:{top:item.top,bottom:item.bottom},icon:{top:icon.top,bottom:icon.bottom},text:rects};
            }''')
            print('SELECT GEOMETRY', json.dumps({'width':width,'phase':phase,'metrics':metrics}), flush=True)
            self.assertTrue(metrics['text'], metrics)
            text_top=min(x['top'] for x in metrics['text']); text_bottom=max(x['bottom'] for x in metrics['text'])
            self.assertLessEqual(abs((text_top+text_bottom-metrics['icon']['top']-metrics['icon']['bottom'])/2), 1, metrics)
            self.assertGreaterEqual(metrics['icon']['top'], metrics['item']['top']-.5, metrics)
            self.assertLessEqual(metrics['icon']['bottom'], metrics['item']['bottom']+.5, metrics)
        self.assertEqual(selected, 1)
