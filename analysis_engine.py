"""Transparent payment-request comparisons with optional local Ollama wording."""
import json
import re
from difflib import SequenceMatcher
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
OLLAMA = 'http://127.0.0.1:11434'


def first(pattern, text, flags=re.I):
    match = re.search(pattern, text, flags)
    return match.group(1).strip().rstrip('.,') if match else ''


def money(text):
    return first(r'(?:total(?:\s+due)?|invoice[^\n]{0,30}?totals?|for)\s*(?::|is)?\s*(?:USD\s*)?(\$?[\d,]+(?:\.\d{2})?)', text)


PRESSURE = re.compile(
    r"\b(urgent(?:ly)?|immediately|asap|right away|as soon as possible|bypass"
    r"|skip (?:the |our )?(?:usual|normal|standard|approval|verification|review|process|call)"
    r"|avoid (?:a |any )?(?:delay|late fee|penalt\w+)|already approved"
    r"|(?:pay|payment|wire|transfer|process|remit|send)\b[^.\n]{0,40}\btoday"
    r"|today\b[^.\n]{0,40}\b(?:pay|payment|wire|transfer|process|remit)"
    r"|before (?:the )?end of (?:the )?(?:day|business)"
    r"|do not (?:call|verify|contact)|don'?t (?:call|verify|contact)|keep this (?:confidential|between us))\b",
    re.I)
AUTH_FAIL = re.compile(r'\b(?:spf|dkim|dmarc)\s*=\s*(?:fail|softfail|permerror|temperror)\b', re.I)


def address(header, text):
    """Return the email address in a header line, with or without a display name."""
    line = first(rf'^{header}:[ \t]*(.+)$', text, re.I | re.M)
    if not line:
        return ''
    angle = re.search(r'<([^<>\s]+@[^<>\s]+)>', line)
    plain = re.search(r'([^\s<>",]+@[^\s<>",]+)', line)
    found = angle or plain
    return found.group(1).strip().rstrip('.,') if found else ''


def auth_failed(text):
    for line in re.findall(r'^(?:Authentication-Results|Received-SPF|ARC-Authentication-Results):.*$', text, re.I | re.M):
        if AUTH_FAIL.search(line) or re.match(r'Received-SPF:\s*(?:fail|softfail)\b', line, re.I):
            return True
    return False


def details(text):
    invoice = first(r'^Invoice(?:\s+(?:number|no\.?))?\s*[:#]\s*([A-Z0-9-]{3,})', text, re.I | re.M)
    if not invoice:
        invoice = first(r'\binvoice\s+([A-Z]{1,8}-\d+)\b', text)
    purchase_order = first(r'\b(PO-\d+)\b', text)
    if not purchase_order:
        purchase_order = first(r'purchase order\s*[:#-]?\s*([A-Z0-9-]{3,})', text)
    return {
        'email': address('From', text) or first(r'([\w.+-]+@[\w.-]+\.[A-Za-z]{2,})', text),
        'reply_to': address('Reply-To', text),
        'account': first(r'(?:account(?:\s+(?:number|on file))?|acct)\s*(?::|#|is|,)?\s*([A-Z0-9-]{4,})', text),
        'amount': money(text),
        'invoice': invoice,
        'purchase_order': purchase_order,
    }


def norm(value):
    return re.sub(r'[^a-z0-9]', '', value.lower())


def display(value):
    return value or 'Not found'


def segments(a, b):
    """Split a into (text, differs) pieces relative to b, so changed characters can be highlighted."""
    if not a:
        return []
    if not b:
        return [{'text': a, 'differs': True}]
    out = []
    if len(a) == len(b):
        # Same length: compare position by position so swapped digits (1402 vs 1042) both show.
        for x, y in zip(a, b):
            if out and out[-1]['differs'] == (x != y):
                out[-1]['text'] += x
            else:
                out.append({'text': x, 'differs': x != y})
        return out
    if SequenceMatcher(None, a, b, autojunk=False).ratio() < 0.6:
        # Different lengths and mostly different: scattered marks would be noise, the Mismatch label says enough.
        return [{'text': a, 'differs': False}]
    for tag, i1, i2, _, _ in SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if i2 > i1:
            out.append({'text': a[i1:i2], 'differs': tag != 'equal'})
    return out


def source_line(value, text):
    """Return the first line of text that contains value, exactly as written."""
    if value:
        for line in text.splitlines():
            if value.lower() in line.lower():
                return line.strip()
    return ''


def local_model_explanation(facts):
    """Let a local model phrase known facts. It cannot add findings or approve payment."""
    try:
        with urlopen(f'{OLLAMA}/api/tags', timeout=0.7) as response:
            models = json.load(response).get('models', [])
        names = [m.get('name', '') for m in models]
        model = next((n for n in names if n.startswith('llama3.2:3b')), '') or next((n for n in names if n.startswith('llama3.2')), '')
        if not model:
            return '', 'rule_based', 'Local Llama 3.2 is not installed. Findings use transparent comparison rules.'
        prompt = (
            'Write exactly two short sentences for an employee reviewing a payment request. '
            'Use only the JSON facts below. Do not infer fraud, approve payment, or add facts. '
            'First summarize the evidence. Then state that normal verification and approval remain required.\n'
            + json.dumps(facts, ensure_ascii=True)
        )
        payload = json.dumps({'model': model, 'prompt': prompt, 'stream': False,
                              'options': {'temperature': 0}}).encode()
        request = Request(f'{OLLAMA}/api/generate', data=payload,
                          headers={'Content-Type': 'application/json'})
        with urlopen(request, timeout=25) as response:
            answer = json.load(response).get('response', '').strip()
        answer = re.sub(r'^Here (?:are|is)[^:]{0,100}:\s*', '', answer, flags=re.I)
        if answer:
            return answer[:900], 'local_model', f'Explanation written locally by {model}; findings were calculated by exact rules.'
    except (URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError):
        pass
    return '', 'rule_based', 'Local Llama 3.2 is unavailable. Findings use transparent comparison rules.'


def analyze(email_text, invoice_text, vendor_id):
    vendors = json.loads((ROOT / 'data/vendors.json').read_text())
    vendor = next((v for v in vendors if v['id'] == vendor_id), None)
    new_vendor = vendor_id == 'new'
    if not (vendor or new_vendor):
        raise ValueError('Choose a vendor record or New Vendor.')

    email = details(email_text)
    invoice = details(invoice_text)
    rows, findings = [], []

    def add(field, request_value, record_value, review, source, req_raw=None, ref_raw=None, found=()):
        req_raw = request_value if req_raw is None else req_raw
        ref_raw = record_value if ref_raw is None else ref_raw
        differs = review == 'Mismatch'
        evidence = {
            'request_segments': segments(req_raw, ref_raw) if differs else ([{'text': req_raw, 'differs': False}] if req_raw else []),
            'reference_segments': segments(ref_raw, req_raw) if differs else ([{'text': ref_raw, 'differs': False}] if ref_raw else []),
            'sources': [{'label': label, 'line': source_line(value, text) or 'This value does not appear in this document'}
                        for label, value, text in found],
        }
        rows.append({'field': field, 'request': display(request_value),
                     'reference': display(record_value), 'review': review, 'source': source,
                     'evidence': evidence})

    vendor_text = '\n'.join(f'{k}: {v}' for k, v in vendor.items()) if vendor else ''
    trusted_email = vendor['email'] if vendor else ''
    trusted_account = vendor['account'] if vendor else ''
    sender = email['email'] or invoice['email']
    reply_to = email['reply_to']
    account = invoice['account'] or email['account']

    if new_vendor:
        add('Sender email', sender, 'No trusted record', 'Not verified', 'Email/PDF', ref_raw='', found=[('Email', sender, email_text), ('PDF', sender, invoice_text)])
        add('Payment account', account, 'No trusted record', 'Not verified', 'PDF/email', ref_raw='', found=[('PDF', account, invoice_text), ('Email', account, email_text)])
        findings.append('No trusted vendor record exists.')
    else:
        email_review = 'Match' if sender and sender.lower() == trusted_email.lower() else 'Mismatch'
        account_review = 'Not found' if not account else 'Match' if norm(account) == norm(trusted_account) else 'Mismatch'
        add('Sender email', sender, trusted_email, email_review, 'Email/PDF vs vendor record', found=[('Email', sender, email_text), ('PDF', sender, invoice_text), ('Vendor record', trusted_email, vendor_text)])
        if reply_to:
            reply_review = 'Match' if reply_to.lower() == trusted_email.lower() else 'Mismatch'
            add('Reply-to email', reply_to, trusted_email, reply_review, 'Email header vs vendor record', found=[('Email', reply_to, email_text), ('Vendor record', trusted_email, vendor_text)])
            if reply_review == 'Mismatch': findings.append('The reply-to email does not match the trusted vendor email.')
        add('Payment account', account, trusted_account, account_review, 'PDF/email vs vendor record', found=[('PDF', account, invoice_text), ('Email', account, email_text), ('Vendor record', trusted_account, vendor_text)])
        if email_review == 'Mismatch': findings.append('The sender email does not match the trusted vendor email.')
        if account_review == 'Mismatch': findings.append('The payment account does not match the trusted vendor account.')
        if account_review == 'Not found': findings.append('No payment account could be found to compare with the trusted record.')

    for field, label in [('invoice', 'Invoice number'), ('purchase_order', 'Purchase order'), ('amount', 'Amount')]:
        e, p = email[field], invoice[field]
        if e and p:
            review = 'Match' if norm(e) == norm(p) else 'Mismatch'
            add(label, f'Email: {e}', f'PDF: {p}', review, 'Email vs PDF', req_raw=e, ref_raw=p, found=[('Email', e, email_text), ('PDF', p, invoice_text)])
            if review == 'Mismatch': findings.append(f'The {label.lower()} differs between the email and PDF.')
        else:
            value = p or e
            add(label, value, 'Not stored in vendor record', 'Verify' if value else 'Not found', 'PDF/email', ref_raw='', found=[('PDF', value, invoice_text), ('Email', value, email_text)])

    pressure = bool(PRESSURE.search(email_text))
    if pressure:
        findings.append('The email contains urgency or language asking the employee to bypass a control.')
    failed_auth = auth_failed(email_text)
    if failed_auth:
        findings.append('The email headers report a failed sender authentication check (SPF, DKIM, or DMARC).')
    missing_account = not new_vendor and any(r['field'] == 'Payment account' and r['review'] == 'Not found' for r in rows)

    mismatch_count = sum(row['review'] == 'Mismatch' for row in rows)
    sensitive_mismatch = any(
        row['review'] == 'Mismatch' and row['field'] in ('Sender email', 'Reply-to email', 'Payment account')
        for row in rows
    )
    if sensitive_mismatch:
        tone, title, risk_level = 'risk', 'Sensitive Detail Mismatch', 'High'
        summary = 'One or more details require independent verification before the request enters the normal approval process.'
    elif failed_auth:
        tone, title, risk_level = 'risk', 'Sender Authentication Failed', 'High'
        summary = 'The email headers report that the sender could not be authenticated, so the sender must be verified independently.'
    elif pressure:
        tone, title, risk_level = 'risk', 'Pressure to Bypass Controls', 'High'
        summary = 'The message pushes for speed or an exception to normal controls, which should be confirmed with the internal owner.'
    elif new_vendor:
        tone, title, risk_level = 'verify', 'Verification Required', 'Medium'
        summary = 'No trusted history is available, so the request must be verified before a vendor record or payment is approved.'
    elif missing_account:
        tone, title, risk_level = 'verify', 'Verification Required', 'Medium'
        summary = 'No payment account was found to compare with the trusted record, so the account must be confirmed before approval.'
    elif mismatch_count:
        tone, title, risk_level = 'verify', 'Document Mismatch', 'Medium'
        summary = 'The request documents do not fully agree and should be resolved before normal approval.'
    else:
        tone, title, risk_level = 'match', 'No Mismatches Found', 'Low'
        summary = 'The details found match the trusted vendor record. This does not confirm the purchase or authorize payment.'

    checks = []
    if new_vendor:
        second = {'title': 'Contact the vendor independently', 'why': 'Invoice contact details are not yet trusted.', 'how': 'Find contact information through an independent source and confirm the invoice and account.', 'sample': 'Contacted the vendor through an independently sourced number and confirmed the invoice details.'}
        if pressure or failed_auth:
            second = {'title': 'Confirm the sender and the urgency', 'why': 'The message shows a warning sign and the vendor has no trusted history.', 'how': 'Find contact information through an independent source, then confirm the invoice, the account and any deadline with the internal owner.', 'sample': 'Contacted the vendor through an independently sourced number. The internal owner confirmed the deadline and the invoice.'}
        checks.extend([
            {'title': 'Confirm the internal purchase', 'why': 'A new vendor has no trusted history.', 'how': 'Confirm the purchase order and receipt with the internal owner.', 'sample': 'The internal owner confirmed the purchase order and receipt.'},
            second,
            {'title': 'Obtain second approval', 'why': 'A trusted record should not be created from one unverified request.', 'how': 'Record a second reviewer’s approval through the normal process.', 'sample': 'Sent the new-vendor review to a second reviewer. No payment was issued.'},
        ])
    else:
        targeted_checks = []
        if any(r['field'] == 'Payment account' and r['review'] == 'Mismatch' for r in rows):
            targeted_checks.append({'title': 'Verify the account independently', 'why': 'A changed account could redirect payment.', 'how': f"Call the trusted number {vendor['phone']}. Do not use contact details from the request.", 'sample': 'Called the trusted number on file. The vendor said they did not send new bank details, so the requested account was rejected and payment placed on hold.'})
        if missing_account:
            targeted_checks.append({'title': 'Confirm the payment account', 'why': 'No account could be found to compare.', 'how': f"Call the trusted number {vendor['phone']} and confirm the account on file. Do not use contact details from the request.", 'sample': 'Called the trusted number on file and confirmed the account before payment.'})
        if failed_auth or any(r['field'] in ('Sender email', 'Reply-to email') and r['review'] == 'Mismatch' for r in rows):
            targeted_checks.append({'title': 'Confirm the contact address', 'why': 'An email address differs from the trusted vendor record.' if not failed_auth else 'The message failed sender authentication, so it may not come from the vendor.', 'how': f"Contact {vendor['email']} or call {vendor['phone']} independently.", 'sample': 'Contacted the vendor at the address on file. The vendor said the different address is not theirs, so the message was reported and payment placed on hold.'})
        if pressure:
            targeted_checks.append({'title': 'Confirm the urgency', 'why': 'Pressure can cause normal controls to be skipped.', 'how': 'Confirm the deadline and purchase with the internal owner.', 'sample': 'The purchase owner said they did not request same-day payment or an exception to normal controls.'})
        if any(r['review'] == 'Mismatch' and r['field'] not in ('Sender email', 'Reply-to email', 'Payment account') for r in rows):
            targeted_checks.append({'title': 'Resolve document differences', 'why': 'The email and invoice do not agree.', 'how': 'Ask the purchase owner and vendor to confirm the correct invoice details.', 'sample': 'The purchase owner and vendor confirmed the correct invoice details, and the records were corrected.'})
        checks.extend(targeted_checks[:2])
        checks.append({'title': 'Confirm purchase and follow approval', 'why': 'A comparison cannot authorize a purchase or payment.', 'how': 'Verify the purchase order and receipt, record the review, and use the normal approval process.', 'sample': 'The purchase order and receipt were checked and the review was recorded for the normal approval process. This tool issued no payment.'})

    high_samples = {
        'Verify the account independently': 'Called the trusted number on file. The vendor did not confirm the requested account. Payment placed on hold.',
        'Confirm the contact address': 'Contacted the vendor at the address on file. The vendor did not recognize the different address. Payment placed on hold.',
        'Confirm the urgency': 'The purchase owner could not confirm the deadline and did not request same-day payment or an exception to normal controls.',
        'Resolve document differences': 'The purchase owner and vendor could not yet confirm the correct invoice details.',
        'Confirm the internal purchase': 'The internal owner could not confirm the purchase order or receipt.',
        'Contact the vendor independently': 'The vendor could not be confirmed through an independently sourced number.',
        'Confirm the sender and the urgency': 'The sender and the deadline could not be confirmed through an independently sourced number.',
        'Obtain second approval': 'The second reviewer did not approve. Payment placed on hold.',
        'Confirm purchase and follow approval': 'The purchase order and receipt could not be confirmed while the request is unresolved. This tool issued no payment.',
    }
    for check in checks:
        if risk_level == 'High':
            check['sample'] = high_samples.get(check['title'], check['sample'])
            check['sample_status'] = 'unconfirmed'
        else:
            check['sample_status'] = 'done'
            if check['title'] == 'Confirm purchase and follow approval':
                check['sample'] = 'The purchase order and receipt were confirmed and the review was recorded for the normal approval process. This tool issued no payment.'

    facts = {'title': title, 'fraud_risk_level': risk_level,
             'findings': findings or ['No exact mismatch was found.'],
             'normal_approval_required': True}
    explanation, mode, mode_note = local_model_explanation(facts)
    return {'tone': tone, 'title': title, 'fraud_risk_level': risk_level, 'description': explanation or summary,
            'rows': rows, 'checks': checks, 'findings': findings,
            'explanation_mode': mode, 'mode_note': mode_note}
