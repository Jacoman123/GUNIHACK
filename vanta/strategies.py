"""How drones decide which sector to search. Three strategies, one interface.

* Vanta: every drone decides for itself from its own knowledge. Sectors are
  held by leases the owner renews while it works; leases spread by gossip. A
  drone that hears nothing keeps working, prefers unclaimed sectors, and only
  takes over a sector whose lease ran out (owner silent: crashed or cut off)
  once nothing unclaimed is left. When contact returns, one merge reconciles
  everything and any double-booked sector goes to a single agreed winner.
* Central: the base station assigns sectors and renews leases for drones it
  can hear (directly or relayed through the mesh). A drone without orders
  hovers and waits, which is what most fielded systems do on link loss.
* Independent: no coordination at all. Each drone works through the sectors
  in its own random order and only reports to base when in range.
"""

from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING

from .knowledge import Claim

if TYPE_CHECKING:
    from .sim import Drone, Simulation

LEASE_S = 20.0
TERRITORY_S = 240.0      # how long a claim marks its owner's territory
TERRITORY_PUSH = 160.0   # metres added per neighbouring sector another drone worked
TERRITORY_PULL = 80.0    # metres taken off per neighbouring sector I worked


def _jitter(drone: int, sector: int) -> float:
    """Deterministic per-(drone, sector) offset so drones launched together
    don't all reach for the same nearest sector."""
    h = (sector * 2654435761 + drone * 40503 + 12345) & 0xFFFFFFFF
    return (h % 1000) / 1000.0 * 120.0


class Strategy:
    name = ""
    label = ""
    peer_radio = True        # drones exchange knowledge with each other

    def setup(self, sim: "Simulation") -> None:
        pass

    def hold(self, sim: "Simulation", d: "Drone", now: float) -> bool:
        """With no work: hover in place (True) or fly home to report (False)."""
        return False

    def choose(self, sim: "Simulation", d: "Drone", now: float) -> int | None:
        raise NotImplementedError

    def base_step(self, sim: "Simulation", now: float) -> None:
        pass


class Vanta(Strategy):
    name = "vanta"
    label = "Vanta"

    def choose(self, sim, d, now):
        k, g = d.knowledge, sim.grid
        if d.task is not None:
            c = k.claims.get(d.task)
            if c is not None and c.owner != d.id:
                sim.log(now, "yield", f"D{d.id} hands sector {d.task} to D{c.owner} (agreed winner)", d.id)
                d.task = None
            elif g.sector_done(k.covered, d.task):
                d.task = None
            else:
                k.claims[d.task] = c.renewed(now + LEASE_S)
                return d.task

        # Territory: sectors next to another drone's recent work are probably
        # where it goes next, so lean away from them (and towards my own).
        # This keeps drones that can't talk from picking the same free sector.
        pull = [0.0] * g.n_sectors
        for c in k.claims.values():
            if now - c.claimed_at > TERRITORY_S:
                continue
            w = -TERRITORY_PULL if c.owner == d.id else TERRITORY_PUSH
            for nb in g.sector_neighbours[c.sector]:
                pull[nb] += w

        best, best_score = None, math.inf
        for s in range(g.n_sectors):
            if g.sector_done(k.covered, s):
                continue
            c = k.claims.get(s)
            if c is None or c.owner == d.id:
                tier = 0.0
            elif c.live(now):
                continue
            else:
                # Owner has gone silent. Take it only when nothing unclaimed is
                # left, and prefer the leases that lapsed longest ago.
                tier = 1e6 - min(now - c.lease_until, 600.0)
            cx, cy = g.sector_centers[s]
            score = tier + math.hypot(d.x - cx, d.y - cy) + _jitter(d.id, s) + pull[s]
            if score < best_score:
                best, best_score = s, score
        if best is None:
            return None

        c = k.claims.get(best)
        if c is None:
            new = Claim(best, d.id, 0, now, now + LEASE_S)
        elif c.owner == d.id:
            new = c.renewed(now + LEASE_S)
        else:
            new = Claim(best, d.id, c.epoch + 1, now, now + LEASE_S)
            sim.log(now, "takeover",
                    f"D{d.id} takes over sector {best} from D{c.owner} "
                    f"(silent {now - c.lease_until + LEASE_S:.0f}s)", d.id)
        k.put_claim(new)
        d.task = best
        return best


class Central(Strategy):
    name = "central"
    label = "Central command"
    RETURN_TO_LINK_S = 30.0

    def hold(self, sim, d, now):
        # Standard lost-link behaviour: hover and wait for orders, and after
        # 30 s without hearing the base, fly back towards it to regain the link.
        if d.knowledge.covered == sim.grid.full_mask:
            return False
        return now - d.knowledge.heard(sim.n) < self.RETURN_TO_LINK_S

    def choose(self, sim, d, now):
        k, g = d.knowledge, sim.grid
        if d.task is not None:
            c = k.claims.get(d.task)
            if c is None or c.owner != d.id or g.sector_done(k.covered, d.task):
                if c is not None and c.owner != d.id:
                    sim.log(now, "yield", f"D{d.id} told sector {d.task} now belongs to D{c.owner}", d.id)
                d.task = None
        if d.task is None:
            # Any orders addressed to me that aren't finished?
            mine = [s for s, c in k.claims.items()
                    if c.owner == d.id and not g.sector_done(k.covered, s)]
            if mine:
                d.task = min(mine, key=lambda s: math.hypot(d.x - g.sector_centers[s][0],
                                                            d.y - g.sector_centers[s][1]))
        return d.task

    def base_step(self, sim, now):
        if not sim.base_on_air(now):
            return
        kb, g = sim.base, sim.grid
        reachable = [i for i in range(sim.n) if now - kb.heard(i) <= LEASE_S]
        for c in list(kb.claims.values()):
            if c.owner in reachable and not g.sector_done(kb.covered, c.sector):
                kb.claims[c.sector] = c.renewed(now + LEASE_S)
        busy = {c.owner for c in kb.claims.values()
                if c.live(now) and not g.sector_done(kb.covered, c.sector)}
        for i in reachable:
            if i in busy:
                continue
            _, x, y = kb.seen[i]
            best, best_d = None, math.inf
            for s in range(g.n_sectors):
                if g.sector_done(kb.covered, s):
                    continue
                c = kb.claims.get(s)
                if c is not None and c.live(now):
                    continue
                cx, cy = g.sector_centers[s]
                dist = math.hypot(x - cx, y - cy)
                if dist < best_d:
                    best, best_d = s, dist
            if best is None:
                break
            c = kb.claims.get(best)
            epoch = 0 if c is None else c.epoch + 1
            if c is not None and c.owner != i:
                sim.log(now, "takeover", f"Base reassigns sector {best} from silent D{c.owner} to D{i}", i)
            kb.put_claim(Claim(best, i, epoch, now, now + LEASE_S))
            busy.add(i)


class Independent(Strategy):
    name = "independent"
    label = "No coordination"
    peer_radio = False

    def setup(self, sim):
        for d in sim.drones:
            order = list(range(sim.grid.n_sectors))
            random.Random(sim.seed * 1000 + d.id).shuffle(order)
            d.order = order

    def choose(self, sim, d, now):
        g, k = sim.grid, d.knowledge
        if d.task is not None and not g.sector_done(k.covered, d.task):
            return d.task
        d.task = next((s for s in d.order if not g.sector_done(k.covered, s)), None)
        return d.task


STRATEGIES: dict[str, Strategy] = {s.name: s for s in (Vanta(), Central(), Independent())}


def get_strategy(name: str) -> Strategy:
    try:
        return STRATEGIES[name]
    except KeyError:
        raise SystemExit(f"unknown strategy {name!r}; choose from {', '.join(STRATEGIES)}") from None
