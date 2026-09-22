#!/usr/bin/env python3
"""Local payment-request review prototype."""
import argparse
import json
import mimetypes
import subprocess
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from analysis_engine import analyze

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / 'static'


class Handler(BaseHTTPRequestHandler):
    def send_content(self, content, mime, status=200):
        self.send_response(status)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(content)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "default-src 'self'; style-src 'self'; script-src 'self'; connect-src 'self'; img-src 'self'; frame-ancestors 'none'")
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(content)

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        # Serve an explicit file list. Vendor records are fictional demo data.
        route = urlsplit(self.path).path
        if route == '/api/health':
            body = {'app': 'Payment Request Checker', 'phase': 5, 'pdf_extraction': True,
                    'status': 'ready', 'analysis_available': True,
                    'model_connected': False, 'analysis_mode': 'rule_based_with_optional_ollama'}
            self.send_content(json.dumps(body).encode(), 'application/json; charset=utf-8')
            return
        routes = {
            '/': STATIC / 'index.html',
            '/styles.css': STATIC / 'styles.css',
            '/app.js': STATIC / 'app.js',
            '/api/vendors': ROOT / 'data/vendors.json',
            '/api/samples': ROOT / 'data/samples.json',
        }
        target = routes.get(route)
        for sample in [x['id'] for x in json.loads((ROOT / 'data/samples.json').read_text())]:
            if route == f'/samples/{sample}-invoice.pdf':
                target = ROOT / 'output/pdf' / f'{sample}-invoice.pdf'
        if target is None:
            self.send_content(b'Not found', 'text/plain', 404)
            return
        try:
            content = target.read_bytes()
        except OSError:
            self.send_content(b'Application file unavailable', 'text/plain', 500)
            return
        mime = mimetypes.guess_type(str(target))[0] or 'application/octet-stream'
        self.send_content(content, mime + '; charset=utf-8')

    def do_POST(self):
        def reply(body, status=200):
            self.send_content(json.dumps(body).encode(), 'application/json', status)
        route = urlsplit(self.path).path
        origin = self.headers.get('Origin')
        if origin and origin != f'http://127.0.0.1:{self.server.server_port}':
            reply({'error': 'Only the local workspace may read invoices.'}, 403)
            return
        if route == '/api/analyze':
            if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                reply({'error': 'The analysis request must be JSON.'}, 415); return
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 300000:
                    reply({'error': 'The request is empty or too large.'}, 413); return
                body = json.loads(self.rfile.read(length))
                email = body.get('email', '')
                invoice = body.get('invoice_text', '')
                if not isinstance(email, str) or not isinstance(invoice, str) or not email.strip():
                    reply({'error': 'Enter the payment email before analyzing.'}, 422); return
                if len(email) > 50000 or len(invoice) > 200000:
                    reply({'error': 'The request contains too much text.'}, 413); return
                reply(analyze(email, invoice, body.get('vendor_id', '')))
            except (json.JSONDecodeError, ValueError) as error:
                reply({'error': str(error)}, 422)
            return
        if route != '/api/extract-pdf':
            reply({'error': 'Not found.'}, 404); return
        if self.headers.get('Content-Type', '').split(';')[0] != 'application/pdf':
            reply({'error': 'Choose a PDF file.'}, 415)
            return
        try:
            length = int(self.headers.get('Content-Length', '0'))
        except ValueError:
            length = 0
        if not 0 < length <= 10 * 1024 * 1024:
            self.close_connection = True
            reply({'error': 'Choose a nonempty PDF up to 10 MB.'}, 413)
            return
        self.connection.settimeout(20)
        try:
            data = self.rfile.read(length)
            result = subprocess.run([sys.executable, str(ROOT / 'pdf_reader.py')], input=data,
                                    capture_output=True, timeout=20)
            if result.returncode:
                reply({'error': 'PDF reader unavailable. Check that pypdf is installed.'}, 503)
                return
            body = json.loads(result.stdout)
            reply(body, 422 if 'error' in body else 200)
        except (subprocess.TimeoutExpired, TimeoutError):
            reply({'error': 'Reading took too long. Choose a smaller or simpler PDF.'}, 408)
        except (OSError, ValueError):
            reply({'error': 'The PDF reader could not finish. Try another PDF.'}, 500)

    def log_message(self, format, *args):
        # Do not log request bodies or invoice contents.
        pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--open', action='store_true', help='Open the app in your browser')
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error('Choose a port between 1 and 65535.')
    try:
        server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    except OSError as error:
        parser.exit(1, f'Could not start the application: {error}\nTry another port with --port 8766.\n')
    url = f'http://127.0.0.1:{args.port}'
    print(f'Payment Request Checker\n{url}\nPhase 4 local analysis. Normal approval remains required.\nPress Control-C to stop.', flush=True)
    if args.open:
        timer = threading.Timer(0.3, webbrowser.open, args=(url,))
        timer.daemon = True
        timer.start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nApplication stopped.')
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
