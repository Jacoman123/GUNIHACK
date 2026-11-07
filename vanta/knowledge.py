"""What one agent believes about the mission, and how two beliefs merge.

Every field is a join-semilattice (a state-based CRDT): merging is commutative,
associative and idempotent. So beliefs converge whatever the order, delay, loss
or duplication of messages, and a drone that was cut off for minutes catches up
with a single merge the moment it hears anyone again, directly or relayed.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

NEVER = float("-inf")


@dataclass(frozen=True)
class Claim:
    """A drone's time-limited lease on one sector of the search area."""

    sector: int
    owner: int
    epoch: int          # bumped each time someone takes over an expired lease
    claimed_at: float
    lease_until: float

    def key(self) -> tuple:
        # The greatest key wins a merge:
        #  * a higher epoch (a takeover) beats the claim it replaced;
        #  * within an epoch the earliest claim wins, then the lower drone id,
        #    so two drones that grab the same sector at once agree on a winner;
        #  * for the same claim, the longest lease wins (a renewal).
        return (self.epoch, -self.claimed_at, -self.owner, self.lease_until)

    def live(self, now: float) -> bool:
        return self.lease_until > now

    def renewed(self, until: float) -> "Claim":
        return replace(self, lease_until=max(self.lease_until, until))


class Knowledge:
    """One node's view: coverage, sector leases, last sightings, finds."""

    __slots__ = ("covered", "claims", "seen", "found")

    def __init__(self, n_nodes: int):
        self.covered = 0                                  # bitset of searched cells
        self.claims: dict[int, Claim] = {}                # sector -> winning claim
        self.seen = [(NEVER, 0.0, 0.0)] * n_nodes         # node -> (time, x, y), last-writer-wins
        self.found: dict[int, tuple[float, int]] = {}     # target cell -> (time, finder), earliest wins

    def snapshot(self) -> "Knowledge":
        """A copy to put in a radio message. Claims and tuples are immutable."""
        k = Knowledge.__new__(Knowledge)
        k.covered = self.covered
        k.claims = dict(self.claims)
        k.seen = list(self.seen)
        k.found = dict(self.found)
        return k

    def put_claim(self, c: Claim) -> bool:
        cur = self.claims.get(c.sector)
        if cur is None or c.key() > cur.key():
            self.claims[c.sector] = c
            return True
        return False

    def merge(self, other: "Knowledge") -> int:
        """Fold another node's knowledge into this one. Returns cells learnt."""
        before = self.covered
        self.covered |= other.covered
        mine = self.claims
        for s, c in other.claims.items():
            cur = mine.get(s)
            if cur is not c and (cur is None or c.key() > cur.key()):
                mine[s] = c
        seen = self.seen
        for i, v in enumerate(other.seen):
            if v > seen[i]:   # whole-tuple order: latest time, ties broken deterministically
                seen[i] = v
        for cell, v in other.found.items():
            cur = self.found.get(cell)
            if cur is None or v < cur:
                self.found[cell] = v
        return (self.covered & ~before).bit_count()

    def heard(self, node: int) -> float:
        return self.seen[node][0]

    def same_as(self, other: "Knowledge") -> bool:
        return (self.covered == other.covered and self.claims == other.claims
                and self.seen == other.seen and self.found == other.found)
