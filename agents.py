"""Bounded tool execution and A2A JSON-RPC agent endpoints."""

import json
import os
from urllib.error import URLError
from urllib.request import Request, urlopen
from uuid import uuid4

from engine import (check_evidence, choose_route, evaluate_schedule, interpret_needs,
                    load_venue, validate_context)
from event_guide import (build_itinerary, classify_gates, fetch_traffic, finalize_visit,
                         read_guide, read_visit)


AGENTS = {
    "needs": ("Needs Interpreter", (validate_context, interpret_needs)),
    "routes": ("Route Planner", (load_venue, evaluate_schedule)),
    "evidence": ("Evidence Verifier", (check_evidence, choose_route)),
}
PREFIX = "/api/scout"
VISIT_TOOLS = {
    "needs": ((read_guide, ("request",), "guide"), (read_visit, ("request", "guide"), "context")),
    "routes": ((build_itinerary, ("guide", "context"), "itinerary"),
               (fetch_traffic, ("context", "itinerary"), "traffic")),
    "evidence": ((classify_gates, ("guide", "context"), "options"),
                 (finalize_visit, ("options", "itinerary", "traffic", "guide", "context"), "plan")),
}


def post_json(url: str, body: dict, headers: dict | None = None) -> dict:
    """Send a bounded JSON request to a configured service and decode its response."""
    request = Request(url, json.dumps(body).encode(),
                      {"Content-Type": "application/json", **(headers or {})})
    with urlopen(request, timeout=5) as response:
        return json.loads(response.read(65536))


def select_tool(name: str, remaining: list, observations: list[str]) -> tuple:
    """Ask the configured model for its next action, with a deterministic fallback."""
    expected = remaining[0]
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        return expected, "deterministic"
    tools = [{"type": "function", "function": {
        "name": tool.__name__, "description": tool.__doc__,
        "parameters": {"type": "object", "properties": {}, "additionalProperties": False}
    }} for tool in remaining]
    try:
        result = post_json("https://api.openai.com/v1/chat/completions", {
            "model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            "messages": [{"role": "system", "content":
                          f"You are the {name}. Select the next tool. "
                          "Follow data dependencies: validate before interpreting needs, "
                          "load venue evidence before checking hours, and classify before recommending."},
                         {"role": "user", "content": json.dumps(observations)}],
            "tools": tools, "tool_choice": "required", "parallel_tool_calls": False,
        }, {"Authorization": f"Bearer {key}"})
        call = result["choices"][0]["message"]["tool_calls"][0]["function"]["name"]
        if call == expected.__name__:
            return expected, "model"
    except (URLError, ValueError, KeyError, IndexError, TypeError, TimeoutError):
        pass
    return expected, "fallback"


def run_agent(slug: str, data: dict) -> dict:
    """Run each required action once, observing its result before the next action."""
    name, tools = AGENTS[slug]
    inputs = dict(data)
    observations = []
    trace = []
    for index in range(len(tools)):
        tool, mode = select_tool(name, list(tools[index:]), observations)
        if tool is validate_context:
            result = tool(inputs.get("arrival"), inputs.get("step_free"))
            inputs["context"] = result
        elif tool is interpret_needs:
            result = tool(inputs["context"])
        elif tool is load_venue:
            result = tool(inputs["context"])
            inputs["entrances"] = result
        elif tool is evaluate_schedule:
            result = tool(inputs["context"], inputs["entrances"])
        elif tool is check_evidence:
            result = tool(inputs["context"], inputs["routes"])
            inputs["checked"] = result
        else:
            result = {"routes": inputs["checked"], **tool(inputs["checked"])}
        if tool is load_venue:
            observation = f"Loaded evidence for {len(result)} entrances"
        elif tool is interpret_needs:
            observation = f'{result["arrival"]} arrival · {result["access_requirement"]}'
        elif isinstance(result, list):
            observation = ", ".join(
                f'{route["gate"]}: {route.get("status", "open" if route["open"] else "closed")}'
                for route in result
            )
        elif tool is choose_route:
            route = result["recommendation"]
            observation = f'{route["name"]} recommended' if route else "No confirmed route selected"
        else:
            observation = "Visitor context validated"
        observations.append(observation)
        trace.append({"agent": name, "tool": tool.__name__, "mode": mode, "observation": observation})
    return {"data": result, "trace": trace}


def agent_card(slug: str, origin: str) -> dict:
    """Describe the agent's A2A endpoint and supported skill."""
    name, tools = AGENTS[slug]
    return {
        "name": name, "description": tools[0].__doc__,
        "url": f"{origin}{PREFIX}/agents/{slug}", "protocolVersion": "0.3.0",
        "version": "1.0.0", "preferredTransport": "JSONRPC", "capabilities": {},
        "defaultInputModes": ["application/json"], "defaultOutputModes": ["application/json"],
        "skills": [
            {"id": slug, "name": name, "description": tools[0].__doc__, "tags": ["accessibility"]},
            {"id": f"{slug}-event", "name": f"{name} for event guides",
             "description": VISIT_TOOLS[slug][0][0].__doc__, "tags": ["event-guide"]},
        ],
    }


def dispatch(slug: str, request: dict) -> dict:
    """Execute an A2A message/send request and return a completed task artifact."""
    request_id = request.get("id")
    response = {"jsonrpc": "2.0", "id": request_id}
    if request.get("jsonrpc") != "2.0" or request.get("method") != "message/send":
        return {**response, "error": {"code": -32601, "message": "Expected message/send."}}
    try:
        message = request["params"]["message"]
        part, = message["parts"]
        if message["role"] != "user" or part["kind"] != "data" or not isinstance(part["data"], dict):
            raise ValueError("Expected a user message containing one data part.")
        data = part["data"]
        if data.get("workflow") == "event":
            result = run_visit_agent(slug, data["state"])
        elif slug != "needs":
            context = data["context"]
            context = validate_context(context["arrival"], context["step_free"])
            data = {"context": context, "routes": data.get("routes")}
            if slug == "evidence":
                expected = evaluate_schedule(context)
                if json.dumps(data["routes"], sort_keys=True) != json.dumps(expected, sort_keys=True):
                    raise ValueError("Route evidence does not match the venue fixture.")
            result = run_agent(slug, data)
        else:
            result = run_agent(slug, data)
    except (KeyError, TypeError, ValueError, AttributeError) as error:
        message = str(error) if isinstance(error, ValueError) else "Invalid agent input."
        return {**response, "error": {"code": -32602, "message": message}}
    return {**response, "result": {
        "kind": "task", "id": str(uuid4()), "contextId": message.get("contextId", str(uuid4())),
        "status": {"state": "completed"},
        "artifacts": [{"artifactId": str(uuid4()), "name": slug,
                       "parts": [{"kind": "data", "data": result}]}],
    }}


def run_visit_agent(slug: str, state: dict) -> dict:
    """Run the two event tools and produce an artifact for the next agent."""
    state = dict(state)
    steps = VISIT_TOOLS[slug]
    trace, observations = [], []
    for index, (expected, inputs, output) in enumerate(steps):
        name = AGENTS[slug][0]
        tool, mode = select_tool(name, [step[0] for step in steps[index:]], observations)
        state[output] = tool(*(state[key] for key in inputs))
        observation = f"{output.replace('_', ' ').capitalize()} prepared"
        if tool is fetch_traffic:
            observation = f"Traffic: {state[output]['status']}"
        observations.append(observation)
        trace.append({"agent": name, "tool": expected.__name__, "mode": mode, "observation": observation})
    state.pop("request", None)
    return {"data": state, "trace": trace}


def plan_route(data: dict, event: bool = False) -> dict:
    """Coordinate three A2A handoffs and return verified route evidence."""
    context_id = str(uuid4())
    origin = os.getenv("SCOUT_A2A_ORIGIN", "").rstrip("/")
    trace = []
    if event:
        data = {"workflow": "event", "state": {"request": data}}
    for slug in AGENTS:
        request = {"jsonrpc": "2.0", "id": str(uuid4()), "method": "message/send",
                   "params": {"message": {"kind": "message", "role": "user",
                                          "messageId": str(uuid4()), "contextId": context_id,
                                          "parts": [{"kind": "data", "data": data}]}}}
        response = post_json(agent_card(slug, origin)["url"], request) if origin else dispatch(slug, request)
        if "error" in response:
            raise ValueError(response["error"]["message"])
        artifact = response["result"]["artifacts"][0]["parts"][0]["data"]
        trace.extend(artifact["trace"])
        if event:
            data["state"] = artifact["data"]
        elif slug == "needs":
            data = {"context": artifact["data"]}
        elif slug == "routes":
            data["routes"] = artifact["data"]
    if event:
        return {**artifact["data"]["plan"], "trace": trace}
    return {**artifact["data"], "context": data["context"], "trace": trace}
