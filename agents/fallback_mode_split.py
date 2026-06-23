"""Fallback-derived mode split reserve candidate.

This candidate keeps the source-guard behavior for 2P while using the
response-margin variant for 4P, matching the strongest local pressure-sweep
result found after the source-guard live run.
"""

from __future__ import annotations

from pathlib import Path
from types import MappingProxyType
from typing import Any

from agents import fallback_source_guard


REPO_ROOT = Path(__file__).resolve().parents[1]
BASE_AGENT_PATH = (
    REPO_ROOT
    / "historical_opponents"
    / "agents"
    / "claude_v3_wide_search_forecast.py"
)

_RESPONSE_MARGIN_PATCHES = (
    ("MARGIN_ENEMY = 4\n", "MARGIN_ENEMY = 8\n"),
    ("RESP_DISCOUNT = 0.55", "RESP_DISCOUNT = 0.75"),
    (
        "MAX_MOVES = 16\n",
        "MAX_MOVES = 14\n"
        "SOURCE_LOSS_GUARD_TICKS = 30\n"
        "SHORT_HOLD_GUARD_TICKS = 28\n",
    ),
)

_RESPONSE_NEEDLE = (
    "        elif owner[ti] != me:\n"
    "            resp = enemy_response(ti, T)\n"
    "            if resp > 0:\n"
    "                V -= RESP_DISCOUNT * min(resp, n)\n"
)
_RESPONSE_PATCH = (
    "        elif owner[ti] != me:\n"
    "            resp = enemy_response(ti, T)\n"
    "            if resp > 0:\n"
    "                V -= RESP_DISCOUNT * min(resp, n)\n"
    "                if pprod[ti] >= 2 and resp >= max(8, int(n * 0.70)):\n"
    "                    return None\n"
)

_EVAL_NEEDLE = (
    "        if funnel:\n"
    "            gain = front_dist(si) - front_dist(ti)\n"
)
_RESPONSE_MARGIN_EVAL_PATCH = (
    "        _, _, source_lost, _ = sim(si, None, ships0=cur_ships[si] - n)\n"
    "        baseline_source_lost = base_tl[si][2]\n"
    "        newly_lost_source = (\n"
    "            source_lost is not None\n"
    "            and (\n"
    "                baseline_source_lost is None\n"
    "                or source_lost + 2 < baseline_source_lost\n"
    "            )\n"
    "        )\n"
    "        if newly_lost_source:\n"
    "            V -= 20.0 + 28.0 * pprod[si]\n"
    "            if source_lost <= SOURCE_LOSS_GUARD_TICKS:\n"
    "                V -= 1.8 * (SOURCE_LOSS_GUARD_TICKS - source_lost)\n"
    "            if pprod[si] >= 3 and source_lost <= 10 and not funnel:\n"
    "                return None\n"
    "        if owner[ti] != me and fg2 is not None and fl2 is not None:\n"
    "            held_for = fl2 - fg2\n"
    "            if held_for <= SHORT_HOLD_GUARD_TICKS:\n"
    "                V -= 26.0 + 24.0 * pprod[ti]\n"
    "                if pprod[ti] >= 3 and held_for <= 10:\n"
    "                    return None\n"
)


def build_source() -> str:
    """Return standalone Python source for the mode-split candidate."""

    return "\n".join(
        (
            '"""Standalone fallback mode-split Orbit Wars agent."""',
            "",
            f"_SOURCE_GUARD_SOURCE = {fallback_source_guard.build_source()!r}",
            f"_RESPONSE_MARGIN_SOURCE = {_response_margin_source()!r}",
            "_source_guard_namespace = {",
            '    "__name__": "fallback_mode_split_source_guard",',
            '    "__file__": "fallback_mode_split_source_guard.py",',
            "}",
            "_response_margin_namespace = {",
            '    "__name__": "fallback_mode_split_response_margin",',
            '    "__file__": "fallback_mode_split_response_margin.py",',
            "}",
            "exec(",
            '    compile(_SOURCE_GUARD_SOURCE, "fallback_mode_split_source_guard.py", "exec"),',
            "    _source_guard_namespace,",
            ")",
            "exec(",
            '    compile(_RESPONSE_MARGIN_SOURCE, "fallback_mode_split_response_margin.py", "exec"),',
            "    _response_margin_namespace,",
            ")",
            "",
            "def _player_count(observation):",
            "    players = set()",
            "    try:",
            '        players.add(int(observation.get("player", 0)))',
            "    except Exception:",
            "        pass",
            '    for planet in observation.get("planets", []) or []:',
            "        try:",
            "            owner = int(planet[1])",
            "        except Exception:",
            "            continue",
            "        if owner >= 0:",
            "            players.add(owner)",
            '    for fleet in observation.get("fleets", []) or []:',
            "        try:",
            "            owner = int(fleet[1])",
            "        except Exception:",
            "            continue",
            "        if owner >= 0:",
            "            players.add(owner)",
            "    return max(players) + 1 if players else 2",
            "",
            "def _selected_agent(observation):",
            "    if _player_count(observation) >= 4:",
            '        return _response_margin_namespace["agent"]',
            '    return _source_guard_namespace["agent"]',
            "",
            "def agent(observation, config=None):",
            "    return _selected_agent(observation)(observation, config)",
            "",
            "def think(observation, config=None):",
            "    return agent(observation, config)",
            "",
        )
    )


def _response_margin_source() -> str:
    source = BASE_AGENT_PATH.read_text(encoding="utf-8")
    for needle, replacement in _RESPONSE_MARGIN_PATCHES:
        source = _replace_once(source, needle, replacement)
    source = _replace_once(source, _RESPONSE_NEEDLE, _RESPONSE_PATCH)
    source = _replace_once(
        source,
        _EVAL_NEEDLE,
        _RESPONSE_MARGIN_EVAL_PATCH + _EVAL_NEEDLE,
    )
    return source


def _replace_once(source: str, needle: str, replacement: str) -> str:
    count = source.count(needle)
    if count != 1:
        raise RuntimeError(f"expected exactly one replacement site for {needle!r}")
    return source.replace(needle, replacement, 1)


_namespace: dict[str, Any] = {
    "__name__": "agents.fallback_mode_split_generated",
    "__file__": str(BASE_AGENT_PATH),
}
exec(compile(build_source(), str(BASE_AGENT_PATH), "exec"), _namespace)

agent = _namespace["agent"]
think = _namespace["think"]
player_count_for_observation = _namespace["_player_count"]
generated_symbols = MappingProxyType(_namespace)


__all__ = (
    "agent",
    "build_source",
    "generated_symbols",
    "player_count_for_observation",
    "think",
)
