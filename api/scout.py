"""HTTP entry point for the Vercel Python function."""

import json
import os
from http.server import BaseHTTPRequestHandler
from urllib.error import URLError
from urllib.parse import parse_qs, urlsplit

from agents import AGENTS, agent_card, dispatch, plan_route


class handler(BaseHTTPRequestHandler):
    def send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def route(self) -> list[str]:
        url = urlsplit(self.path)
        route = parse_qs(url.query).get("route", [url.path.removeprefix("/api/scout/")])[0]
        return route.strip("/").split("/")

    def do_GET(self) -> None:
        parts = self.route()
        if len(parts) == 4 and parts[0] == "agents" and parts[1] in AGENTS and parts[2:] == [".well-known", "agent-card.json"]:
            deployment = os.getenv("VERCEL_URL")
            origin = f"https://{deployment}" if deployment else f'http://{self.headers.get("Host", "localhost:8000")}'
            self.send_json(200, agent_card(parts[1], origin))
        else:
            self.send_json(404, {"error": "Endpoint not found."})

    def do_POST(self) -> None:
        parts = self.route()
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 48000:
                raise ValueError("Request body must be between 1 and 48000 bytes.")
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                raise ValueError("Expected a JSON object.")
            if parts == ["plan"]:
                self.send_json(200, plan_route(payload))
            elif parts == ["visit"]:
                self.send_json(200, plan_route(payload, event=True))
            elif len(parts) == 2 and parts[0] == "agents" and parts[1] in AGENTS:
                self.send_json(200, dispatch(parts[1], payload))
            else:
                self.send_json(404, {"error": "Endpoint not found."})
        except (ValueError, UnicodeError) as error:
            self.send_json(400, {"error": str(error)})
        except (URLError, TimeoutError):
            self.send_json(502, {"error": "An agent is temporarily unavailable. Try again."})
