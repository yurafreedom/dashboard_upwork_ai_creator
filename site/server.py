"""Serve the local project board and only its public-facing assets on loopback."""
import argparse
import errno
import json
import os
import re
import threading
import sys
import webbrowser
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from http.client import HTTPException
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, parse_qs

SITE = Path(__file__).resolve().parent
REPORTS = SITE.parent / "reports"
sys.path.insert(0, str(SITE.parent))
FILES = {
    "/original-brief.js": ("original-brief.js", "text/javascript; charset=utf-8"),
    "/practice": ("practice.html", "text/html; charset=utf-8"),
    "/practice.html": ("practice.html", "text/html; charset=utf-8"),
    "/practice.js": ("practice.js", "text/javascript; charset=utf-8"),
    "/practice.css": ("practice.css", "text/css; charset=utf-8"),
    "/": ("index.html", "text/html; charset=utf-8"),
    "/style.css": ("style.css", "text/css; charset=utf-8"),
    "/board.js": ("board.js", "text/javascript; charset=utf-8"),
    "/portrait.jpg": ("portrait.jpg", "image/jpeg"),
    "/fashion.jpg": ("fashion.jpg", "image/jpeg"),
    "/mark.svg": ("mark.svg", "image/svg+xml"),
}
BLOCK = re.compile(r"^```project-cards\s*\n(.*?)^```[ \t]*$", re.M | re.S)


from catalog import catalog


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        route = urlsplit(self.path).path
        if route in ("/api/projects", "/api/projects.json"):
            body = json.dumps(catalog(), ensure_ascii=False).encode()
            mime = "application/json; charset=utf-8"
        elif route in ("/api/practice", "/api/practice.json"):
            data = SITE.parent / "data" / "practice.json"
            body = data.read_bytes() if data.exists() else b'{"projects":[]}'
            mime = "application/json; charset=utf-8"
        elif route in ("/api/reports", "/api/reports.json"):
            rows = [{"name": p.name, "label": datetime.strptime(p.name, "live_%Y%m%dT%H%M%SZ.md").replace(tzinfo=timezone.utc).astimezone(ZoneInfo("Europe/Kyiv")).strftime("%d.%m.%Y · %H:%M Киев — отчёт и черновики")}
                    for p in sorted(REPORTS.glob("live_*.md"), reverse=True) if not p.is_symlink()]
            body = json.dumps({"reports": rows}, ensure_ascii=False).encode()
            mime = "application/json; charset=utf-8"
        elif route == "/report" or route.startswith("/reports/"):
            name = route.removeprefix("/reports/") if route.startswith("/reports/") else parse_qs(urlsplit(self.path).query).get("name", [""])[0]
            if not re.fullmatch(r"live_\d{8}T\d{6}Z\.md", name):
                self.send_error(404); return
            path = REPORTS / name
            if not path.is_file() or path.is_symlink():
                self.send_error(404); return
            body = path.read_bytes()
            mime = "text/plain; charset=utf-8"
        elif route in FILES:
            name, mime = FILES[route]
            try:
                body = (SITE / name).read_bytes()
            except OSError:
                self.send_error(503, "Catalog file unavailable")
                return
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--open", action="store_true")
    args = parser.parse_args()
    # A working directory follows a folder rename on macOS.
    os.chdir(SITE.parent)
    address = ("127.0.0.1", 47321)
    url = "http://127.0.0.1:47321/"
    try:
        server = ThreadingHTTPServer(address, Handler)
    except OSError as error:
        if error.errno != errno.EADDRINUSE or not args.open:
            raise
        from urllib.request import urlopen
        try:
            with urlopen(url, timeout=3) as response:
                if response.read() != Path("site/index.html").read_bytes():
                    raise SystemExit("На порту 47321 открыта другая страница.")
            with urlopen(url + "api/projects", timeout=3) as response:
                data = json.load(response)
                if not isinstance(data, dict) or not isinstance(data.get("projects"), list):
                    raise ValueError("Invalid catalog")
        except (OSError, HTTPException, ValueError) as problem:
            raise SystemExit("Сервер на порту 47321 не смог отдать страницу или карточки.") from problem
        print(f"Каталог уже открыт для просмотра: {url}", flush=True)
        webbrowser.open(url)
        return
    if args.open:
        threading.Timer(0.4, webbrowser.open, args=(url,)).start()
    print(url, flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

