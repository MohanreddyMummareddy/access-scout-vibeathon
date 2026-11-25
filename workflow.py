"""Shared, bounded tool runner for the sample and event workflows."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


def summarize(result: Any) -> str:
    """Provide a safe, generic observation without exposing request data."""
    return "Tool result prepared"


@dataclass(frozen=True)
class ToolStep:
    action: Callable[..., Any]
    inputs: tuple[str, ...]
    output: str
    observe: Callable[[Any], str] = summarize


def run_steps(name: str, steps: tuple[ToolStep, ...], state: dict,
              select: Callable) -> tuple[dict, list[dict]]:
    """Execute declared dependencies and return the updated state and public trace."""
    state = dict(state)
    trace, observations = [], []
    for index, step in enumerate(steps):
        remaining = [candidate.action for candidate in steps[index:]]
        action, mode = select(name, remaining, observations)
        result = action(*(state.get(key) for key in step.inputs))
        state[step.output] = result
        observation = step.observe(result)
        observations.append(observation)
        trace.append({"agent": name, "tool": action.__name__, "mode": mode,
                      "observation": observation})
    return state, trace
