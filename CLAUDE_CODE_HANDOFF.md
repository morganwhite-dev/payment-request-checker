# Claude Code Handoff: Payment Request Checker

## Project location

Working application:

`/Users/morguewhite/Documents/Codex/2026-09-17/new-chat/outputs/payment-request-checker`

Group-project copy:

`/Users/morguewhite/Desktop/GSU MSIS/Gen AI for Business/Group Projects/Payment Request Checker/outputs/payment-request-checker`

Local URL:

`http://127.0.0.1:8765/`

## Current completed state

This is a local browser application for a Gen AI and Business class project. It compares an incoming payment email and invoice with a trusted vendor record. Exact rules calculate all findings. A local Ollama model may explain those findings, but it cannot add findings, determine fraud, approve a payment, or send a payment.

The interface uses **Fraud risk level: Low, Medium, or High**. This level summarizes detected warning signs. It is not a calculated probability or a fraud determination. Keep that disclaimer visible if the result design changes.

Risk mapping (full ordered rules are in README.md under How the risk level is decided; pressure and failed authentication also make a result High, and a new vendor with pressure is High):

- Low: the extracted evidence matches.
- Medium: the vendor is new or the request documents disagree with each other.
- High: the sender, Reply-To address, or payment account differs from the trusted record, or the message pressures the employee to bypass a control.

The verification checklist is limited to three actions. The separate Employee notes field was removed. The sample checklist contains fictional responses without repeating `DEMO ONLY` on every item.

## Final scenario set (rebuilt from FBI IC3 BEC patterns)

Core: Routine invoice (Low); First invoice from a new contractor (Medium); Vendor announces new bank details (High, account only).
Hard-to-spot: Bank details changed only inside the PDF; Vendor contact writing from a personal address (display-name spoof, two rows mismatch); Replies are quietly redirected (reply-to plus failed authentication header). All High.

## Important files

- `analysis_engine.py`: extraction, comparison rules, risk mapping, checklist generation, and optional Ollama wording.
- `data/samples.json`: the five fictional scenarios.
- `data/vendors.json`: fictional trusted vendor records.
- `static/index.html`: application structure and disclosure text.
- `static/app.js`: scenario loading, PDF loading, results, and checklist interactions.
- `static/styles.css`: burgundy, ivory, rose, and sage visual system.
- `server.py`: local server and explicit sample-PDF routes.
- `create_sample_pdfs.py`: rebuilds fictional invoice PDFs.
- `test_analysis_engine.py` and `test_pdf_reader.py`: automated checks.

## Run and test

Start with `Start.command`, or run:

```sh
/Users/morguewhite/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 server.py --port 8765
```

Run all tests while the server is running:

```sh
/Users/morguewhite/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m unittest test_analysis_engine.py test_pdf_reader.py
```

Expected scenario results:

- Routine invoice: No Mismatches Found, Low.
- First invoice from a new contractor: Verification Required, Medium.
- Vendor announces new bank details: Sensitive Detail Mismatch, High (Payment account).
- Bank details changed only inside the PDF: Sensitive Detail Mismatch, High (Payment account).
- Vendor contact writing from a personal address: Sensitive Detail Mismatch, High (Sender email and Payment account).
- Replies are quietly redirected: Sensitive Detail Mismatch, High (Reply-to email; also a failed authentication finding).

Each checklist must contain three or fewer actions. Findings must remain rule-based even when Ollama writes the explanation.

## Design and writing constraints

- Preserve the modern burgundy, ivory, rose, and sage design.
- Use polished academic student language without corporate jargon.
- Do not use em dashes in presentation copy.
- Do not add paid APIs or external services.
- Keep all organizations, addresses, accounts, and invoices fictional.
- Never describe the Low, Medium, or High label as a calculated probability.
- Normal human verification and approval must remain required.

## Phase 5 status: complete

Added highlighted character differences, expandable source-line evidence per row, per-action status (Not started, Done, Could not confirm), and a Review outcome label (recorded only, never approves payment). Health reports phase 5. 14 automated tests pass. Restart the server after Python edits.

## Likely next work

Phase 6: the new vendor approval workflow. Keep the checklist at three or fewer actions and all existing constraints.

(Older note, now done: Phase 5 should strengthen the evidence views and employee verification workflow.)

Phase 5 should strengthen the evidence views and employee verification workflow without increasing the checklist above three actions. After any change, explain how the presenter can test it, run the automated tests, test the browser workflow, and sync the finished application to the group-project copy.
