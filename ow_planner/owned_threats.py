"""Owned-production threat fact extraction.

V1 Deterministic Leak Fix Cycle 1 exposes pressure facts for already-owned
planets only. It does not generate missions, score options, select actions, run
rollouts, or mutate game state.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from ow_sim.forecast import fleet_speed
from ow_sim.geometry import distance
from ow_sim.state import Fleet, GameState, Planet


DEFAULT_THREAT_HORIZON_TICKS = 80


@dataclass(frozen=True, slots=True)
class IncomingFleetThreatFacts:
    """One fleet projected toward an owned planet."""

    fleet_id: int
    owner: int
    ships: int
    eta_ticks: int
    distance_to_planet: float

    def to_dict(self) -> dict[str, object]:
        return {
            "distance_to_planet": self.distance_to_planet,
            "eta_ticks": self.eta_ticks,
            "fleet_id": self.fleet_id,
            "owner": self.owner,
            "ships": self.ships,
        }


@dataclass(frozen=True, slots=True)
class OwnedPlanetThreatFacts:
    """Threat facts for one currently owned planet."""

    planet_id: int
    owner: int
    current_ships: int
    production: int
    production_bearing: bool
    incoming_enemy_ships: int
    incoming_friendly_ships: int
    earliest_hostile_eta: int | None
    earliest_friendly_eta: int | None
    projected_balance_at_earliest_hostile: int
    production_under_pressure: bool
    likely_flip: bool
    at_risk: bool
    outgoing_friendly_fleet_count: int
    outgoing_friendly_ships: int
    source_drained_by_outgoing: bool
    hostile_fleets: tuple[IncomingFleetThreatFacts, ...] = ()
    friendly_fleets: tuple[IncomingFleetThreatFacts, ...] = ()
    labels: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "at_risk": self.at_risk,
            "current_ships": self.current_ships,
            "earliest_friendly_eta": self.earliest_friendly_eta,
            "earliest_hostile_eta": self.earliest_hostile_eta,
            "friendly_fleets": [fleet.to_dict() for fleet in self.friendly_fleets],
            "hostile_fleets": [fleet.to_dict() for fleet in self.hostile_fleets],
            "incoming_enemy_ships": self.incoming_enemy_ships,
            "incoming_friendly_ships": self.incoming_friendly_ships,
            "labels": list(self.labels),
            "likely_flip": self.likely_flip,
            "outgoing_friendly_fleet_count": self.outgoing_friendly_fleet_count,
            "outgoing_friendly_ships": self.outgoing_friendly_ships,
            "owner": self.owner,
            "planet_id": self.planet_id,
            "production": self.production,
            "production_bearing": self.production_bearing,
            "production_under_pressure": self.production_under_pressure,
            "projected_balance_at_earliest_hostile": (
                self.projected_balance_at_earliest_hostile
            ),
            "source_drained_by_outgoing": self.source_drained_by_outgoing,
        }


@dataclass(frozen=True, slots=True)
class OwnedProductionThreatReport:
    """Aggregate owned-production threat facts for a state."""

    player_id: int | None
    horizon_ticks: int
    planet_facts: tuple[OwnedPlanetThreatFacts, ...] = ()
    production_pressure_count: int = 0
    threatened_planet_count: int = 0
    likely_flip_count: int = 0
    production_under_pressure: int = 0
    production_at_risk: int = 0
    labels: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "horizon_ticks": self.horizon_ticks,
            "labels": list(self.labels),
            "likely_flip_count": self.likely_flip_count,
            "planet_facts": [facts.to_dict() for facts in self.planet_facts],
            "player_id": self.player_id,
            "production_at_risk": self.production_at_risk,
            "production_pressure_count": self.production_pressure_count,
            "production_under_pressure": self.production_under_pressure,
            "threatened_planet_count": self.threatened_planet_count,
        }


def owned_production_threat_facts(
    state: GameState,
    *,
    horizon_ticks: int = DEFAULT_THREAT_HORIZON_TICKS,
) -> OwnedProductionThreatReport:
    """Return deterministic owned-production threat facts for ``state``."""

    if not isinstance(state, GameState):
        raise ValueError("state must be a GameState")
    if (
        isinstance(horizon_ticks, bool)
        or not isinstance(horizon_ticks, int)
        or horizon_ticks < 0
    ):
        raise ValueError("horizon_ticks must be an integer >= 0")

    if state.player_id is None:
        return OwnedProductionThreatReport(
            player_id=None,
            horizon_ticks=horizon_ticks,
            labels=("missing_player_id",),
        )

    planet_facts = tuple(
        _owned_planet_threat_facts(state, planet, horizon_ticks)
        for planet in state.planets
        if planet.owner == state.player_id
    )
    threatened = tuple(facts for facts in planet_facts if facts.at_risk)
    likely_flip = tuple(facts for facts in planet_facts if facts.likely_flip)
    pressured = tuple(facts for facts in planet_facts if facts.production_under_pressure)
    labels: list[str] = []
    if pressured:
        labels.append("owned_production_pressure")
    if threatened:
        labels.append("owned_production_threat")
    if likely_flip:
        labels.append("owned_planet_likely_flip")
    if any(facts.source_drained_by_outgoing for facts in threatened):
        labels.append("threatened_source_drained")

    return OwnedProductionThreatReport(
        player_id=state.player_id,
        horizon_ticks=horizon_ticks,
        planet_facts=planet_facts,
        production_pressure_count=len(pressured),
        threatened_planet_count=len(threatened),
        likely_flip_count=len(likely_flip),
        production_under_pressure=sum(facts.production for facts in pressured),
        production_at_risk=sum(facts.production for facts in threatened),
        labels=tuple(labels),
    )


def _owned_planet_threat_facts(
    state: GameState,
    planet: Planet,
    horizon_ticks: int,
) -> OwnedPlanetThreatFacts:
    hostile_fleets = tuple(
        sorted(
            (
                facts
                for fleet in state.fleets
                if fleet.owner != planet.owner
                for facts in (_incoming_fleet_facts(fleet, planet, horizon_ticks),)
                if facts is not None
            ),
            key=lambda facts: (facts.eta_ticks, facts.fleet_id),
        )
    )
    friendly_fleets = tuple(
        sorted(
            (
                facts
                for fleet in state.fleets
                if fleet.owner == planet.owner
                for facts in (_incoming_fleet_facts(fleet, planet, horizon_ticks),)
                if facts is not None
            ),
            key=lambda facts: (facts.eta_ticks, facts.fleet_id),
        )
    )
    outgoing_fleets = tuple(
        fleet
        for fleet in state.fleets
        if fleet.owner == planet.owner and fleet.from_planet_id == planet.planet_id
    )
    incoming_enemy_ships = sum(fleet.ships for fleet in hostile_fleets)
    incoming_friendly_ships = sum(fleet.ships for fleet in friendly_fleets)
    earliest_hostile_eta = (
        None if not hostile_fleets else min(fleet.eta_ticks for fleet in hostile_fleets)
    )
    earliest_friendly_eta = (
        None
        if not friendly_fleets
        else min(fleet.eta_ticks for fleet in friendly_fleets)
    )
    projected_balance = planet.ships + incoming_friendly_ships - incoming_enemy_ships
    production_bearing = planet.production > 0
    production_under_pressure = incoming_enemy_ships > 0 and production_bearing
    likely_flip = incoming_enemy_ships > 0 and projected_balance < 0
    at_risk = incoming_enemy_ships > 0 and production_bearing and (
        likely_flip or projected_balance <= planet.production
    )
    outgoing_ships = sum(fleet.ships for fleet in outgoing_fleets)
    source_drained = outgoing_ships > 0 and outgoing_ships >= max(1, planet.ships)

    labels: list[str] = []
    if incoming_enemy_ships > 0:
        labels.append("hostile_inbound")
    if production_bearing:
        labels.append("production_bearing")
    if production_under_pressure:
        labels.append("owned_production_pressure")
    if likely_flip:
        labels.append("likely_flip")
    if at_risk:
        labels.append("owned_production_at_risk")
    if source_drained:
        labels.append("source_drained_by_outgoing")

    return OwnedPlanetThreatFacts(
        planet_id=planet.planet_id,
        owner=planet.owner,
        current_ships=planet.ships,
        production=planet.production,
        production_bearing=production_bearing,
        incoming_enemy_ships=incoming_enemy_ships,
        incoming_friendly_ships=incoming_friendly_ships,
        earliest_hostile_eta=earliest_hostile_eta,
        earliest_friendly_eta=earliest_friendly_eta,
        projected_balance_at_earliest_hostile=projected_balance,
        production_under_pressure=production_under_pressure,
        likely_flip=likely_flip,
        at_risk=at_risk,
        outgoing_friendly_fleet_count=len(outgoing_fleets),
        outgoing_friendly_ships=outgoing_ships,
        source_drained_by_outgoing=source_drained,
        hostile_fleets=hostile_fleets,
        friendly_fleets=friendly_fleets,
        labels=tuple(labels),
    )


def _incoming_fleet_facts(
    fleet: Fleet,
    planet: Planet,
    horizon_ticks: int,
) -> IncomingFleetThreatFacts | None:
    eta_ticks = _fleet_eta_to_planet(fleet, planet)
    if eta_ticks is None or eta_ticks > horizon_ticks:
        return None
    return IncomingFleetThreatFacts(
        fleet_id=fleet.fleet_id,
        owner=fleet.owner,
        ships=fleet.ships,
        eta_ticks=eta_ticks,
        distance_to_planet=round(distance(fleet.position, planet.position), 6),
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
    "DEFAULT_THREAT_HORIZON_TICKS",
    "IncomingFleetThreatFacts",
    "OwnedPlanetThreatFacts",
    "OwnedProductionThreatReport",
    "owned_production_threat_facts",
)
