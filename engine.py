"""Access Scout venue evidence and deterministic route tools."""

import re


VENUE = (
    {"gate": "A", "name": "Main Gate", "walk": 3, "close": "20:00",
     "segments": [("Entrance", False, "Venue map shows six steps."),
                  ("Path to festival", True, "Venue map marks a paved path.")]},
    {"gate": "B", "name": "Library Gate", "walk": 5, "close": "18:00",
     "segments": [("Entrance", True, "Event access sheet confirms a ramp."),
                  ("Path to festival", True, "Event access sheet confirms a step-free path.")]},
    {"gate": "C", "name": "Garden Gate", "walk": 7, "close": "20:00",
     "segments": [("Entrance", None, "The venue map does not describe the entrance level."),
                  ("Path to festival", True, "Event access sheet confirms a level path.")]},
)


def validate_context(arrival: str, step_free: bool) -> dict:
    """Validate a visitor's local HH:MM arrival and required step-free choice."""
    if not isinstance(arrival, str) or not re.fullmatch(r"(?:[01][0-9]|2[0-3]):[0-5][0-9]", arrival):
        raise ValueError("Enter an arrival time in HH:MM format.")
    if not isinstance(step_free, bool):
        raise ValueError("Choose whether you need a step-free route.")
    return {"arrival": arrival, "step_free": step_free}


def evaluate_schedule(context: dict) -> list[dict]:
    """List gate routes and whether each entrance admits visitors at arrival."""
    return [
        {**route, "open": "16:00" <= context["arrival"] < route["close"]}
        for route in VENUE
    ]


def check_evidence(context: dict, routes: list[dict]) -> list[dict]:
    """Classify each route from its hours and documented segment conditions."""
    checked = []
    for route in routes:
        segments = route["segments"]
        if not route["open"]:
            status, reason = "closed", f'Gate hours are 16:00–{route["close"]}.'
        elif context["step_free"] and any(access is False for _, access, _ in segments):
            status, reason = "blocked", "This route includes a segment with steps."
        elif context["step_free"] and any(access is None for _, access, _ in segments):
            status, reason = "uncertain", "Step-free access is unconfirmed for part of this route."
        else:
            status, reason = "available", "Open and meets your selected requirements."
        checked.append({**route, "status": status, "reason": reason})
    return checked


def choose_route(routes: list[dict]) -> dict:
    """Select the shortest verified option or suggest a question about missing evidence."""
    available = [route for route in routes if route["status"] == "available"]
    uncertain = [route for route in routes if route["status"] == "uncertain"]
    if available:
        return {"recommendation": min(available, key=lambda route: route["walk"]), "question": None}
    if uncertain:
        route = min(uncertain, key=lambda option: option["walk"])
        return {"recommendation": None,
                "question": f'Is {route["name"]} step-free from the street to the level festival path?'}
    return {"recommendation": None, "question": None}
