"""Parse reviewed event text and build an evidence-based visit plan."""

import json
import os
import re
from datetime import datetime, timezone
from math import ceil
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from engine import validate_context

TIME = r"(?:[01]?\d|2[0-3]):[0-5]\d(?:\s*[ap]\.?m\.?)?"
RANGE = re.compile(rf"(?P<start>{TIME})\s*(?:[-–—]|\bto\b)\s*(?P<end>{TIME})", re.I)
GATE = re.compile(r"\b(?:gate|entrance|exit)\b", re.I)
POINT = re.compile(r"^(-?\d{1,3}(?:\.\d+)?)\s*,\s*(-?\d{1,3}(?:\.\d+)?)$")


def clock(value: str) -> str:
    value = re.sub(r"[.\s]", "", value.lower())
    fmt = "%I:%M%p" if value.endswith(("am", "pm")) else "%H:%M"
    return datetime.strptime(value, fmt).strftime("%H:%M")


def coordinate(value: str) -> str | None:
    match = POINT.fullmatch(value.strip())
    if match:
        lat, lon = map(float, match.groups())
        if -90 <= lat <= 90 and -180 <= lon <= 180:
            return f"{lat},{lon}"
    return None


def read_guide(request: dict) -> dict:
    """Extract same-line gate hours, access evidence, sessions, and location from reviewed text."""
    text = request.get("guide")
    if not isinstance(text, str) or not text.strip() or len(text) > 4800:
        raise ValueError("Enter up to 4,800 characters of event guide text.")
    gates, sessions, notes = [], [], []
    venue = ""
    for raw in text.splitlines()[:100]:
        line = raw.strip()[:250]
        if not line:
            continue
        if line.lower().startswith(("venue:", "address:", "location:")):
            venue = line.split(":", 1)[1].strip()
            continue
        period = RANGE.search(line)
        start, end = (None, None)
        if period:
            try:
                start, end = map(clock, period.groups())
            except ValueError:
                period = None
        if period and start >= end:
            notes.append(line)
            continue
        if GATE.search(line):
            label = (line[:period.start()] if period else line.split("|", 1)[0]).strip(" |:-–")[:75]
            if not label:
                notes.append(line)
                continue
            lowered = line.lower()
            blocked = re.search(r"\b(?:stairs|steps|(?:not|no) step[- ]free)\b", lowered)
            accessible = re.search(r"\bstep[- ]free\b", lowered)
            unconfirmed = re.search(r"\b(?:unconfirmed|unknown|unclear|check|confirm with)\b|\?", lowered)
            access = False if blocked else True if accessible and not unconfirmed else None
            direction = "exit" if "exit only" in lowered or lowered.startswith("exit ") else (
                "entry" if "entry only" in lowered or "entrance only" in lowered else "both"
            )
            point = next((coord for part in line.split("|") if (coord := coordinate(part))), None)
            gates.append({"name": label, "start": start, "end": end, "access": access, "point": point,
                          "direction": direction, "source": line})
        elif period:
            label = (line[:period.start()] or line[period.end():]).strip(" |:-–")
            if label:
                sessions.append({"name": label[:100], "start": start, "end": end, "source": line})
        else:
            notes.append(line)
    return {"gates": gates[:20], "sessions": sessions[:25], "venue": venue, "notes": notes[:12]}


def read_visit(request: dict, guide: dict) -> dict:
    """Validate arrival, exit, accessibility preferences and optional map endpoints."""
    context = validate_context(request.get("arrival"), request.get("step_free"))
    leave = validate_context(request.get("leave"), context["step_free"])["arrival"]
    if leave <= context["arrival"]:
        raise ValueError("Set an exit time after arrival on the same event day.")
    fields = {key: request.get(key, "") for key in ("origin", "destination")}
    if any(not isinstance(value, str) or len(value) > 180 for value in fields.values()):
        raise ValueError("Enter map locations of 180 characters or fewer.")
    return {**context, "leave": leave, "origin": fields["origin"].strip(),
            "destination": fields["destination"].strip() or guide["venue"]}


def build_itinerary(guide: dict, context: dict) -> dict:
    """List sessions that fit and alternate sessions that overlap the visit."""
    arrival, leave = context["arrival"], context["leave"]
    sessions = []
    for session in sorted(guide["sessions"], key=lambda item: item["start"]):
        start, end = session["start"], session["end"]
        if start < leave and end > arrival:
            sessions.append({**session, "fit": "full" if arrival <= start and end <= leave else "partial",
                             "overlaps": any(other is not session and start < other["end"]
                                             and end > other["start"] for other in guide["sessions"])})
    options = classify_gates(guide, context)
    targets = {}
    for leg, gates in options.items():
        candidates = [gate for gate in gates if gate["status"] == "Eligible" and gate["point"]]
        if len(candidates) == 1:
            targets[leg] = {"name": candidates[0]["name"], "point": candidates[0]["point"]}
    return {"sessions": sessions, "targets": targets}


def fetch_traffic(context: dict, itinerary: dict) -> dict:
    """Look up a current driving estimate and delay for supplied endpoint coordinates."""
    key = os.getenv("TOMTOM_API_KEY")
    origin, destination = (coordinate(context[name]) for name in ("origin", "destination"))
    entry = itinerary["targets"].get("entry", {}).get("point", destination)
    exit_point = itinerary["targets"].get("exit", {}).get("point", destination)
    if not key or not origin or not entry or not exit_point:
        return {"status": "unavailable", "reason": (
            "Live traffic requires a configured provider and latitude, longitude for both points. "
            "Open directions to check road routing independently."
        )}
    params = urlencode({"key": key, "traffic": "true", "routeRepresentation": "summaryOnly",
                        "travelMode": "car"})
    estimates = []
    try:
        for start, end in ((origin, entry), (exit_point, origin)):
            url = f"https://api.tomtom.com/routing/1/calculateRoute/{start}:{end}/json?{params}"
            with urlopen(url, timeout=3) as response:
                summary = json.loads(response.read(32768))["routes"][0]["summary"]
            estimates.append({"minutes": ceil(summary["travelTimeInSeconds"] / 60),
                              "delay": ceil(summary["trafficDelayInSeconds"] / 60)})
    except (URLError, ValueError, KeyError, IndexError, TypeError, TimeoutError):
        return {"status": "unavailable", "reason": "The traffic provider did not return a route."}
    return {"status": "current", "provider": "TomTom", "inbound": estimates[0],
            "outbound": estimates[1], "checked": datetime.now(timezone.utc).isoformat()}


def classify_gates(guide: dict, context: dict) -> dict:
    """Check gate hours, direction and explicitly stated accessibility for both legs."""
    result = {}
    for leg, time in (("entry", context["arrival"]), ("exit", context["leave"])):
        options = []
        for gate in guide["gates"]:
            if gate["direction"] not in ("both", leg):
                status = "Wrong direction"
            elif gate["start"] and not gate["start"] <= time < gate["end"]:
                status = "Closed at this time"
            elif context["step_free"] and gate["access"] is False:
                status = "Has steps or is marked inaccessible"
            elif not gate["start"] or (context["step_free"] and gate["access"] is None):
                status = "Needs confirmation"
            else:
                status = "Eligible"
            options.append({**gate, "status": status})
        result[leg] = options
    return result


def finalize_visit(options: dict, itinerary: dict, traffic: dict, guide: dict, context: dict) -> dict:
    """Return visit options, road estimates and the remaining guide uncertainties."""
    road = None
    if traffic["status"] == "current":
        hour, minute = map(int, context["arrival"].split(":"))
        departure = hour * 60 + minute - traffic["inbound"]["minutes"]
        if departure >= 0:
            road = f"{departure // 60:02d}:{departure % 60:02d}"
    return {**options, **itinerary, "traffic": traffic, "leave_base_if_current": road,
            "venue": guide["venue"], "context": context, "notes": guide["notes"]}
