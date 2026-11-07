# Vanta

**A drone swarm that keeps searching when the radios go dark.**

Built for the GreatUniHack 2026 **Neptune North Challenge**: *design a system where
multiple agents keep working toward a shared goal, even when communication fails.*

Ten drones search a 1.3 km × 1 km area for eight missing people. Partway through,
the radios get jammed, a ridge splits the swarm in two, the base station drops off
the air, and drones crash. Vanta's drones never stop searching, and they never
need anyone to tell them what to do next. When contact comes back, they reconcile
everything they learnt in a single exchange.

Most fielded drone systems do the opposite: when the link drops, they hover and
wait for orders, then fly home. Vanta runs the same mission side by side with that
kind of **central command** system, so you can watch the difference live.

## Run it

Needs Python 3.10+ and nothing else (standard library only).

```bash
python -m vanta serve
```

Open http://localhost:8000. Vanta is on the left and the rival on the right, flying
the same mission with the same seed. Use the **Break things** bar to jam the
radios, split the swarm, cut the base station, crash drones, or turn up message
loss. Both missions get exactly the same fault at the same moment.

Other commands:

```bash
python -m vanta run gauntlet          # one mission, all strategies, printed
python -m vanta bench --seeds 10      # full benchmark -> results/BENCHMARK.md
python -m vanta scenarios             # list the scenarios
python -m unittest discover -s tests -t .
```

## How it keeps working without contact

Each drone carries its **own copy of the mission picture** and makes every
decision from that copy alone. Nothing in flight depends on the base station or
on any other drone being reachable.

The picture has four parts. Each one merges in a way that can't go wrong, whatever
order messages arrive in, however late, and however many are lost or repeated. (In
computer science this is a *state-based CRDT*: the merge is commutative,
associative and idempotent, and the tests check this on random inputs.)

| Part | What it records | How two copies merge |
|---|---|---|
| Searched cells | 3072-bit map of the area | union (bitwise OR) |
| Sector leases | who is searching which 160 m sector, and until when | the agreed winner (see below) |
| Last sightings | when and where each drone was last heard of | the latest one |
| Survivors | where each person was found, by whom | the earliest find |

**Gossip, not orders.** Every second, each drone broadcasts its picture to whoever
is in radio range, and merges whatever it hears. Information hops drone to drone,
so a drone out of the base's range still reaches it through the others.

**Leases, not assignments.** A drone claims a sector with a 20-second lease and
keeps renewing it while it works. Leases travel with the gossip.

* **Cut off?** Keep searching your sector. When it's done, pick the nearest
  *unclaimed* sector. A territory rule steers you away from sectors next to
  another drone's recent work, so drones that can't talk rarely pick the same one.
* **Someone went silent?** Their lease runs out. Once nothing unclaimed is left,
  take over their sector, oldest silence first. A crashed drone's sector still
  gets finished, and nobody had to declare it dead.
* **Two drones grabbed the same sector?** When their pictures meet, both apply the
  same rule: a takeover beats the claim it replaced, otherwise the earlier claim
  wins, then the lower drone id. Both reach the same answer independently, the
  loser moves on, and its partial search is kept.
* **Back in contact?** One merge. No resync protocol and no leader election.
* **Nothing left to do?** Fly home. This also carries the picture back to base
  (data muling), which is how the base gets the full story even after it was off
  the air.

## Results

From [`results/BENCHMARK.md`](results/BENCHMARK.md): 10 seeds per row. Times are
medians. *Mission complete* means the base station knows every cell is searched
and where every survivor is.

| Scenario | Vanta | Central command | No coordination |
|---|---|---|---|
| Clear skies | **13.5 min** | 14.2 min | 3/10 finish in 40 min |
| Total blackout (3 min) | **15.3 min** | 17.1 min | 3/10 |
| Ridge split (5 min) | **14.0 min** | 14.2 min | 3/10 |
| Radio shadows + 30% loss | **13.8 min** | 17.5 min | 3/10 |
| Split + 3 crashes | **17.7 min** | 19.5 min | 0/10 |
| Base station down 15 min | **16.0 min**\* | 28.7 min | 3/10 |
| The gauntlet (everything) | **16.1 min** | 25.8 min | 0/10 |

\* The base is off the air until minute 16, so 16.0 is as early as anyone can
report. Vanta's drones had already **searched every cell by minute 11.8**. Central
command's drones finished searching at 28.7 min.

Vanta completed **every scenario on every seed**. The price of working without
contact is some double searching (7–9% of the area in the blackout and the
gauntlet, against 1–3% for central command). That's the trade the challenge asks
for: spend a little extra effort and never stall.

## Layout

```
vanta/
  knowledge.py   the shared mission picture and its merge (the core idea)
  strategies.py  Vanta, Central command, No coordination
  sim.py         drones, base station, lossy radio, ground truth, metrics
  scenarios.py   the seven fault scenarios
  world.py       grid, sectors, sensor footprint
  bench.py       benchmark -> results/BENCHMARK.md
  server.py      dashboard backend (stdlib http.server)
  static/        dashboard front end (plain JS + canvas)
tests/           merge laws, blackout, split, reconvergence, crash takeover
```

## A 60-second demo

1. Start on **Clear skies** against **Central command**. Both swarms spread out and search.
2. Press **Jam all radios**. The links vanish. Vanta's drones carry on searching
   their sectors and then move to new ones. Central command's drones finish their
   current sector and stop, then fly back toward base to look for orders.
3. Press **Crash a drone** twice. The dead drones' leases run out after 20 s of
   silence. Once the unclaimed sectors are used up, Vanta's drones take over the
   half-searched sectors (look for "takes over" in the log), and the mission still
   reaches 100%.
4. Switch **Map shows** to *What drone D3 believes*. Each drone's picture differs
   from the truth while it's in the dark.
5. Release the jam. Watch the pictures snap back together on the first exchange,
   and any double-booked sector get settled on its own ("hands sector … to").

## Honest limits

* It is a simulation: point-mass drones, a disc radio model, a downward camera
  that sees a 3 × 3-cell footprint. No wind, obstacles or battery limits.
* Sector choice is greedy, not optimal. The territory rule is a heuristic tuned by
  hand on seeds 1–3.
* Central command here relays orders through the drone mesh, and flies drones back
  toward base after 30 s without the link. That's a fair, reasonably strong
  baseline, not a straw man: on clear skies it is within a minute of Vanta.
