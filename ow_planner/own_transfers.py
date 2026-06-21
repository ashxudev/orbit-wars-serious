"""Own-to-own transfer intent fact extraction.

V1 Deterministic Leak Fix Cycle 3 classifies already in-flight friendly
own-to-own transfers. It does not generate missions, score options, select
actions, run rollouts, or mutate game state.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from ow_sim.forecast import fleet_speed
from ow_sim.geometry import distance
from ow_sim.state import Fleet, GameState, Planet

from .owned_threats import (
    OwnedPlanetThreatFacts,
    OwnedProductionThreatReport,
    owned_production_threat_facts,
)


@dataclass(frozen=True, slots=True)
class OwnTransferFleetFacts:
    """Intent facts for one inferred own-to-own transfer fleet."""

    fleet_id: int
    owner: int
    source_planet_id: int
    target_planet_id: int
    ships: int
    eta_ticks: int
    distance_to_target: float
    source_current_ships: int
    target_current_ships: int
    source_production: int
    target_production: int
    source_production_bearing: bool
    target_production_bearing: bool
    source_under_pressure: bool
    target_under_pressure: bool
    target_at_risk: bool
    repeated_source_target_transfer_count: int
    purposeful: bool
    potentially_spammy: bool
    labels: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "distance_to_target": self.distance_to_target,
            "eta_ticks": self.eta_ticks,
            "fleet_id": self.fleet_id,
            "labels": list(self.labels),
            "owner": self.owner,
            "potentially_spammy": self.potentially_spammy,
            "purposeful": self.purposeful,
            "repeated_source_target_transfer_count": (
                self.repeated_source_target_transfer_count
            ),
            "ships": self.ships,
            "source_current_ships": self.source_current_ships,
            "source_planet_id": self.source_planet_id,
            "source_production": self.source_production,
            "source_production_bearing": self.source_production_bearing,
            "source_under_pressure": self.source_under_pressure,
            "target_at_risk": self.target_at_risk,
            "target_current_ships": self.target_current_ships,
            "target_planet_id": self.target_planet_id,
            "target_production": self.target_production,
            "target_production_bearing": self.target_production_bearing,
            "target_under_pressure": self.target_under_pressure,
        }


@dataclass(frozen=True, slots=True)
class OwnTransferIntentReport:
    """Aggregate own-to-own transfer intent facts for a state."""

    player_id: int | None
    transfer_facts: tuple[OwnTransferFleetFacts, ...] = ()
    transfer_count: int = 0
    purposeful_count: int = 0
    potentially_spammy_count: int = 0
    repeated_transfer_group_count: int = 0
    labels: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "labels": list(self.labels),
            "player_id": self.player_id,
            "potentially_spammy_count": self.potentially_spammy_count,
            "purposeful_count": self.purposeful_count,
            "repeated_transfer_group_count": self.repeated_transfer_group_count,
            "transfer_count": self.transfer_count,
            "transfer_facts": [facts.to_dict() for facts in self.transfer_facts],
        }


def own_transfer_intent_facts(
    state: GameState,
    *,
    threat_report: OwnedProductionThreatReport | None = None,
) -> OwnTransferIntentReport:
    """Return deterministic own-to-own transfer intent facts for ``state``."""

    if not isinstance(state, GameState):
        raise ValueError("state must be a GameState")
    if threat_report is not None and not isinstance(
        threat_report,
        OwnedProductionThreatReport,
    ):
        raise ValueError("threat_report must be None or OwnedProductionThreatReport")

    if state.player_id is None:
        return OwnTransferIntentReport(
            player_id=None,
            labels=("missing_player_id",),
        )

    effective_threat_report = threat_report or owned_production_threat_facts(state)
    owned_planets = {
        planet.planet_id: planet
        for planet in state.planets
        if planet.owner == state.player_id
    }
    threat_by_planet_id = {
        facts.planet_id: facts for facts in effective_threat_report.planet_facts
    }
    preliminary = tuple(
        transfer
        for fleet in state.fleets
        for transfer in (
            _infer_own_transfer(fleet, owned_planets),
        )
        if transfer is not None
    )
    repeated_counts: dict[tuple[int, int], int] = {}
    for fleet, source, target, _eta_ticks, _distance_to_target in preliminary:
        key = (source.planet_id, target.planet_id)
        repeated_counts[key] = repeated_counts.get(key, 0) + 1

    transfer_facts = tuple(
        _transfer_facts(
            fleet,
            source,
            target,
            eta_ticks,
            distance_to_target,
            repeated_counts[(source.planet_id, target.planet_id)],
            threat_by_planet_id,
        )
        for fleet, source, target, eta_ticks, distance_to_target in preliminary
    )
    labels: list[str] = []
    if transfer_facts:
        labels.append("own_transfer_activity")
    if any(facts.purposeful for facts in transfer_facts):
        labels.append("purposeful_own_transfer")
    if any(facts.potentially_spammy for facts in transfer_facts):
        labels.append("potentially_spammy_own_transfer")
    if any(facts.repeated_source_target_transfer_count > 1 for facts in transfer_facts):
        labels.append("repeated_own_transfer")

    return OwnTransferIntentReport(
        player_id=state.player_id,
        transfer_facts=transfer_facts,
        transfer_count=len(transfer_facts),
        purposeful_count=sum(1 for facts in transfer_facts if facts.purposeful),
        potentially_spammy_count=sum(
            1 for facts in transfer_facts if facts.potentially_spammy
        ),
        repeated_transfer_group_count=len(
            tuple(count for count in repeated_counts.values() if count > 1)
        ),
        labels=tuple(labels),
    )


def _infer_own_transfer(
    fleet: Fleet,
    owned_planets: dict[int, Planet],
) -> tuple[Fleet, Planet, Planet, int, float] | None:
    source = owned_planets.get(fleet.from_planet_id)
    if source is None or fleet.owner != source.owner:
        return None

    inferred_targets = tuple(
        sorted(
            (
                (eta_ticks, distance_to_target, planet)
                for planet in owned_planets.values()
                if planet.planet_id != source.planet_id
                for eta_ticks in (_fleet_eta_to_planet(fleet, planet),)
                if eta_ticks is not None
                for distance_to_target in (
                    round(distance(fleet.position, planet.position), 6),
                )
            ),
            key=lambda item: (item[0], item[1], item[2].planet_id),
        )
    )
    if not inferred_targets:
        return None

    eta_ticks, distance_to_target, target = inferred_targets[0]
    return fleet, source, target, eta_ticks, distance_to_target


def _transfer_facts(
    fleet: Fleet,
    source: Planet,
    target: Planet,
    eta_ticks: int,
    distance_to_target: float,
    repeated_count: int,
    threat_by_planet_id: dict[int, OwnedPlanetThreatFacts],
) -> OwnTransferFleetFacts:
    source_threat = threat_by_planet_id.get(source.planet_id)
    target_threat = threat_by_planet_id.get(target.planet_id)
    source_under_pressure = (
        source_threat is not None and source_threat.production_under_pressure
    )
    target_under_pressure = (
        target_threat is not None and target_threat.production_under_pressure
    )
    target_at_risk = target_threat is not None and target_threat.at_risk
    labels: list[str] = ["own_to_own_transfer"]
    if target_under_pressure:
        labels.append("reinforces_threatened_owned_production")
    elif target.production > 0 and target.production >= source.production:
        labels.append("consolidates_into_production")
    if repeated_count > 1:
        labels.append("repeated_source_target_transfer")
    if source_under_pressure and not target_under_pressure:
        labels.append("drains_pressured_source")

    purposeful = any(
        label
        in (
            "reinforces_threatened_owned_production",
            "consolidates_into_production",
        )
        for label in labels
    )
    no_defense_purpose = not target_under_pressure and not target_at_risk
    potentially_spammy = no_defense_purpose and (
        repeated_count > 1
        or fleet.ships <= 1
        or (source.production > 0 and target.production <= source.production)
        or source_under_pressure
    )
    if potentially_spammy:
        labels.append("potentially_spammy_own_transfer")
    if no_defense_purpose:
        labels.append("no_visible_defense_purpose")

    return OwnTransferFleetFacts(
        fleet_id=fleet.fleet_id,
        owner=fleet.owner,
        source_planet_id=source.planet_id,
        target_planet_id=target.planet_id,
        ships=fleet.ships,
        eta_ticks=eta_ticks,
        distance_to_target=distance_to_target,
        source_current_ships=source.ships,
        target_current_ships=target.ships,
        source_production=source.production,
        target_production=target.production,
        source_production_bearing=source.production > 0,
        target_production_bearing=target.production > 0,
        source_under_pressure=source_under_pressure,
        target_under_pressure=target_under_pressure,
        target_at_risk=target_at_risk,
        repeated_source_target_transfer_count=repeated_count,
        purposeful=purposeful,
        potentially_spammy=potentially_spammy,
        labels=tuple(labels),
    )


def _fleet_eta_to_planet(fleet: Fleet, planet: Planet) -> int | None:
    speed = fleet_speed(fleet.ships)
    dx = math.cos(fleet.angle)
    dy = math.sin(fleet.angle)
    rel_x = planet.x - fleet.x
    rel_y = planet.y - fleet.y
    along_track = rel_x * dx + rel_y * dy
    if along_track < 0.0:
        return None
    perpendicular_sq = max(0.0, rel_x * rel_x + rel_y * rel_y - along_track * along_track)
    if math.sqrt(perpendicular_sq) > planet.radius:
        return None
    offset_to_circle = math.sqrt(max(0.0, planet.radius * planet.radius - perpendicular_sq))
    distance_to_edge = max(0.0, along_track - offset_to_circle)
    return int(math.ceil(distance_to_edge / speed))


__all__ = (
    "OwnTransferFleetFacts",
    "OwnTransferIntentReport",
    "own_transfer_intent_facts",
)
