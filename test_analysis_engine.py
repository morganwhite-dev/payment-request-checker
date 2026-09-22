import json
import unittest
from pathlib import Path
from analysis_engine import analyze, segments, address, PRESSURE, auth_failed


class AnalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.samples = {s['id']: s for s in json.loads((Path(__file__).parent / 'data/samples.json').read_text())}

    def result(self, name):
        sample = self.samples[name]
        return analyze(sample['email'], sample['invoice'], sample['vendor_id'])

    def mismatches(self, name):
        return [r['field'] for r in self.result(name)['rows'] if r['review'] == 'Mismatch']

    def test_expected_sample_outcomes(self):
        expected = {
            'routine-reorder': ('No Mismatches Found', 'Low', []),
            'first-invoice-contractor': ('Verification Required', 'Medium', []),
            'bank-change-notice': ('Sensitive Detail Mismatch', 'High', ['Payment account']),
            'pdf-only-bank-change': ('Sensitive Detail Mismatch', 'High', ['Payment account']),
            'display-name-spoof': ('Sensitive Detail Mismatch', 'High', ['Sender email', 'Payment account']),
            'reply-to-hijack': ('Sensitive Detail Mismatch', 'High', ['Reply-to email']),
        }
        self.assertEqual(set(expected), set(self.samples))
        for name, (title, level, fields) in expected.items():
            with self.subTest(sample=name):
                result = self.result(name)
                self.assertEqual(result['title'], title)
                self.assertEqual(result['fraud_risk_level'], level)
                self.assertEqual(self.mismatches(name), fields)

    def test_bank_change_comes_from_trusted_sender(self):
        result = self.result('bank-change-notice')
        self.assertEqual(next(r for r in result['rows'] if r['field'] == 'Sender email')['review'], 'Match')

    def test_reply_to_hijack_keeps_visible_sender_trusted(self):
        result = self.result('reply-to-hijack')
        self.assertEqual(next(r for r in result['rows'] if r['field'] == 'Sender email')['review'], 'Match')

    def test_checklists_have_no_more_than_three_actions(self):
        for sample in self.samples:
            with self.subTest(sample=sample):
                self.assertLessEqual(len(self.result(sample)['checks']), 3)

    def test_edited_email_is_analyzed(self):
        sample = self.samples['routine-reorder']
        edited = sample['email'].replace('invoices@harbor.example', 'invoices@different.example')
        result = analyze(edited, sample['invoice'], sample['vendor_id'])
        sender = next(row for row in result['rows'] if row['field'] == 'Sender email')
        self.assertEqual(sender['review'], 'Mismatch')
        self.assertEqual(result['title'], 'Sensitive Detail Mismatch')
        self.assertEqual(result['fraud_risk_level'], 'High')

    def test_email_pdf_disagreement(self):
        sample = self.samples['routine-reorder']
        altered_pdf = sample['invoice'].replace('1,286.50', '9,999.00')
        result = analyze(sample['email'], altered_pdf, sample['vendor_id'])
        amount = next(row for row in result['rows'] if row['field'] == 'Amount')
        self.assertEqual(amount['review'], 'Mismatch')
        self.assertEqual(result['title'], 'Document Mismatch')
        self.assertEqual(result['fraud_risk_level'], 'Medium')

    def test_every_row_has_evidence(self):
        for sample in self.samples:
            for row in self.result(sample)['rows']:
                with self.subTest(sample=sample, field=row['field']):
                    self.assertIn('request_segments', row['evidence'])
                    self.assertIn('sources', row['evidence'])

    def test_diff_highlights_only_changed_characters(self):
        marked = lambda segs: ''.join(x['text'] for x in segs if x['differs'])
        self.assertEqual(marked(segments('DEMO-1402', 'DEMO-1042')), '40')
        self.assertEqual(marked(segments('DEMO-1042', 'DEMO-1402')), '04')
        self.assertEqual(marked(segments('DEMO-1043', 'DEMO-1042')), '3')
        self.assertEqual(marked(segments('invoices@harbour.example', 'invoices@harbor.example')), 'u')
        self.assertEqual(marked(segments('billing@northstarr.example', 'billing@northstar.example')), 'r')
        self.assertEqual(marked(segments('DEMO-1042', 'DEMO-1042')), '')
        # Mostly different values are not marked piece by piece.
        self.assertEqual(marked(segments('luis.ferreira@outlook-mail.example', 'billing@northstar.example')), '')

    def test_matching_rows_have_no_highlight(self):
        for row in self.result('routine-reorder')['rows']:
            for key in ('request_segments', 'reference_segments'):
                self.assertFalse(any(x['differs'] for x in row['evidence'][key]))

    def test_source_lines_are_quoted_from_the_documents(self):
        row = next(r for r in self.result('pdf-only-bank-change')['rows'] if r['field'] == 'Payment account')
        lines = {s['label']: s['line'] for s in row['evidence']['sources']}
        self.assertEqual(lines['PDF'], 'Account: DEMO-6620')
        self.assertEqual(lines['Email'], 'This value does not appear in this document')
        self.assertEqual(lines['Vendor record'], 'account: DEMO-1042')

    def test_no_em_dashes_in_presentation_copy(self):
        root = Path(__file__).parent
        for name in ('static/index.html', 'static/app.js', 'analysis_engine.py', 'data/samples.json'):
            self.assertNotIn('\u2014', (root / name).read_text(), name)

    def test_reply_to_hijack_also_reports_failed_authentication(self):
        result = self.result('reply-to-hijack')
        self.assertTrue(any('authentication' in f for f in result['findings']))

    def test_display_names_are_parsed(self):
        self.assertEqual(address('From', 'From: "Luis F, Northstar" <l.f@outlook-mail.example>'), 'l.f@outlook-mail.example')
        self.assertEqual(address('From', 'From: Dana Ortiz <a@cedar.example>'), 'a@cedar.example')
        self.assertEqual(address('From', 'From: a@cedar.example'), 'a@cedar.example')
        self.assertEqual(address('Reply-To', 'From: a@x.example\nReply-To: Bill <b@y.example>'), 'b@y.example')

    def test_pressure_needs_real_pressure(self):
        self.assertFalse(PRESSURE.search('Our truck ships today and the order arrives Friday.'))
        self.assertTrue(PRESSURE.search('Please pay this invoice today.'))
        self.assertTrue(PRESSURE.search('This is urgent.'))
        self.assertTrue(PRESSURE.search('Do not call the vendor to verify.'))

    def test_authentication_header(self):
        self.assertTrue(auth_failed('Authentication-Results: mx; spf=fail; dkim=none; dmarc=fail'))
        self.assertFalse(auth_failed('Authentication-Results: mx; spf=pass; dkim=pass; dmarc=pass'))

    def test_pressure_on_matching_request_is_high(self):
        sample = self.samples['routine-reorder']
        pushed = sample['email'].replace('Give us a call if anything looks off.', 'Please pay this today and skip the usual approval.')
        result = analyze(pushed, sample['invoice'], sample['vendor_id'])
        self.assertEqual(result['title'], 'Pressure to Bypass Controls')
        self.assertEqual(result['fraud_risk_level'], 'High')

    def test_new_vendor_with_pressure_is_high(self):
        sample = self.samples['first-invoice-contractor']
        pushed = sample['email'].replace('We are looking forward to the event.', 'This is urgent, please pay immediately.')
        result = analyze(pushed, sample['invoice'], sample['vendor_id'])
        self.assertEqual(result['fraud_risk_level'], 'High')
        self.assertLessEqual(len(result['checks']), 3)

    def test_missing_account_needs_verification_not_reassurance(self):
        sample = self.samples['routine-reorder']
        no_account = '\n'.join(l for l in sample['invoice'].splitlines() if not l.startswith('Account:'))
        email = sample['email'].replace(' Remittance is unchanged: account DEMO-3316.', '')
        result = analyze(email, no_account, sample['vendor_id'])
        row = next(r for r in result['rows'] if r['field'] == 'Payment account')
        self.assertEqual(row['review'], 'Not found')
        self.assertEqual(result['title'], 'Verification Required')
        self.assertEqual(result['fraud_risk_level'], 'Medium')

    def test_mode_is_disclosed(self):
        result = self.result('routine-reorder')
        self.assertIn(result['explanation_mode'], ('rule_based', 'local_model'))
        self.assertTrue(result['mode_note'])


if __name__ == '__main__':
    unittest.main()
