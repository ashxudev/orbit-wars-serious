"""Fallback mode split with retention applied only to 4P.

This opt-in candidate is a safer follow-up to ``fallback_mode_split_retention``:
2P keeps the live source-guard behavior, while 4P uses the retention-patched
response-margin planner that fixed the historical mixed-style 4P collapse
locally and in Daytona.
"""

from __future__ import annotations

from pathlib import Path
from types import MappingProxyType
from typing import Any

from agents import (
    fallback_mode_split,
    fallback_mode_split_retention,
    fallback_source_guard,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
BASE_AGENT_PATH = (
    REPO_ROOT
    / "historical_opponents"
    / "agents"
    / "claude_v3_wide_search_forecast.py"
)


def build_source() -> str:
    """Return standalone Python source for the 4P-retention split candidate."""

    return "\n".join(
        (
            '"""Standalone fallback 4P-retention mode-split Orbit Wars agent."""',
            "",
            f"_SOURCE_GUARD_SOURCE = {fallback_source_guard.build_source()!r}",
            (
                "_RESPONSE_MARGIN_RETENTION_SOURCE = "
                f"{_response_margin_retention_source()!r}"
            ),
            "_source_guard_namespace = {",
            '    "__name__": "fallback_mode_split_4p_retention_source_guard",',
            '    "__file__": "fallback_mode_split_4p_retention_source_guard.py",',
            "}",
            "_response_margin_namespace = {",
            '    "__name__": "fallback_mode_split_4p_retention_response_margin",',
            '    "__file__": "fallback_mode_split_4p_retention_response_margin.py",',
            "}",
            "exec(",
            '    compile(_SOURCE_GUARD_SOURCE, "fallback_mode_split_4p_retention_source_guard.py", "exec"),',
            "    _source_guard_namespace,",
            ")",
            "exec(",
            "    compile(",
            '        _RESPONSE_MARGIN_RETENTION_SOURCE,',
            '        "fallback_mode_split_4p_retention_response_margin.py",',
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


def _response_margin_retention_source() -> str:
    return fallback_mode_split_retention._retention_source(
        fallback_mode_split._response_margin_source(),
    )


_namespace: dict[str, Any] = {
    "__name__": "agents.fallback_mode_split_4p_retention_generated",
    "__file__": str(BASE_AGENT_PATH),
}
exec(compile(build_source(), str(BASE_AGENT_PATH), "exec"), _namespace)

agent = _namespace["agent"]
think = _namespace["think"]
player_count_for_observation = _namespace["player_count_for_observation"]
generated_symbols = MappingProxyType(_namespace)


__all__ = (
    "agent",
    "build_source",
    "generated_symbols",
    "player_count_for_observation",
    "think",
)
