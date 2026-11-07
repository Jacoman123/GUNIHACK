"""Command line: `python -m vanta serve | run | bench | scenarios`."""

from __future__ import annotations

import argparse
from pathlib import Path

from .scenarios import SCENARIOS, get_scenario
from .strategies import STRATEGIES


def main() -> None:
    p = argparse.ArgumentParser(prog="vanta", description="A drone swarm that keeps searching when the radios go dark.")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("serve", help="live side-by-side dashboard")
    s.add_argument("--port", type=int, default=8000)
    s.add_argument("--host", default="127.0.0.1")

    r = sub.add_parser("run", help="fly one mission and print the result")
    r.add_argument("scenario", nargs="?", default="gauntlet", choices=list(SCENARIOS))
    r.add_argument("--strategy", default="all", choices=["all", *STRATEGIES])
    r.add_argument("--seed", type=int, default=1)

    b = sub.add_parser("bench", help="every strategy on every scenario, many seeds")
    b.add_argument("--seeds", type=int, default=10)
    b.add_argument("--jobs", type=int, default=None)
    b.add_argument("--out", type=Path, default=Path("results/BENCHMARK.md"))

    sub.add_parser("scenarios", help="list scenarios")

    a = p.parse_args()
    if a.cmd == "serve":
        from .server import serve
        serve(a.host, a.port)
    elif a.cmd == "run":
        from .sim import Simulation
        sc = get_scenario(a.scenario)
        print(f"{sc.title}: {sc.description}\n")
        for st in (STRATEGIES if a.strategy == "all" else [a.strategy]):
            m = Simulation(sc, st, a.seed).run().metrics()
            done = "—" if m["reported_t"] is None else f"{m['reported_t'] / 60:.1f} min"
            print(f"{STRATEGIES[st].label:18} mission complete {done:>9} | searched {m['true_pct']:5.1f}% "
                  f"| survivors reported {m['reported']}/{m['targets']} | wasted {m['overlap_pct']:4.1f}% "
                  f"| idle {m['idle_min']:4.0f} drone-min")
    elif a.cmd == "bench":
        from .bench import benchmark
        print(benchmark(a.seeds, a.jobs, a.out))
        print(f"written to {a.out}")
    elif a.cmd == "scenarios":
        for sc in SCENARIOS.values():
            print(f"{sc.name:10} {sc.title}: {sc.description}")


if __name__ == "__main__":
    main()
