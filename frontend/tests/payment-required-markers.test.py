import pathlib
import unittest

SOURCE = pathlib.Path(__file__).parents[1] / 'components' / 'payments-workspace.tsx'

class PaymentRequiredMarkers(unittest.TestCase):
    def test_form_required_markers_follow_validation(self):
        source = SOURCE.read_text()
        self.assertIn("required={extra.required || id==='preview-amount' || id==='preview-date'}", source)
        for field in ('pm-category', 'pm-direction', 'pt-reference', 'preview-currency'):
            self.assertIn(f'<Label htmlFor="{field}" required>', source)
        for field in ('pm-fiscal', 'pt-method'):
            self.assertIn(f'<Label htmlFor="{field}">', source)

    def test_installment_headers_mark_required_and_conditional_fixed_day(self):
        source = SOURCE.read_text()
        self.assertIn("['percentage','offsetMonths','offsetDays','offsetBase','dateRule'].includes(key)", source)
        self.assertIn("key==='fixedDay' && term.installments.some(row=>row.dateRule==='FIXED_DAY')", source)
        self.assertIn('aria-hidden="true"> *</span>', source)

if __name__ == '__main__':
    unittest.main()
