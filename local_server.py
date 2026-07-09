import os
import sys
from http.server import SimpleHTTPRequestHandler, HTTPServer

# Add current directory to path so we can import api/explain.py
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from api.explain import handler as ExplainHandler

class DevServerHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        # Serve from public directory
        public_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'public')
        super().__init__(*args, directory=public_dir, **kwargs)
        
    def do_OPTIONS(self):
        if self.path.startswith("/api/explain"):
            ExplainHandler.do_OPTIONS(self)
        else:
            super().do_OPTIONS()

    def do_POST(self):
        if self.path.startswith("/api/explain"):
            # Route POST requests to the API handler
            ExplainHandler.do_POST(self)
        else:
            self.send_error(404, "File not found")

# Start server on port 3000
def run(port=3000):
    server_address = ('', port)
    httpd = HTTPServer(server_address, DevServerHandler)
    print(f"🚀 SQL Optimizer local server started at http://localhost:{port}")
    print("Press Ctrl+C to stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server...")
        httpd.server_close()

if __name__ == '__main__':
    run()
