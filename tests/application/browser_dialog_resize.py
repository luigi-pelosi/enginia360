"""Authenticated Chromium regression for shared modal resize grips."""
from playwright.sync_api import expect
from browser_payment_layout import PaymentLayout

class DialogResize(PaymentLayout):
    def check_grip(self, dialog):
        box = dialog.bounding_box(); grip = dialog.locator('[data-dialog-resize]').bounding_box()
        self.assertLess(abs(box['x'] + box['width'] - grip['x'] - grip['width']), 4, (box, grip))
        self.assertLess(abs(box['y'] + box['height'] - grip['y'] - grip['height']), 4, (box, grip))
        x, y = grip['x'] + grip['width'] - 5, grip['y'] + grip['height'] - 5
        self.assertTrue(self.page.evaluate('([x,y]) => !!document.elementFromPoint(x,y)?.closest("[data-dialog-resize]")', [x,y]), (box, grip))
        return box, x, y

    def test_organization_flex_desktop_mobile(self):
        self.login()
        self.page.locator('nav').get_by_role('button', name='Organizzazioni di vendita', exact=True).click()
        self.page.get_by_role('button', name='Nuovo', exact=True).first.click()
        dialog=self.page.get_by_role('dialog'); expect(dialog).to_be_visible()
        field=dialog.locator('#field-name'); field.fill('Draft resize')
        for width,height in ((1440,900),(390,600)):
            self.page.set_viewport_size({'width':width,'height':height}); self.page.wait_for_timeout(300)
            box,x,y=self.check_grip(dialog)
            self.page.mouse.move(x,y); self.page.mouse.down(); self.page.mouse.move(x-50,y-50,steps=5); self.page.mouse.up()
            self.page.wait_for_timeout(150)
            after=dialog.bounding_box()
            self.assertGreater(abs(after['height']-box['height'])+abs(after['width']-box['width']),20,(box,after))
            expect(field).to_have_value('Draft resize'); self.check_grip(dialog)

    def test_grid_scroll_desktop(self):
        w=self.payments(); self.page.set_viewport_size({'width':1440,'height':600})
        w.get_by_role('button',name='Condizioni di pagamento',exact=True).click()
        w.get_by_role('button',name='Nuovo',exact=True).click()
        dialog=self.page.get_by_role('dialog'); field=dialog.locator('#pt-code'); field.fill('DESKTOP-DRAFT')
        dialog.get_by_role('tab',name='Rate',exact=True).click()
        self.assertGreater(dialog.evaluate('(e) => e.scrollHeight - e.clientHeight'),0)
        self.check_grip(dialog)
        dialog.evaluate('(e) => { e.scrollTop = e.scrollHeight; }'); self.page.wait_for_timeout(150)
        self.assertGreater(dialog.evaluate('(e) => e.scrollTop'),0)
        box,x,y=self.check_grip(dialog)
        self.page.mouse.move(x,y); self.page.mouse.down(); self.page.mouse.move(x-60,y-60,steps=5); self.page.mouse.up()
        self.page.wait_for_timeout(150); after=dialog.bounding_box()
        self.assertGreater(abs(after['height']-box['height']),20,(box,after))
        self.check_grip(dialog)
        dialog.get_by_role('tab',name='Generale',exact=True).click(); expect(field).to_have_value('DESKTOP-DRAFT')

    def test_grid_scroll_touch(self):
        self.test_overflow_grip_and_touch()
