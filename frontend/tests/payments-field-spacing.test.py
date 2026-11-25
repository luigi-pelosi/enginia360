import re
import unittest
from pathlib import Path


class PaymentFieldSpacingTests(unittest.TestCase):
    def test_payment_select_fields_use_standard_field_spacing(self):
        source = (Path(__file__).parents[1] / 'components/payments-workspace.tsx').read_text()
        fields = re.findall(r'<div([^>]*)><Label htmlFor=.*?</Label>\{select\(', source)
        self.assertGreaterEqual(len(fields), 8)
        compact_fields = re.findall(r'<Label className="sr-only" htmlFor=\{`(?:base|rule|method)-\$\{i\}`\}>', source)
        self.assertEqual(len(compact_fields), 3)
        css = (Path(__file__).parents[1] / 'app/globals.css').read_text()
        self.assertIn(':is([data-payments-workspace], [role="dialog"]:has(#pm-code), [data-payment-term-dialog])', css)
        self.assertIn('div:not(.space-y-2) > label:has(+ [data-slot="select-trigger"])', css)


if __name__ == '__main__':
    unittest.main()
