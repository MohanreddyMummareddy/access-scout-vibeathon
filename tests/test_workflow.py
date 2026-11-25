import json
import os
import threading
import unittest
from http.server import ThreadingHTTPServer
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import urlopen

from agents import post_json
from serve import LocalHandler


class WorkflowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), LocalHandler)
        cls.origin = f"http://127.0.0.1:{cls.server.server_port}"
        cls.worker = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.worker.start()
        cls.environment = patch.dict(os.environ, {"SCOUT_A2A_ORIGIN": cls.origin, "OPENAI_API_KEY": ""})
        cls.environment.start()

    @classmethod
    def tearDownClass(cls):
        cls.environment.stop()
        cls.server.shutdown()
        cls.server.server_close()
        cls.worker.join()

    def plan(self, arrival, step_free=True):
        return post_json(self.origin + "/api/scout/plan", {"arrival": arrival, "step_free": step_free})

    def test_before_and_after_closing_over_http(self):
        early = self.plan("17:30")
        self.assertEqual(early["recommendation"]["gate"], "B")
        self.assertEqual(len(early["trace"]), 4)
        for time in ("18:00", "18:30"):
            late = self.plan(time)
            self.assertIsNone(late["recommendation"])
            self.assertIn("Garden Gate", late["question"])
            self.assertEqual([route["status"] for route in late["routes"]],
                             ["blocked", "closed", "uncertain"])

    def test_context_change_and_all_closed(self):
        self.assertEqual(self.plan("18:30", False)["recommendation"]["gate"], "A")
        overnight = self.plan("20:00")
        self.assertIsNone(overnight["recommendation"])
        self.assertIsNone(overnight["question"])

    def test_invalid_context(self):
        with self.assertRaises(HTTPError) as failure:
            self.plan("24:00")
        self.assertEqual(failure.exception.code, 400)

    def test_frontend_and_discovery(self):
        with urlopen(self.origin) as response:
            self.assertIn(b"Find your way in.", response.read())
        with urlopen(self.origin + "/api/scout/agents/evidence/.well-known/agent-card.json") as response:
            self.assertEqual(json.load(response)["protocolVersion"], "0.3.0")
