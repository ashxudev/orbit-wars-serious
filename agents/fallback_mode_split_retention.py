"""Fallback-derived mode split with production-retention defense margin.

This opt-in candidate keeps the current mode split shape, but adds a bounded
extra margin when defending owned production that the forecast says will fall.
The local pressure-six sweep showed the margin-18 variant preserved the same
4/6 result as ``fallback_mode_split`` while extending the hard 4P mixed-style
collapse from turn 240 to turn 431.
"""

from __future__ import annotations

from pathlib import Path
from types import MappingProxyType
from typing import Any

from agents import fallback_mode_split, fallback_source_guard


DEFENSE_MARGIN = 18

REPO_ROOT = Path(__file__).resolve().parents[1]
BASE_AGENT_PATH = (
    REPO_ROOT
    / "historical_opponents"
    / "agents"
    / "claude_v3_wide_search_forecast.py"
)

_MIN_VALUE_NEEDLE = (
    "MIN_V = 1.0             # do not commit missions below this marginal value\n"
)
_MARGIN_NEEDLE = (
    "            margin = MARGIN_ENEMY if owner[ti] != -1 and owner[ti] != me else MARGIN_NEUTRAL\n"
    "            n = need + margin\n"
)


def build_source() -> str:
    """Return standalone Python source for the retention mode-split candidate."""

    return "\n".join(
        (
            '"""Standalone fallback retention mode-split Orbit Wars agent."""',
            "",
            f"_SOURCE_GUARD_RETENTION_SOURCE = {_retention_source(fallback_source_guard.build_source())!r}",
            f"_RESPONSE_MARGIN_RETENTION_SOURCE = {_retention_source(fallback_mode_split._response_margin_source())!r}",
            "_source_guard_namespace = {",
            '    "__name__": "fallback_mode_split_retention_source_guard",',
            '    "__file__": "fallback_mode_split_retention_source_guard.py",',
            "}",
            "_response_margin_namespace = {",
            '    "__name__": "fallback_mode_split_retention_response_margin",',
            '    "__file__": "fallback_mode_split_retention_response_margin.py",',
            "}",
            "exec(",
            "    compile(",
            '        _SOURCE_GUARD_RETENTION_SOURCE,',
            '        "fallback_mode_split_retention_source_guard.py",',
            '        "exec",',
            "    ),",
            "    _source_guard_namespace,",
            ")",
            "exec(",
            "    compile(",
            '        _RESPONSE_MARGIN_RETENTION_SOURCE,',
            '        "fallback_mode_split_retention_response_margin.py",',
            '        "exec",',
            "    ),",
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
            "    return max(2, max(players) + 1) if players else 2",
            "",
            "player_count_for_observation = _player_count",
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
            "__all__ = (",
            '    "agent",',
            '    "player_count_for_observation",',
            '    "think",',
            ")",
            "",
        )
    )


def _retention_source(source: str) -> str:
    source = _replace_once(
        source,
        _MIN_VALUE_NEEDLE,
        _MIN_VALUE_NEEDLE + f"DEFENSE_MARGIN = {DEFENSE_MARGIN}\n",
    )
    return _replace_once(
        source,
        _MARGIN_NEEDLE,
        (
            "            margin = MARGIN_ENEMY if owner[ti] != -1 and owner[ti] != me else MARGIN_NEUTRAL\n"
            "            if owner[ti] == me and base_tl[ti][2] is not None:\n"
            "                margin = max(margin, DEFENSE_MARGIN + max(0, 14 - base_tl[ti][2]))\n"
            "            n = need + margin\n"
        ),
    )


def _replace_once(source: str, needle: str, replacement: str) -> str:
    count = source.count(needle)
    if count != 1:
        raise RuntimeError(f"expected exactly one replacement site for {needle!r}")
    return source.replace(needle, replacement, 1)


_namespace: dict[str, Any] = {
    "__name__": "agents.fallback_mode_split_retention_generated",
    "__file__": str(BASE_AGENT_PATH),
}
exec(compile(build_source(), str(BASE_AGENT_PATH), "exec"), _namespace)

agent = _namespace["agent"]
think = _namespace["think"]
player_count_for_observation = _namespace["player_count_for_observation"]
generated_symbols = MappingProxyType(_namespace)


__all__ = (
    "DEFENSE_MARGIN",
    "agent",
    "build_source",
    "generated_symbols",
    "player_count_for_observation",
    "think",
)
