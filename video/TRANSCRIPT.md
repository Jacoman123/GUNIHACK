# Vanta explainer: voice-over transcript

Length 2:00. Each section is written to fit its slot at a relaxed pace (about 150 words a minute).
Headings mark scene changes. *Italic* lines are on-screen cues for you, not for reading aloud.

---

**0:00 · Title**

This is Vanta: a drone swarm that keeps searching, even when the radios go dark.

**0:06 · Why we built it**

We started out building wildfire drones, and found one weak spot: they all needed a signal. But drones are needed most in valleys, forests and disaster zones, exactly where radio fails. So we started again.

**0:20 · The problem**

Today, most swarms take orders from a base. Lose the link, and drones finish their job, and wait. The search stalls when it matters most.

**0:30 · How Vanta works**

In Vanta, there's no boss. Every drone carries its own copy of the mission, and decides for itself. Drones in range swap notes, so news spreads drone to drone.

**0:42 · Leases, not orders**

Drones claim sectors with short leases. If one crashes or goes quiet, its lease runs out, and another drone finishes its work.

**0:52 · Live comparison** *(real simulation: "The gauntlet", seed 1)*

Same mission, same faults. Vanta on the left, central command on the right.

*0:57: radio blackout.* Radios jammed. Vanta keeps searching. Central command's drones stop, and head home for orders.

*1:01: crash, then base off air at 1:04, ridge split at 1:07.* A crash. The base goes down. A ridge splits the swarm. Vanta keeps going on both sides.

*1:22: Vanta completes.* Vanta finishes after 15.5 minutes.

*1:25: central command completes.* Central command, nearly 9 minutes later.

**1:27 · Why it matters**

That matters. Survivors are found sooner, in the places help struggles to reach, with fewer rescuers at risk. And it saves money: far less idle flight time, and no costly link to keep up.

*On screen: 2.4× faster full search with the base down; 10× less idle flight time in the gauntlet; 70/70 missions completed. All simulated.*

**1:41 · The business**

Vanta is software, so it runs on drones people already own. We'd license it per drone to rescue, wildfire and inspection teams, and to drone makers.

**1:53 · Close**

Vanta. Cut the radios, and the search keeps going.

---

## If a judge asks

* **Are the numbers real?** They're from the simulator: 7 failure scenarios, 10 runs each, Vanta against a fair central-command baseline. Vanta finished all 70 and had the faster median time in 7 of 7 scenarios. On clear skies the two are within a minute.
* **What's not modelled?** Wind, obstacles and battery limits. Real use needs hardware trials and aviation approval.
* **Why can't central command just add relays?** It can, but relays cost money and still fail. Vanta treats losing contact as normal, so cheap short-range radios are enough.
