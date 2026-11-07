"""Mission scenarios: the same search job under different communication failures."""

from __future__ import annotations

from dataclasses import dataclass, replace

from .world import Rect

Window = tuple[float, float]


@dataclass(frozen=True)
class Scenario:
    name: str
    title: str
    description: str
    n_drones: int = 10
    n_targets: int = 8
    duration_s: float = 2400.0
    loss: float = 0.05                         # chance any single message is lost
    range_m: float = 320.0                     # drone-to-drone radio range
    base_range_m: float = 700.0                # base station mast reaches further
    jam: tuple[Window, ...] = ()               # whole-swarm radio blackout
    split: tuple[tuple[float, float, float], ...] = ()   # (t0, t1, x): no link crosses x
    base_down: tuple[Window, ...] = ()         # base station off the air
    dead_zones: tuple[Rect, ...] = ()          # radio shadows (valleys): no link in or out
    kills: tuple[tuple[float, int], ...] = ()  # (t, drone): drone crashes
    seed: int = 1

    def with_(self, **kw) -> "Scenario":
        return replace(self, **kw)


VALLEYS = (Rect(420, 260, 620, 520), Rect(900, 600, 1180, 820))

SCENARIOS: dict[str, Scenario] = {s.name: s for s in [
    Scenario(
        "nominal", "Clear skies",
        "No faults beyond 5% message loss. The baseline every strategy should ace.",
    ),
    Scenario(
        "blackout", "Total blackout",
        "Every radio in the area is jammed for 3 minutes, starting 2 minutes in.",
        jam=((120.0, 300.0),),
    ),
    Scenario(
        "split", "Ridge split",
        "A ridge cuts the swarm in two for 5 minutes: no link crosses the middle of the map.",
        split=((90.0, 390.0, 640.0),),
    ),
    Scenario(
        "valleys", "Radio shadows",
        "Two valleys where radios don't work, and 30% of messages lost everywhere.",
        loss=0.30, dead_zones=VALLEYS,
    ),
    Scenario(
        "attrition", "Attrition under split",
        "The swarm is split for 5 minutes and 3 drones crash on the far side, mid-sector.",
        split=((90.0, 390.0, 640.0),),
        kills=((200.0, 7), (240.0, 8), (280.0, 9)),
    ),
    Scenario(
        "base_down", "Lost base station",
        "The base station goes off the air 1 minute in and stays down for 15 minutes.",
        base_down=((60.0, 960.0),),
    ),
    Scenario(
        "gauntlet", "The gauntlet",
        "Everything at once: 25% loss, radio shadows, a 2-minute blackout, a 4-minute split, "
        "the base down for 4 minutes, and 2 crashes.",
        loss=0.25, dead_zones=VALLEYS,
        jam=((100.0, 220.0),),
        split=((300.0, 540.0, 640.0),),
        base_down=((240.0, 480.0),),
        kills=((180.0, 3), (360.0, 8)),
    ),
]}


def get_scenario(name: str) -> Scenario:
    try:
        return SCENARIOS[name]
    except KeyError:
        raise SystemExit(f"unknown scenario {name!r}; choose from {', '.join(SCENARIOS)}") from None


def active(windows, t: float) -> bool:
    return any(a <= t < b for a, b in windows)


def split_at(splits, t: float) -> float | None:
    for a, b, x in splits:
        if a <= t < b:
            return x
    return None

