# Payment Request Checker

A Python and JavaScript tool that reviews payment requests for fraud risk before they get approved.

## What it does

It checks a payment request against three sources: the incoming email, the attached PDF invoice, and the company's trusted vendor record. It compares the sender address, the reply to address, and the bank account details across all three. If something does not match, it flags it and points to exactly where the mismatch came from.

Each request gets a risk level, Low, Medium, or High, based on what it finds, plus a short checklist of steps to verify before approving payment. It never approves anything on its own. The decision stays with a person.

## Why I built it

This was a project for my Gen AI for Business class at Georgia State. Business email compromise, where someone impersonates a vendor to redirect a payment, is a real and common fraud pattern. I wanted to build something that catches the kind of small, easy to miss detail that makes these scams work, like one changed digit in a bank account number, instead of something obvious like a phishing link.

## How it works

- `analysis_engine.py`: pulls the details out of each document and compares them
- `pdf_reader.py`: reads the PDF invoice
- `server.py`: runs a local server so the app works in a browser
- `static/`: the browser interface
- `data/`: fictional vendor records and sample scenarios

All six sample scenarios are fictional and follow patterns described in FBI IC3 warnings about business email compromise.

## Running it

Double click `Start.command`. It opens in your browser at http://127.0.0.1:8765. Python 3.10 or later is recommended. No paid API key is required.

Run the automated tests with:

```
python3 -m unittest test_analysis_engine.py test_pdf_reader.py
```

## What it is not

This is a classroom prototype, not a production payment system. It does not check domain age or anything outside the pasted email headers and the PDF text. It supports PDFs up to 10 MB and 30 pages, and does not read scanned or encrypted PDFs.
