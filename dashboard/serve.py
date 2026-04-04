"""
dashboard/serve.py
------------------
Lightweight HTTP server that serves the analytics dashboard.

    python dashboard/serve.py          # opens on http://localhost:8765
    python dashboard/serve.py --port 9000

Endpoints:
    GET /              → dashboard HTML
    GET /api/reports   → all JSON report data combined
    GET /api/channels  → channel list from channels.json
"""

import http.server
import json
import pathlib
import argparse
import webbrowser
import threading
import os

ROOT       = pathlib.Path(__file__).parent.parent   # jde-ai/
REPORTS    = ROOT / "reports"
CHANNELS   = ROOT / "channels.json"
HTML_FILE  = pathlib.Path(__file__).parent / "index.html"


def load_reports() -> list[dict]:
    """Return the latest JSON report per channel (sorted by channel name)."""
    if not REPORTS.exists():
        return []

    # Group report files by channel slug (name before first date suffix)
    latest: dict[str, pathlib.Path] = {}
    for f in sorted(REPORTS.glob("*.json")):
        # skip video / analytics / summary CSVs stored as JSON (shouldn't exist,
        # but guard anyway)
        if "_videos_" in f.name or "_analytics_" in f.name or f.name.startswith("summary"):
            continue
        # key = everything before the date, e.g. "aspirants360"
        parts = f.stem.rsplit("_", 1)
        slug = parts[0] if len(parts) == 2 else f.stem
        # keep the lexicographically last (most recent date suffix)
        if slug not in latest or f.name > latest[slug].name:
            latest[slug] = f

    reports = []
    for slug, path in sorted(latest.items()):
        try:
            reports.append(json.loads(path.read_text(encoding="utf-8")))
        except Exception as e:
            print(f"  [WARN] Could not parse {path}: {e}")

    return reports


def load_channels() -> list[dict]:
    if CHANNELS.exists():
        data = json.loads(CHANNELS.read_text(encoding="utf-8"))
        return data.get("channels", [])
    return []


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        # cleaner console output
        print(f"  {self.address_string()}  {fmt % args}")

    def send_json(self, data: dict | list, status: int = 200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def send_html(self, path: pathlib.Path):
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        p = self.path.split("?")[0]

        if p in ("/", "/index.html"):
            if HTML_FILE.exists():
                self.send_html(HTML_FILE)
            else:
                self.send_error(404, "index.html not found")

        elif p == "/api/reports":
            self.send_json(load_reports())

        elif p == "/api/channels":
            self.send_json(load_channels())

        else:
            self.send_error(404)


def main():
    parser = argparse.ArgumentParser(description="Analytics dashboard server")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    url = f"http://localhost:{args.port}"
    print(f"\n  YouTube Analytics Dashboard")
    print(f"  ----------------------------")
    print(f"  URL  : {url}")
    print(f"  Data : {REPORTS}")
    print(f"  Press Ctrl+C to stop\n")

    # ensure stdout handles unicode on Windows
    import sys
    if sys.stdout.encoding and sys.stdout.encoding.lower() not in ('utf-8', 'utf8'):
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

    if not args.no_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()

    server = http.server.HTTPServer(("", args.port), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Server stopped.")


if __name__ == "__main__":
    main()
