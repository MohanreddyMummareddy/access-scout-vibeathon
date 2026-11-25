"""Boundary and provider tests for the general event planner."""

import json
import os
import unittest
from io import BytesIO
from unittest.mock import patch
from urllib.error import URLError

from agents import dispatch, plan_route, select_tool
from engine import choose_route, validate_context
from event_guide import coordinate, fetch_traffic, read_guide


class EventGuideTest(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {"SCOUT_A2A_ORIGIN": "", "OPENAI_API_KEY": "",
                                           "TOMTOM_API_KEY": ""})
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_empty_oversized_and_invalid_context(self):
        request = {"arrival": "17:30", "leave": "19:30", "step_free": True}
        for invalid in ({"guide": ""}, {"guide": "x" * 4801},
                        {"guide": "Notes", "leave": "17:30"},
                        {"guide": "Notes", "step_free": "true"},
                        {"guide": "Notes", "origin": []}):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                plan_route({**request, **invalid}, event=True)

    def test_session_boundaries_and_alternatives(self):
        plan = plan_route({
            "guide": "Before | 16:00–17:00\nFirst | 17:00–18:00\nSecond | 18:00–19:00\nAfter | 19:00–20:00",
            "arrival": "17:00", "leave": "19:00", "step_free": False,
        }, event=True)
        self.assertEqual([(s["name"], s["fit"], s["overlaps"]) for s in plan["sessions"]],
                         [("First", "full", False), ("Second", "full", False)])
        self.assertEqual(plan["entry"], [])
        self.assertEqual(plan["exit"], [])

    def test_missing_hours_and_explicit_access_limits(self):
        plan = plan_route({
            "guide": "Gate A | step-free\nGate B | 16:00–20:00 | no step-free path\n"
                     "Gate C | 17:30–19:30 | step-free",
            "arrival": "17:30", "leave": "19:30", "step_free": True,
        }, event=True)
        self.assertEqual([gate["status"] for gate in plan["entry"]],
                         ["Needs confirmation", "Has steps or is marked inaccessible", "Eligible"])
        self.assertEqual(plan["exit"][-1]["status"], "Closed at this time")

    def test_guide_am_pm_and_overnight_rows(self):
        guide = read_guide({"guide": "Gate B | 4:00 PM–6:00 PM | step-free\nLate | 22:00–01:00"})
        self.assertEqual((guide["gates"][0]["start"], guide["gates"][0]["end"]), ("16:00", "18:00"))
        self.assertEqual(guide["notes"], ["Late | 22:00–01:00"])

    def test_time_first_rows_and_gate_words_in_session_titles(self):
        guide = read_guide({"guide": "17:00–18:00 | Gate B | step-free\n"
                                    "17:15–17:40 | Exit Strategy Workshop"})
        self.assertEqual(guide["gates"][0]["name"], "Gate B")
        self.assertEqual(guide["sessions"][0]["name"], "Exit Strategy Workshop")

    def test_coordinate_validation(self):
        self.assertEqual(coordinate("28.59, 77.22"), "28.59,77.22")
        for value in ("91,12", "9,181", "Station"):
            with self.subTest(value=value):
                self.assertIsNone(coordinate(value))

    def test_traffic_provider_success_feeds_departure_estimate(self):
        summary = {"routes": [{"summary": {"travelTimeInSeconds": 901, "trafficDelayInSeconds": 61}}]}
        with patch.dict(os.environ, {"TOMTOM_API_KEY": "test-only"}), patch(
            "event_guide.urlopen", side_effect=lambda *_a, **_k: BytesIO(json.dumps(summary).encode())
        ) as mocked:
            plan = plan_route({
                "guide": "Gate A | 16:00–20:00 | step-free | 28.59,77.22",
                "arrival": "17:30", "leave": "19:30", "step_free": True, "origin": "28.5,77.1",
            }, event=True)
        self.assertEqual(plan["traffic"]["inbound"], {"minutes": 16, "delay": 2})
        self.assertEqual(plan["leave_base_if_current"], "17:14")
        self.assertEqual(mocked.call_count, 2)
        self.assertIn("/28.59,77.22:28.5,77.1/", mocked.call_args.args[0])

    def test_traffic_failure_does_not_invent_estimates(self):
        context = {"origin": "28.5,77.1", "destination": "28.59,77.22"}
        with patch.dict(os.environ, {"TOMTOM_API_KEY": "test-only"}), patch(
            "event_guide.urlopen", side_effect=URLError("unavailable")
        ):
            result = fetch_traffic(context, {"targets": {}})
        self.assertEqual(result["status"], "unavailable")
        self.assertNotIn("inbound", result)

    def test_model_out_of_order_falls_back(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-only"}), patch(
            "agents.post_json", return_value={"choices": [{"message": {"tool_calls": [
                {"function": {"name": "choose_route"}}
            ]}}]}
        ):
            action, mode = select_tool("Test", [validate_context, choose_route], [])
        self.assertIs(action, validate_context)
        self.assertEqual(mode, "fallback")

    def test_a2a_rejects_unsupported_and_malformed_messages(self):
        self.assertEqual(dispatch("needs", {"jsonrpc": "2.0", "method": "tasks/get"})["error"]["code"], -32601)
        response = dispatch("needs", {"jsonrpc": "2.0", "method": "message/send", "id": "test"})
        self.assertEqual(response["id"], "test")
        self.assertEqual(response["error"]["code"], -32602)
