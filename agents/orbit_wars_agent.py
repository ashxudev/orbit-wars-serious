"""Minimal Orbit Wars runtime entrypoint boundary.

Runtime / Submission Cycle 0 exposes the Kaggle-callable ``agent`` function
and intentionally returns safe no-action output. Planner wiring, observation
parsing, action conversion, timing budgets, and submission bundling are
deferred to later runtime cycles.
"""

from __future__ import annotations

from typing import TypeAlias


KaggleActionRow: TypeAlias = list[int | float]


def agent(
    observation: object,
    configuration: object | None = None,
) -> list[KaggleActionRow]:
    """Return a fresh no-action list for the current runtime boundary."""

    return []


__all__ = ("agent",)
