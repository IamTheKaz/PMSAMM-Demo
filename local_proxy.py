#!/usr/bin/env python3
import http.server
import json
import socketserver
import sys
import urllib.request
from urllib.error import URLError, HTTPError

LAMBDA_URL = 'https://wtcqbp7rmnoy3pf7hty2bcyoea0dcese.lambda-url.us-west-2.on.aws/'
PORT = 8000

class ProxyHandler(http.server.SimpleHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_POST(self):
        if self.path != '/infer':
            return super().do_POST()

        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)
        headers = {'Content-Type': self.headers.get('Content-Type', 'application/json')}

        try:
            req = urllib.request.Request(LAMBDA_URL, data=body, headers=headers, method='POST')
            with urllib.request.urlopen(req, timeout=30) as resp:
                resp_body = resp.read()
                self.send_response(resp.getcode())
                self.send_header('Content-Type', resp.headers.get('Content-Type', 'application/json'))
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(resp_body)
        except HTTPError as e:
            resp_body = e.read()
            self.send_response(e.code)
            self.send_header('Content-Type', e.headers.get('Content-Type', 'application/json', 'text/plain'))
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(resp_body)
        except URLError as e:
            self.send_response(502)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({'error': 'Proxy request failed', 'details': str(e)}).encode('utf-8'))

    def log_message(self, format, *args):
        sys.stdout.write("%s - - [%s] %s\n" % (self.client_address[0], self.log_date_time_string(), format % args))

if __name__ == '__main__':
    with socketserver.TCPServer(('', PORT), ProxyHandler) as httpd:
        print(f'Serving on http://localhost:{PORT}')
        print('Open http://localhost:8000/simple_sam_inference.html and upload an image.')
        httpd.serve_forever()
