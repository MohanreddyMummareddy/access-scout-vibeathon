"""Run the app locally using only the Python standard library."""

import argparse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from api.scout import handler


class LocalHandler(handler, SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=Path(__file__).parent / "public", **kwargs)

    def do_GET(self):
        if urlsplit(self.path).path.startswith("/api/scout/"):
            super().do_GET()
        else:
            SimpleHTTPRequestHandler.do_GET(self)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    print(f"Access Scout at http://127.0.0.1:{args.port}", flush=True)
    with ThreadingHTTPServer(("127.0.0.1", args.port), LocalHandler) as server:
        server.serve_forever()
