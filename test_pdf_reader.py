import io
import json
import unittest
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from pypdf import PdfWriter
from pdf_reader import extract

class PDFTests(unittest.TestCase):
    def test_samples(self):
        for name, account in [('routine-reorder','DEMO-3316'),('pdf-only-bank-change','DEMO-6620'),('first-invoice-contractor','DEMO-8812')]:
            data=(Path(__file__).parent / f'output/pdf/{name}-invoice.pdf').read_bytes()
            result=extract(data)
            self.assertEqual(result['page_count'],1)
            self.assertIn(account,result['pages'][0]['text'])
            request=Request('http://127.0.0.1:8765/api/extract-pdf',data=data,headers={'Content-Type':'application/pdf'})
            with urlopen(request) as response:
                self.assertEqual(json.load(response)['page_count'],1)

    def test_invalid(self):
        for data in [b'not a PDF',b'%PDF- damaged']:
            with self.assertRaises(ValueError): extract(data)

    def test_no_text_encrypted_and_page_limit(self):
        for count, password, expected in [(1,False,'No readable'),(1,True,'Password'),(31,False,'30-page')]:
            writer=PdfWriter()
            for _ in range(count): writer.add_blank_page(width=612,height=792)
            if password: writer.encrypt('test')
            buf=io.BytesIO(); writer.write(buf)
            with self.assertRaisesRegex(ValueError,expected): extract(buf.getvalue())

    def test_wrong_type_and_origin(self):
        for headers, status in [({'Content-Type':'text/plain'},415),({'Content-Type':'application/pdf','Origin':'https://example.com'},403)]:
            with self.assertRaises(HTTPError) as error:
                urlopen(Request('http://127.0.0.1:8765/api/extract-pdf',data=b'test',headers=headers))
            self.assertEqual(error.exception.code,status)

if __name__=='__main__': unittest.main()
