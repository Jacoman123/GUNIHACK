"""The shared-knowledge merge must be a join: order, repeats and grouping don't matter."""

import itertools
import random
import unittest

from vanta.knowledge import Claim, Knowledge


def random_knowledge(rng: random.Random, n_nodes=4, n_sectors=6) -> Knowledge:
    k = Knowledge(n_nodes)
    k.covered = rng.getrandbits(64)
    for s in range(n_sectors):
        if rng.random() < 0.7:
            k.claims[s] = Claim(s, rng.randrange(n_nodes), rng.randrange(3),
                                float(rng.randrange(5)), float(rng.randrange(10, 40)))
    k.seen = [(float(rng.randrange(50)), rng.random(), rng.random()) for _ in range(n_nodes)]
    for _ in range(3):
        k.found[rng.randrange(20)] = (float(rng.randrange(30)), rng.randrange(n_nodes))
    return k


def merged(*ks: Knowledge) -> Knowledge:
    out = ks[0].snapshot()
    for k in ks[1:]:
        out.merge(k)
    return out


class MergeLaws(unittest.TestCase):
    def test_commutative_associative_idempotent(self):
        rng = random.Random(0)
        for _ in range(300):
            a, b, c = (random_knowledge(rng) for _ in range(3))
            self.assertTrue(merged(a, b).same_as(merged(b, a)))
            self.assertTrue(merged(merged(a, b), c).same_as(merged(a, merged(b, c))))
            self.assertTrue(merged(a, a).same_as(a))

    def test_any_delivery_order_converges(self):
        rng = random.Random(1)
        ks = [random_knowledge(rng) for _ in range(4)]
        results = [merged(*p) for p in itertools.permutations(ks)]
        for r in results[1:]:
            self.assertTrue(r.same_as(results[0]))

    def test_merge_reports_new_cells(self):
        a, b = Knowledge(2), Knowledge(2)
        a.covered, b.covered = 0b0011, 0b0110
        self.assertEqual(a.merge(b), 1)
        self.assertEqual(a.covered, 0b0111)


class ClaimRules(unittest.TestCase):
    def test_simultaneous_claims_agree_on_lower_id(self):
        a, b = Claim(5, 3, 0, 10.0, 30.0), Claim(5, 1, 0, 10.0, 30.0)
        self.assertGreater(b.key(), a.key())

    def test_earlier_claim_wins(self):
        early, late = Claim(5, 7, 0, 9.0, 29.0), Claim(5, 1, 0, 10.0, 30.0)
        self.assertGreater(early.key(), late.key())

    def test_takeover_beats_original_even_if_original_renews(self):
        original = Claim(5, 2, 0, 0.0, 20.0)
        takeover = Claim(5, 4, 1, 60.0, 80.0)
        renewed_late = original.renewed(500.0)   # owner was cut off, kept renewing locally
        k = Knowledge(5)
        k.put_claim(takeover)
        k.put_claim(renewed_late)
        self.assertEqual(k.claims[5].owner, 4)

    def test_renewal_extends_lease(self):
        c = Claim(1, 0, 0, 0.0, 20.0)
        self.assertEqual(c.renewed(50.0).lease_until, 50.0)
        self.assertEqual(c.renewed(10.0).lease_until, 20.0)
        self.assertTrue(c.live(19.0))
        self.assertFalse(c.live(20.0))


if __name__ == "__main__":
    unittest.main()
