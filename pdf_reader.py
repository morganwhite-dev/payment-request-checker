"""Isolated, bounded PDF text extraction. No OCR or document actions."""
import io
import json
import sys
from pypdf import PdfReader

def extract(data):
    if not data.startswith(b'%PDF-'):
        raise ValueError('This file is not a valid PDF. Choose a text-based PDF.')
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise ValueError('Password-protected PDFs are not supported. Choose an unencrypted copy.')
        if len(reader.pages) > 30:
            raise ValueError('This PDF exceeds the 30-page limit. Choose a shorter invoice.')
        pages, total = [], 0
        for number, page in enumerate(reader.pages, 1):
            text = page.extract_text() or ''
            total += len(text)
            if total > 200000:
                raise ValueError('This PDF contains too much text. Choose a shorter invoice.')
            pages.append({'page': number, 'text': text.strip()})
        if not any(p['text'] for p in pages):
            raise ValueError('No readable text found. This may be a scanned PDF. OCR is not available; use a text-based invoice.')
        blank = [p['page'] for p in pages if not p['text']]
        return {'pages': pages, 'page_count': len(pages), 'warnings': [f'No text found on pages {blank}. They may contain scanned images or be blank.'] if blank else []}
    except ValueError:
        raise
    except Exception:
        raise ValueError('This PDF could not be read. It may be damaged or unsupported.') from None

if __name__ == '__main__':
    try:
        print(json.dumps(extract(sys.stdin.buffer.read(10 * 1024 * 1024 + 1))))
    except ValueError as error:
        print(json.dumps({'error': str(error)}))
