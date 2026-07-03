"""Pine → Python bridge receiver (stdlib only, zero dependencies).

Accepts the Section 16 JSON export from TradingView alert webhooks on
POST /pine and stores every payload in the learning database — the audit
trail and parity dataset for the single source of truth.

Run:  python -m ia_sr webhook --port 8787 --db ia_sr.db
"""
from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer

from .learning import LearningEngine


def serve(port: int = 8787, db_path: str = "ia_sr.db") -> None:
    engine = LearningEngine(db_path)

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802 — stdlib API
            if self.path.rstrip("/") != "/pine":
                self.send_response(404)
                self.end_headers()
                return
            try:
                length = int(self.headers.get("Content-Length", 0))
                payload = json.loads(self.rfile.read(length) or b"{}")
                engine.record_pine_payload(payload)
                self.send_response(200)
            except (json.JSONDecodeError, ValueError):
                self.send_response(400)
            self.end_headers()

        def log_message(self, fmt, *args):  # quiet
            pass

    print(f"IA-SR webhook listening on :{port} (POST /pine) → {db_path}")
    HTTPServer(("0.0.0.0", port), Handler).serve_forever()
