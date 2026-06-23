"""Fallback-derived reserve candidate with source/hold guards.

This module keeps the historical fallback source immutable and applies a small,
deterministic patch at import time so the variant can be evaluated separately.
Use ``scripts/build_fallback_source_guard_submission.py`` to emit a standalone
submission file if this candidate ever earns promotion evidence.
"""

from __future__ import annotations

from pathlib import Path
from types import MappingProxyType
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
BASE_AGENT_PATH = (
    REPO_ROOT
    / "historical_opponents"
    / "agents"
    / "claude_v3_wide_search_forecast.py"
)

_CONSTANT_NEEDLE = "MAX_MOVES = 16\n"
_CONSTANT_PATCH = (
    "MAX_MOVES = 16\n"
    "SOURCE_LOSS_GUARD_TICKS = 24\n"
    "SHORT_HOLD_GUARD_TICKS = 28\n"
)

_EVAL_NEEDLE = (
    "        if funnel:\n"
    "            gain = front_dist(si) - front_dist(ti)\n"
)
_EVAL_PATCH = (
    "        source_owner, source_ships, source_lost, _ = sim(\n"
    "            si, None, ships0=cur_ships[si] - n\n"
    "        )\n"
    "        baseline_source_lost = base_tl[si][2]\n"
    "        newly_lost_source = (\n"
    "            source_lost is not None\n"
    "            and (\n"
    "                baseline_source_lost is None\n"
    "                or source_lost + 2 < baseline_source_lost\n"
    "            )\n"
    "        )\n"
    "        if newly_lost_source:\n"
    "            source_penalty = 18.0 + 32.0 * pprod[si]\n"
    "            if source_lost <= SOURCE_LOSS_GUARD_TICKS:\n"
    "                source_penalty += 2.0 * (SOURCE_LOSS_GUARD_TICKS - source_lost)\n"
    "            V -= source_penalty\n"
    "            if pprod[si] >= 3 and source_lost <= 8 and not funnel:\n"
    "                return None\n"
    "        if owner[ti] != me and fg2 is not None and fl2 is not None:\n"
    "            held_for = fl2 - fg2\n"
    "            if held_for <= SHORT_HOLD_GUARD_TICKS:\n"
    "                V -= 24.0 + 24.0 * pprod[ti]\n"
    "                if pprod[ti] >= 3 and held_for <= 8:\n"
    "                    return None\n"
)


def build_source() -> str:
    """Return standalone Python source for the source-guard candidate."""

    source = BASE_AGENT_PATH.read_text(encoding="utf-8")
    source = _replace_once(source, _CONSTANT_NEEDLE, _CONSTANT_PATCH)
    source = _replace_once(source, _EVAL_NEEDLE, _EVAL_PATCH + _EVAL_NEEDLE)
    return source


def _replace_once(source: str, needle: str, replacement: str) -> str:
    count = source.count(needle)
    if count != 1:
        raise RuntimeError(f"expected exactly one replacement site for {needle!r}")
    return source.replace(needle, replacement, 1)


_namespace: dict[str, Any] = {
    "__name__": "agents.fallback_source_guard_generated",
    "__file__": str(BASE_AGENT_PATH),
}
exec(compile(build_source(), str(BASE_AGENT_PATH), "exec"), _namespace)

agent = _namespace["agent"]
think = _namespace["think"]
generated_symbols = MappingProxyType(_namespace)


__all__ = ("agent", "build_source", "generated_symbols", "think")
