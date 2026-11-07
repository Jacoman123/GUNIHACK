"""Live dashboard: Vanta and a rival strategy fly the same mission side by side,
and you break their radios from the browser. Standard library only."""

from __future__ import annotations

import json
import mimetypes
import random
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .scenarios import SCENARIOS, get_scenario
from .sim import Simulation
from .strategies import STRATEGIES

STATIC = Path(__file__).parent / "static"
TICK_S = 0.05


class Runner:
    """Steps both simulations together in a background thread."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.speed = 10.0        # simulated seconds per real second
        self.paused = False
        self._acc = 0.0
        self.reset("nominal", "central", 1)
        threading.Thread(target=self._loop, daemon=True).start()

    def reset(self, scenario: str, rival: str, seed: int) -> None:
        sc = get_scenario(scenario)
        if rival not in STRATEGIES or rival == "vanta":
            rival = "central"
        self.scenario, self.rival, self.seed = sc, rival, seed
        self.sims = [Simulation(sc, "vanta", seed), Simulation(sc, rival, seed)]
        self._kill_rng = random.Random(seed * 31 + 7)
        self._acc = 0.0

    def _loop(self) -> None:
        while True:
            time.sleep(TICK_S)
            with self.lock:
                if self.paused:
                    continue
                self._acc += TICK_S * self.speed
                while self._acc >= 1.0:
                    self._acc -= 1.0
                    for s in self.sims:
                        if not s.finished:
                            s.step()

    def control(self, action: str, value=None) -> None:
        if action in ("jam", "split", "base_down"):
            for s in self.sims:
                s.controls[action] = bool(value)
                s.log(s.t, "fault", _FAULT_TEXT[action][bool(value)])
        elif action == "loss":
            v = None if value is None else max(0.0, min(1.0, float(value)))
            for s in self.sims:
                s.controls["loss"] = v
        elif action == "kill":
            # Same drone in both missions, for a fair comparison.
            alive = [i for i in range(self.sims[0].n) if all(s.drones[i].alive for s in self.sims)]
            if alive:
                i = self._kill_rng.choice(alive)
                for s in self.sims:
                    s.kill(i, s.t)
        elif action == "pause":
            self.paused = bool(value)
        elif action == "speed":
            self.speed = max(0.5, min(120.0, float(value)))

    def state(self, view: str) -> dict:
        with self.lock:
            g = self.sims[0].grid
            sc = self.scenario
            return {
                "grid": g.to_json(),
                "base": self.sims[0].base_xy,
                "scenario": {"name": sc.name, "title": sc.title, "description": sc.description,
                             "dead_zones": [z.to_json() for z in sc.dead_zones],
                             "range_m": sc.range_m, "base_range_m": sc.base_range_m},
                "seed": self.seed, "rival": self.rival,
                "speed": self.speed, "paused": self.paused,
                "sims": [s.to_json(view) for s in self.sims],
            }


_FAULT_TEXT = {
    "jam": {True: "Operator jams every radio", False: "Radios back on"},
    "split": {True: "Operator splits the swarm down the middle", False: "Split lifted"},
    "base_down": {True: "Operator takes the base station off the air", False: "Base station back on the air"},
}


def make_handler(runner: Runner):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):  # keep the console quiet
            pass

        def _send(self, code: int, body: bytes, ctype: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, obj, code: int = 200) -> None:
            self._send(code, json.dumps(obj).encode(), "application/json")

        def do_GET(self):
            u = urlparse(self.path)
            if u.path == "/api/state":
                view = parse_qs(u.query).get("view", ["truth"])[0]
                return self._json(runner.state(view))
            if u.path == "/api/meta":
                return self._json({
                    "scenarios": [{"name": s.name, "title": s.title, "description": s.description}
                                  for s in SCENARIOS.values()],
                    "rivals": [{"name": s.name, "label": s.label} for s in STRATEGIES.values()
                               if s.name != "vanta"],
                })
            name = "index.html" if u.path in ("/", "") else u.path.lstrip("/")
            f = (STATIC / name).resolve()
            if STATIC.resolve() not in f.parents or not f.is_file():
                return self._send(404, b"not found", "text/plain")
            ctype = mimetypes.guess_type(f.name)[0] or "application/octet-stream"
            return self._send(200, f.read_bytes(), ctype)

        def do_POST(self):
            n = int(self.headers.get("Content-Length") or 0)
            try:
                body = json.loads(self.rfile.read(n) or b"{}")
            except json.JSONDecodeError:
                return self._json({"error": "bad json"}, 400)
            path = urlparse(self.path).path
            with runner.lock:
                if path == "/api/reset":
                    runner.reset(body.get("scenario", "nominal"), body.get("rival", "central"),
                                 int(body.get("seed", 1)))
                elif path == "/api/control":
                    runner.control(body.get("action", ""), body.get("value"))
                else:
                    return self._json({"error": "unknown endpoint"}, 404)
            return self._json({"ok": True})

    return Handler


def serve(host: str = "127.0.0.1", port: int = 8000) -> None:
    runner = Runner()
    httpd = ThreadingHTTPServer((host, port), make_handler(runner))
    print(f"Vanta dashboard on http://{host}:{port}  (Ctrl+C to stop)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
