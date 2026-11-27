"""Acceptance HTTP F5: sorgenti vere, stringhe decimali e nessuna fixture implicita.

La discovery non legge credenziali e non avvia servizi. Solo il wrapper autorizzato
può eseguire questi casi sulle due immagini candidate consegnate dal coordinatore.
Gli helper F4 sono composti per nome, mai tramite ereditarietà dei suoi TestCase.
"""
from copy import deepcopy
from decimal import Decimal
from fractions import Fraction
import itertools
import json
import os
from pathlib import Path
import unittest
import urllib.error
import urllib.request
import uuid

from tax_helpers import configure_fixture, login_root
from test_tax_determination_http import TaxDeterminationHttp, SOURCE_READS

CALCULATION_READ = 'tax-calculation.read'
CALCULATION_SIMULATE = 'tax-calculation.simulate'
CALCULATION_ACTUAL = 'tax-calculation.calculate'
ACQUIRE_SIMULATE = 'tax-determination.simulate'
ACQUIRE_ACTUAL = 'tax-determination.determine'
SIMULATION_GRANTS = SOURCE_READS + [CALCULATION_READ, CALCULATION_SIMULATE,
                                    'tax-determination.read', ACQUIRE_SIMULATE]
ALL_GRANTS = SIMULATION_GRANTS + [CALCULATION_ACTUAL, ACQUIRE_ACTUAL]
REFERENCE_CASES = (
    '01_exclusive_100_22', '02_inclusive_122_22', '03_discount10',
    '04_sequential10_5', '05_multirate', '06_document_discount15',
    '07_three_small_group_rounding', '08_purchase40', '09_reversal',
    '10_currency_mismatch', '11_discount_over_capacity',
    '12_unsupported_treatment', '13_foreign_tenant_source',
)


def adjustment(value, sequence=1, kind='DISCOUNT', mode='PERCENTAGE', **extra):
    return {'adjustment_id': str(uuid.uuid4()), 'type': kind,
            'calculation_mode': mode, 'value': value, 'sequence': sequence, **extra}


class TaxCalculationHttp(unittest.TestCase):
    # Elenco deliberatamente finito: aggiungere un helper richiede review esplicita.
    actor = TaxDeterminationHttp.actor
    path = TaxDeterminationHttp.path
    scope = TaxDeterminationHttp.scope
    req = TaxDeterminationHttp.req
    sql = TaxDeterminationHttp.sql
    company_create = TaxDeterminationHttp.company_create
    company_read = TaxDeterminationHttp.company_read
    identifier = TaxDeterminationHttp.identifier
    profile = TaxDeterminationHttp.profile
    registration = TaxDeterminationHttp.registration
    payload = TaxDeterminationHttp.payload
    list_route = TaxDeterminationHttp.list_route
    route = TaxDeterminationHttp.route
    create = TaxDeterminationHttp.create
    command = TaxDeterminationHttp.command
    assign_companies = TaxDeterminationHttp.assign_companies
    core = TaxDeterminationHttp.core
    simulate = TaxDeterminationHttp.simulate
    determine = TaxDeterminationHttp.determine
    rule_route = TaxDeterminationHttp.rule_route
    version_payload = TaxDeterminationHttp.version_payload
    new_rule = TaxDeterminationHttp.new_rule
    transition = TaxDeterminationHttp.transition
    fingerprint = TaxDeterminationHttp.fingerprint

    @classmethod
    def setUpClass(cls):
        if os.environ.get('ENGINIA360_TAX_CALCULATION_PROOF') != '1':
            raise RuntimeError('Runtime vietato: usare il wrapper F5 con handoff esclusivo')
        cls.fixture = configure_fixture('enginia360-company-tax-proof')
        cls.fixture.EVIDENCE = Path(os.environ['ENGINIA360_COMPANY_TAX_EVIDENCE'])
        if not all(cls.fixture.verify_target(x) for x in (cls.fixture.DB, cls.fixture.API)):
            raise RuntimeError('Scope isolato F5 assente o non verificato')
        cls.root, cls.credentials = login_root()

    def setUp(self):
        TaxDeterminationHttp.setUp(self)
        self.codes = {}
        self.rules = {}
        # Le aliquote NON sono JSON fiscali del client: si configurano via API.
        for kind, rate in (('GOOD', '22'), ('SERVICE', '10')):
            self.codes[kind] = self.req('codes', 'POST', {
                'values': {'code': 'F5_' + kind, 'name': 'Aliquota sintetica ' + rate,
                           'country_id': self.country_id, 'tax_type_id': self.vat['id']},
                'versions': [{'rate': rate, 'treatment': 'TAXABLE', 'tax_nature_code_id': None,
                              'legal_reference': 'Riferimento aritmetico sintetico F5',
                              'valid_from': self.start, 'valid_to': None}]}, 201)
            for operation in ('SALE', 'PURCHASE'):
                rule = self.new_rule([{'field': 'item.nature', 'operator': 'EQUALS', 'value': kind}],
                                     tax_code_id=self.codes[kind]['id'], operation_type=operation)
                self.rules[kind, operation] = self.transition(rule, 'publish')

    def line(self, price='100', kind='GOOD', operation='SALE', **extra):
        return {'line_id': str(uuid.uuid4()), 'quantity': '1', 'unit_price': price,
                'price_mode': 'TAX_EXCLUSIVE', 'adjustments': [],
                'fiscal_context': self.core(kind=kind, operation=operation), **extra}

    def document(self, lines=None, operation='SALE', **extra):
        return {'company_id': self.company['id'], 'currency': 'EUR',
                'operation_type': operation, 'direction': 'NORMAL',
                'lines': lines if lines is not None else [self.line(operation=operation)],
                'document_adjustments': [], **extra}

    def calculate(self, body=None, simulation=True, expected=200, client=None):
        output = self.req('calculations' + ('/simulate' if simulation else ''), 'POST',
                          body if body is not None else self.document(), expected, client=client)
        if expected == 200:
            self.assertEqual(set(output), {'isSimulation', 'result'}, output)
            self.assertIs(output['isSimulation'], simulation)
            self.reconciles(output['result'])
            return output['result']
        return output

    def policy(self, expected=200, client=None):
        return self.req('calculation-policy', company_id=self.company['id'], currency='EUR',
                        expected=expected, client=client)

    def reconciles(self, result):
        self.assertEqual((result['currency'], result['calculationPolicyCode'],
                          result['calculationPolicyVersion']), ('EUR', 'IT_VAT_STANDARD_V1', 1))
        self.assertTrue(result['calculationTrace'])
        totals = result['totals']
        for line in result['lines']:
            for key in ('netBeforeAdjustments', 'netDiscountAmount', 'netSurchargeAmount',
                        'netAmount', 'taxableAmount', 'taxAmount', 'invoiceTaxAmount',
                        'grossAmount', 'roundingAdjustment', 'netRoundingAdjustment',
                        'taxRoundingAdjustment'):
                self.assertRegex(line[key], r'^-?[0-9]+\.[0-9]{2}$', (key, line))
                self.assertNotEqual(line[key], '-0.00')
            self.assertEqual(Decimal(line['netAmount']) + Decimal(line['invoiceTaxAmount']),
                             Decimal(line['grossAmount']))
            self.assertEqual(Decimal(line['netBeforeAdjustments']) - Decimal(line['netDiscountAmount'])
                             + Decimal(line['netSurchargeAmount']) + Decimal(line['netRoundingAdjustment']),
                             Decimal(line['netAmount']))
            if line['deductibility'] is not None:
                split = line['deductibility']
                self.assertEqual(Decimal(split['deductibleAmount']) + Decimal(split['nonDeductibleAmount']),
                                 Decimal(line['taxAmount']))
        for line_key, total_key in (('netAmount', 'netAmount'), ('taxableAmount', 'totalTaxableAmount'),
                                    ('taxAmount', 'totalTaxAmount'), ('invoiceTaxAmount', 'totalInvoiceTaxAmount'),
                                    ('grossAmount', 'grossAmount')):
            line_sum = sum((Decimal(x[line_key]) for x in result['lines']), Decimal(0))
            summary_sum = sum((Decimal(x[line_key]) for x in result['summaries']), Decimal(0))
            self.assertEqual(line_sum, summary_sum, (line_key, result))
            self.assertEqual(line_sum, Decimal(totals[total_key]))
        self.assertEqual(totals['grossAmount'], totals['amountPayable'])
        self.assertEqual(Decimal(totals['netAmount']) + Decimal(totals['totalInvoiceTaxAmount']),
                         Decimal(totals['amountPayable']))
        trace = result['calculationTrace']
        self.assertEqual(len(trace['sources']), len(result['lines']))
        self.assertEqual({x['lineId'] for x in trace['sources']}, {x['lineId'] for x in result['lines']})
        for item in trace['adjustments']:
            self.assertEqual(sum((Fraction(x['priceBaseAmountExact']) for x in item['allocations']), Fraction(0)),
                             Fraction(item['priceBaseAmountExact']))

    def assert_totals(self, result, net, tax, gross):
        self.assertEqual(tuple(result['totals'][x] for x in ('netAmount', 'totalTaxAmount', 'amountPayable')),
                         (net, tax, gross))

    def raw_post(self, route, text):
        if not self.root.token:
            self.root.token = self.root.request('/api/auth/csrf')[1]['token']
        request = urllib.request.Request(self.fixture.ORIGIN + self.path(route), data=text.encode(),
                                        method='POST', headers={'Origin': self.fixture.ORIGIN,
                                        'Content-Type': 'application/json', 'X-CSRF-TOKEN': self.root.token})
        try:
            response = self.root.opener.open(request, timeout=60)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            payload = response.read()
            return response.status, payload

    def test_01_catalog_policy_and_independent_read(self):
        permissions = []
        for page in (1, 2):
            status, body = self.root.request(self.scope('/api/data/permissions?pageSize=100&page=' + str(page)))
            self.assertEqual(status, 200, body)
            permissions.extend(body['items'])
        self.assertEqual((body['total'], len(permissions), len({x['code'] for x in permissions})), (147, 147, 147))
        self.assertTrue({CALCULATION_READ, CALCULATION_SIMULATE, CALCULATION_ACTUAL} <= {x['code'] for x in permissions})
        actor, role, _ = self.actor(['companies.read', CALCULATION_READ])
        self.assign_companies(role, [self.company])
        policy = self.policy(client=actor)
        self.assertEqual(policy['permissions'], ['read'])
        self.assertEqual((policy['policy']['code'], policy['policy']['version'], policy['currency']['minor_units']),
                         ('IT_VAT_STANDARD_V1', 1, 2))
        self.assertEqual(policy['policy']['roundingScope'], 'TAX_GROUP')
        self.assertEqual(policy['policy']['roundingMode'], 'HALF_UP')
        self.assertEqual(policy['policy']['residualAllocationMode'], 'LARGEST_REMAINDER')
        self.assertGreaterEqual(policy['policy']['internalScale'], 12)
        self.assertTrue(policy['currency']['id'])
        self.assertIsNotNone(policy['currency']['version'])
        self.calculate(client=actor, expected=403)

    def test_02_reference_first_six_real_configured_rates(self):
        scenarios = [
            (REFERENCE_CASES[0], self.document(), ('100.00', '22.00', '122.00')),
            (REFERENCE_CASES[1], self.document([self.line('122', price_mode='TAX_INCLUSIVE')]), ('100.00', '22.00', '122.00')),
            (REFERENCE_CASES[2], self.document([self.line(adjustments=[adjustment('10')])]), ('90.00', '19.80', '109.80')),
            (REFERENCE_CASES[3], self.document([self.line(adjustments=[adjustment('10'), adjustment('5', 2)])]), ('85.50', '18.81', '104.31')),
            (REFERENCE_CASES[4], self.document([self.line(), self.line('50', kind='SERVICE')]), ('150.00', '27.00', '177.00')),
            (REFERENCE_CASES[5], self.document([self.line(), self.line('50', kind='SERVICE')],
                document_adjustments=[adjustment('15', mode='FIXED_AMOUNT')]), ('135.00', '24.30', '159.30')),
        ]
        for name, body, totals in scenarios:
            with self.subTest(reference=name):
                for simulation in (True, False):
                    result = self.calculate(body, simulation=simulation)
                    self.assert_totals(result, *totals)
                    self.assertEqual({x['taxRate'] for x in result['lines']},
                                     {'22.000000', '10.000000'} if len(body['lines']) == 2 else {'22.000000'})
        for kind, rate in (('GOOD', '22.000000'), ('SERVICE', '10.000000')):
            result = self.calculate(self.document([self.line(kind=kind)]))
            self.assertEqual(result['lines'][0]['taxCodeId'], self.codes[kind]['id'])
            self.assertEqual(result['lines'][0]['taxRate'], rate)

    def test_03_three_small_rounding_permutations_inclusive_fractional(self):
        lines = [self.line('0.03', line_id=str(uuid.UUID(int=i))) for i in (1, 2, 3)]
        baseline = self.calculate(self.document(lines))
        self.assert_totals(baseline, '0.09', '0.02', '0.11')
        by_id = {x['lineId']: x['taxAmount'] for x in baseline['lines']}
        self.assertEqual([by_id[x['line_id']] for x in lines], ['0.01', '0.01', '0.00'])
        for permutation in itertools.permutations(lines):
            actual = self.calculate(self.document(list(permutation)))
            self.assertEqual({x['lineId']: x for x in actual['lines']}, {x['lineId']: x for x in baseline['lines']})
            self.assertEqual(actual['summaries'], baseline['summaries'])
            self.assertEqual(actual['calculationTrace'], baseline['calculationTrace'])
        for mode in ('TAX_INCLUSIVE', 'TAX_EXCLUSIVE'):
            # Tre batch veri = 300 righe, con frazioni e permutazione degli stessi ID.
            for batch in range(3):
                fractional = [self.line('0.01357913', quantity='0.333333', price_mode=mode,
                                       line_id=str(uuid.UUID(int=1000 + batch * 100 + i))) for i in range(100)]
                normal = self.calculate(self.document(fractional))
                reversed_input = self.calculate(self.document(list(reversed(fractional))))
                self.assertEqual(normal, reversed_input)
                if mode == 'TAX_INCLUSIVE':
                    exact = Decimal('0.01357913') * Decimal('0.333333') * 100
                    from decimal import ROUND_HALF_UP
                    self.assertEqual(normal['totals']['grossAmount'], str(exact.quantize(Decimal('.01'), rounding=ROUND_HALF_UP)))

    def test_04_sequence_document_allocations_and_ordinary_surcharge(self):
        first = self.line('100')
        second = self.line('50', kind='SERVICE')
        body = self.document([first, second], document_adjustments=[adjustment('15', mode='FIXED_AMOUNT')])
        result = self.calculate(body)
        self.assertEqual(sorted(x['netDiscountAmount'] for x in result['lines']), ['10.00', '5.00'])
        surcharge = self.document([first, second], document_adjustments=[adjustment('15', kind='SURCHARGE', mode='FIXED_AMOUNT')])
        self.assert_totals(self.calculate(surcharge), '165.00', '29.70', '194.70')
        line = self.line(adjustments=[adjustment('10', 1), adjustment('10', 2, kind='SURCHARGE', mode='FIXED_AMOUNT')])
        self.assert_totals(self.calculate(self.document([line])), '100.00', '22.00', '122.00')
        line['adjustments'].reverse()
        self.assert_totals(self.calculate(self.document([line])), '100.00', '22.00', '122.00')
        line['adjustments'][0]['sequence'], line['adjustments'][1]['sequence'] = 1, 2
        self.assert_totals(self.calculate(self.document([line])), '99.00', '21.78', '120.78')
        # Sconto sul lordo incluso: la traccia conserva la base prezzo lorda.
        inclusive = self.document([self.line('122', price_mode='TAX_INCLUSIVE')],
                                 document_adjustments=[adjustment('12.20', mode='FIXED_AMOUNT')])
        self.assert_totals(self.calculate(inclusive), '90.00', '19.80', '109.80')
        zero = self.calculate(self.document([self.line(adjustments=[adjustment('100')])]))
        self.assert_totals(zero, '0.00', '0.00', '0.00')
        self.calculate(self.document([self.line(adjustments=[adjustment('100.01', mode='FIXED_AMOUNT')])]), expected=422)
        scoped = deepcopy(body)
        scoped['document_adjustments'][0]['applicable_line_ids'] = [second['line_id']]
        scoped_result = self.calculate(scoped)
        untouched = next(x for x in scoped_result['lines'] if x['lineId'] == first['line_id'])
        self.assertEqual(untouched['netDiscountAmount'], '0.00')
        fractional = self.document([self.line('0.004'), self.line('0.006')],
                                   document_adjustments=[adjustment('100')])
        self.assert_totals(self.calculate(fractional), '0.00', '0.00', '0.00')
        weighted = self.document([self.line('0.12345678'), self.line('0.98765432')],
                                 document_adjustments=[adjustment('0.01', mode='FIXED_AMOUNT')])
        allocated = self.calculate(weighted)
        self.assertEqual(allocated, self.calculate({**weighted, 'lines': list(reversed(weighted['lines']))}))
        ordered_document = self.document([first, second], document_adjustments=[
            adjustment('10'), adjustment('15', 2, mode='FIXED_AMOUNT')])
        sequential = self.calculate(ordered_document)
        self.assertEqual((sequential['totals']['netAmount'], sequential['totals']['totalTaxAmount']),
                         ('120.00', '21.60'))
        self.assertEqual(sequential, self.calculate({**ordered_document,
            'document_adjustments': list(reversed(ordered_document['document_adjustments']))}))
        zero_weight = self.document([self.line(adjustments=[adjustment('100')]), self.line('50')],
                                   document_adjustments=[adjustment('5', kind='SURCHARGE', mode='FIXED_AMOUNT')])
        zero_result = self.calculate(zero_weight)
        zero_id = zero_weight['lines'][0]['line_id']
        self.assertEqual(next(x for x in zero_result['lines'] if x['lineId'] == zero_id)['netSurchargeAmount'], '0.00')

    def test_05_reversal_all_monetary_signs_and_trace_allocations(self):
        lines = [self.line('122', operation='PURCHASE', price_mode='TAX_INCLUSIVE', deductible_percentage='40',
                           adjustments=[adjustment('10'), adjustment('3.01', 2, 'SURCHARGE', 'FIXED_AMOUNT')]),
                 self.line('50', kind='SERVICE', operation='PURCHASE', price_mode='TAX_INCLUSIVE')]
        body = self.document(lines, operation='PURCHASE', document_adjustments=[adjustment('5.03', mode='FIXED_AMOUNT')])
        positive = self.calculate(body)
        negative = self.calculate({**body, 'direction': 'REVERSAL'})
        checked = []
        def symmetric(left, right, path=''):
            if isinstance(left, dict):
                self.assertEqual(set(left), set(right))
                for key in left:
                    symmetric(left[key], right[key], path + '.' + key)
            elif isinstance(left, list):
                self.assertEqual(len(left), len(right))
                for i, (a, b) in enumerate(zip(left, right)):
                    symmetric(a, b, path + '[' + str(i) + ']')
            elif isinstance(left, str) and (path.endswith('AmountExact') or
                    any(path.endswith('.' + key) for key in ('netBeforeAdjustments', 'netDiscountAmount',
                        'netSurchargeAmount', 'netAmount', 'taxableAmount', 'taxAmount', 'invoiceTaxAmount',
                        'grossAmount', 'amountPayable', 'totalTaxableAmount', 'totalNonTaxableAmount',
                        'totalTaxAmount', 'totalInvoiceTaxAmount', 'roundingAdjustment', 'netRoundingAdjustment',
                        'taxRoundingAdjustment', 'deductibleAmount', 'nonDeductibleAmount'))):
                self.assertEqual(Fraction(right), -Fraction(left), path)
                self.assertNotEqual(right, '-0.00', path)
                checked.append(path)
            else:
                self.assertEqual(left, right, path)
        symmetric(positive, negative)
        self.assertGreater(len(checked), 50)
        self.assert_totals(self.calculate(self.document(direction='REVERSAL')), '-100.00', '-22.00', '-122.00')

    def test_06_purchase_declared40_nullable_zero_and_sale_reject(self):
        for percentage, expected in [('40', ('88.00', '132.00')), ('0', ('0.00', '220.00')),
                                     ('100', ('220.00', '0.00')), (None, None)]:
            body = self.document([self.line('1000', operation='PURCHASE', deductible_percentage=percentage)], operation='PURCHASE')
            result = self.calculate(body)
            self.assert_totals(result, '1000.00', '220.00', '1220.00')
            split = result['lines'][0]['deductibility']
            if expected is None:
                self.assertIsNone(split)
            else:
                self.assertEqual((split['deductibleAmount'], split['nonDeductibleAmount']), expected)
        error = self.calculate(self.document([self.line(deductible_percentage='40')]), expected=400)
        self.assertEqual(error['field'], 'lines[0].deductible_percentage')

    def test_07_strict_numbers_overflow_unknown_fields_and_duplicate_json(self):
        for field, values in [('quantity', [1, True, None, '0', '-1', '1e2', '1,000', ' 1', '1.0000001', '100000000000000']),
                              ('unit_price', [1.2, '0', '-0.01', 'NaN', '1e2', '1,50', '1.000000001', '1000000000000'])]:
            for value in values:
                with self.subTest(field=field, value=value):
                    line = self.line(**{field: value})
                    error = self.calculate(self.document([line]), expected=400)
                    self.assertEqual(error['field'], 'lines[0].' + field)
        overflow = self.document([self.line('999999999999.99999999', quantity='99999999999999.999999')])
        self.calculate(overflow, expected=422)
        for field in ('policy', 'determination', 'tax_rate', 'result'):
            for level in ('document', 'line', 'context'):
                body = self.document()
                target = body if level == 'document' else body['lines'][0] if level == 'line' else body['lines'][0]['fiscal_context']
                target[field] = {'rate': '0', 'treatment': 'TAXABLE'}
                self.calculate(body, expected=400)
        for patch in ({'direction': 'CREDIT'}, {'currency': 'eur'}, {'lines': []}, {'document_adjustments': None}):
            self.calculate({**self.document(), **patch}, expected=400)
        for value in ('x\x00y', 'x\ud800y'):
            body = self.document()
            body['lines'][0]['fiscal_context']['transaction_facts']['source_reference'] = value
            self.calculate(body, expected=400)
        body = self.document()
        raw = json.dumps(body)[:-1] + ',"currency":"EUR"}'
        self.assertEqual(self.raw_post('calculations/simulate', raw)[0], 400)
        raw = json.dumps(body).replace('"quantity": "1"', '"quantity":"1","quantity":"2"', 1)
        self.assertEqual(self.raw_post('calculations/simulate', raw)[0], 400)
        raw = json.dumps(body).replace('"tax_date":', '"tax_date":"' + self.day + '","tax_date":', 1)
        self.assertEqual(self.raw_post('calculations/simulate', raw)[0], 400)

    def test_08_ids_sequences_limits_mixed_modes_and_scope(self):
        first = self.line()
        self.calculate(self.document([first, deepcopy(first)]), expected=400)
        for identifier in (uuid.uuid4().hex, '{' + str(uuid.uuid4()) + '}', str(uuid.UUID(int=0))):
            self.calculate(self.document([self.line(line_id=identifier)]), expected=400)
        for field, value in [('sequence', 0), ('sequence', 1.5), ('sequence', '1'), ('type', 'REBATE'),
                             ('value', '-1'), ('value', '1e2'), ('value', 10),
                             ('value', '100.000001'), ('calculation_mode', 'ABSOLUTE')]:
            bad = adjustment('10'); bad[field] = value
            self.calculate(self.document([self.line(adjustments=[bad])]), expected=400)
        duplicate = adjustment('1')
        self.calculate(self.document([self.line(adjustments=[duplicate, deepcopy(duplicate)])]), expected=400)
        self.calculate(self.document([self.line(adjustments=[adjustment('1'), adjustment('2')])]), expected=400)
        self.calculate(self.document([self.line(adjustments=[duplicate])], document_adjustments=[deepcopy(duplicate)]), expected=400)
        self.calculate(self.document([self.line(adjustments=[adjustment('1', i + 1) for i in range(21)])]), expected=400)
        self.calculate(self.document(document_adjustments=[adjustment('1', i + 1) for i in range(21)]), expected=400)
        self.calculate(self.document([self.line() for _ in range(101)]), expected=400)
        for ids in ([], [str(uuid.uuid4())], [first['line_id'], first['line_id']]):
            self.calculate(self.document([first], document_adjustments=[adjustment('1', applicable_line_ids=ids)]), expected=400)
        self.calculate(self.document([self.line(adjustments=[adjustment('1', applicable_line_ids=[first['line_id']])])]), expected=400)
        self.calculate(self.document([first, self.line('122', price_mode='TAX_INCLUSIVE')],
                                     document_adjustments=[adjustment('1')]), expected=422)

    def test_09_currency_mismatch_disabled_zero_wrong_and_null_minor_units(self):
        self.calculate(self.document([self.line(currency='USD')]), expected=400)
        self.calculate(self.document(currency='USD'), expected=400)
        original = json.loads(self.sql("SELECT to_jsonb(c) FROM foundation.currency c WHERE code='EUR';"))
        self.assertEqual(original['minor_units'], 2)
        self.assertTrue(original['is_enabled'])
        try:
            # Fault finiti sul catalogo isolato; nessuna configurazione fiscale via SQL.
            for assignment in ('minor_units=0', 'minor_units=3', 'minor_units=NULL', 'is_enabled=false'):
                self.sql("UPDATE foundation.currency SET minor_units=2,is_enabled=true WHERE code='EUR';")
                self.sql("UPDATE foundation.currency SET " + assignment + " WHERE code='EUR';")
                before = self.fingerprint()
                self.policy(expected=422)
                self.calculate(expected=422)
                self.assertEqual(self.fingerprint(), before)
        finally:
            self.sql("UPDATE foundation.currency SET minor_units=2,is_enabled=true WHERE code='EUR';")
        self.assertEqual(self.policy()['currency']['id'], original['id'])

    def test_10_bad_fiscal_context_indexed_422_trace_and_foreign_source(self):
        for field, value, outcome in [('ordinary_vat_territory_confirmed', None, 'INCOMPLETE_CONTEXT'),
                                      ('special_tax_treatment', 'REVERSE_CHARGE', 'UNSUPPORTED_OPERATION')]:
            body = self.document([self.line(), self.line()])
            body['lines'][1]['fiscal_context']['transaction_facts'][field] = value
            for simulation in (True, False):
                failure = self.calculate(body, simulation=simulation, expected=422)
                self.assertEqual((failure['code'], failure['field'], failure['outcome']),
                                 ('tax_calculation_determination_failed', 'lines[1].fiscal_context', outcome))
                self.assertIs(failure['isSimulation'], simulation)
                self.assertTrue(failure['trace'])
                self.assertNotIn('result', failure)
        body = self.document()
        body['lines'][0]['fiscal_context']['tax_date'] = '2026-02-30'
        self.assertEqual(self.calculate(body, expected=400)['field'], 'lines[0].fiscal_context.tax_date')
        body = self.document()
        body['lines'][0]['fiscal_context']['company_id'] = self.company_create()['id']
        self.calculate(body, expected=400)
        body = self.document()
        body['lines'][0]['fiscal_context']['operation_type'] = 'PURCHASE'
        self.calculate(body, expected=400)
        other = TaxCalculationHttp(unittest.defaultTestLoader.getTestCaseNames(TaxCalculationHttp)[0])
        other.setUp()
        body = self.document()
        body['lines'][0]['fiscal_context']['item_id'] = other.items['GOOD']['id']
        before = self.fingerprint()
        self.calculate(body, expected=(403, 404))
        self.assertEqual(self.fingerprint(), before)

    def test_11_selected_drafts_only_simulation_actual_rejects_even_empty(self):
        rule = self.new_rule([{'field': 'item.nature', 'operator': 'EQUALS', 'value': 'GOOD'}],
                             priority=200, tax_code_id=self.codes['SERVICE']['id'])
        body = self.document()
        body['lines'][0]['fiscal_context']['draft_version_ids'] = [rule['versions'][0]['id']]
        result = self.calculate(body)
        self.assertEqual(result['lines'][0]['taxRuleVersionId'], rule['versions'][0]['id'])
        self.assert_totals(result, '100.00', '10.00', '110.00')
        for drafts in ([], [rule['versions'][0]['id']]):
            body['lines'][0]['fiscal_context']['draft_version_ids'] = drafts
            self.calculate(body, simulation=False, expected=400)
        self.assert_totals(self.calculate(simulation=False), '100.00', '22.00', '122.00')

    def test_12_independent_source_and_acquisition_permissions_fresh_revocation(self):
        actor, role, _ = self.actor(SIMULATION_GRANTS)
        self.assign_companies(role, [self.company])
        self.calculate(client=actor)
        self.calculate(client=actor, simulation=False, expected=403)
        for missing in SOURCE_READS + [CALCULATION_SIMULATE, ACQUIRE_SIMULATE]:
            with self.subTest(missing=missing):
                limited, limited_role, _ = self.actor([x for x in SIMULATION_GRANTS if x != missing])
                self.assign_companies(limited_role, [self.company])
                self.calculate(client=limited, expected=403)
        actual, actual_role, _ = self.actor(ALL_GRANTS)
        self.assign_companies(actual_role, [self.company])
        self.calculate(client=actual, simulation=False)
        for missing in (CALCULATION_ACTUAL, ACQUIRE_ACTUAL):
            limited, limited_role, _ = self.actor([x for x in ALL_GRANTS if x != missing])
            self.assign_companies(limited_role, [self.company])
            self.calculate(client=limited, simulation=False, expected=403)
        status, _ = self.root.request(self.scope('/api/links/role-permissions/' + role['id']), 'PUT', {'ids': []})
        self.assertEqual(status, 204)
        status, readback = self.root.request(self.scope('/api/links/role-permissions/' + role['id']))
        self.assertEqual(status, 200, readback)
        self.assertEqual(readback['ids'], [])
        self.calculate(client=actor, expected=403)
        self.simulate(client=actor, expected=403)
        self.policy(client=actor, expected=403)

    def test_13_crossed_company_scope_disabled_roles_and_tenant(self):
        actor, action_role, _ = self.actor(ALL_GRANTS)
        other_company = self.company_create()
        self.assign_companies(action_role, [other_company])
        status, scope_role = self.root.request(self.scope('/api/data/roles'), 'POST', {'name': 'Ambito senza azioni F5'})
        self.assertEqual(status, 201, scope_role)
        self.assign_companies(scope_role, [self.company])
        user = actor.request('/api/session')[1]['id']
        self.assertEqual(self.root.request(self.scope('/api/links/user-roles/' + user), 'PUT',
                                           {'ids': [action_role['id'], scope_role['id']]})[0], 204)
        self.calculate(client=actor, expected=403)
        self.calculate(client=actor, simulation=False, expected=403)
        self.simulate(client=actor, expected=403)
        self.assign_companies(action_role, [self.company])
        self.calculate(client=actor)
        self.assertEqual(self.root.request(self.scope('/api/data/roles/' + action_role['id']), 'PUT', {'is_enabled': False})[0], 200)
        self.calculate(client=actor, expected=403)
        self.simulate(client=actor, expected=403)
        status, foreign = self.root.request('/api/data/tenants', 'POST',
                                           {'code': 'f5foreign-' + uuid.uuid4().hex[:10], 'name': 'Tenant sintetico esterno'})
        self.assertEqual(status, 201, foreign)
        self.req('calculations/simulate', 'POST', self.document(), (403, 404), tenant=foreign['id'])

    def test_14_readonly_65_tables_and_f4_extraction_regression(self):
        body = self.document([self.line(), self.line('50', kind='SERVICE')])
        before = self.fingerprint()
        for simulation in (True, False):
            calculated = self.calculate(body, simulation=simulation)
            sources = {x['lineId']: x for x in calculated['calculationTrace']['sources']}
            for line in body['lines']:
                result = self.simulate(line['fiscal_context']) if simulation else self.determine(line['fiscal_context'])
                self.assertEqual(result['outcome'], 'SUCCESS')
                self.assertIs(result['isSimulation'], simulation)
                for key in ('taxRuleVersionId', 'taxCodeId', 'taxCodeVersionId', 'companyTaxRegistrationId'):
                    self.assertEqual(sources[line['line_id']][key], result['result'][key])
        self.assertEqual(self.fingerprint(), before, 'F4 estratta e F5 non scrivono nessuna delle 65 tabelle')
        self.calculate({**body, 'policy': {}}, expected=400)
        failure = deepcopy(body)
        failure['lines'][0]['fiscal_context']['transaction_facts']['special_tax_treatment'] = 'SPLIT_PAYMENT'
        self.calculate(failure, expected=422)
        self.assertEqual(self.fingerprint(), before)

    def test_15_100_lines_body_above64k_below1m_actual_not_partial_and_global_limit(self):
        lines = [self.line('1.00', line_id=str(uuid.UUID(int=10000 + i))) for i in range(100)]
        for line in lines:
            line['fiscal_context']['transaction_facts']['source_reference'] = 'Fonte sintetica ' + 'x' * 220
        body = self.document(lines)
        encoded = json.dumps(body)
        self.assertGreater(len(encoded.encode()), 65536)
        self.assertLess(len(encoded.encode()), 1048576)
        before = self.fingerprint()
        result = self.calculate(body, simulation=False)
        self.assertEqual(len(result['lines']), 100)
        self.assertEqual({x['lineId'] for x in result['lines']}, {x['line_id'] for x in lines})
        self.assert_totals(result, '100.00', '22.00', '122.00')
        self.assertEqual(self.fingerprint(), before)
        # Il limite del trasporto precede il parsing: whitespace JSON valido, niente campo enorme inventato.
        oversized = ' ' * 1048576 + json.dumps(self.document())
        for endpoint in ('calculations', 'calculations/simulate'):
            self.assertEqual(self.raw_post(endpoint, oversized)[0], 413)
        ordinary = ' ' * 65536 + json.dumps(self.core())
        self.assertEqual(self.raw_post('determinations/simulate', ordinary)[0], 413)
        self.assertEqual(self.fingerprint(), before)


def load_tests(loader, tests, pattern):
    # Il TestCase F4 importato non entra nella discovery del modulo F5.
    return loader.loadTestsFromTestCase(TaxCalculationHttp)


if __name__ == '__main__':
    unittest.main()
