"""Render the 2-minute Vanta explainer video and its voice-over transcript.

The comparison footage is drawn from real simulation runs (The gauntlet, seed 1),
and the results chart is read from results/BENCHMARK.md, so nothing is faked.

    pip install pillow imageio-ffmpeg
    python tools/make_video.py            # -> video/vanta_explainer.mp4 + video/TRANSCRIPT.md
"""

from __future__ import annotations

import colorsys
import math
import re
import sys
from pathlib import Path

import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from vanta.scenarios import SCENARIOS  # noqa: E402
from vanta.sim import Simulation  # noqa: E402

W, H, FPS = 1280, 720, 30
OUT = ROOT / "video"

BG = (5, 6, 8)
PANEL = (12, 14, 18)
LINE = (28, 32, 41)
TEXT = (230, 233, 239)
MUTED = (138, 147, 163)
ACCENT = (94, 234, 212)
WARN = (251, 191, 36)
BAD = (248, 113, 113)
GOOD = (74, 222, 128)
VIOLET = (196, 181, 253)

FONT_DIR = Path("C:/Windows/Fonts")


def font(size: int, weight: str = "regular") -> ImageFont.FreeTypeFont:
    name = {"regular": "segoeui.ttf", "bold": "segoeuib.ttf", "light": "segoeuisl.ttf"}[weight]
    for p in (FONT_DIR / name, Path(name)):
        try:
            return ImageFont.truetype(str(p), size)
        except OSError:
            pass
    return ImageFont.load_default(size)


F = {k: font(*k) for k in [(64, "bold"), (40, "bold"), (30, "bold"), (26, "regular"), (22, "regular"),
                           (20, "bold"), (18, "regular"), (16, "bold"), (15, "regular"), (13, "bold"),
                           (28, "light"), (22, "light")]}

DRONE = [tuple(int(c * 255) for c in colorsys.hls_to_rgb(((i * 137.5 + 200) % 360) / 360, 0.66, 0.85))
         for i in range(16)]


def mix(a, b, t):
    t = max(0.0, min(1.0, t))
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def fade(c, a):
    return mix(BG, c, a)


def ease(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def appear(t, start, dur=0.5):
    return ease((t - start) / dur)


def ctext(d, xy, s, f, fill, anchor="mm"):
    d.text(xy, s, font=f, fill=fill, anchor=anchor)


def wrap(d, x, y, text, f, fill, width, gap=8):
    words, line, lines = text.split(), "", []
    for w_ in words:
        trial = (line + " " + w_).strip()
        if d.textlength(trial, font=f) > width and line:
            lines.append(line)
            line = w_
        else:
            line = trial
    lines.append(line)
    for ln in lines:
        d.text((x, y), ln, font=f, fill=fill)
        y += f.size + gap
    return y


def drone_dot(d, x, y, color, r=9, label=None, ring=None, a=1.0):
    if ring:
        d.ellipse([x - r - 6, y - r - 6, x + r + 6, y + r + 6], outline=fade(ring, a), width=3)
    d.ellipse([x - r, y - r, x + r, y + r], fill=fade(color, a))
    if label:
        d.text((x + r + 4, y - r - 10), label, font=F[(16, "bold")], fill=fade(TEXT, a))


def cross(d, x, y, r, color, w=3):
    d.line([x - r, y - r, x + r, y + r], fill=color, width=w)
    d.line([x - r, y + r, x + r, y - r], fill=color, width=w)


def header(d, kicker, title, a=1.0):
    d.text((80, 64), kicker.upper(), font=F[(16, "bold")], fill=fade(ACCENT, a))
    d.text((80, 88), title, font=F[(40, "bold")], fill=fade(TEXT, a))


# ---------------------------------------------------------------- scenes
def scene_title(img, d, t, dur):
    a = appear(t, 0.2, 0.8) * (1 - appear(t, dur - 0.5, 0.5))
    cx, cy = W // 2, 300
    r = 46
    d.ellipse([cx - r - 6, cy - 170 - r - 6, cx + r + 6, cy - 170 + r + 6], outline=fade(ACCENT, a), width=4)
    d.ellipse([cx - r, cy - 170 - r, cx + r, cy - 170 + r], fill=(0, 0, 0))
    ctext(d, (cx, cy - 20), "V A N T A", F[(64, "bold")], fade(TEXT, a))
    ctext(d, (cx, cy + 50), "The search keeps going when the radios go dark.", F[(28, "light")], fade(MUTED, a))
    b = appear(t, 2.0, 0.8) * (1 - appear(t, dur - 0.5, 0.5))
    ctext(d, (cx, cy + 150), "GreatUniHack 2026  ·  Neptune North Challenge", F[(20, "bold")], fade(ACCENT, b))
    ctext(d, (cx, cy + 184), "Multiple agents, one shared goal, even when communication fails.",
          F[(18, "regular")], fade(MUTED, b))


def scene_problem(img, d, t, dur):
    a = appear(t, 0, 0.5) * (1 - appear(t, dur - 0.4, 0.4))
    header(d, "The usual way", "Central command: drones wait for orders", a)
    bx, by = 330, 420
    pts = [(170, 300), (520, 290), (150, 560), (540, 560)]
    lost = appear(t, 5.5, 0.6)
    for i, (x, y) in enumerate(pts):
        col = mix(ACCENT, BAD, lost)
        # dashed order line
        n = 14
        for k in range(n):
            if k % 2:
                continue
            x0 = bx + (x - bx) * k / n
            y0 = by + (y - by) * k / n
            x1 = bx + (x - bx) * (k + 1) / n
            y1 = by + (y - by) * (k + 1) / n
            d.line([x0, y0, x1, y1], fill=fade(mix(col, BG, 0.3 * lost), a * (1 - 0.6 * lost)), width=3)
        if lost > 0.5:
            mx, my = (bx + x) / 2, (by + y) / 2
            cross(d, mx, my, 10, fade(BAD, a * lost))
        ring = WARN if lost > 0.6 else None
        drone_dot(d, x, y, DRONE[i], 11, f"D{i}", ring=ring, a=a)
        if lost > 0.6 and int(t * 2) % 2 == 0:
            d.text((x - 30, y + 20), "waiting…", font=F[(15, "regular")], fill=fade(WARN, a))
    d.rectangle([bx - 22, by - 22, bx + 22, by + 22], fill=fade(ACCENT, a))
    ctext(d, (bx, by + 44), "BASE", F[(16, "bold")], fade(ACCENT, a))

    x0 = 720
    steps = [
        (0.8, ACCENT, "The base decides who searches where."),
        (2.6, ACCENT, "Orders go out by radio. Drones obey."),
        (5.5, BAD, "Then the link drops: a ridge, jamming, a crashed relay."),
        (8.0, WARN, "Drones finish their job, then hover or fly home to find the signal."),
        (10.5, MUTED, "The search stalls exactly when it matters most."),
    ]
    y = 250
    for st, col, s in steps:
        b = appear(t, st, 0.5) * a
        if b > 0:
            d.ellipse([x0, y + 10, x0 + 10, y + 20], fill=fade(col, b))
            y = wrap(d, x0 + 26, y, s, F[(22, "regular")], fade(TEXT, b), 470) + 18
        else:
            y += 70


def mini_grid(d, x, y, cells, cols=6, rows=4, s=22, color=ACCENT, a=1.0, outline=LINE):
    for r in range(rows):
        for c in range(cols):
            on = (r * cols + c) in cells
            fill = fade(mix(PANEL, color, 0.55), a) if on else fade(PANEL, a)
            d.rectangle([x + c * s, y + r * s, x + c * s + s - 3, y + r * s + s - 3], fill=fill,
                        outline=fade(outline, a))


def scene_notebook(img, d, t, dur):
    a = appear(t, 0, 0.5) * (1 - appear(t, dur - 0.4, 0.4))
    header(d, "The Vanta way", "Every drone carries its own copy of the mission", a)
    A = {0, 1, 2, 6, 7, 8, 12}
    B = {4, 5, 10, 11, 17, 22, 23}
    C = {14, 15, 19, 20, 21}
    merge1 = appear(t, 6.0, 0.6)   # D0 and D1 in range
    merge2 = appear(t, 8.5, 0.6)   # D1 and D2 in range
    k0 = A | (B if merge1 > 0.5 else set()) | ((C if merge2 > 0.5 else set()) if merge1 > 0.5 else set())
    k1 = B | (A if merge1 > 0.5 else set()) | (C if merge2 > 0.5 else set())
    k2 = C | ((A | B) if merge2 > 0.5 else set())
    if merge2 > 0.5:
        k0 = k0 | C  # D1 relays on the next exchange
    xs = [130, 520, 910]
    for i, (x, kn) in enumerate(zip(xs, [k0, k1, k2])):
        b = appear(t, 0.6 + i * 0.5, 0.5) * a
        drone_dot(d, x + 66, 250, DRONE[i], 13, f"D{i}", a=b)
        d.text((x, 290), f"D{i}'s notebook", font=F[(16, "bold")], fill=fade(MUTED, b))
        mini_grid(d, x, 318, kn, a=b, color=DRONE[i] if not merge1 else ACCENT)
        d.text((x, 420), f"{len(kn)} of 24 searched", font=F[(15, "regular")], fill=fade(MUTED, b))
    for (x1, x2, m) in ((xs[0] + 140, xs[1] - 10, merge1), (xs[1] + 140, xs[2] - 10, merge2)):
        if m > 0:
            col = fade(ACCENT, m * a)
            d.line([x1, 386, x2, 386], fill=col, width=3)
            d.polygon([(x2, 386), (x2 - 12, 379), (x2 - 12, 393)], fill=col)
            d.polygon([(x1, 386), (x1 + 12, 379), (x1 + 12, 393)], fill=col)
            ctext(d, ((x1 + x2) / 2, 370), "in range: swap notes", F[(15, "regular")], col)
    items = [("Searched cells", "ticked by anyone stays ticked"),
             ("Sector leases", "who is searching where, until when"),
             ("Last sightings", "where each drone was last heard"),
             ("Survivors", "where each person was found")]
    for i, (k, v) in enumerate(items):
        b = appear(t, 2.0 + i * 0.6, 0.5) * a
        x = 130 + i * 265
        d.text((x, 500), k, font=F[(20, "bold")], fill=fade(TEXT, b))
        wrap(d, x, 530, v, F[(18, "regular")], fade(MUTED, b), 235, 4)
    b = appear(t, 9.5, 0.6) * a
    ctext(d, (W // 2, 640), "No boss. Each drone decides from its own notebook.", F[(22, "light")], fade(ACCENT, b))


def scene_leases(img, d, t, dur):
    a = appear(t, 0, 0.5) * (1 - appear(t, dur - 0.4, 0.4))
    header(d, "Leases, not orders", "A silent drone's work gets picked up", a)
    gx, gy, s = 130, 190, 120
    crash = appear(t, 3.0, 0.3)
    take = appear(t, 8.0, 0.4)
    owners = {0: 3, 2: 7, 4: 5}
    for r in range(3):
        for c in range(4):
            i = r * 4 + c
            x, y = gx + c * s, gy + r * s
            own = owners.get(i)
            if take > 0.5 and i == 2:
                own = 5
            elif take > 0.5 and i == 4:
                own = None   # D5 finished its own sector before taking over
            col = DRONE[own] if own is not None else None
            fill = fade(mix(PANEL, col, 0.25), a) if col else fade(PANEL, a)
            d.rectangle([x, y, x + s - 6, y + s - 6], fill=fill, outline=fade(col or LINE, a), width=3 if col else 1)
            if own is not None:
                d.text((x + 10, y + 8), f"D{own}", font=F[(16, "bold")], fill=fade(col, a))
    # D3 working in sector 0, D7 in sector 2, D5 in sector 4 then moves to sector 2
    wob = math.sin(t * 2.2) * 30
    drone_dot(d, gx + 57 + wob, gy + 70, DRONE[3], 10, a=a)
    if crash < 0.5:
        drone_dot(d, gx + 2 * s + 57 - wob, gy + 70, DRONE[7], 10, a=a)
    else:
        cross(d, gx + 2 * s + 57, gy + 70, 12, fade(MUTED, a))
    if take < 0.5:
        p = appear(t, 6.5, 1.5)
        x5 = gx + 57 + p * (2 * s) + (0 if p else wob)
        y5 = gy + s + 70 - p * s
        drone_dot(d, x5, y5, DRONE[5], 10, a=a)
    else:
        drone_dot(d, gx + 2 * s + 57 + wob * 0.6, gy + 50, DRONE[5], 10, a=a)

    # lease bars
    bx = 680
    def bar(y, label, level, col, note):
        d.text((bx, y), label, font=F[(20, "bold")], fill=fade(TEXT, a))
        d.rectangle([bx, y + 34, bx + 440, y + 50], fill=fade(PANEL, a), outline=fade(LINE, a))
        d.rectangle([bx, y + 34, bx + int(440 * max(0, min(1, level))), y + 50], fill=fade(col, a))
        d.text((bx, y + 58), note, font=F[(18, "regular")], fill=fade(MUTED, a))
    renew = 1 - (t % 1.2) / 1.2 * 0.15
    bar(200, "D3's lease on its sector", renew, DRONE[3], "renewed every second while D3 works")
    if take < 0.5:
        drain = 1 - appear(t, 3.0, 4.5)
        note = "D7 crashed: no renewals, lease running out" if crash > 0.5 else "renewed every second"
        if drain <= 0.02 and crash > 0.5:
            note = "lease expired: sector is up for grabs"
        bar(320, "D7's lease", drain if crash > 0.5 else renew, BAD if crash > 0.5 else DRONE[7], note)
    else:
        bar(320, "D5 takes over D7's sector", renew, DRONE[5], "keeps D7's half-finished search")
    b = appear(t, 9.0, 0.5) * a
    wrap(d, bx, 450, "No one declares a drone dead. Its lease simply runs out, and the nearest free "
         "drone carries on where it left off.", F[(22, "regular")], fade(TEXT, b), 470)


def scene_merge(img, d, t, dur):
    a = appear(t, 0, 0.5) * (1 - appear(t, dur - 0.4, 0.4))
    header(d, "Back in contact", "One exchange puts everyone back in sync", a)
    L = {0, 1, 2, 6, 7, 8, 12, 13, 18}
    R = {4, 5, 10, 11, 16, 17, 22, 23, 15}
    m = appear(t, 3.0, 1.0)
    s = 30
    lx, rx, y = 150, 830, 220
    d.text((lx, y - 34), "Left group, cut off", font=F[(18, "regular")], fill=fade(MUTED, a))
    d.text((rx, y - 34), "Right group, cut off", font=F[(18, "regular")], fill=fade(MUTED, a))
    mini_grid(d, lx, y, L, s=s, color=DRONE[1], a=a * (1 - 0.6 * m))
    mini_grid(d, rx, y, R, s=s, color=DRONE[6], a=a * (1 - 0.6 * m))
    if m > 0:
        cx = (W - 6 * s) // 2
        mini_grid(d, cx, y + 40, L | R, s=s, color=ACCENT, a=a * m)
        d.text((cx, y + 172), "merged picture", font=F[(18, "regular")], fill=fade(ACCENT, a * m))
        for sx in (lx + 6 * s + 10, rx - 10):
            ex = cx - 10 if sx < cx else cx + 6 * s + 10
            d.line([sx, y + 60, ex, y + 100], fill=fade(ACCENT, a * m), width=3)
    rules = [
        "Searched by anyone? Stays searched.",
        "Two drones grabbed the same sector? Both apply the same tie-break, so both agree on the winner.",
        "Messages late, lost or repeated? Same result, in any order.",
    ]
    yy = 450
    for i, r in enumerate(rules):
        b = appear(t, 4.5 + i * 1.3, 0.5) * a
        d.ellipse([150, yy + 10, 160, yy + 20], fill=fade(ACCENT, b))
        yy = wrap(d, 176, yy, r, F[(22, "regular")], fade(TEXT, b), 950) + 12


# ------------------------------------------------------- live comparison
LIVE_SLOW_SIM = 560.0     # the fault-heavy first 9 sim-minutes at 20x, so the faults are readable
LIVE_SLOW_RATE = 20.0
LIVE_FAST_RATE = 170.0    # then fast-forward until both swarms finish


def live_sim_time(tl: float) -> float:
    slow_v = LIVE_SLOW_SIM / LIVE_SLOW_RATE
    if tl <= slow_v:
        return tl * LIVE_SLOW_RATE
    return LIVE_SLOW_SIM + (tl - slow_v) * LIVE_FAST_RATE


def live_video_time(sim_t: float) -> float:
    if sim_t <= LIVE_SLOW_SIM:
        return sim_t / LIVE_SLOW_RATE
    return LIVE_SLOW_SIM / LIVE_SLOW_RATE + (sim_t - LIVE_SLOW_SIM) / LIVE_FAST_RATE


class Live:
    def __init__(self):
        sc = SCENARIOS["gauntlet"]
        self.sc = sc
        self.sims = [Simulation(sc, "vanta", 1), Simulation(sc, "central", 1)]
        self.cov = [None, None]

    def advance_to(self, sim_t):
        for s in self.sims:
            while s.t < sim_t and not s.finished:
                s.step()


def fmt(sec):
    return f"{int(sec // 60)}:{int(sec % 60):02d}"


def draw_map(img, d, sim, x0, y0, mw, mh):
    g = sim.grid
    k = min(mw / g.width_m, mh / g.height_m)
    X = lambda x: x0 + x * k  # noqa: E731
    Y = lambda y: y0 + y * k  # noqa: E731
    bits = sim.true_covered
    raw = bytearray()
    for i in range(g.n_cells):
        raw += bytes((32, 120, 110) if bits >> i & 1 else (10, 12, 16))
    layer = Image.frombytes("RGB", (g.cols, g.rows), bytes(raw)).resize((int(g.width_m * k), int(g.height_m * k)), Image.NEAREST)
    img.paste(layer, (int(x0), int(y0)))
    sm = g.sector * g.cell_m
    for x in range(1, g.sx):
        d.line([X(x * sm), Y(0), X(x * sm), Y(g.height_m)], fill=(22, 26, 32))
    for y in range(1, g.sy):
        d.line([X(0), Y(y * sm), X(g.width_m), Y(y * sm)], fill=(22, 26, 32))
    for z in sim.sc.dead_zones:
        d.rectangle([X(z.x0), Y(z.y0), X(z.x1), Y(z.y1)], outline=(80, 84, 98), width=1)
        for off in range(0, int((z.x1 - z.x0) + (z.y1 - z.y0)), 16):
            xa, ya = z.x0 + off, z.y0
            xb, yb = z.x0 + off - (z.y1 - z.y0), z.y1
            # clip the hatch to the rectangle
            if xa > z.x1:
                ya += xa - z.x1
                xa = z.x1
            if xb < z.x0:
                yb -= z.x0 - xb
                xb = z.x0
            d.line([X(xa), Y(ya), X(xb), Y(yb)], fill=(52, 56, 68))
    for dr in sim.drones:
        if dr.alive and dr.task is not None:
            sx, sy = (dr.task % g.sx) * sm, (dr.task // g.sx) * sm
            d.rectangle([X(sx) + 1, Y(sy) + 1, X(min(sx + sm, g.width_m)) - 1, Y(min(sy + sm, g.height_m)) - 1],
                        outline=DRONE[dr.id], width=2)
    for c in sim.targets:
        cx, cy = g.cell_center(c)
        if c in sim.true_found:
            col = GOOD if c in sim.base.found else (40, 110, 70)
            d.ellipse([X(cx) - 5, Y(cy) - 5, X(cx) + 5, Y(cy) + 5], fill=col)
        else:
            d.ellipse([X(cx) - 5, Y(cy) - 5, X(cx) + 5, Y(cy) + 5], outline=(110, 110, 120))
    bx, by = sim.base_xy
    pos = lambda i: sim.base_xy if i == sim.n else (sim.drones[i].x, sim.drones[i].y)  # noqa: E731
    for a_, b_ in sim.links:
        (x1, y1), (x2, y2) = pos(a_), pos(b_)
        base_link = sim.n in (a_, b_)
        d.line([X(x1), Y(y1), X(x2), Y(y2)], fill=(60, 140, 130) if base_link else (70, 74, 84), width=1)
    base_down = not sim.base_on_air(sim.t)
    d.rectangle([X(bx) - 7, Y(by) - 7, X(bx) + 7, Y(by) + 7], fill=(58, 63, 75) if base_down else ACCENT)
    if base_down:
        cross(d, X(bx), Y(by), 8, BAD, 2)
    split = sim.split_x(sim.t)
    if split is not None:
        for yy in range(0, int(g.height_m), 40):
            d.line([X(split), Y(yy), X(split), Y(min(yy + 24, g.height_m))], fill=BAD, width=3)
    for dr in sim.drones:
        x, y = X(dr.x), Y(dr.y)
        if not dr.alive:
            cross(d, x, y, 6, (110, 114, 128), 2)
            continue
        if dr.state == "holding":
            d.ellipse([x - 11, y - 11, x + 11, y + 11], outline=WARN, width=2)
        elif dr.state == "returning" and sim.true_covered != g.full_mask:
            d.ellipse([x - 9, y - 9, x + 9, y + 9], outline=WARN, width=2)
        d.ellipse([x - 5, y - 5, x + 5, y + 5], fill=DRONE[dr.id])
    if sim.jammed(sim.t):
        overlay = Image.new("RGB", (int(g.width_m * k), int(g.height_m * k)), (120, 20, 20))
        region = img.crop((int(x0), int(y0), int(x0) + overlay.width, int(y0) + overlay.height))
        img.paste(Image.blend(region, overlay, 0.12), (int(x0), int(y0)))


def scene_live(img, d, t, dur, live: Live):
    sim_t = live_sim_time(t)
    live.advance_to(sim_t)
    a = appear(t, 0, 0.5)
    d.text((40, 22), "SAME MISSION · SAME FAULTS · SAME MOMENTS", font=F[(16, "bold")], fill=fade(ACCENT, a))
    sim0 = live.sims[0]
    ct = min(sim_t, max(s.t for s in live.sims))
    rate = f"{LIVE_SLOW_RATE:.0f}×" if sim_t <= LIVE_SLOW_SIM else f"{LIVE_FAST_RATE:.0f}×"
    d.text((40, 44), f"The gauntlet  ·  mission clock {fmt(ct)}  ·  {rate} speed", font=F[(26, "regular")], fill=fade(TEXT, a))

    # fault chips
    chips = []
    if sim0.jammed(ct):
        chips.append("RADIO BLACKOUT")
    if not sim0.base_on_air(ct):
        chips.append("BASE OFF AIR")
    if sim0.split_x(ct) is not None:
        chips.append("RIDGE SPLIT")
    if any(abs(ct - kt) < 25 for kt, _ in live.sc.kills):
        chips.append("DRONE CRASH")
    chips.append("25% MESSAGES LOST")
    x = W - 40
    for c in reversed(chips):
        tw = d.textlength(c, font=F[(13, "bold")]) + 20
        red = c != "25% MESSAGES LOST"
        d.rounded_rectangle([x - tw, 30, x, 56], radius=6, fill=(127, 29, 29) if red else (40, 44, 54))
        d.text((x - tw + 10, 36), c, font=F[(13, "bold")], fill=(254, 202, 202) if red else MUTED)
        x -= tw + 8

    mw, mh = 592, 444
    for i, s in enumerate(live.sims):
        x0 = 40 + i * (mw + 16)
        y0 = 120
        name = "Vanta" if i == 0 else "Central command"
        d.text((x0, 84), name, font=F[(22, "regular")] if i else F[(20, "bold")], fill=ACCENT if i == 0 else TEXT)
        m = s.metrics()
        if m["reported_t"] is not None:
            pill, col = f"MISSION COMPLETE · {fmt(m['reported_t'])}", GOOD
        else:
            waiting = sum(dr.state in ("holding",) or (dr.state == "returning" and s.true_covered != s.grid.full_mask)
                          for dr in s.drones)
            if i == 1 and waiting:
                pill, col = f"{waiting} DRONES NOT SEARCHING", WARN
            else:
                pill, col = "SEARCHING", MUTED
        tw = d.textlength(pill, font=F[(13, "bold")]) + 20
        d.rounded_rectangle([x0 + mw - tw, 84, x0 + mw, 108], radius=12, outline=col, width=1)
        d.text((x0 + mw - tw + 10, 89), pill, font=F[(13, "bold")], fill=col)
        d.rectangle([x0 - 1, y0 - 1, x0 + mw, y0 + mh], fill=(0, 0, 0))
        draw_map(img, d, s, x0, y0, mw, mh)
        stats = [(f"{m['true_pct']:.0f}%", "area searched"), (f"{m['base_pct']:.0f}%", "base knows"),
                 (f"{m['reported']}/{m['targets']}", "survivors reported"), (f"{m['alive']}/10", "drones flying")]
        for j, (v, lab) in enumerate(stats):
            sx = x0 + j * (mw // 4)
            d.text((sx, y0 + mh + 14), v, font=F[(30, "bold")], fill=TEXT)
            d.text((sx, y0 + mh + 52), lab, font=F[(15, "regular")], fill=MUTED)
    # timeline
    tx0, tx1, ty = 40, W - 40, 700
    total = live_sim_time(dur)
    d.line([tx0, ty, tx1, ty], fill=LINE, width=4)
    X = lambda s_: tx0 + (tx1 - tx0) * s_ / total  # noqa: E731
    spans = [(live.sc.jam[0][0], live.sc.jam[0][1], 0, BAD, "blackout"),
             (live.sc.base_down[0][0], live.sc.base_down[0][1], -6, WARN, "base off air"),
             (live.sc.split[0][0], live.sc.split[0][1], 6, VIOLET, "ridge split")]
    lx = tx0
    for a_, b_, dy, col, lab in spans:
        d.line([X(a_), ty + dy, X(b_), ty + dy], fill=col, width=4 if dy == 0 else 3)
        d.rectangle([lx, 676, lx + 10, 686], fill=col)
        d.text((lx + 16, 672), lab, font=F[(15, "regular")], fill=MUTED)
        lx += 40 + d.textlength(lab, font=F[(15, "regular")])
    d.text((lx, 672), "· white dot: mission clock", font=F[(15, "regular")], fill=MUTED)
    px = tx0 + (tx1 - tx0) * min(ct, total) / total
    d.ellipse([px - 6, ty - 6, px + 6, ty + 6], fill=TEXT)


# ------------------------------------------------------ benchmark numbers
def read_benchmark():
    """{scenario title: {strategy: {...}}}, parsed from results/BENCHMARK.md."""
    names = {"**Vanta**": "vanta", "Central command": "central", "No coordination": "independent"}
    num = lambda s: float(s.split()[0]) if s[:1].isdigit() else None  # noqa: E731
    rows = {}
    for line in (ROOT / "results" / "BENCHMARK.md").read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != 8 or cells[1] not in names:
            continue
        done, n = (int(x) for x in cells[4].split("/"))
        rows.setdefault(cells[0], {})[names[cells[1]]] = {
            "searched": num(cells[2]), "complete": num(cells[3]), "done": done, "n": n, "idle": num(cells[7])}
    return rows


BENCH = read_benchmark()


def headline_numbers():
    b = BENCH
    base = b["Lost base station"]
    gaunt = b["The gauntlet"]
    return {
        "base_v": base["vanta"]["searched"], "base_c": base["central"]["searched"],
        "base_ratio": base["central"]["searched"] / base["vanta"]["searched"],
        "idle_v": gaunt["vanta"]["idle"], "idle_c": gaunt["central"]["idle"],
        "idle_ratio": gaunt["central"]["idle"] / max(gaunt["vanta"]["idle"], 1.0),
        "done": sum(r["vanta"]["done"] for r in b.values()),
        "runs": sum(r["vanta"]["n"] for r in b.values()),
        "faster": sum(r["vanta"]["complete"] < r["central"]["complete"] for r in b.values()),
        "scenarios": len(b),
    }


NUM = headline_numbers()


# ----------------------------------------------------------- story scene
def _icon(d, kind, cx, cy, a):
    col = fade((150, 158, 175), a)
    if kind == "valley":
        d.polygon([(cx - 70, cy + 30), (cx - 30, cy - 35), (cx + 5, cy + 30)], outline=col, width=3)
        d.polygon([(cx - 5, cy + 30), (cx + 35, cy - 25), (cx + 70, cy + 30)], outline=col, width=3)
    elif kind == "forest":
        for dx in (-45, 0, 45):
            d.polygon([(cx + dx - 20, cy + 15), (cx + dx, cy - 35), (cx + dx + 20, cy + 15)], outline=col, width=3)
            d.line([cx + dx, cy + 15, cx + dx, cy + 32], fill=col, width=3)
    elif kind == "disaster":
        d.line([cx - 25, cy + 32, cx, cy - 35], fill=col, width=3)
        d.line([cx + 25, cy + 32, cx, cy - 35], fill=col, width=3)
        d.line([cx - 14, cy + 2, cx + 14, cy + 2], fill=col, width=3)
        d.line([cx + 30, cy - 30, cx + 60, cy + 20], fill=col, width=3)  # snapped section
        d.line([cx - 70, cy + 32, cx + 70, cy + 32], fill=col, width=3)
    elif kind == "sea":
        for row in range(3):
            y = cy - 20 + row * 22
            pts = [(cx - 70 + k * 10, y + (6 if k % 2 else -6)) for k in range(15)]
            d.line(pts, fill=col, width=3)


def scene_story(img, d, t, dur):
    a = appear(t, 0, 0.5) * (1 - appear(t, dur - 0.4, 0.4))
    header(d, "Why we built Vanta", "Drones are needed most where radio works least", a)
    b1 = appear(t, 0.6) * a
    d.text((80, 168), "We started out building drones to spot wildfires.", font=F[(22, "regular")], fill=fade(TEXT, b1))
    b2 = appear(t, 2.4) * a
    d.text((80, 202), "Every test found the same weak spot: they all needed a signal to the ground.",
           font=F[(22, "regular")], fill=fade(MUTED, b2))
    places = [("valley", "Mountain valleys", "ridges block the signal"),
              ("forest", "Deep forest", "trees soak up radio"),
              ("disaster", "Disaster zones", "phone masts are down"),
              ("sea", "Open sea", "nothing to relay through")]
    tw, gap = 260, 20
    x0 = (W - 4 * tw - 3 * gap) // 2
    for i, (kind, title, sub) in enumerate(places):
        b = appear(t, 4.2 + i * 0.6) * a
        x = x0 + i * (tw + gap)
        d.rounded_rectangle([x, 262, x + tw, 492], radius=10, fill=fade(PANEL, b), outline=fade(LINE, b))
        _icon(d, kind, x + tw // 2, 330, b)
        ctext(d, (x + tw // 2, 404), title, F[(20, "bold")], fade(TEXT, b))
        ctext(d, (x + tw // 2, 432), sub, F[(15, "regular")], fade(MUTED, b))
        nb = appear(t, 6.6 + i * 0.5, 0.3) * a
        if nb > 0:
            lab = "NO SIGNAL"
            lw = d.textlength(lab, font=F[(13, "bold")]) + 20
            d.rounded_rectangle([x + (tw - lw) / 2, 452, x + (tw + lw) / 2, 478], radius=6, fill=fade((127, 29, 29), nb))
            ctext(d, (x + tw / 2, 465), lab, F[(13, "bold")], fade((254, 202, 202), nb))
    b3 = appear(t, 9.4) * a
    ctext(d, (W // 2, 552), "Exactly where search drones are needed. So we started again, from one question:",
          F[(22, "regular")], fade(TEXT, b3))
    b4 = appear(t, 11.0) * a
    ctext(d, (W // 2, 610), "What if no drone ever needed to be told what to do?", F[(30, "bold")], fade(ACCENT, b4))


# ----------------------------------------------------------- impact scene
def scene_impact(img, d, t, dur):
    a = appear(t, 0, 0.5) * (1 - appear(t, dur - 0.4, 0.4))
    header(d, "Why it matters", "Faster searches, lower costs", a)
    d.text((80, 170), "SOCIAL", font=F[(16, "bold")], fill=fade(GOOD, a))
    social = ["Survivors found sooner, in the places help struggles to reach",
              "Keeps working when disasters knock out phone networks",
              "Drones search ground too dangerous to send rescuers into"]
    y = 204
    for i, s in enumerate(social):
        b = appear(t, 0.8 + i * 0.9) * a
        d.ellipse([80, y + 10, 90, y + 20], fill=fade(GOOD, b))
        y = wrap(d, 104, y, s, F[(22, "regular")], fade(TEXT, b), 430) + 22

    x0 = 640
    d.text((x0, 170), "FINANCIAL", font=F[(16, "bold")], fill=fade(ACCENT, a))
    stats = [
        (f"{NUM['base_ratio']:.1f}× faster", f"full search with the base station down ({NUM['base_v']:.1f} vs {NUM['base_c']:.1f} min)"),
        (f"{NUM['idle_ratio']:.0f}× less idle", f"flight time when everything fails ({NUM['idle_v']:.0f} vs {NUM['idle_c']:.0f} drone-min)"),
        (f"{NUM['done']}/{NUM['runs']}", "simulated missions completed, with no always-on link to pay for"),
    ]
    y = 204
    for i, (big, small) in enumerate(stats):
        b = appear(t, 4.0 + i * 1.2) * a
        d.text((x0, y), big, font=F[(40, "bold")], fill=fade(TEXT, b))
        wrap(d, x0, y + 52, small, F[(18, "regular")], fade(MUTED, b), 560, 4)
        y += 120
    b = appear(t, 8.5) * a
    d.text((80, 640), f"Simulated: {NUM['scenarios']} failure scenarios × 10 runs each, Vanta vs central command "
           "(results/BENCHMARK.md).", font=F[(15, "regular")], fill=fade(MUTED, b))


# ---------------------------------------------------------- business scene
def scene_business(img, d, t, dur):
    a = appear(t, 0, 0.5) * (1 - appear(t, dur - 0.4, 0.4))
    header(d, "The business", "Software that runs on drones people already own", a)
    d.text((80, 170), "WHO PAYS", font=F[(16, "bold")], fill=fade(ACCENT, a))
    chips = ["Search & rescue", "Wildfire agencies", "Infrastructure inspection",
             "Mining & agriculture", "Maritime & offshore"]
    x, y = 80, 200
    for i, c in enumerate(chips):
        b = appear(t, 0.6 + i * 0.35) * a
        w_ = d.textlength(c, font=F[(20, "bold")]) + 32
        if x + w_ > W - 80:
            x, y = 80, y + 52
        d.rounded_rectangle([x, y, x + w_, y + 40], radius=20, outline=fade(ACCENT, b), width=2)
        d.text((x + 16, y + 7), c, font=F[(20, "bold")], fill=fade(TEXT, b))
        x += w_ + 12

    top = y + 70
    d.text((80, top), "HOW IT EARNS", font=F[(16, "bold")], fill=fade(ACCENT, a))
    cards = [("Licence per drone", "for rescue, wildfire and inspection teams running their own fleets"),
             ("Built into drone makers' products", "an SDK licence, so “works without signal” ships as a feature"),
             ("Blackout testing as a service", "prove a fleet copes with failures before it ever flies")]
    cw, gap = 360, 20
    for i, (title, sub) in enumerate(cards):
        b = appear(t, 3.0 + i * 1.0) * a
        cx = 80 + i * (cw + gap)
        d.rounded_rectangle([cx, top + 30, cx + cw, top + 180], radius=10, fill=fade(PANEL, b), outline=fade(LINE, b))
        wrap(d, cx + 20, top + 48, title, F[(20, "bold")], fade(TEXT, b), cw - 40, 4)
        wrap(d, cx + 20, top + 100, sub, F[(18, "regular")], fade(MUTED, b), cw - 40, 4)
    b = appear(t, 7.5) * a
    ctext(d, (W // 2, top + 250), "No new hardware. No always-on link. Just a smarter swarm.", F[(26, "regular")], fade(ACCENT, b))


def scene_outro(img, d, t, dur):
    a = appear(t, 0.1, 0.6)
    cx = W // 2
    ctext(d, (cx, 290), "V A N T A", F[(64, "bold")], fade(TEXT, a))
    ctext(d, (cx, 362), "Cut the radios. The search keeps going.", F[(28, "light")], fade(ACCENT, a))
    b = appear(t, 1.2, 0.6)
    ctext(d, (cx, 450), "Built for the Neptune North Challenge  ·  GreatUniHack 2026", F[(18, "regular")], fade(MUTED, b))
    ctext(d, (cx, 480), "github.com/Jacoman123/GUNIHACK", F[(18, "regular")], fade(MUTED, b))


# ------------------------------------------------------------- timeline
# (name, start, end, draw function, length the animation was designed for)
SCENES = [
    ("title", 0.0, 6.0, scene_title, 8.0),
    ("story", 6.0, 20.0, scene_story, 14.0),
    ("problem", 20.0, 30.0, scene_problem, 13.0),
    ("notebook", 30.0, 42.0, scene_notebook, 12.0),
    ("leases", 42.0, 52.0, scene_leases, 12.0),
    ("live", 52.0, 87.0, scene_live, None),
    ("impact", 87.0, 101.0, scene_impact, 14.0),
    ("business", 101.0, 113.0, scene_business, 12.0),
    ("outro", 113.0, 120.0, scene_outro, 7.0),
]
DURATION = SCENES[-1][2]


def start(name):
    return next(s[1] for s in SCENES if s[0] == name)


def draw_frame(t: float, live: Live) -> Image.Image:
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    for name, a, b, fn, designed in SCENES:
        if a <= t < b:
            tl, dur = t - a, b - a
            if name == "live":
                fn(img, d, tl, dur, live)
            else:
                k = designed / dur      # play the animation faster or slower to fit its slot
                fn(img, d, tl * k, dur * k)
            break
    return img


def render(live: Live):
    writer = imageio_ffmpeg.write_frames(
        str(OUT / "vanta_explainer.mp4"), (W, H), fps=FPS, codec="libx264",
        quality=8, macro_block_size=8, output_params=["-movflags", "+faststart"])
    writer.send(None)
    for f in range(int(DURATION * FPS)):
        writer.send(draw_frame(f / FPS, live).tobytes())
        if f % (FPS * 10) == 0:
            print(f"  {f / FPS:5.0f}s / {DURATION:.0f}s")
    writer.close()


def stills(live: Live, times):
    for t in times:
        draw_frame(t, live).save(OUT / f"still_{int(t):03d}.png")


def live_moments():
    """Fly the comparison once to find when things happen, for the transcript."""
    sc = SCENARIOS["gauntlet"]
    v = Simulation(sc, "vanta", 1).run(until_reported=True)
    c = Simulation(sc, "central", 1).run(until_reported=True)
    at = lambda sim_t: start("live") + live_video_time(sim_t)  # noqa: E731
    end = next(s[2] for s in SCENES if s[0] == "live")
    assert at(c.reported_t) < end - 1.0, "central command must finish on screen; retime the live scene"
    return {
        "jam": at(sc.jam[0][0]), "kill1": at(sc.kills[0][0]), "base": at(sc.base_down[0][0]),
        "split": at(sc.split[0][0]), "fast": at(LIVE_SLOW_SIM),
        "vanta_done": (at(v.reported_t), v.reported_t), "central_done": (at(c.reported_t), c.reported_t),
    }


def ts(sec):
    return f"{int(sec // 60)}:{int(sec % 60):02d}"


def transcript(mo) -> str:
    vd, vsim = mo["vanta_done"]
    cd, csim = mo["central_done"]
    gap = (csim - vsim) / 60
    gap_words = f"nearly {math.ceil(gap)}" if gap % 1 > 0.5 else f"{gap:.0f}"
    n = NUM
    sec = lambda name, title: f"**{ts(start(name))} · {title}**"  # noqa: E731
    return "\n".join([
        "# Vanta explainer: voice-over transcript",
        "",
        "Length 2:00. Each section is written to fit its slot at a relaxed pace (about 150 words a minute).",
        "Headings mark scene changes. *Italic* lines are on-screen cues for you, not for reading aloud.",
        "",
        "---",
        "",
        sec("title", "Title"),
        "",
        "This is Vanta: a drone swarm that keeps searching, even when the radios go dark.",
        "",
        sec("story", "Why we built it"),
        "",
        "We started out building wildfire drones, and found one weak spot: they all needed a signal. "
        "But drones are needed most in valleys, forests and disaster zones, exactly where radio fails. "
        "So we started again.",
        "",
        sec("problem", "The problem"),
        "",
        "Today, most swarms take orders from a base. Lose the link, and drones finish their job, and wait. "
        "The search stalls when it matters most.",
        "",
        sec("notebook", "How Vanta works"),
        "",
        "In Vanta, there's no boss. Every drone carries its own copy of the mission, and decides for itself. "
        "Drones in range swap notes, so news spreads drone to drone.",
        "",
        sec("leases", "Leases, not orders"),
        "",
        "Drones claim sectors with short leases. If one crashes or goes quiet, its lease runs out, "
        "and another drone finishes its work.",
        "",
        sec("live", "Live comparison") + " *(real simulation: \"The gauntlet\", seed 1)*",
        "",
        "Same mission, same faults. Vanta on the left, central command on the right.",
        "",
        f"*{ts(mo['jam'])}: radio blackout.* Radios jammed. Vanta keeps searching. "
        "Central command's drones stop, and head home for orders.",
        "",
        f"*{ts(mo['kill1'])}: crash, then base off air at {ts(mo['base'])}, ridge split at {ts(mo['split'])}.* "
        "A crash. The base goes down. A ridge splits the swarm. Vanta keeps going on both sides.",
        "",
        f"*{ts(vd)}: Vanta completes.* Vanta finishes after {vsim / 60:.1f} minutes.",
        "",
        f"*{ts(cd)}: central command completes.* Central command, {gap_words} minutes later.",
        "",
        sec("impact", "Why it matters"),
        "",
        "That matters. Survivors are found sooner, in the places help struggles to reach, with fewer "
        "rescuers at risk. And it saves money: far less idle flight time, and no costly link to keep up.",
        "",
        f"*On screen: {n['base_ratio']:.1f}× faster full search with the base down; {n['idle_ratio']:.0f}× less idle "
        f"flight time in the gauntlet; {n['done']}/{n['runs']} missions completed. All simulated.*",
        "",
        sec("business", "The business"),
        "",
        "Vanta is software, so it runs on drones people already own. We'd license it per drone to rescue, "
        "wildfire and inspection teams, and to drone makers.",
        "",
        sec("outro", "Close"),
        "",
        "Vanta. Cut the radios, and the search keeps going.",
        "",
        "---",
        "",
        "## If a judge asks",
        "",
        f"* **Are the numbers real?** They're from the simulator: {n['scenarios']} failure scenarios, 10 runs each, "
        f"Vanta against a fair central-command baseline. Vanta finished all {n['runs']} and had the faster median "
        f"time in {n['faster']} of {n['scenarios']} scenarios. On clear skies the two are within a minute.",
        "* **What's not modelled?** Wind, obstacles and battery limits. Real use needs hardware trials and aviation approval.",
        "* **Why can't central command just add relays?** It can, but relays cost money and still fail. "
        "Vanta treats losing contact as normal, so cheap short-range radios are enough.",
        "",
    ])


def main():
    OUT.mkdir(exist_ok=True)
    mo = live_moments()
    (OUT / "TRANSCRIPT.md").write_text(transcript(mo), encoding="utf-8")
    print("transcript written; key moments:", mo)
    if "--stills" in sys.argv:
        stills(Live(), [3, 9, 18, 26, 36, 48, 58, 66, 80, 86, 95, 100, 108, 117])
        return
    render(Live())
    print("video written to", OUT / "vanta_explainer.mp4")


if __name__ == "__main__":
    main()
