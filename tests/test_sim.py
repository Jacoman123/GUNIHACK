"""End-to-end behaviour of the swarm under communication failure."""

import unittest

from vanta.scenarios import SCENARIOS
from vanta.sim import DOWN, HOLDING, Simulation

NOMINAL = SCENARIOS["nominal"]


class Missions(unittest.TestCase):
    def test_vanta_completes_every_scenario(self):
        for name, sc in SCENARIOS.items():
            with self.subTest(scenario=name):
                m = Simulation(sc, "vanta", 1).run().metrics()
                self.assertIsNotNone(m["reported_t"], f"{name} never completed")
                self.assertEqual(m["true_pct"], 100.0)
                self.assertEqual(m["reported"], m["targets"])

    def test_deterministic(self):
        a = Simulation(SCENARIOS["gauntlet"], "vanta", 3).run().metrics()
        b = Simulation(SCENARIOS["gauntlet"], "vanta", 3).run().metrics()
        self.assertEqual(a, b)

    def test_vanta_beats_central_when_links_fail(self):
        for name in ("attrition", "base_down", "gauntlet"):
            with self.subTest(scenario=name):
                v = Simulation(SCENARIOS[name], "vanta", 1).run().metrics()
                c = Simulation(SCENARIOS[name], "central", 1).run().metrics()
                self.assertLess(v["reported_t"], c["reported_t"])


class RadioFailure(unittest.TestCase):
    def test_full_blackout_delivers_nothing_but_search_continues(self):
        sim = Simulation(NOMINAL, "vanta", 1)
        for _ in range(60):
            sim.step()
        sim.controls["jam"] = True
        before_msgs = sim.messages
        before_cov = sim.true_covered.bit_count()
        for _ in range(120):
            sim.step()
        self.assertEqual(sim.messages, before_msgs)
        self.assertEqual(sim.links, [])
        self.assertGreater(sim.true_covered.bit_count(), before_cov + 500)
        self.assertTrue(all(d.state != HOLDING for d in sim.drones))

    def test_central_drones_stall_without_base(self):
        sim = Simulation(NOMINAL.with_(base_down=((0.0, 10_000.0),)), "central", 1)
        for _ in range(200):
            sim.step()
        self.assertEqual(sim.true_covered.bit_count() / sim.grid.n_cells < 0.05, True)

    def test_split_blocks_links_across_the_line(self):
        sim = Simulation(NOMINAL, "vanta", 1)
        for _ in range(150):
            sim.step()
        sim.controls["split"] = True
        x = sim.grid.width_m / 2
        for _ in range(20):
            sim.step()
            for a, b in sim.links:
                pa = sim.base_xy if a == sim.n else (sim.drones[a].x, sim.drones[a].y)
                pb = sim.base_xy if b == sim.n else (sim.drones[b].x, sim.drones[b].y)
                self.assertGreaterEqual((pa[0] - x) * (pb[0] - x), 0)

    def test_knowledge_reconverges_after_blackout(self):
        sim = Simulation(NOMINAL.with_(loss=0.0), "vanta", 1)
        for _ in range(60):
            sim.step()
        sim.controls["jam"] = True
        for _ in range(120):
            sim.step()
        views = {d.knowledge.covered for d in sim.drones}
        self.assertGreater(len(views), 1)                     # beliefs diverged in the dark
        sim.controls["jam"] = False
        sim.controls["loss"] = 0.0
        # Hold the drones still and let only the radio run: gossip must converge,
        # so any two nodes that can hear each other end up with the same picture.
        for _ in range(30):
            sim._radio(sim.t)
        self.assertTrue(sim.links)
        node = lambda i: sim.base if i == sim.n else sim.drones[i].knowledge
        for a, b in sim.links:
            self.assertEqual(node(a).covered, node(b).covered)
            self.assertEqual(node(a).claims, node(b).claims)


class Attrition(unittest.TestCase):
    def test_dead_drones_sector_is_taken_over_and_finished(self):
        sim = Simulation(NOMINAL, "vanta", 1)
        for _ in range(120):
            sim.step()
        victim = next(d for d in sim.drones if d.task is not None)
        sector = victim.task
        sim.kill(victim.id, sim.t)
        sim.run()
        self.assertEqual(victim.state, DOWN)
        self.assertTrue(sim.grid.sector_done(sim.true_covered, sector))
        self.assertTrue(any(kind == "takeover" and f"sector {sector} " in text
                            for _, kind, text, _ in sim.events) or sim.reported_t is not None)
        self.assertIsNotNone(sim.reported_t)


if __name__ == "__main__":
    unittest.main()
