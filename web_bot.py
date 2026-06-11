import os, threading, json
from http.server import HTTPServer, BaseHTTPRequestHandler

PORT = int(os.getenv("PORT", 8000))

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"status": "alive"}).encode())
    def log_message(self, *a):
        pass

def run_http():
    server = HTTPServer(("0.0.0.0", PORT), HealthHandler)
    server.serve_forever()

t = threading.Thread(target=run_http, daemon=True)
t.start()

import suggest_bot
