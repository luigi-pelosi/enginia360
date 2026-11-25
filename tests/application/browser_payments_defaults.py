import sys, unittest, json, os
import browser_business_partners as b
from playwright.sync_api import expect
class Proof(b.BusinessPartnerBrowserTests):
 def assert_modal_geometry(self, dialog):
  for width,height in ((1440,1000),(390,844)):
   self.page.set_viewport_size({'width':width,'height':height})
   expect(dialog).to_be_visible()
   box=dialog.bounding_box()
   self.assertIsNotNone(box)
   self.assertGreaterEqual(box['x'],-1); self.assertGreaterEqual(box['y'],-1)
   self.assertLessEqual(box['x']+box['width'],width+1); self.assertLessEqual(box['y']+box['height'],height+1)
   print('Modal viewport',width,height,'rect',box,flush=True)
  self.page.set_viewport_size({'width':1440,'height':1000})
 def assert_default_field_spacing(self, dialog):
  measurements=[]
  for width,height in ((1440,1000),(390,844)):
   self.page.set_viewport_size({'width':width,'height':height})
   for field in ('defaults-role','defaults-term','defaults-method'):
    expect(dialog.locator('#'+field)).to_be_visible()
   dialog.evaluate('async el => { await Promise.all(el.getAnimations({subtree:true}).map(a => a.finished.catch(() => {}))); await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r))); }')
   for field in ('defaults-role','defaults-term','defaults-method'):
    label=dialog.locator('label[for="'+field+'"]').bounding_box()
    control=dialog.locator('#'+field).bounding_box()
    self.assertIsNotNone(label); self.assertIsNotNone(control)
    gap=control['y']-(label['y']+label['height'])
    measurements.append((width,field,gap))
    print('BP label gap',width,field,round(gap,2),'px',flush=True)
  self.page.set_viewport_size({'width':1440,'height':1000})
  self.assertTrue(all(gap >= 7.5 for _,_,gap in measurements),str(measurements))
 def test_payments(self):
  status,first=self.case.root.request('/api/data/companies?tenantId='+self.case.tenant_id,'POST',{'name':'Payments A first'}); self.assertEqual(status,201,first)
  status,company=self.case.root.request('/api/data/companies?tenantId='+self.case.tenant_id,'POST',{'name':'Payments browser company'}); self.assertEqual(status,201,company)
  self.login(); self.page.locator('nav').get_by_role('button',name='Pagamenti',exact=True).click()
  w=self.page.locator('[data-payments-workspace]'); expect(w).to_be_visible()
  w.locator('#payment-company').click(); self.page.get_by_role('option',name='Payments browser company',exact=True).click()
  w.get_by_role('button',name='Nuovo',exact=True).click(); dialog=self.page.get_by_role('dialog'); expect(dialog).to_be_visible(); self.assert_modal_geometry(dialog); dialog.locator('#pm-code').fill('BANK'); dialog.locator('#pm-name').fill('Bank browser')
  with self.page.expect_response(lambda r:r.request.method=='POST' and '/payment-methods' in r.url) as response: dialog.get_by_role('button',name='Salva',exact=True).click()
  self.assertEqual(response.value.status,201); method=response.value.json(); expect(w.get_by_text('Bank browser',exact=True)).to_be_visible()
  w.get_by_role('button',name='Condizioni di pagamento',exact=True).click(); w.get_by_role('button',name='Nuovo',exact=True).click(); dialog=self.page.get_by_role('dialog'); expect(dialog).to_be_visible(); self.assert_modal_geometry(dialog); dialog.locator('#pt-code').fill('NET'); dialog.locator('#pt-name').fill('Net browser'); dialog.get_by_role('tab',name='Rate',exact=True).click()
  if not os.environ.get('BP_DEFAULTS_ONLY'):
   dialog.locator('#preview-date').fill('2026-11-19')
   calculate=dialog.get_by_role('button',name='Calcola',exact=True)
   expect(calculate).to_be_disabled()
   dialog.locator('#preview-currency').click(); self.page.get_by_role('option',name='EUR · Euro',exact=True).click()
   expect(calculate).to_be_enabled()
   with self.page.expect_response(lambda r:r.request.method=='POST' and '/payment-schedule/preview' in r.url) as preview: calculate.click()
   self.assertEqual(preview.value.status,200,preview.value.text())
   self.assertEqual(preview.value.request.post_data_json['currency'],'EUR')
   self.assertEqual(preview.value.json()['items'][0]['amount'],1200)
   expect(dialog.locator('table').last).to_contain_text('1200')
  with self.page.expect_response(lambda r:r.request.method=='POST' and '/payment-terms' in r.url) as response: dialog.get_by_role('button',name='Salva',exact=True).click()
  self.assertEqual(response.value.status,201); term=response.value.json(); expect(w.get_by_text('Net browser',exact=True)).to_be_visible()
  term_row=w.locator('tbody tr').filter(has_text='Net browser')
  expect(term_row).to_contain_text('100%')
  w.get_by_role('button',name='Impostazioni aziendali',exact=True).click(); expect(w.locator('#defaultSalesTermId')).to_be_visible()
  w.locator('#defaultSalesTermId').click(); self.page.get_by_role('option',name='NET · Net browser',exact=True).click()
  w.locator('#defaultSalesMethodId').click(); self.page.get_by_role('option',name='BANK · Bank browser',exact=True).click()
  with self.page.expect_response(lambda r:r.request.method=='PUT' and '/payment-settings' in r.url) as s: w.get_by_role('button',name='Salva',exact=True).click()
  bp=self.case.create('Payments browser partner'); base='/api/companies/'+company['id']; suffix='?tenantId='+self.case.tenant_id
  association=self.case.root.request(base+'/business-partners'+suffix,'POST',{'businessPartnerId':bp['id'],'roles':['CUSTOMER']}); self.assertEqual(association[0],201,association)
  self.assertEqual(self.case.root.request('/api/companies/'+first['id']+'/business-partners'+suffix,'POST',{'businessPartnerId':bp['id'],'roles':['CUSTOMER']})[0],201)
  self.navigate(); self.page.get_by_role('button',name='Modifica Payments browser partner',exact=True).click()
  rows=self.page.locator('[data-bp-company-relations] tbody tr'); expect(rows).to_have_count(2)
  row=self.page.locator('[data-bp-company-relations] tr').filter(has_text='Payments browser company'); expect(row).to_be_visible(); self.assertEqual(self.page.locator('[data-action="open-payment-defaults"]').count(),0)
  for width,height in ((1440,1000),(390,844)):
   self.page.set_viewport_size({'width':width,'height':height})
   cells=rows.locator('td:last-child').evaluate_all('(cells)=>cells.map(c=>({x:c.getBoundingClientRect().x,width:c.getBoundingClientRect().width,right:c.getBoundingClientRect().right}))')
   self.assertEqual(len(cells),2); self.assertAlmostEqual(cells[0]['x'],cells[1]['x'],delta=1); self.assertAlmostEqual(cells[0]['width'],cells[1]['width'],delta=1)
   print('Row actions viewport',width,cells,flush=True)
  self.page.set_viewport_size({'width':1440,'height':1000})
  writes=[]; self.page.on('request',lambda r:writes.append(r.url) if r.method=='PUT' and '/payment-defaults/' in r.url else None)
  row.locator('[data-action^="payment-defaults-"]').click(); dialog=self.page.get_by_role('dialog'); expect(dialog).to_contain_text('Payments browser company'); dialog.get_by_role('button',name='Annulla',exact=True).click(); expect(dialog).not_to_be_visible(); self.assertEqual(writes,[]); row.locator('[data-action^="payment-defaults-"]').click(); dialog=self.page.get_by_role('dialog'); expect(dialog.locator('#defaults-term')).to_be_visible(); self.assert_modal_geometry(dialog); self.assert_default_field_spacing(dialog)
  dialog.locator('#defaults-term').click(); self.page.get_by_role('option',name='NET · Net browser',exact=True).click()
  dialog.locator('#defaults-method').click(); self.page.get_by_role('option',name='BANK · Bank browser',exact=True).click()
  target=base+'/business-partners/'+bp['id']+'/payment-defaults/CUSTOMER'
  before_url=self.page.url
  with self.page.expect_response(lambda r:r.request.method=='PUT' and target in r.url, timeout=5000) as saved:
   dialog.get_by_role('button',name='Salva',exact=True).click()
  self.assertEqual(saved.value.status,200,saved.value.text())
  self.assertEqual(saved.value.request.post_data_json, {'paymentTermId':term['id'], 'paymentMethodId':method['id'], 'expectedVersion':0})
  status,readback=self.case.root.request(target+suffix)
  self.assertEqual(status,200)
  self.assertEqual(readback, {'paymentTermId':term['id'],'paymentMethodId':method['id'],'version':1})
  expect(self.page.locator('[data-bp-company-relations] tr').filter(has_text='Payments browser company')).to_contain_text('Net browser')
  self.assertEqual(self.page.url,before_url)
  print('BP PUT',saved.value.status,saved.value.request.post_data_json,'GET',status,readback,flush=True)
if __name__=='__main__': unittest.main()
