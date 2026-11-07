"""The simulation: drones, a base station, a lossy radio, and ground truth.

One tick is one second. Each tick every flying drone decides (from its own
knowledge only), flies, and searches the cells under it; then the radio
delivers whatever links survive this tick's conditions, and receivers merge.
The simulator alone sees the truth; no agent ever reads it.
"""

from __future__ import annotations

import base64
import math
import random
from collections import deque
from dataclasses import dataclass, field

from .knowledge import Knowledge
from .scenarios import Scenario, active, split_at
from .strategies import Strategy, get_strategy
from .world import Grid

SPEED_MS = 5.0
DT = 1.0

WORKING, RETURNING, HOLDING, LANDED, DOWN = "working", "returning", "holding", "landed", "down"


@dataclass
class Drone:
    id: int
    x: float
    y: float
    knowledge: Knowledge
    state: str = WORKING
    task: int | None = None
    alive: bool = True
    order: list[int] = field(default_factory=list)


class Simulation:
    def __init__(self, scenario: Scenario, strategy: Strategy | str, seed: int | None = None):
        self.sc = scenario
        self.strategy = get_strategy(strategy) if isinstance(strategy, str) else strategy
        self.seed = scenario.seed if seed is None else seed
        self.rng = random.Random(self.seed)
        self.grid = g = Grid()
        self.n = n = scenario.n_drones
        self.base_xy = (40.0, 40.0)
        self.base = Knowledge(n + 1)

        bx, by = self.base_xy
        self.drones = [Drone(i, bx + 12.0 * (i % 5) - 24.0 + 10, by + 12.0 * (i // 5), Knowledge(n + 1))
                       for i in range(n)]

        # Targets (people to find), placed from the seed away from the base.
        lay = random.Random(self.seed * 7919 + 17)
        far = [i for i in range(g.n_cells)
               if math.dist(g.cell_center(i), self.base_xy) > 200.0]
        self.targets = sorted(lay.sample(far, scenario.n_targets))
        self.target_mask = 0
        for c in self.targets:
            self.target_mask |= 1 << c

        self.t = 0.0
        self.true_covered = 0
        self.true_found: dict[int, tuple[float, int]] = {}
        self.events: deque = deque(maxlen=300)
        self.controls = {"jam": False, "split": False, "base_down": False, "loss": None}
        self.links: list[tuple[int, int]] = []
        self.kills = sorted(scenario.kills)
        self.covered_t: float | None = None
        self.reported_t: float | None = None
        self.overlap = 0          # cells searched again only because the drone didn't know
        self.idle_s = 0.0         # drone-seconds alive but not searching while work remained
        self.messages = 0
        self.strategy.setup(self)
        self.log(0.0, "info", f"{self.strategy.label}: {n} drones launch on '{scenario.title}'")

    # ----------------------------------------------------------------- helpers
    def log(self, t: float, kind: str, text: str, drone: int | None = None) -> None:
        self.events.append((round(t), kind, text, drone))

    def jammed(self, t: float) -> bool:
        return self.controls["jam"] or active(self.sc.jam, t)

    def split_x(self, t: float) -> float | None:
        if self.controls["split"]:
            return self.grid.width_m / 2
        return split_at(self.sc.split, t)

    def base_on_air(self, t: float) -> bool:
        return not (self.controls["base_down"] or active(self.sc.base_down, t))

    def loss(self) -> float:
        v = self.controls["loss"]
        return self.sc.loss if v is None else v

    def kill(self, i: int, t: float) -> bool:
        d = self.drones[i]
        if not d.alive:
            return False
        d.alive, d.state = False, DOWN
        where = f"in sector {d.task}" if d.task is not None else ""
        self.log(t, "crash", f"D{i} goes down {where}".rstrip(), i)
        return True

    @property
    def finished(self) -> bool:
        if self.t >= self.sc.duration_s:
            return True
        return self.reported_t is not None and all(
            d.state in (LANDED, DOWN) for d in self.drones)

    # -------------------------------------------------------------------- tick
    def step(self) -> None:
        t = self.t
        while self.kills and self.kills[0][0] <= t:
            _, i = self.kills.pop(0)
            self.kill(i, t)

        for d in self.drones:
            if d.alive:
                self._act(d, t)

        self.base.seen[self.n] = (t, *self.base_xy)
        self.strategy.base_step(self, t)
        self._radio(t)
        self._score(t)
        self.t = t + DT

    def run(self, until_reported: bool = True) -> "Simulation":
        while not self.finished:
            self.step()
            if until_reported and self.reported_t is not None:
                break
        return self

    def _act(self, d: Drone, t: float) -> None:
        g, k = self.grid, d.knowledge
        k.seen[d.id] = (t, d.x, d.y)
        task = self.strategy.choose(self, d, t)

        target = None
        if task is not None:
            d.state = WORKING
            target = self._nearest_unsearched(d, task)
        else:
            if self.strategy.hold(self, d, t):
                d.state = HOLDING
            elif math.dist((d.x, d.y), self.base_xy) < 1.0:
                if d.state != LANDED:
                    self.log(t, "land", f"D{d.id} lands at base", d.id)
                d.state = LANDED
            else:
                d.state = RETURNING
                target = self.base_xy

        if target is not None:
            dx, dy = target[0] - d.x, target[1] - d.y
            dist = math.hypot(dx, dy)
            step = SPEED_MS * DT
            if dist <= step:
                d.x, d.y = target
            else:
                d.x += dx / dist * step
                d.y += dy / dist * step

        if d.state != LANDED:
            self._search(d, task, t)
        if d.state != WORKING and self.true_covered != g.full_mask:
            self.idle_s += DT

    def _nearest_unsearched(self, d: Drone, s: int) -> tuple[float, float]:
        g = self.grid
        left = d.knowledge.covered & g.sector_masks[s] ^ g.sector_masks[s]
        best, best_d = None, math.inf
        for i in g.sector_cells[s]:
            if left >> i & 1:
                cx, cy = g.cell_center(i)
                dd = (cx - d.x) ** 2 + (cy - d.y) ** 2
                if dd < best_d:
                    best, best_d = (cx, cy), dd
        return best if best is not None else g.sector_centers[s]

    def _search(self, d: Drone, task: int | None, t: float) -> None:
        g, k = self.grid, d.knowledge
        fp = g.footprints[g.cell_at(d.x, d.y)]
        if task is not None:
            self.overlap += (fp & g.sector_masks[task] & ~k.covered & self.true_covered).bit_count()
        self.true_covered |= fp
        k.covered |= fp
        hits = fp & self.target_mask
        if hits:
            for cell in self.targets:
                if hits >> cell & 1:
                    if cell not in self.true_found:
                        self.true_found[cell] = (t, d.id)
                        self.log(t, "find", f"D{d.id} finds a survivor", d.id)
                    if cell not in k.found:
                        k.found[cell] = (t, d.id)

    # ------------------------------------------------------------------- radio
    def _radio(self, t: float) -> None:
        self.links = []
        if self.jammed(t):
            return
        sc = self.sc
        split = self.split_x(t)
        base_up = self.base_on_air(t)
        loss = self.loss()
        rng = self.rng

        # Nodes: live drones, then the base (id n).
        nodes = [(d.id, d.x, d.y, d.knowledge) for d in self.drones if d.alive]
        if base_up:
            nodes.append((self.n, *self.base_xy, self.base))
        dark = [any(z.contains(x, y) for z in sc.dead_zones) for _, x, y, _ in nodes]

        deliveries = []
        for a in range(len(nodes)):
            if dark[a]:
                continue
            ia, xa, ya, _ = nodes[a]
            for b in range(a + 1, len(nodes)):
                if dark[b]:
                    continue
                ib, xb, yb, _ = nodes[b]
                with_base = ib == self.n or ia == self.n
                if not self.strategy.peer_radio and not with_base:
                    continue
                reach = sc.base_range_m if with_base else sc.range_m
                if (xa - xb) ** 2 + (ya - yb) ** 2 > reach * reach:
                    continue
                if split is not None and (xa - split) * (xb - split) < 0:
                    continue
                up = False
                # a -> b, and b -> a (a drone without peer radio never listens).
                if rng.random() >= loss and (self.strategy.peer_radio or ib == self.n):
                    deliveries.append((a, b))
                    up = True
                if rng.random() >= loss and self.strategy.peer_radio:
                    deliveries.append((b, a))
                    up = True
                if up:
                    self.links.append((ia, ib))

        snaps: dict[int, Knowledge] = {}
        for src, dst in deliveries:
            if src not in snaps:
                snaps[src] = nodes[src][3].snapshot()
        for src, dst in deliveries:
            nodes[dst][3].merge(snaps[src])
        self.messages += len(deliveries)

    # ----------------------------------------------------------------- scoring
    def _score(self, t: float) -> None:
        full = self.grid.full_mask
        if self.covered_t is None and self.true_covered == full:
            self.covered_t = t
            self.log(t, "goal", f"Every cell searched at {t:.0f}s")
        if (self.reported_t is None and self.base.covered == full
                and len(self.base.found) == len(self.targets)):
            self.reported_t = t
            self.log(t, "goal", f"Base has the full picture at {t:.0f}s: mission complete")

    def metrics(self) -> dict:
        n_cells = self.grid.n_cells
        return {
            "t": self.t,
            "covered_t": self.covered_t,
            "reported_t": self.reported_t,
            "true_pct": 100.0 * self.true_covered.bit_count() / n_cells,
            "base_pct": 100.0 * self.base.covered.bit_count() / n_cells,
            "found": len(self.true_found),
            "reported": len(self.base.found),
            "targets": len(self.targets),
            "overlap_pct": 100.0 * self.overlap / n_cells,
            "idle_min": self.idle_s / 60.0,
            "alive": sum(d.alive for d in self.drones),
            "messages": self.messages,
        }

    # -------------------------------------------------------------- dashboard
    def to_json(self, view: str = "truth") -> dict:
        g = self.grid
        if view == "base":
            layer = self.base.covered
        elif view.isdigit() and int(view) < self.n:
            layer = self.drones[int(view)].knowledge.covered
        else:
            layer = self.true_covered
        t = self.t
        drones = []
        for d in self.drones:
            heard = self.base.heard(d.id)
            drones.append({
                "id": d.id, "x": round(d.x, 1), "y": round(d.y, 1), "state": d.state,
                "task": d.task, "alive": d.alive,
                "known_pct": round(100.0 * d.knowledge.covered.bit_count() / g.n_cells, 1),
                "base_silent_s": None if heard == float("-inf") else round(t - heard),
            })
        return {
            "strategy": self.strategy.name,
            "label": self.strategy.label,
            "metrics": self.metrics(),
            "drones": drones,
            "links": self.links,
            "layer": _b64(layer, g.n_cells),
            "targets": [{"cell": c, "found": c in self.true_found,
                         "reported": c in self.base.found} for c in self.targets],
            "conditions": {
                "jammed": self.jammed(t), "split_x": self.split_x(t),
                "base_down": not self.base_on_air(t), "loss": self.loss(),
            },
            "finished": self.finished,
            "events": list(self.events)[-60:],
        }


def _b64(bits: int, n: int) -> str:
    return base64.b64encode(bits.to_bytes((n + 7) // 8, "little")).decode()
