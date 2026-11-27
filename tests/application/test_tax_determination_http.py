"""Acceptance Fase4 reale; discovery inerte, runtime solo candidate finali isolate.

Nessuna suite storica ereditata: solo helper nominati e verificabili. Le fonti
fiscali positive sono create via HTTP, mai tramite insert SQL sostitutivi.
"""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import date, timedelta
import json
import os
from pathlib import Path
import subprocess
import time
import unittest
import urllib.error
import urllib.request
import uuid

from tax_helpers import configure_fixture, login_root
from test_company_tax_http import CompanyTaxHttp
from test_taxclassification_http import TaxClassificationHttp
from test_tax_http import TaxHttp

RULE_ACTIONS = ('read', 'create', 'update', 'validate', 'publish', 'withdraw', 'install_templates')
SOURCE_READS = ['companies.read', 'company-tax-configurations.read', 'catalog-items.read',
                'business-partners.read', 'tax-item-profiles.read', 'tax-partner-profiles.read']


class TaxDeterminationHttp(unittest.TestCase):
    # Reuse helpers only. Do not subclass predecessor TestCases (lost coverage oracle).
    actor = TaxHttp.actor
    path = CompanyTaxHttp.path
    scope = CompanyTaxHttp.scope
    req = CompanyTaxHttp.req
    sql = CompanyTaxHttp.sql
    company_create = CompanyTaxHttp.company_create
    company_read = CompanyTaxHttp.company_read
    identifier = CompanyTaxHttp.identifier
    profile = CompanyTaxHttp.profile
    registration = CompanyTaxHttp.registration
    payload = CompanyTaxHttp.payload
    list_route = CompanyTaxHttp.list_route
    route = CompanyTaxHttp.route
    create = CompanyTaxHttp.create
    command = CompanyTaxHttp.command
    assign_companies = CompanyTaxHttp.assign_companies

    @classmethod
    def setUpClass(cls):
        if os.environ.get('ENGINIA360_TAX_DETERMINATION_PROOF') != '1':
            raise RuntimeError('Use run_tax_determination_proof.py; runtime not authorized')
        cls.fixture = configure_fixture('enginia360-company-tax-proof')
        cls.fixture.EVIDENCE = Path(os.environ['ENGINIA360_COMPANY_TAX_EVIDENCE'])
        if not all(cls.fixture.verify_target(x) for x in (cls.fixture.DB, cls.fixture.API)):
            raise RuntimeError('Exact isolated scope unavailable')
        cls.root, cls.credentials = login_root()

    def setUp(self):
        CompanyTaxHttp.setUp(self)
        self.day = self.today.isoformat()
        self.tax_code = self.req('codes', 'POST', {
            'values': {'code': 'VAT_STANDARD', 'name': 'Synthetic configured VAT',
                       'country_id': self.country_id, 'tax_type_id': self.vat['id']},
            'versions': [{'rate': '17.375', 'treatment': 'TAXABLE', 'tax_nature_code_id': None,
                          'legal_reference': 'Synthetic configurable rate', 'valid_from': self.start, 'valid_to': None}]}, 201)
        for kind in ('item', 'partner'):
            self.req(kind + '-classifications/templates/install', 'POST',
                     {'country_id': self.country_id, 'tax_type_id': self.vat['id']})
        self.item_classes = {x['code']: x for x in self.req('item-classifications', pageSize=100)['items']}
        self.partner_classes = {x['code']: x for x in self.req('partner-classifications', pageSize=100)['items']}
        # A methodName must be real; use the first default-loader method, not a guess.
        self.source = TaxClassificationHttp(unittest.defaultTestLoader.getTestCaseNames(TaxClassificationHttp)[0])
        self.source.root, self.source.fixture = self.root, self.fixture
        self.source.code, self.source.tenant_id = self.code, self.tenant_id
        self.source.country_id, self.source.vat = self.country_id, self.vat
        self.items = {}
        for kind, classification in (('GOOD', 'GENERAL_GOODS'), ('SERVICE', 'GENERAL_SERVICES')):
            payload = self.source.subject_payload('item')
            item_type = next(t for t in self.source.item_refs['types'] if t['kind'] == kind)
            payload['values']['item_type_id'] = item_type['id']
            payload['taxProfiles'] = [self.source.profile('item', self.item_classes[classification], valid_from=self.start)]
            status, item = self.root.request(self.source.subject_endpoint('item', write=True), 'POST', payload)
            self.assertEqual(status, 201, item)
            # Catalog source must be usable for new use, not silently assumed ACTIVE.
            if item['status'] != 'ACTIVE':
                status, item = self.root.request(self.scope('/api/catalog/items/' + item['id'] + '/status'),
                                                 'PUT', {'status': 'ACTIVE', 'expectedVersion': item['version']})
                self.assertEqual(status, 200, item)
            self.items[kind] = item
        self.partners = {code: self.source.subject('partner', taxProfiles=[
            self.source.profile('partner', self.partner_classes[code], valid_from=self.start)])
            for code in ('TAXABLE_PERSON', 'NON_TAXABLE_PERSON')}
        self.configuration = self.command(self.create(), 'activate')
        self.registration_id = self.configuration['registrations'][0]['id']

    def core(self, kind='GOOD', taxable=True, operation='SALE', **changes):
        return {'company_id': self.company['id'], 'business_partner_id': self.partners['TAXABLE_PERSON' if taxable else 'NON_TAXABLE_PERSON']['id'],
                'item_id': self.items[kind]['id'], 'tax_type_id': self.vat['id'], 'tax_date': self.day,
                'operation_type': operation, 'company_tax_registration_id': self.registration_id,
                'partner_acting_as_taxable_person': taxable,
                'dispatch_country_id': self.country_id if kind == 'GOOD' else None,
                'destination_country_id': self.country_id if kind == 'GOOD' else None,
                'service_location_country_id': self.country_id if kind == 'SERVICE' else None,
                'transaction_facts': {'operation_category': 'ORDINARY_MOVABLE_GOODS' if kind == 'GOOD' else 'GENERAL_SERVICES',
                    'partner_establishment_country_id': self.country_id, 'ordinary_vat_territory_confirmed': True,
                    'special_tax_treatment': 'NONE', 'goods_location_country_id': self.country_id if kind == 'GOOD' else None,
                    'goods_customs_status': 'NATIONAL_OR_UNION' if kind == 'GOOD' else None,
                    'source_reference': 'Synthetic declared facts; no VIES evidence'}, **changes}

    def simulate(self, body=None, expected=200, client=None):
        return self.req('determinations/simulate', 'POST', body if body is not None else self.core(), expected, client=client)

    def determine(self, body=None, expected=200, client=None):
        return self.req('determinations', 'POST', body if body is not None else self.core(), expected, client=client)

    def install(self, **changes):
        return self.req('rules/templates/install', 'POST', {'validFrom': self.day, **changes})

    def rule_route(self, rule):
        return 'rules/' + rule['id']

    def version_payload(self, conditions=None, **changes):
        return {'values': {'tax_code_id': self.tax_code['id'], 'priority': 100, 'operation_type': 'SALE',
                           'legal_reference': 'Synthetic configured ordinary VAT', 'valid_from': self.day,
                           'valid_to': None, **changes}, 'conditions': conditions or []}

    def new_rule(self, conditions=None, company=None, expected=201, **changes):
        return self.req('rules', 'POST', {'values': {'code': 'RULE_' + uuid.uuid4().hex[:12],
            'name': 'Synthetic rule', 'country_id': self.country_id, 'tax_type_id': self.vat['id'],
            'company_id': company}, 'versions': [self.version_payload(conditions, **changes)]}, expected)

    def transition(self, rule, action, version=None, expected=200, client=None):
        return self.req(self.rule_route(rule) + '/versions/' + (version or rule['versions'][-1])['id'] + '/' + action,
                        'POST', {'expectedVersion': rule['version']}, expected, client=client)

    def publish_templates(self):
        installed = self.install()
        self.assertEqual(len(installed['created']), 6)
        return [self.transition(rule, 'publish') for rule in installed['created']]

    def fingerprint(self):
        # Compare every application table, not only the three newly introduced ones.
        names = self.sql("SELECT schemaname||'.'||tablename FROM pg_tables WHERE schemaname IN ('foundation','masterdata','taxmanagement') ORDER BY 1;").splitlines()
        self.assertEqual(len(names), 65)
        statements = ["SELECT '" + name + "',md5(coalesce(string_agg(to_jsonb(t)::text,'' ORDER BY to_jsonb(t)::text),'')) FROM " + name + ' t' for name in names]
        return self.sql('SELECT * FROM (' + ' UNION ALL '.join(statements) + ') fingerprints ORDER BY 1;')

    def assert_success(self, result, simulation=True, rate='17.375000'):
        self.assertEqual((result['outcome'], result['isSimulation']), ('SUCCESS', simulation), result)
        row = result['result']
        self.assertEqual((row['taxCodeId'], row['rate'], row['treatment']), (self.tax_code['id'], rate, 'TAXABLE'))
        self.assertEqual((row['liableParty'], row['collectionMechanism']), ('SUPPLIER', 'STANDARD'))
        self.assertEqual(row['companyTaxRegistrationId'], self.registration_id)
        self.assertIsNone(row['taxNatureCode'])
        self.assertTrue(row['taxRuleId'] and row['taxRuleVersionId'] and row['taxCodeVersionId'])

    def test_01_current_baseline_catalog_and_lookups(self):
        self.assertEqual(self.sql("SELECT count(*) FROM pg_tables WHERE schemaname IN ('foundation','masterdata','taxmanagement');"), '65')
        rows = []
        for page in (1, 2):
            status, body = self.root.request(self.scope('/api/data/permissions?pageSize=100&page=' + str(page)))
            self.assertEqual(status, 200, body)
            rows += body['items']
        self.assertEqual((body['total'], len(rows), len({r['code'] for r in rows})), (144, 144, 144))
        self.assertTrue({'tax-rules.' + a for a in RULE_ACTIONS} | {'tax-determination.' + a for a in ('read', 'simulate', 'determine')} <= {r['code'] for r in rows})
        refs = self.req('rule-lookups')
        self.assertTrue({'countries','types','companies','codes','itemClassifications','partnerClassifications','regimes','fields','operators','permissions'} <= refs.keys())
        unavailable = next(x for x in refs['fields'] if x['key'] == 'partner.vatValidationStatus')
        self.assertFalse(unavailable['available'])

    def test_02_six_draft_templates_explicit_idempotence_and_no_real_outcome(self):
        first = self.install()
        self.assertEqual((len(first['created']), len(first['existing'])), (6, 0))
        self.assertTrue(all(len(r['versions']) == 1 and r['versions'][0]['status'] == 'DRAFT' for r in first['created']))
        snapshot = self.fingerprint()
        second = self.install()
        self.assertEqual((len(second['created']), set(second['existing'])), (0, {r['id'] for r in first['created']}))
        self.assertEqual(self.fingerprint(), snapshot)
        self.assertEqual(self.simulate()['outcome'], 'NO_MATCHING_RULE')
        self.determine(expected=422)
        selected = [first['created'][0]['versions'][0]['id']]
        preview = self.simulate({**self.core(), 'draft_version_ids': selected})
        self.assertTrue(preview['isSimulation'])
        self.assertEqual(self.fingerprint(), snapshot)
        self.determine({**self.core(), 'draft_version_ids': []}, expected=400)

    def test_03_six_published_branches_same_configured_rules_and_dynamic_rate(self):
        roots = self.publish_templates()
        before = self.fingerprint()
        winners = set()
        for kind, taxable, operation in [('GOOD',True,'SALE'),('GOOD',False,'SALE'),('SERVICE',True,'SALE'),('SERVICE',False,'SALE'),('GOOD',True,'PURCHASE'),('SERVICE',True,'PURCHASE')]:
            with self.subTest(kind=kind,taxable=taxable,operation=operation):
                body = self.core(kind,taxable,operation)
                result = self.simulate(body)
                self.assert_success(result)
                winners.add(result['result']['taxRuleVersionId'])
                self.assert_success(self.determine(body), False)
        self.assertEqual(winners, {r['versions'][0]['id'] for r in roots})
        self.assertEqual(self.fingerprint(), before, 'Simulation AND operational consultation are read-only across all 65 tables')

    def test_04_missing_facts_unknown_and_positive_unsupported_never_fallback(self):
        self.publish_templates()
        for field in ('ordinary_vat_territory_confirmed','special_tax_treatment','partner_establishment_country_id','goods_customs_status','goods_location_country_id','operation_category'):
            body = self.core(); body['transaction_facts'][field] = None
            with self.subTest(missing=field):
                result = self.simulate(body)
                self.assertEqual(result['outcome'], 'INCOMPLETE_CONTEXT', result)
                self.assertIsNone(result['result'])
                trace_field = {'ordinary_vat_territory_confirmed':'transaction.ordinaryVatTerritoryConfirmed',
                               'special_tax_treatment':'transaction.specialTaxTreatment',
                               'partner_establishment_country_id':'partner.establishmentCountry',
                               'goods_customs_status':'transaction.goodsCustomsStatus',
                               'goods_location_country_id':'transaction.goodsLocationCountry',
                               'operation_category':'transaction.operationCategory'}[field]
                self.assertIn(trace_field, result['trace']['missingFields'])
        for field, value in [('ordinary_vat_territory_confirmed',False),('special_tax_treatment','REVERSE_CHARGE'),('goods_customs_status','OTHER')]:
            body = self.core(); body['transaction_facts'][field] = value
            self.assertEqual(self.simulate(body)['outcome'], 'UNSUPPORTED_OPERATION')
        self.assertEqual(self.simulate(self.core(partner_acting_as_taxable_person=None))['outcome'], 'INCOMPLETE_CONTEXT')
        self.assertEqual(self.simulate(self.core(taxable=False,operation='PURCHASE'))['outcome'], 'UNSUPPORTED_OPERATION')

    def test_05_future_rule_and_taxcode_versions_withdraw_history(self):
        rule = self.transition(self.new_rule(), 'publish')
        future = max(date(2027,1,1), self.today + timedelta(days=30)).isoformat()
        values = {'rate':'19.125','treatment':'TAXABLE','tax_nature_code_id':None,'legal_reference':'Synthetic future rate','valid_from':future,'valid_to':None}
        code = self.req('codes/' + self.tax_code['id'] + '/versions','POST',{'values':values,'expectedVersion':self.tax_code['version']})
        rule = self.req(self.rule_route(rule)+'/versions','POST',{**self.version_payload(valid_from=future),'expectedVersion':rule['version']},201)
        rule = self.transition(rule,'publish',rule['versions'][-1])
        self.assertEqual(rule['versions'][0]['valid_to'], (date.fromisoformat(future)-timedelta(days=1)).isoformat())
        self.assert_success(self.simulate())
        later = self.simulate(self.core(tax_date=future)); self.assert_success(later,rate='19.125000')
        self.assertIn('15', json.dumps(later['trace']))
        self.assertEqual(later['result']['taxCodeVersionId'], next(v['id'] for v in code['versions'] if v['valid_from']==future))
        rule = self.transition(rule,'withdraw',rule['versions'][-1])
        self.assertEqual(rule['versions'][-1]['status'],'WITHDRAWN')
        self.assertEqual(self.simulate(self.core(tax_date=future))['outcome'],'NO_MATCHING_RULE')
        self.assert_success(self.simulate())

    def test_06_conflict_tie_scope_overlap_and_priority(self):
        first = self.transition(self.new_rule(), 'publish')
        tie = self.new_rule(company=self.company['id'])
        validation = self.transition(tie,'validate')
        self.assertFalse(validation['valid']); self.assertTrue(validation['conflicts'])
        self.transition(tie,'publish',expected=409)
        higher = self.transition(self.new_rule(priority=101),'publish')
        self.assertEqual(self.simulate()['result']['taxRuleId'],higher['id'])
        self.assertNotEqual(first['id'],higher['id'])

    def test_07_competitive_unknown_blocks_lower_known_rule(self):
        self.transition(self.new_rule(priority=10),'publish')
        unknown = [{'field':'partner.taxIdentifierCountry','operator':'NOT_EQUALS','value':self.countries['DE']['id']}]
        self.transition(self.new_rule(unknown,priority=20),'publish')
        result = self.simulate()
        self.assertEqual(result['outcome'],'INCOMPLETE_CONTEXT',result)
        self.assertIsNone(result['result'])
        self.assertIn('UNKNOWN',json.dumps(result['trace']))

    def test_08_explicit_preview_one_draft_per_root_and_no_writes(self):
        rule = self.transition(self.new_rule(),'publish')
        published = self.simulate()
        rule = self.req(self.rule_route(rule)+'/versions','POST',{**self.version_payload(priority=110),'expectedVersion':rule['version']},201)
        draft = rule['versions'][-1]
        rule = self.req(self.rule_route(rule)+'/versions','POST',{**self.version_payload(priority=120),'expectedVersion':rule['version']},201)
        before = self.fingerprint()
        preview = self.simulate({**self.core(),'draft_version_ids':[draft['id']]})
        self.assertEqual(preview['result']['taxRuleVersionId'],draft['id'])
        self.assertEqual(self.simulate()['result']['taxRuleVersionId'],published['result']['taxRuleVersionId'])
        self.simulate({**self.core(),'draft_version_ids':[draft['id'],rule['versions'][-1]['id']]},expected=400)
        self.assertEqual(self.fingerprint(),before)

    def test_09_strict_input_uuid_unknown_keys_enums_and_dates(self):
        for patch in ({'company_id':'not-uuid'},{'tax_date':'2026-02-30'},{'tax_date':'2026-1-01'},
                      {'operation_type':'BUY'},{'status':'ACTIVE'},{'amount':'100'},{'organization_id':self.tenant_id},
                      {'partner_acting_as_taxable_person':'true'},{'partnerTaxRegistrationId':str(uuid.uuid4())}):
            with self.subTest(patch=patch): self.simulate({**self.core(),**patch},expected=400)
        body=self.core(); body['transaction_facts']['mystery']=True
        self.simulate(body,expected=400)
        for text in ('x\x00y','x\ud800y','x'*256):
            body=self.core(); body['transaction_facts']['source_reference']=text
            self.simulate(body,expected=400)

    def test_10_duplicate_json_keys_rejected_before_write(self):
        # Client.request serializes dictionaries; send raw JSON through its real cookie opener.
        if not self.root.token: self.root.token=self.root.request('/api/auth/csrf')[1]['token']
        raw=json.dumps(self.core())[:-1]+',"company_id":"'+self.company['id']+'"}'
        request=urllib.request.Request(self.fixture.ORIGIN+self.path('determinations/simulate'),data=raw.encode(),method='POST',
            headers={'Origin':self.fixture.ORIGIN,'Content-Type':'application/json','X-CSRF-TOKEN':self.root.token})
        try: response=self.root.opener.open(request,timeout=20)
        except urllib.error.HTTPError as error: response=error
        with response: self.assertEqual(response.status,400,response.read())

    def test_11_conditions_typed_limits_duplicates_and_unavailable_vies(self):
        bad = [[{'field':'raw.anything','operator':'EQUALS','value':'x'}],
               [{'field':'item.nature','operator':'MATCHES','value':'GOOD'}],
               [{'field':'partner.actingAsTaxablePerson','operator':'EQUALS','value':'true'}],
               [{'field':'item.nature','operator':'IN','value':['GOOD','GOOD']}],
               [{'field':'item.nature','operator':'IN','value':[]}]]
        cond={'field':'item.nature','operator':'EQUALS','value':'GOOD'}
        bad += [[cond,cond],[cond]*101]
        before=self.req('rules')['total']
        for conditions in bad:
            with self.subTest(conditions=conditions[:2]): self.new_rule(conditions,expected=400)
        self.assertEqual(self.req('rules')['total'],before)
        snapshot=self.fingerprint()
        rejected=self.new_rule([{'field':'partner.vatValidationStatus','operator':'EQUALS','value':'VALID'}],expected=400)
        self.assertEqual((rejected['code'],rejected['field']),('tax_rule_field_unavailable','partner.vatValidationStatus'))
        self.assertEqual(self.fingerprint(),snapshot)

    def test_12_root_and_version_revisions_metadata_stale_and_lifecycle(self):
        rule=self.new_rule(); draft=rule['versions'][0]
        changed=self.req(self.rule_route(rule),'PUT',{'values':{'name':'Metadata only','description':'Independent'},'expectedVersion':rule['version']})
        self.assertEqual(changed['version'],rule['version']+1)
        self.assertEqual(changed['versions'],rule['versions'])
        self.transition(rule,'publish',expected=409)
        before=self.fingerprint(); self.transition(changed,'validate'); self.assertEqual(self.fingerprint(),before)
        published=self.transition(changed,'publish')
        self.assertEqual(published['version'],changed['version']+1)
        self.req(self.rule_route(published)+'/versions/'+draft['id'],'PUT',{**self.version_payload(),'expectedVersion':published['version']},409)
        self.req(self.rule_route(published),'PUT',{'values':{'company_id':self.company['id']},'expectedVersion':published['version']},400)
        self.req(self.rule_route(published),'DELETE',expected=(404,405))
        self.req(self.rule_route(published)+'/versions','POST',{**self.version_payload(status='PUBLISHED'),'expectedVersion':published['version']},400)

    def test_13_audit_commit_failure_atomic_root_versions_and_revision(self):
        rule=self.new_rule(); before=self.fingerprint()
        self.sql("CREATE FUNCTION taxmanagement.phase4_reject_audit() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF NEW.tenant_id='"+self.tenant_id+"'::uuid THEN RAISE EXCEPTION 'Synthetic deferred audit rejection'; END IF; RETURN NEW; END $$; CREATE CONSTRAINT TRIGGER phase4_reject_audit AFTER INSERT ON foundation.audit_event DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION taxmanagement.phase4_reject_audit();")
        try:
            self.transition(rule,'publish',expected=500)
            self.req(self.rule_route(rule),'PUT',{'values':{'name':'Must rollback','description':None},'expectedVersion':rule['version']},500)
            self.req(self.rule_route(rule)+'/versions','POST',{**self.version_payload(),'expectedVersion':rule['version']},500)
            self.new_rule(expected=500)
            self.assertEqual(self.req(self.rule_route(rule)),rule)
            self.assertEqual(self.fingerprint(),before)
        finally:
            self.sql('DROP TRIGGER phase4_reject_audit ON foundation.audit_event; DROP FUNCTION taxmanagement.phase4_reject_audit();')

    def test_14_read_simulate_determine_dedicated_permissions_and_revocation(self):
        self.publish_templates()
        actor,role,_=self.actor(SOURCE_READS+['tax-determination.read','tax-determination.simulate'])
        self.assign_companies(role,[self.company])
        self.assert_success(self.simulate(client=actor))
        self.determine(client=actor,expected=403)
        self.req('rules',client=actor,expected=403)
        self.req('determination-lookups',client=actor,company_id=self.company['id'],date=self.day,tax_type_id=self.vat['id'])
        self.assertEqual(self.root.request(self.scope('/api/links/role-permissions/'+role['id']),'PUT',{'ids':[]})[0],204)
        self.simulate(client=actor,expected=403)
        self.req('determination-lookups',client=actor,company_id=self.company['id'],expected=403)

    def test_15_source_permissions_each_required_no_editor_grants(self):
        self.publish_templates()
        for missing in SOURCE_READS:
            with self.subTest(missing=missing):
                actor,role,_=self.actor([x for x in SOURCE_READS if x!=missing]+['tax-determination.read','tax-determination.simulate'])
                self.assign_companies(role,[self.company]); self.simulate(client=actor,expected=403)

    def test_16_crossed_roles_disabled_membership_company_and_tenant_isolation(self):
        rule=self.new_rule(company=self.company['id'])
        actor,action_role,_=self.actor(['companies.read','tax-rules.read','tax-rules.publish'])
        other=self.company_create(); self.assign_companies(action_role,[other])
        status,scope_role=self.root.request(self.scope('/api/data/roles'),'POST',{'name':'Scope without action'})
        self.assertEqual(status,201,scope_role)
        user=actor.request('/api/session')[1]['id']
        self.assertEqual(self.root.request(self.scope('/api/links/user-roles/'+user),'PUT',{'ids':[action_role['id'],scope_role['id']]})[0],204)
        self.assign_companies(scope_role,[self.company])
        self.transition(rule,'publish',expected=403,client=actor)
        listing=self.req('rules',client=actor)
        self.assertNotIn(rule['id'],{x['id'] for x in listing['items']})
        self.assign_companies(action_role,[self.company])
        self.req(self.rule_route(rule),client=actor)
        status,disabled=self.root.request(self.scope('/api/data/roles/'+action_role['id']),'PUT',{'is_enabled':False})
        self.assertEqual(status,200,disabled)
        self.transition(rule,'publish',expected=403,client=actor)
        status,tenant=self.root.request('/api/data/tenants','POST',{'code':'foreign-'+uuid.uuid4().hex[:10],'name':'Other synthetic tenant'})
        self.assertEqual(status,201,tenant)
        self.req(self.rule_route(rule),tenant=tenant['id'],expected=404)
        self.simulate(self.core(item_id=str(uuid.uuid4())),expected=(403,404))

    def test_17_current_bp_identifier_country_truth_without_raw_values_or_vies(self):
        partner=self.partners['TAXABLE_PERSON']
        raw='DE'+str(uuid.uuid4().int % 1000000000).zfill(9)
        status,updated=self.root.request(self.source.subject_endpoint('partner',partner,True),'PUT',
            {'values':{},'expectedVersion':partner['version'],'taxIdentifiers':[{'country_code':'DE','identifier_type':'VAT','value':raw}]})
        self.assertEqual(status,200,updated)
        # Read current regenerated IDs from the authoritative BP endpoint.
        current=self.source.subject_read('partner',updated)
        identifiers=current['tax_identifiers']
        self.assertEqual(len(identifiers),1)
        identifier=identifiers[0]
        rule=self.transition(self.new_rule([{'field':'partner.taxIdentifierCountry','operator':'EQUALS','value':self.countries['DE']['id']}]),'publish')
        result=self.simulate(self.core(partner_tax_identifier_id=identifier['id']))
        self.assert_success(result)
        trace=json.dumps(result['trace'])
        self.assertIn(identifier['id'],trace); self.assertNotIn(raw,trace)
        self.assertNotIn('partnerTaxRegistrationId',trace)
        self.simulate(self.core(partner_tax_identifier_id=str(uuid.uuid4())),expected=(400,404))
        self.assertEqual(result['result']['taxRuleId'],rule['id'])

    def test_18_withdraw_determination_barrier_public_advisory_key(self):
        rule=self.transition(self.new_rule(),'publish')
        key='tax-determination:rules:'+self.tenant_id+':'+self.country_id+':'+self.vat['id']+':SALE'
        # A real SQL session holds the exact normative key. Both HTTP operations
        # must demonstrably wait; releasing it yields one coherent legal ordering.
        self.assertTrue(self.fixture.verify_target(self.fixture.DB))
        process=subprocess.Popen(['docker','exec','-i',self.fixture.DB,'psql','-X','-qAt','-U','postgres','-d','enginia360','-v','ON_ERROR_STOP=1'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        self.addCleanup(lambda: process.communicate('ROLLBACK;\n\\q\n',timeout=10) if process.poll() is None else None)
        process.stdin.write("BEGIN; SELECT 'phase4-barrier-ready' FROM (SELECT pg_advisory_xact_lock(hashtextextended('"+key+"',0))) held;\n"); process.stdin.flush()
        import select
        ready=False
        deadline=time.monotonic()+10
        while time.monotonic()<deadline:
            if select.select([process.stdout],[],[],.2)[0] and process.stdout.readline().strip()=='phase4-barrier-ready': ready=True; break
        self.assertTrue(ready,'Barrier SQL not acquired')
        clients=[login_root()[0],login_root()[0]]
        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                withdrawn=pool.submit(clients[0].request,self.path(self.rule_route(rule)+'/versions/'+rule['versions'][0]['id']+'/withdraw'),'POST',{'expectedVersion':rule['version']})
                determined=pool.submit(clients[1].request,self.path('determinations'),'POST',self.core())
                deadline=time.monotonic()+8
                while time.monotonic()<deadline:
                    waiting=int(self.sql("SELECT count(*) FROM pg_stat_activity WHERE datname='enginia360' AND wait_event='advisory';"))
                    if waiting>=2: break
                    time.sleep(.1)
                both_blocked = not withdrawn.done() and not determined.done()
                process.stdin.write('COMMIT;\n\\q\n'); process.stdin.flush()
                self.assertGreaterEqual(waiting,2,'Both operations must acquire the exact public key')
                self.assertTrue(both_blocked)
                self.assertEqual(withdrawn.result(timeout=20)[0],200)
                status,result=determined.result(timeout=20)
                self.assertIn(status,(200,422),result)
                if status==200:
                    self.assert_success(result,False)
                    self.assertEqual(result['result']['taxRuleVersionId'],rule['versions'][0]['id'])
                else:
                    self.assertIn('NO_MATCHING_RULE',json.dumps(result))
        finally:
            if process.poll() is None:
                process.stdin.write('ROLLBACK;\n\\q\n'); process.stdin.flush()
            process.communicate(timeout=10)
        self.assertEqual(self.simulate()['outcome'],'NO_MATCHING_RULE')

    def test_19_conditions_exactly100_supported_references_and_int32_bounds(self):
        status,countries=self.root.request('/api/data/countries?pageSize=100&page=1')
        self.assertEqual(status,200,countries)
        status,second=self.root.request('/api/data/countries?pageSize=100&page=2')
        self.assertEqual(status,200,second)
        ids=[c['id'] for c in countries['items']+second['items'] if c['id']!=self.country_id][:100]
        self.assertEqual(len(set(ids)),100)
        conditions=[{'field':'transaction.destinationCountry','operator':'NOT_EQUALS','value':identifier} for identifier in ids]
        rule=self.new_rule(conditions,priority=-2147483648)
        self.assertEqual(len(rule['versions'][0]['conditions']),100)
        self.assertTrue(self.transition(rule,'validate')['valid'])
        self.new_rule(conditions+[{'field':'item.nature','operator':'EQUALS','value':'GOOD'}],expected=400)
        self.new_rule(priority=2147483648,expected=400)
        self.new_rule(priority=-2147483649,expected=400)
        self.new_rule(priority=1.5,expected=400)

    def test_20_template_prerequisite_failure_zero_mutations(self):
        status,tenant=self.root.request('/api/data/tenants','POST',{'code':'empty-'+uuid.uuid4().hex[:10],'name':'Missing explicit tax prerequisites'})
        self.assertEqual(status,201,tenant)
        before=self.fingerprint()
        failure=self.req('rules/templates/install','POST',{'validFrom':self.day},409,tenant=tenant['id'])
        self.assertTrue(failure['code'])
        self.assertEqual(self.fingerprint(),before)
        self.assertEqual(self.req('rules',tenant=tenant['id'])['total'],0)

    def test_21_winning_unavailable_taxcode_never_uses_lower_rule(self):
        self.transition(self.new_rule(priority=1),'publish')
        alternative=self.req('codes','POST',{
            'values':{'code':'ALT_'+uuid.uuid4().hex[:8],'name':'Alternate configured code','country_id':self.country_id,'tax_type_id':self.vat['id']},
            'versions':[{'rate':'11.25','treatment':'TAXABLE','tax_nature_code_id':None,'valid_from':self.start,'valid_to':None}]},201)
        winner=self.transition(self.new_rule(priority=200,tax_code_id=alternative['id']),'publish')
        self.req('codes/'+alternative['id']+'/deactivate','POST',{'expectedVersion':alternative['version']})
        outcome=self.simulate()
        self.assertEqual(outcome['outcome'],'TAX_CODE_UNAVAILABLE',outcome)
        self.assertIsNone(outcome['result'])
        self.assertIn(winner['id'],json.dumps(outcome['trace']))
        self.determine(expected=422)

    def test_22_rule_publish_dedicated_without_validate_and_csrf(self):
        rule=self.new_rule(company=self.company['id'])
        actor,role,_=self.actor(['companies.read','tax-rules.read','tax-rules.publish'])
        self.assign_companies(role,[self.company])
        self.transition(rule,'validate',client=actor,expected=403)
        published=self.transition(rule,'publish',client=actor)
        self.assertEqual(published['versions'][0]['status'],'PUBLISHED')
        self.transition(published,'withdraw',client=actor,expected=403)
        route=self.path(self.rule_route(published))
        body={'values':{'name':'CSRF must not mutate'},'expectedVersion':published['version']}
        self.assertIn(self.root.request(route,'PUT',body,csrf=False)[0],(400,403))
        self.assertEqual(self.root.request(route,'PUT',body,origin='https://foreign.invalid')[0],403)
        self.assertEqual(self.req(self.rule_route(published)),published)


    def test_23_group_role_membership_fresh_disabled_and_removed(self):
        self.transition(self.new_rule(),'publish')
        actor,role,_=self.actor(SOURCE_READS+['tax-determination.read','tax-determination.simulate'])
        self.assign_companies(role,[self.company])
        user=actor.request('/api/session')[1]['id']
        status,group=self.root.request(self.scope('/api/data/groups'),'POST',{'name':'Synthetic indirect authority'})
        self.assertEqual(status,201,group)
        for relation,owner,ids in [('user-roles',user,[]),('group-users',group['id'],[user]),('group-roles',group['id'],[role['id']])]:
            self.assertEqual(self.root.request(self.scope('/api/links/'+relation+'/'+owner),'PUT',{'ids':ids})[0],204)
        self.assert_success(self.simulate(client=actor))
        self.assertEqual(self.root.request(self.scope('/api/data/groups/'+group['id']),'PUT',{'is_enabled':False})[0],200)
        self.simulate(client=actor,expected=403)
        self.assertEqual(self.root.request(self.scope('/api/data/groups/'+group['id']),'PUT',{'is_enabled':True})[0],200)
        self.assert_success(self.simulate(client=actor))
        self.assertEqual(self.root.request(self.scope('/api/links/group-users/'+group['id']),'PUT',{'ids':[]})[0],204)
        self.simulate(client=actor,expected=403)


def load_tests(loader, tests, pattern):
    # Imported predecessor TestCases are helpers, never implicit acceptance.
    return loader.loadTestsFromTestCase(TaxDeterminationHttp)


if __name__ == '__main__':
    unittest.main()
