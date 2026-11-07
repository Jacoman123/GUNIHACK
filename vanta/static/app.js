"use strict";

const $ = (s, el = document) => el.querySelector(s);
const panels = [...document.querySelectorAll(".panel")];
const ui = {
  scenario: $("#scenario"), rival: $("#rival"), seed: $("#seed"), restart: $("#restart"),
  pause: $("#pause"), speed: $("#speed"), loss: $("#loss"), lossOut: $("#loss-out"),
  view: $("#view"), kill: $("#kill"), desc: $("#scenario-desc"),
};
const faults = {};  // operator toggles: jam / split / base_down
let state = null;
let nDrones = 0;
const offscreen = document.createElement("canvas");

const DRONE_COLORS = Array.from({ length: 16 }, (_, i) => `hsl(${(i * 137.5 + 200) % 360} 85% 64%)`);

async function post(path, body) {
  await fetch(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
}
const control = (action, value) => post("/api/control", { action, value });

async function restart() {
  for (const k of Object.keys(faults)) faults[k] = false;
  document.querySelectorAll(".fault[data-action]").forEach(b => b.setAttribute("aria-pressed", "false"));
  ui.loss.value = 5; ui.lossOut.textContent = "default";
  await post("/api/reset", { scenario: ui.scenario.value, rival: ui.rival.value, seed: +ui.seed.value || 1 });
}

async function init() {
  const meta = await (await fetch("/api/meta")).json();
  for (const s of meta.scenarios) ui.scenario.add(new Option(s.title, s.name));
  for (const r of meta.rivals) ui.rival.add(new Option(r.label, r.name));
  ui.scenario.value = "nominal";
  ui.lossOut.textContent = "default";

  ui.restart.onclick = restart;
  ui.scenario.onchange = restart;
  ui.rival.onchange = restart;
  ui.seed.onchange = restart;
  ui.pause.onclick = () => {
    const on = ui.pause.getAttribute("aria-pressed") !== "true";
    ui.pause.setAttribute("aria-pressed", String(on));
    ui.pause.textContent = on ? "Play" : "Pause";
    control("pause", on);
  };
  ui.speed.onchange = () => control("speed", +ui.speed.value);
  ui.loss.oninput = () => { ui.lossOut.textContent = ui.loss.value + "%"; };
  ui.loss.onchange = () => control("loss", ui.loss.value / 100);
  ui.kill.onclick = () => control("kill");
  document.querySelectorAll(".fault[data-action]").forEach(btn => {
    btn.onclick = () => {
      const a = btn.dataset.action;
      faults[a] = !faults[a];
      btn.setAttribute("aria-pressed", String(faults[a]));
      control(a, faults[a]);
    };
  });

  await restart();
  await control("speed", +ui.speed.value);
  poll();
}

async function poll() {
  try {
    const r = await fetch("/api/state?view=" + encodeURIComponent(ui.view.value || "truth"));
    state = await r.json();
    render();
  } catch (e) { /* server restarting; try again */ }
  setTimeout(poll, 100);
}

function syncViewOptions(n) {
  if (n === nDrones) return;
  nDrones = n;
  const cur = ui.view.value;
  ui.view.innerHTML = "";
  ui.view.add(new Option("Ground truth", "truth"));
  ui.view.add(new Option("What the base knows", "base"));
  for (let i = 0; i < n; i++) ui.view.add(new Option(`What drone D${i} believes`, String(i)));
  ui.view.value = [...ui.view.options].some(o => o.value === cur) ? cur : "truth";
}

const fmtT = s => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;

function render() {
  const s = state;
  ui.desc.textContent = s.scenario.description;
  syncViewOptions(s.sims[0].drones.length);
  s.sims.forEach((sim, i) => renderPanel(panels[i], sim, s));
}

function renderPanel(el, sim, s) {
  const m = sim.metrics;
  $("h2", el).textContent = sim.label;
  const pill = $(".pill", el);
  const holding = sim.drones.filter(d => d.state === "holding").length;
  if (m.reported_t != null) {
    pill.textContent = `Mission complete · ${fmtT(m.reported_t)}`; pill.className = "pill done";
  } else if (holding) {
    pill.textContent = `${holding} drone${holding > 1 ? "s" : ""} waiting for orders`; pill.className = "pill stuck";
  } else {
    pill.textContent = `Searching · ${fmtT(m.t)}`; pill.className = "pill";
  }

  const stats = [
    [fmtT(m.t), "Mission clock"],
    [m.true_pct.toFixed(1) + "%", "Area searched"],
    [m.base_pct.toFixed(1) + "%", "Area the base knows"],
    [`${m.reported}/${m.targets}`, "Survivors reported"],
    [m.overlap_pct.toFixed(1) + "%", "Searched twice by mistake"],
    [`${m.alive}/${sim.drones.length}`, "Drones flying"],
  ];
  $(".stats", el).innerHTML = stats.map(([v, l]) => `<div class="stat"><b>${v}</b><span>${l}</span></div>`).join("");

  $(".fleet", el).innerHTML = sim.drones.map(d => {
    const what = !d.alive ? "down" : d.state === "working" ? `sector ${d.task}` : d.state;
    return `<span class="chip ${d.alive ? d.state : "down"}" title="D${d.id} believes ${d.known_pct}% is searched"><i style="background:${DRONE_COLORS[d.id]}"></i>D${d.id} ${what}</span>`;
  }).join("");

  const log = $(".log", el);
  const atBottom = log.scrollTop === 0;
  log.innerHTML = sim.events.slice().reverse().map(([t, kind, text]) =>
    `<li class="${kind}"><time>${fmtT(t)}</time><span>${text}</span></li>`).join("");
  if (atBottom) log.scrollTop = 0;

  draw($("canvas", el), sim, s);
}

function decodeBits(b64) {
  const bin = atob(b64);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

function draw(canvas, sim, s) {
  const g = s.grid;
  const dpr = window.devicePixelRatio || 1;
  const W = Math.round(canvas.clientWidth * dpr), H = Math.round(canvas.clientHeight * dpr);
  if (canvas.width !== W || canvas.height !== H) { canvas.width = W; canvas.height = H; }
  const ctx = canvas.getContext("2d");
  const k = Math.min(W / g.width_m, H / g.height_m);
  const ox = (W - g.width_m * k) / 2, oy = (H - g.height_m * k) / 2;
  const X = x => ox + x * k, Y = y => oy + y * k;
  const cond = sim.conditions;

  ctx.fillStyle = "#000"; ctx.fillRect(0, 0, W, H);

  // Coverage layer, one pixel per cell, scaled up.
  offscreen.width = g.cols; offscreen.height = g.rows;
  const octx = offscreen.getContext("2d");
  const img = octx.createImageData(g.cols, g.rows);
  const bits = decodeBits(sim.layer);
  for (let i = 0; i < g.cols * g.rows; i++) {
    const on = (bits[i >> 3] >> (i & 7)) & 1;
    const p = i * 4;
    if (on) { img.data[p] = 32; img.data[p + 1] = 120; img.data[p + 2] = 110; img.data[p + 3] = 255; }
    else { img.data[p] = 10; img.data[p + 1] = 12; img.data[p + 2] = 16; img.data[p + 3] = 255; }
  }
  octx.putImageData(img, 0, 0);
  ctx.imageSmoothingEnabled = false;
  ctx.drawImage(offscreen, X(0), Y(0), g.width_m * k, g.height_m * k);

  // Sector grid.
  const sm = g.sector * g.cell_m;
  ctx.strokeStyle = "rgba(255,255,255,0.06)"; ctx.lineWidth = 1;
  ctx.beginPath();
  for (let x = sm; x < g.width_m; x += sm) { ctx.moveTo(X(x), Y(0)); ctx.lineTo(X(x), Y(g.height_m)); }
  for (let y = sm; y < g.height_m; y += sm) { ctx.moveTo(X(0), Y(y)); ctx.lineTo(X(g.width_m), Y(y)); }
  ctx.stroke();

  // Radio shadows.
  for (const [x0, y0, x1, y1] of s.scenario.dead_zones) {
    ctx.save();
    ctx.beginPath(); ctx.rect(X(x0), Y(y0), (x1 - x0) * k, (y1 - y0) * k); ctx.clip();
    ctx.fillStyle = "rgba(60,64,80,0.25)"; ctx.fillRect(X(x0), Y(y0), (x1 - x0) * k, (y1 - y0) * k);
    ctx.strokeStyle = "rgba(120,126,145,0.35)"; ctx.lineWidth = 1 * dpr;
    ctx.beginPath();
    for (let d = -(y1 - y0); d < (x1 - x0); d += 14) {
      ctx.moveTo(X(x0 + d), Y(y1)); ctx.lineTo(X(x0 + d + (y1 - y0)), Y(y0));
    }
    ctx.stroke(); ctx.restore();
    label(ctx, "radio shadow", X(x0) + 4 * dpr, Y(y0) + 12 * dpr, "rgba(160,166,185,0.8)", dpr);
  }

  // Sectors being searched.
  for (const d of sim.drones) {
    if (!d.alive || d.task == null) continue;
    const sx = (d.task % g.sx) * sm, sy = Math.floor(d.task / g.sx) * sm;
    const w = Math.min(sm, g.width_m - sx), h = Math.min(sm, g.height_m - sy);
    ctx.fillStyle = withAlpha(DRONE_COLORS[d.id], 0.10);
    ctx.fillRect(X(sx), Y(sy), w * k, h * k);
    ctx.strokeStyle = withAlpha(DRONE_COLORS[d.id], 0.75); ctx.lineWidth = 1.5 * dpr;
    ctx.strokeRect(X(sx) + 1, Y(sy) + 1, w * k - 2, h * k - 2);
  }

  // Survivors.
  for (const t of sim.targets) {
    const cx = ((t.cell % g.cols) + 0.5) * g.cell_m, cy = (Math.floor(t.cell / g.cols) + 0.5) * g.cell_m;
    ctx.beginPath(); ctx.arc(X(cx), Y(cy), 5 * dpr, 0, Math.PI * 2);
    if (t.found) {
      ctx.fillStyle = t.reported ? "#4ade80" : "rgba(74,222,128,0.45)"; ctx.fill();
    } else {
      ctx.setLineDash([2 * dpr, 2 * dpr]); ctx.strokeStyle = "rgba(160,160,170,0.7)"; ctx.lineWidth = 1.2 * dpr;
      ctx.stroke(); ctx.setLineDash([]);
    }
  }

  // Base station.
  const [bx, by] = s.base;
  ctx.beginPath(); ctx.arc(X(bx), Y(by), s.scenario.base_range_m * k, 0, Math.PI * 2);
  ctx.strokeStyle = cond.base_down ? "rgba(248,113,113,0.12)" : "rgba(94,234,212,0.10)"; ctx.lineWidth = 1 * dpr; ctx.stroke();

  // Radio links this second.
  const pos = id => id === sim.drones.length ? [bx, by] : [sim.drones[id].x, sim.drones[id].y];
  ctx.lineWidth = 1 * dpr;
  for (const [a, b] of sim.links) {
    const [x1, y1] = pos(a), [x2, y2] = pos(b);
    const toBase = a === sim.drones.length || b === sim.drones.length;
    ctx.strokeStyle = toBase ? "rgba(94,234,212,0.45)" : "rgba(255,255,255,0.22)";
    ctx.beginPath(); ctx.moveTo(X(x1), Y(y1)); ctx.lineTo(X(x2), Y(y2)); ctx.stroke();
  }

  const bs = 9 * dpr;
  ctx.fillStyle = cond.base_down ? "#3a3f4b" : "#5eead4";
  ctx.fillRect(X(bx) - bs / 2, Y(by) - bs / 2, bs, bs);
  if (cond.base_down) cross(ctx, X(bx), Y(by), 8 * dpr, "#f87171", dpr);
  label(ctx, "BASE", X(bx) + 9 * dpr, Y(by) + 4 * dpr, cond.base_down ? "#f87171" : "#5eead4", dpr);

  // Split line.
  if (cond.split_x != null) {
    ctx.strokeStyle = "rgba(248,113,113,0.85)"; ctx.lineWidth = 2 * dpr; ctx.setLineDash([8 * dpr, 6 * dpr]);
    ctx.beginPath(); ctx.moveTo(X(cond.split_x), Y(0)); ctx.lineTo(X(cond.split_x), Y(g.height_m)); ctx.stroke();
    ctx.setLineDash([]);
    label(ctx, "NO LINK ACROSS", X(cond.split_x) + 6 * dpr, Y(g.height_m) - 8 * dpr, "#f87171", dpr);
  }

  // Drones.
  for (const d of sim.drones) {
    const x = X(d.x), y = Y(d.y), r = 5 * dpr;
    if (!d.alive) { cross(ctx, x, y, 6 * dpr, "#6b7280", dpr); continue; }
    if (d.state === "landed") { ctx.globalAlpha = 0.5; }
    ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2);
    ctx.fillStyle = DRONE_COLORS[d.id]; ctx.fill();
    if (d.state === "holding") {
      const pulse = 8 + 3 * Math.sin(performance.now() / 180);
      ctx.beginPath(); ctx.arc(x, y, pulse * dpr, 0, Math.PI * 2);
      ctx.strokeStyle = "#fbbf24"; ctx.lineWidth = 2 * dpr; ctx.stroke();
    } else if (d.state === "returning") {
      ctx.beginPath(); ctx.arc(x, y, r + 3 * dpr, 0, Math.PI * 2);
      ctx.strokeStyle = "rgba(255,255,255,0.5)"; ctx.lineWidth = 1 * dpr; ctx.stroke();
    }
    ctx.globalAlpha = 1;
    label(ctx, "D" + d.id, x + 7 * dpr, y - 6 * dpr, "rgba(230,233,239,0.85)", dpr);
  }

  // Banners.
  const banners = [];
  if (cond.jammed) banners.push("RADIO BLACKOUT");
  if (cond.base_down) banners.push("BASE OFF AIR");
  if (cond.loss >= 0.3) banners.push(`${Math.round(cond.loss * 100)}% MESSAGES LOST`);
  if (cond.jammed) { ctx.fillStyle = "rgba(248,113,113,0.07)"; ctx.fillRect(0, 0, W, H); }
  banners.forEach((b, i) => {
    ctx.font = `600 ${12 * dpr}px ui-sans-serif, system-ui, sans-serif`;
    const tw = ctx.measureText(b).width + 16 * dpr;
    const bx0 = W - tw - 10 * dpr, by0 = 10 * dpr + i * 26 * dpr;
    ctx.fillStyle = "rgba(127,29,29,0.85)"; ctx.fillRect(bx0, by0, tw, 20 * dpr);
    ctx.fillStyle = "#fecaca"; ctx.fillText(b, bx0 + 8 * dpr, by0 + 14 * dpr);
  });
  if (ui.view.value !== "truth") {
    const v = ui.view.value === "base" ? "WHAT THE BASE KNOWS" : `WHAT D${ui.view.value} BELIEVES`;
    label(ctx, v, 10 * dpr, H - 10 * dpr, "#c4b5fd", dpr, 12);
  }
}

function label(ctx, text, x, y, color, dpr, size = 10) {
  ctx.font = `600 ${size * dpr}px ui-sans-serif, system-ui, sans-serif`;
  ctx.fillStyle = color; ctx.fillText(text, x, y);
}

function cross(ctx, x, y, r, color, dpr) {
  ctx.strokeStyle = color; ctx.lineWidth = 2 * dpr;
  ctx.beginPath(); ctx.moveTo(x - r, y - r); ctx.lineTo(x + r, y + r); ctx.moveTo(x + r, y - r); ctx.lineTo(x - r, y + r); ctx.stroke();
}

function withAlpha(hsl, a) { return hsl.replace(")", ` / ${a})`); }

init();
