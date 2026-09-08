"""
CarDex V2.1.3 — vehicle list + clickable sales report.
Replace app.py with this file on GitHub.
"""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from flask import Flask, jsonify, render_template_string, request

from scraper import InventoryEngine, list_adapters
from store import InventoryStore
from sales_brain import build_sales_brain

__version__ = "2.4.0-vdp-fix-ui"

app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False

store = InventoryStore()
engine = InventoryEngine(store=store)

INDEX_HTML = r"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>CarDex — Vehicle Sales Intelligence</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=JetBrains+Mono:wght@400;600;700&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg: #05030a;
      --panel: rgba(15, 9, 24, 0.66);
      --panel-solid: #0e0817;
      --ink: #ede8f7;
      --muted: #8f83ab;
      --dim: #6a5f85;
      --line: rgba(140, 92, 246, 0.16);
      --line-hot: rgba(178, 122, 255, 0.5);
      --violet: #a855f7;
      --violet-deep: #6d28d9;
      --magenta: #e879f9;
      --cyan: #67e8f9;
      --green: #4ade80;
      --amber: #fbbf24;
      --red: #fb7185;
      --mono: "JetBrains Mono", ui-monospace, SFMono-Regular, Menlo, monospace;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    html { scroll-behavior: smooth; }
    body {
      font-family: Inter, system-ui, -apple-system, sans-serif;
      background: var(--bg); color: var(--ink);
      min-height: 100vh; overflow-x: hidden;
      -webkit-font-smoothing: antialiased;
    }

    /* ---------- Ambience: aurora + garage grid + scanlines ---------- */
    .amb { position: fixed; inset: 0; pointer-events: none; z-index: -1; }
    .amb-aurora {
      position: absolute; inset: -30%;
      background:
        radial-gradient(38% 28% at 16% 10%, rgba(168,85,247,.30), transparent 70%),
        radial-gradient(32% 24% at 84% 6%, rgba(232,121,249,.18), transparent 70%),
        radial-gradient(46% 30% at 62% 92%, rgba(109,40,217,.26), transparent 70%);
      filter: blur(6px);
      animation: aurora 22s ease-in-out infinite alternate;
      will-change: transform;
    }
    @keyframes aurora {
      0%   { transform: translate3d(-2%, 0, 0) scale(1); }
      50%  { transform: translate3d(1%, 1.5%, 0) scale(1.05); }
      100% { transform: translate3d(2%, -1%, 0) scale(1.08); }
    }
    .amb-grid {
      position: absolute; inset: 0;
      background-image:
        linear-gradient(rgba(168,85,247,.055) 1px, transparent 1px),
        linear-gradient(90deg, rgba(168,85,247,.055) 1px, transparent 1px);
      background-size: 58px 58px;
      mask-image: radial-gradient(120% 78% at 50% 0%, #000 8%, transparent 78%);
      -webkit-mask-image: radial-gradient(120% 78% at 50% 0%, #000 8%, transparent 78%);
    }
    .amb-scan {
      position: absolute; inset: 0; opacity: .5;
      background: repeating-linear-gradient(180deg, rgba(255,255,255,.022) 0 1px, transparent 1px 3px);
      mix-blend-mode: overlay;
    }
    .amb-sweep {
      position: absolute; left: 0; right: 0; height: 180px; top: -180px;
      background: linear-gradient(180deg, transparent, rgba(168,85,247,.09), transparent);
      animation: sweepDown 9s linear infinite;
    }
    @keyframes sweepDown { from { transform: translateY(0); } to { transform: translateY(140vh); } }

    /* ---------- Header / wordmark ---------- */
    header {
      position: sticky; top: 0; z-index: 40;
      display: flex; align-items: center; gap: 1rem;
      padding: .85rem 1.5rem;
      background: linear-gradient(180deg, rgba(6,3,12,.95), rgba(6,3,12,.55));
      backdrop-filter: blur(18px) saturate(140%); -webkit-backdrop-filter: blur(18px) saturate(140%);
      border-bottom: 1px solid var(--line);
    }
    header::after {
      content: ""; position: absolute; left: 0; right: 0; bottom: -1px; height: 1px;
      background: linear-gradient(90deg, transparent, var(--violet), var(--magenta), transparent);
      opacity: .65;
      animation: railShift 7s linear infinite;
      background-size: 200% 100%;
    }
    @keyframes railShift { from { background-position: 0% 0; } to { background-position: 200% 0; } }

    .mark { display: flex; align-items: baseline; gap: .1rem; }
    .mark .slash {
      display: inline-block; width: 3px; height: 22px; margin-right: .55rem;
      background: linear-gradient(180deg, var(--magenta), var(--violet-deep));
      transform: skewX(-18deg); border-radius: 2px;
      box-shadow: 0 0 14px rgba(217,70,239,.7);
      animation: markPulse 3.6s ease-in-out infinite;
    }
    @keyframes markPulse { 0%,100% { opacity: .8; } 50% { opacity: 1; box-shadow: 0 0 22px rgba(232,121,249,.9); } }
    .mark .car { font-size: 1.28rem; font-weight: 900; letter-spacing: -.045em; color: #fff; }
    .mark .dex {
      font-size: 1.28rem; font-weight: 900; letter-spacing: -.045em;
      background: linear-gradient(92deg, #f5d0fe, #a855f7 55%, #67e8f9);
      -webkit-background-clip: text; background-clip: text; color: transparent;
    }
    .mark .tag {
      font-family: var(--mono); font-size: .56rem; letter-spacing: .32em; text-transform: uppercase;
      color: var(--dim); margin-left: .65rem; align-self: center; white-space: nowrap;
    }
    .badge {
      font-family: var(--mono); background: rgba(168,85,247,.12); border: 1px solid var(--line-hot);
      color: #e9d5ff; font-size: .63rem; padding: .24rem .55rem; border-radius: 4px; font-weight: 700;
      letter-spacing: .08em;
    }
    .spacer { flex: 1; }
    .live { display: flex; align-items: center; gap: .45rem; font-family: var(--mono); font-size: .62rem; color: var(--muted); letter-spacing: .18em; text-transform: uppercase; }
    .dot { width: 6px; height: 6px; border-radius: 50%; background: var(--green); box-shadow: 0 0 10px var(--green); animation: blink 2s ease-in-out infinite; }
    @keyframes blink { 0%,100% { opacity: 1 } 50% { opacity: .3 } }

    main { max-width: 1180px; margin: 0 auto; padding: 1.6rem 1.25rem 4rem; }

    /* ---------- Panels with corner brackets ---------- */
    .card {
      position: relative;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 4px;
      padding: 1.25rem 1.4rem; margin-bottom: 1.1rem;
      backdrop-filter: blur(14px); -webkit-backdrop-filter: blur(14px);
      box-shadow: 0 22px 60px rgba(0,0,0,.55), inset 0 1px 0 rgba(255,255,255,.035);
      transition: border-color .25s ease, box-shadow .25s ease, transform .25s cubic-bezier(.2,.7,.3,1);
      animation: rise .5s cubic-bezier(.2,.7,.3,1) both;
    }
    .card::before, .card::after {
      content: ""; position: absolute; width: 12px; height: 12px; pointer-events: none;
      border-color: var(--line-hot); opacity: .8;
    }
    .card::before { top: -1px; left: -1px; border-top: 1px solid; border-left: 1px solid; }
    .card::after { bottom: -1px; right: -1px; border-bottom: 1px solid; border-right: 1px solid; }
    .card:hover { border-color: rgba(178,122,255,.34); box-shadow: 0 28px 70px rgba(76,29,149,.4); transform: translateY(-2px); }
    @keyframes rise { from { opacity: 0; transform: translateY(14px); } to { opacity: 1; transform: none; } }

    h2 {
      font-family: var(--mono); font-size: .63rem; color: var(--muted); font-weight: 700;
      text-transform: uppercase; letter-spacing: .26em; margin-bottom: .95rem;
      display: flex; align-items: center; gap: .7rem;
    }
    h2::after { content: ""; flex: 1; height: 1px; background: linear-gradient(90deg, var(--line-hot), transparent); }

    /* ---------- Instrument gauges ---------- */
    .gauges { display: grid; grid-template-columns: repeat(4, 1fr); gap: .7rem; margin-bottom: 1.1rem; }
    @media (max-width: 760px) { .gauges { grid-template-columns: repeat(2, 1fr); } }
    .gauge {
      position: relative; overflow: hidden;
      background: linear-gradient(180deg, rgba(21,13,33,.8), rgba(10,6,17,.8));
      border: 1px solid var(--line); border-radius: 4px; padding: .85rem .95rem .95rem;
      animation: rise .5s cubic-bezier(.2,.7,.3,1) both;
      transition: transform .22s ease, border-color .22s ease;
    }
    .gauge:hover { transform: translateY(-3px); border-color: var(--line-hot); }
    .gauge .k { font-family: var(--mono); font-size: .58rem; text-transform: uppercase; letter-spacing: .22em; color: var(--dim); }
    .gauge .v { font-family: var(--mono); font-size: 1.55rem; font-weight: 700; margin-top: .3rem; letter-spacing: -.02em; color: #fff; }
    .gauge .v.hot { background: linear-gradient(92deg, #f5d0fe, #a855f7); -webkit-background-clip: text; background-clip: text; color: transparent; }
    .ticks { display: flex; gap: 3px; margin-top: .6rem; }
    .ticks i { display: block; flex: 1; height: 4px; border-radius: 1px; background: rgba(168,85,247,.16); }
    .ticks i.on { background: linear-gradient(90deg, var(--violet), var(--magenta)); box-shadow: 0 0 8px rgba(168,85,247,.55); }

    /* ---------- Controls ---------- */
    .search-row { display: flex; gap: .6rem; }
    input[type="text"] {
      flex: 1; background: rgba(5,3,10,.9); border: 1px solid var(--line); border-radius: 4px;
      padding: .9rem 1rem; color: var(--ink); font-size: .98rem; outline: none;
      font-family: var(--mono); letter-spacing: .01em;
      transition: border-color .2s ease, box-shadow .2s ease;
    }
    input[type="text"]::placeholder { color: #5d5378; }
    input[type="text"]:focus { border-color: var(--violet); box-shadow: 0 0 0 3px rgba(168,85,247,.16), inset 0 0 24px rgba(168,85,247,.07); }

    button {
      position: relative; overflow: hidden;
      background: linear-gradient(135deg, var(--violet-deep), #c026d3);
      color: #fff; border: none; border-radius: 4px; padding: .88rem 1.2rem;
      font-family: var(--mono); font-size: .74rem; font-weight: 700; letter-spacing: .14em; text-transform: uppercase;
      cursor: pointer; white-space: nowrap;
      transition: transform .16s ease, box-shadow .16s ease, filter .16s ease;
      box-shadow: 0 8px 24px rgba(109,40,217,.4);
    }
    button:hover:not(:disabled) { transform: translateY(-2px); box-shadow: 0 14px 34px rgba(192,38,211,.42); filter: brightness(1.08); }
    button:active:not(:disabled) { transform: translateY(0); }
    button:focus-visible { outline: 2px solid var(--magenta); outline-offset: 2px; }
    button:disabled { opacity: .45; cursor: not-allowed; }
    button.secondary { background: rgba(168,85,247,.08); border: 1px solid var(--line-hot); color: #e9d5ff; box-shadow: none; }
    button.secondary:hover:not(:disabled) { background: rgba(168,85,247,.18); }
    button.ghost { background: transparent; border: 1px solid var(--line); color: var(--muted); box-shadow: none; }
    button.ghost:hover { color: var(--ink); border-color: var(--line-hot); }
    button.busy::after {
      content: ""; position: absolute; inset: 0;
      background: linear-gradient(90deg, transparent, rgba(255,255,255,.25), transparent);
      background-size: 200% 100%; animation: railShift 1.1s linear infinite;
    }
    .actions { display: flex; gap: .55rem; margin-top: .85rem; flex-wrap: wrap; }

    .status { font-family: var(--mono); font-size: .74rem; color: var(--muted); margin-top: .85rem; min-height: 1.3em; letter-spacing: .04em; }
    .status.ok { color: var(--green); }
    .status.err { color: var(--red); }

    /* ---------- Vehicle rows: instrument strips ---------- */
    .vehicle {
      position: relative; display: flex; gap: 1rem; align-items: center; flex-wrap: wrap;
      background: linear-gradient(90deg, rgba(14,8,23,.85), rgba(9,5,15,.7));
      border: 1px solid var(--line); border-left: 2px solid rgba(168,85,247,.35);
      border-radius: 3px; padding: .9rem 1.1rem; margin-bottom: .55rem; cursor: pointer;
      transition: transform .2s cubic-bezier(.2,.7,.3,1), border-color .2s ease, background .2s ease, box-shadow .2s ease;
      animation: itemIn .4s cubic-bezier(.2,.7,.3,1) both;
    }
    .vehicle:hover { transform: translateX(6px); border-left-color: var(--magenta); border-color: var(--line-hot); background: linear-gradient(90deg, rgba(28,16,44,.9), rgba(12,7,20,.8)); box-shadow: 0 14px 34px rgba(76,29,149,.35); }
    .vehicle:focus-visible { outline: 2px solid var(--magenta); outline-offset: 2px; }
    @keyframes itemIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: none; } }
    .v-main { flex: 1; min-width: 210px; }
    .vehicle .title { font-size: 1.02rem; font-weight: 700; letter-spacing: -.015em; margin-bottom: .4rem; }
    .vehicle .meta { display: flex; flex-wrap: wrap; gap: .35rem; }
    .tagchip {
      font-family: var(--mono); font-size: .62rem; letter-spacing: .1em; text-transform: uppercase;
      color: var(--muted); background: rgba(168,85,247,.07);
      border: 1px solid var(--line); border-radius: 3px; padding: .18rem .45rem;
    }
    .vehicle .price {
      font-family: var(--mono); font-size: 1.22rem; font-weight: 700; letter-spacing: -.02em;
      background: linear-gradient(92deg, #f5d0fe, #c084fc); -webkit-background-clip: text; background-clip: text; color: transparent;
      text-align: right; min-width: 120px;
    }

    .empty { color: var(--muted); text-align: center; padding: 1.9rem 0; font-size: .9rem; font-family: var(--mono); letter-spacing: .06em; }

    /* ---------- Report ---------- */
    #report-view { display: none; }
    .back-row { margin-bottom: 1rem; }
    .report-hero { display: flex; gap: 1.35rem; flex-wrap: wrap; align-items: flex-start; }
    .report-photo {
      position: relative; width: 270px; height: 180px; flex: none; overflow: hidden;
      background: rgba(5,3,10,.85); border: 1px solid var(--line); border-radius: 3px;
      display: flex; align-items: center; justify-content: center; color: var(--dim);
      font-family: var(--mono); font-size: .68rem; letter-spacing: .16em; text-transform: uppercase;
    }
    .report-photo img { width: 100%; height: 100%; object-fit: cover; transition: transform .5s ease, filter .35s ease; }
    .report-photo:hover img { transform: scale(1.06); filter: saturate(1.15) contrast(1.04); }
    .report-photo::after {
      content: ""; position: absolute; inset: 0; pointer-events: none;
      background: repeating-linear-gradient(180deg, rgba(0,0,0,.16) 0 1px, transparent 1px 3px);
      opacity: .55;
    }
    .report-title { font-size: 1.5rem; font-weight: 800; line-height: 1.2; letter-spacing: -.03em; }
    .report-price {
      font-family: var(--mono); font-size: 2rem; font-weight: 700; margin: .35rem 0 .2rem; letter-spacing: -.03em;
      background: linear-gradient(92deg, #f5d0fe, #a855f7); -webkit-background-clip: text; background-clip: text; color: transparent;
    }
    .report-sub { color: var(--muted); font-size: .88rem; font-family: var(--mono); letter-spacing: .06em; }

    .chips { display: flex; flex-wrap: wrap; gap: .4rem; margin-top: .8rem; }
    .chip {
      font-family: var(--mono); font-size: .64rem; letter-spacing: .12em; text-transform: uppercase; font-weight: 600;
      background: rgba(168,85,247,.07); border: 1px solid var(--line); border-radius: 3px; padding: .26rem .6rem; color: var(--muted);
    }
    .chip.ok { border-color: rgba(74,222,128,.42); color: var(--green); background: rgba(74,222,128,.08); }
    .chip.warn { border-color: rgba(251,191,36,.42); color: var(--amber); background: rgba(251,191,36,.08); }

    .grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: .55rem; }
    @media (max-width: 640px) { .grid2 { grid-template-columns: 1fr; } .report-photo { width: 100%; } .vehicle .price { text-align: left; } }
    .spec {
      background: rgba(5,3,10,.72); border: 1px solid var(--line); border-radius: 3px; padding: .72rem .9rem;
      transition: transform .18s ease, border-color .18s ease, background .18s ease;
    }
    .spec:hover { transform: translateY(-2px); border-color: var(--line-hot); background: rgba(20,12,32,.85); }
    .spec .label { font-family: var(--mono); font-size: .58rem; color: var(--dim); text-transform: uppercase; letter-spacing: .2em; }
    .spec .value { font-size: .98rem; font-weight: 600; margin-top: .3rem; word-break: break-word; }
    .spec .value.verify { color: var(--amber); font-weight: 700; }

    .section-title {
      font-family: var(--mono); font-size: .63rem; color: var(--muted); font-weight: 700;
      text-transform: uppercase; letter-spacing: .26em; margin: 1.4rem 0 .65rem;
      display: flex; align-items: center; gap: .7rem;
    }
    .section-title::before { content: "//"; color: var(--violet); }
    .section-title::after { content: ""; flex: 1; height: 1px; background: linear-gradient(90deg, var(--line-hot), transparent); }

    .bullet {
      background: rgba(5,3,10,.7); border: 1px solid var(--line); border-left: 2px solid var(--violet);
      border-radius: 0 3px 3px 0; padding: .72rem .95rem; margin-bottom: .45rem;
      font-size: .93rem; line-height: 1.55;
      transition: transform .18s ease, background .18s ease, border-color .18s ease;
    }
    .bullet:hover { transform: translateX(4px); background: rgba(22,13,35,.85); border-left-color: var(--magenta); }
    .bullet.warn { border-left-color: var(--amber); }
    .pitch {
      background: linear-gradient(135deg, rgba(109,40,217,.16), rgba(232,121,249,.06));
      border: 1px solid var(--line-hot); border-radius: 3px; padding: 1rem 1.1rem;
      font-size: .98rem; line-height: 1.6;
    }
    a.link { color: #e9d5ff; font-size: .84rem; font-family: var(--mono); letter-spacing: .08em; text-decoration: none; border-bottom: 1px solid rgba(233,213,255,.35); }
    a.link:hover { color: var(--magenta); }

    .loading-shimmer {
      background: linear-gradient(90deg, rgba(14,8,23,.7) 25%, rgba(46,26,72,.85) 37%, rgba(14,8,23,.7) 63%);
      background-size: 400% 100%; animation: shimmer 1.35s ease infinite;
      border-radius: 3px; height: 74px; margin-bottom: .55rem; border: 1px solid var(--line);
    }
    @keyframes shimmer { 0% { background-position: 100% 0 } 100% { background-position: -100% 0 } }

    @media (prefers-reduced-motion: reduce) {
      *, *::before, *::after { animation: none !important; transition: none !important; }
    }
  </style>
</head>
<body>
  <div class="amb" aria-hidden="true">
    <div class="amb-aurora"></div>
    <div class="amb-grid"></div>
    <div class="amb-scan"></div>
    <div class="amb-sweep"></div>
  </div>
  <header>
    <h1 class="mark">
      <span class="slash"></span><span class="car">Car</span><span class="dex">Dex</span>
      <span class="tag">Midnight Performance Desk</span>
    </h1>
    <span class="badge">V{{ version }}</span>
    <div class="spacer"></div>
    <div class="live"><span class="dot"></span> Online</div>
  </header>
  <main>
    <div id="list-view">
      <div class="gauges">
        <div class="gauge"><div class="k">Units</div><div class="v hot" id="stat-count">—</div><div class="ticks" id="tick-count"></div></div>
        <div class="gauge"><div class="k">Avg price</div><div class="v" id="stat-avg">—</div><div class="ticks" id="tick-avg"></div></div>
        <div class="gauge"><div class="k">VIN verified</div><div class="v" id="stat-vin">—</div><div class="ticks" id="tick-vin"></div></div>
        <div class="gauge"><div class="k">Photographed</div><div class="v" id="stat-photo">—</div><div class="ticks" id="tick-photo"></div></div>
      </div>
      <div class="card">
        <h2>Inventory Console</h2>
        <div class="search-row">
          <input type="text" id="q" placeholder="VIN / STOCK / YEAR / MAKE / MODEL" aria-label="Search inventory" />
          <button id="btn-search" onclick="doSearch()">Search</button>
        </div>
        <div class="actions">
          <button class="secondary" id="btn-scan" onclick="doScan()">Scan Lithia Missoula</button>
          <button class="secondary" id="btn-backfill" onclick="doBackfill()">Backfill Data</button>
          <button class="secondary" onclick="loadAll()">Show All Saved</button>
        </div>
        <div class="status" id="status" role="status" aria-live="polite"></div>
      </div>
      <div class="card">
        <h2>Bay — select a unit</h2>
        <div id="results"><div class="empty">Search or scan to load inventory</div></div>
      </div>
    </div>
    <div id="report-view">
      <div class="back-row"><button class="ghost" onclick="showList()">← Back to bay</button></div>
      <div class="card" id="report-body"><div class="empty">Loading…</div></div>
    </div>
  </main>
  <script>
    const statusEl = document.getElementById("status");
    const resultsEl = document.getElementById("results");
    const listView = document.getElementById("list-view");
    const reportView = document.getElementById("report-view");
    const reportBody = document.getElementById("report-body");

    function setStatus(msg, type) {
      statusEl.textContent = msg || "";
      statusEl.className = "status" + (type ? " " + type : "");
    }
    function setBusy(id, on) {
      const el = document.getElementById(id);
      if (!el) return;
      el.disabled = !!on;
      el.classList.toggle("busy", !!on);
    }
    function money(n) {
      if (n == null || n === "") return "—";
      return "$" + Number(n).toLocaleString();
    }
    function esc(s) {
      return String(s == null ? "" : s).replace(/[&<>"']/g, function(c) {
        return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
      });
    }
    function titleOf(v) {
      const t = [v.year, v.make, v.model, v.trim].filter(Boolean).join(" ");
      return t || (v.vin ? ("VIN " + v.vin) : "Vehicle");
    }
    function showSkeleton(n) {
      let out = "";
      for (let i = 0; i < (n || 5); i++) out += '<div class="loading-shimmer"></div>';
      resultsEl.innerHTML = out;
    }
    function renderTicks(id, ratio) {
      const host = document.getElementById(id);
      if (!host) return;
      const total = 10, on = Math.round(Math.max(0, Math.min(1, ratio || 0)) * total);
      let out = "";
      for (let i = 0; i < total; i++) out += '<i class="' + (i < on ? "on" : "") + '"></i>';
      host.innerHTML = out;
    }
    function animateNumber(el, target, formatter) {
      const dur = 700, t0 = performance.now();
      function step(now) {
        const p = Math.min(1, (now - t0) / dur);
        const eased = 1 - Math.pow(1 - p, 3);
        el.textContent = formatter(Math.round(target * eased));
        if (p < 1) requestAnimationFrame(step);
      }
      requestAnimationFrame(step);
    }
    function updateStats(vehicles) {
      const list = vehicles || [];
      const priced = list.filter(function(v) { return v.price != null && v.price !== ""; });
      const avg = priced.length ? Math.round(priced.reduce(function(a, v) { return a + Number(v.price); }, 0) / priced.length) : 0;
      const withVin = list.filter(function(v) { return !!v.vin; }).length;
      const withPhoto = list.filter(function(v) { return !!v.image_url; }).length;
      const n = function(x) { return x.toLocaleString(); };
      animateNumber(document.getElementById("stat-count"), list.length, n);
      animateNumber(document.getElementById("stat-avg"), avg, function(x) { return x ? "$" + x.toLocaleString() : "—"; });
      animateNumber(document.getElementById("stat-vin"), withVin, n);
      animateNumber(document.getElementById("stat-photo"), withPhoto, n);
      renderTicks("tick-count", list.length ? Math.min(1, list.length / 100) : 0);
      renderTicks("tick-avg", avg ? Math.min(1, avg / 90000) : 0);
      renderTicks("tick-vin", list.length ? withVin / list.length : 0);
      renderTicks("tick-photo", list.length ? withPhoto / list.length : 0);
    }
    function renderVehicles(vehicles) {
      updateStats(vehicles);
      if (!vehicles || !vehicles.length) {
        resultsEl.innerHTML = '<div class="empty">No vehicles found yet</div>';
        return;
      }
      resultsEl.innerHTML = vehicles.map((v, i) => {
        const miles = v.mileage != null ? Number(v.mileage).toLocaleString() + " mi" : "— mi";
        return '<div class="vehicle" tabindex="0" style="animation-delay:' + Math.min(i,14)*28 + 'ms" onclick="openReport(' + v.id + ')" onkeydown="if(event.key===\'Enter\')openReport(' + v.id + ')">' +
          '<div class="v-main"><div class="title">' + esc(titleOf(v)) + '</div>' +
          '<div class="meta">' +
            '<span class="tagchip">VIN ' + esc(v.vin || "—") + '</span>' +
            '<span class="tagchip">STK ' + esc(v.stock_number || "—") + '</span>' +
            '<span class="tagchip">' + miles + '</span>' +
            '<span class="tagchip">' + esc(v.condition || "—") + '</span>' +
          '</div></div>' +
          '<div class="price">' + money(v.price) + '</div></div>';
      }).join("");
    }
    async function doSearch() {
      const q = document.getElementById("q").value.trim();
      setStatus("Searching…");
      setBusy("btn-search", true);
      showSkeleton(5);
      try {
        let url = "/api/vehicles?limit=500";
        if (q) url += "&q=" + encodeURIComponent(q);
        const r = await fetch(url);
        const data = await r.json();
        renderVehicles(data.vehicles || []);
        const total = (data.summary && data.summary.active) || data.count || 0;
        setStatus(total + " vehicle(s)", "ok");
      } catch (e) { setStatus("Search failed", "err"); resultsEl.innerHTML = '<div class="empty">Search failed</div>'; }
      setBusy("btn-search", false);
    }
    async function loadAll() {
      document.getElementById("q").value = "";
      await doSearch();
    }
    async function doScan() {
      setStatus("Scanning Lithia public inventory… this can take up to a minute.");
      setBusy("btn-scan", true);
      try {
        const r = await fetch("/api/discover", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            inventory_url: "https://www.lithiachryslermissoula.com/all-inventory/index.htm",
            name: "Lithia Chrysler Jeep Dodge Ram Missoula"
          })
        });
        const data = await r.json();
        if (data.ok) {
          setStatus("Scan complete — found " + (data.vehicles_found || 0) + " vehicles", "ok");
          await loadAll();
        } else {
          setStatus("Scan problem: " + (data.error || "unknown"), "err");
        }
      } catch (e) { setStatus("Scan failed — " + e.message, "err"); }
      setBusy("btn-scan", false);
    }
    async function doBackfill() {
      setStatus("Fast enrichment: pulling public Lithia stock, mileage, photos and specs…");
      setBusy("btn-backfill", true);
      let totalUpdated = 0;
      try {
        while (true) {
          const r = await fetch("/api/backfill_nhtsa", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ limit: 24 })
          });
          const data = await r.json();
          if (!data.ok) { setStatus("Backfill problem: " + (data.error || "unknown"), "err"); break; }
          totalUpdated += data.updated;
          if (data.checked === 0) {
            setStatus(totalUpdated ? ("Backfill complete — updated " + totalUpdated + " vehicle(s)") : "Public vehicle info is already filled in", "ok");
            break;
          }
          setStatus("Backfilled " + totalUpdated + " so far — " + data.remaining + " left…");
        }
      } catch (e) { setStatus("Backfill failed — " + e.message, "err"); }
      setBusy("btn-backfill", false);
      await loadAll();
    }
    function showList() {
      reportView.style.display = "none";
      listView.style.display = "block";
    }
    function showReport() {
      listView.style.display = "none";
      reportView.style.display = "block";
      window.scrollTo({ top: 0, behavior: "smooth" });
    }
    function chip(text, kind) {
      return '<span class="chip ' + (kind || "") + '">' + esc(text) + "</span>";
    }
    function specRow(label, value) {
      const display = value != null && value !== "" ? esc(value) : "Not available in public vehicle data";
      const cls = value != null && value !== "" ? "" : "";
      return '<div class="spec"><div class="label">' + label + '</div><div class="value ' + cls + '">' + display + "</div></div>";
    }
    function buildSales(v, nhtsa) {
      const raw = (v.sales_brain && typeof v.sales_brain === "object") ? v.sales_brain : {};
      return {
        points: Array.isArray(raw.points) ? raw.points : [],
        objections: Array.isArray(raw.objections) ? raw.objections : [],
        pitch: raw.pitch || "",
        competitors: Array.isArray(raw.competitors) ? raw.competitors : [],
        questions: Array.isArray(raw.questions) ? raw.questions : [],
        demo: Array.isArray(raw.demo) ? raw.demo : [],
        fallback: raw.fallback || {},
        resolved: raw.resolved || {}
      };
    }
    async function openReport(id) {
      showReport();
      reportBody.innerHTML = '<div class="loading-shimmer" style="height:180px"></div><div class="loading-shimmer"></div><div class="loading-shimmer"></div>';
      try {
        const r = await fetch("/api/vehicles/" + id);
        const data = await r.json();
        if (!data.vehicle) {
          reportBody.innerHTML = '<div class="empty">Vehicle not found</div>';
          return;
        }
        const v = data.vehicle;
        const nhtsa = data.nhtsa || v.nhtsa || null;
        const sales = buildSales(v, nhtsa);
        const title = titleOf(v);
        const hpValue = sales.resolved.engine_hp || (nhtsa && nhtsa.engine_hp);
        const hp = hpValue ? (hpValue + " hp") : null;
        const engineValue = v.engine || sales.resolved.engine;
        const torqueValue = v.torque || sales.resolved.torque;
        const bodyValue = sales.resolved.body_style || v.body_style || (nhtsa && nhtsa.body_style);
        const photo = v.image_url
          ? '<div class="report-photo"><img src="' + esc(v.image_url) + '" alt="" loading="lazy" /></div>'
          : '<div class="report-photo">No photo yet</div>';
        const chips = [];
        if (v.condition) chips.push(chip(v.condition, "ok"));
        if (v.vin) chips.push(chip("VIN verified", "ok"));
        else chips.push(chip("VIN missing", "warn"));
        if (!v.year || !v.make || !v.model) chips.push(chip("Y/M/M incomplete", "warn"));
        if (!v.trim) chips.push(chip("Trim not published", "warn"));
        reportBody.innerHTML =
          '<div class="report-hero">' + photo +
          '<div style="flex:1;min-width:200px;">' +
          '<div class="report-title">' + esc(title) + '</div>' +
          '<div class="report-price">' + money(v.price) + '</div>' +
          '<div class="report-sub">' + esc(v.dealership_name || "Lithia Missoula") + '</div>' +
          '<div class="chips">' + chips.join("") + '</div>' +
          (v.listing_url ? '<div style="margin-top:0.8rem;"><a class="link" href="' + esc(v.listing_url) + '" target="_blank" rel="noopener">Open listing on dealership site →</a></div>' : "") +
          '</div></div>' +
          '<div class="section-title">Basics</div><div class="grid2">' +
          specRow("VIN", v.vin) + specRow("Stock #", v.stock_number) +
          specRow("Mileage", v.mileage != null ? Number(v.mileage).toLocaleString() + " mi" : null) +
          specRow("Condition", v.condition) +
          specRow("Year", v.year) + specRow("Make", v.make) +
          specRow("Model", v.model) + specRow("Trim", v.trim) +
          '</div>' +
          '<div class="section-title">Specs (public listing / model-year reference)</div><div class="grid2">' +
          specRow("Engine", engineValue || sales.resolved.engine) +
          specRow("Horsepower", hp || sales.resolved.engine_hp) +
          specRow("Drivetrain", v.drivetrain || sales.resolved.drivetrain || (nhtsa && nhtsa.drivetrain)) +
          specRow("Transmission", v.transmission || sales.resolved.transmission) +
          specRow("Fuel", (nhtsa && nhtsa.fuel) || v.fuel_economy) +
          specRow("Body", bodyValue || sales.resolved.body_style) +
          specRow("Torque", torqueValue || sales.resolved.torque) +
          specRow("Flat-tow", sales.resolved.flat_tow || v.flat_tow) +
          specRow("Towing capacity", sales.resolved.towing_capacity || v.towing_capacity) +
          '</div>' +
          '<div class="section-title">Sales Brain — Best selling points</div>' +
          (sales.points.length ? sales.points.map(function(p){ return '<div class="bullet">' + esc(p) + '</div>'; }).join("") : '<div class="bullet warn">No selling points were returned for this vehicle. The Sales Brain needs to be connected to the current sales_brain.py.</div>') +
          (sales.fallback && sales.fallback.source ? '<div class="section-title">Smart fallback</div><div class="pitch">Some vehicle-specific data was unavailable, so CarDex filled only stable same-year/model facts. Configuration-dependent items are described as model-level references when exact listing data is unavailable.</div>' : '') +
          (sales.competitors.length ? '<div class="section-title">Competitive intelligence</div>' + sales.competitors.map(function(c){
            var details = '<div class="bullet"><strong>' + esc(c.name) + '</strong>: ' + (c.hp != null ? esc(c.hp) + ' hp' : 'Horsepower: manufacturer model reference') + (c.torque != null ? ' / ' + esc(c.torque) + ' lb-ft' : '') + (c.engine ? ' • ' + esc(c.engine) : '') + (c.max_towing != null ? ' • up to ' + Number(c.max_towing).toLocaleString() + ' lbs towing' : (c.towing_label ? ' • ' + esc(c.towing_label) : '')) + '</div>';
            var compare = (c.comparison || []).map(function(x){ return '<div class="bullet">' + esc(x) + '</div>'; }).join('');
            return details + '<div class="bullet">' + esc(c.angle || '') + '</div>' + compare + (c.edge ? '<div class="pitch"><strong>How to sell it:</strong> ' + esc(c.edge) + '</div>' : '');
          }).join('') + '<div style="font-size:.76rem;opacity:.7;margin-top:.5rem;">Competitor numbers are model-level references, not VIN-to-VIN matches. Maximum towing varies by configuration.</div>' : '') +
          '<div class="section-title">Customer pitch</div><div class="pitch">' + esc(sales.pitch || "Start by asking what matters most to the customer, then connect the vehicle's verified equipment to that need.") + '</div>' +
          '<div class="section-title">Questions to ask</div>' +
          (sales.questions.length ? sales.questions.map(function(p){ return '<div class="bullet">' + esc(p) + '</div>'; }).join("") : '<div class="bullet">What is the #1 thing this vehicle needs to do for you?</div>') +
          '<div class="section-title">Test-drive / demo focus</div>' +
          (sales.demo.length ? sales.demo.map(function(p){ return '<div class="bullet">' + esc(p) + '</div>'; }).join("") : '<div class="bullet">Demonstrate the verified feature that matters most to the customer.</div>') +
          '<div class="section-title">Know before you sell</div>' +
          sales.objections.map(function(p){ return '<div class="bullet warn">' + esc(p) + '</div>'; }).join("");
      } catch (e) {
        reportBody.innerHTML = '<div class="empty">Failed to load report</div>';
      }
    }
    document.getElementById("q").addEventListener("keydown", function(e) {
      if (e.key === "Enter") doSearch();
    });
    loadAll();
  </script>
</body>
</html>
"""


@app.get("/api/health")
def health():
    return jsonify({
        "status": "ok",
        "service": "CarDex",
        "version": __version__,
        "environment": os.environ.get("CARDEX_ENV", "development"),
    })


@app.get("/api/adapters")
def api_adapters():
    return jsonify({"adapters": list_adapters()})


@app.get("/api/dealerships")
def api_dealerships():
    return jsonify({"dealerships": store.list_dealerships()})


@app.post("/api/dealerships")
def api_add_dealership():
    data = request.get_json(silent=True) or {}
    url = (data.get("inventory_url") or "").strip()
    name = (data.get("name") or "").strip() or None
    if not url:
        return jsonify({"ok": False, "error": "inventory_url is required"}), 400
    result = engine.discover(url, dealership_name=name)
    return jsonify(result), (200 if result.get("ok") else 400)


@app.post("/api/discover")
def api_discover():
    data = request.get_json(silent=True) or {}
    url = (data.get("inventory_url") or data.get("url") or "").strip()
    name = (data.get("name") or "").strip() or None
    force = bool(data.get("force", False))
    if not url:
        return jsonify({"ok": False, "error": "inventory_url is required"}), 400
    result = engine.discover(url, dealership_name=name, force=force)
    return jsonify(result), (200 if result.get("ok") else 400)


@app.post("/api/backfill_nhtsa")
def api_backfill_nhtsa():
    """Fast public-data enrichment. VDP lookups run concurrently in a small pool."""
    data = request.get_json(silent=True) or {}
    limit = data.get("limit") or request.args.get("limit", 24, type=int) or 24
    limit = max(1, min(int(limit), 32))
    candidates = store.vehicles_needing_enrichment(limit=limit)

    def enrich(row):
        vin = row.get("vin")
        if not vin:
            return False
        changed = False
        try:
            from vdp_scraper import scrape_vdp
            current = store.get_vehicle(row["id"]) or {}
            listing_url = current.get("listing_url")
            vdp_data = scrape_vdp(listing_url, known_vin=vin) if listing_url else {}
            if vdp_data:
                is_new = str(vdp_data.get("condition") or current.get("condition") or "").strip().lower() == "new" or "/new/" in str(listing_url or "").lower()
                if is_new and len(str(vin).strip()) >= 8:
                    v = str(vin).strip().upper()
                    vdp_data["stock_number"] = v[-8:]
                    vdp_data["condition"] = vdp_data.get("condition") or "New"
                store.fill_vdp_fields(row["id"], vdp_data)
                changed = True
        except Exception:
            pass
        # NHTSA is supplemental; don't make the user wait for it before the
        # public Lithia fields are saved.
        try:
            from vin_decode import decode_vin
            nhtsa = decode_vin(vin)
            if nhtsa:
                store.fill_nhtsa_fields(row["id"], nhtsa)
                changed = True
        except Exception:
            pass
        return changed

    updated = 0
    if candidates:
        with ThreadPoolExecutor(max_workers=6) as pool:
            futures = [pool.submit(enrich, row) for row in candidates]
            for f in as_completed(futures):
                try:
                    if f.result():
                        updated += 1
                except Exception:
                    pass

    remaining = store.count_needing_enrichment()
    return jsonify({
        "ok": True,
        "checked": len(candidates),
        "updated": updated,
        "remaining": remaining,
    })

@app.get("/api/vehicles")
def api_vehicles():
    dealership_id = request.args.get("dealership_id", type=int)
    q = request.args.get("q")
    year = request.args.get("year", type=int)
    make = request.args.get("make")
    model = request.args.get("model")
    condition = request.args.get("condition")
    min_price = request.args.get("min_price", type=float)
    max_price = request.args.get("max_price", type=float)
    max_mileage = request.args.get("max_mileage", type=int)
    active_only = request.args.get("active_only", "1") != "0"
    limit = min(request.args.get("limit", 100, type=int), 500)
    offset = request.args.get("offset", 0, type=int)
    vehicles = store.search_vehicles(
        dealership_id=dealership_id, q=q, year=year, make=make, model=model,
        condition=condition, min_price=min_price, max_price=max_price,
        max_mileage=max_mileage, active_only=active_only, limit=limit, offset=offset,
    )
    summary = store.inventory_summary(dealership_id)
    return jsonify({"vehicles": vehicles, "summary": summary, "count": len(vehicles)})


@app.get("/api/vehicles/<int:vehicle_id>")
def api_vehicle_detail(vehicle_id: int):
    vehicle = store.get_vehicle(vehicle_id)
    if not vehicle:
        return jsonify({"ok": False, "error": "Vehicle not found"}), 404
    events = store.get_vehicle_events(vehicle_id)

    # Enrich with public NHTSA VIN decode (factory data, not guesses)
    nhtsa = None
    vin = vehicle.get("vin")
    if vin:
        try:
            from vin_decode import decode_vin
            nhtsa = decode_vin(vin)
        except Exception:
            nhtsa = None

    if nhtsa:
        # Fill blanks only — never overwrite a verified listing value with empty
        fill_map = {
            "year": "year",
            "make": "make",
            "model": "model",
            "trim": "trim",
            "body_style": "body_style",
            "drivetrain": "drivetrain",
            "transmission": "transmission",
            "engine": "engine",
        }
        for src, dest in fill_map.items():
            if nhtsa.get(src) and not vehicle.get(dest):
                vehicle[dest] = nhtsa[src]
        # Title-case make for display
        if vehicle.get("make"):
            vehicle["make"] = str(vehicle["make"]).title()
        vehicle["nhtsa"] = {
            "engine_hp": nhtsa.get("engine_hp"),
            "engine_displacement_l": nhtsa.get("engine_displacement_l"),
            "engine_cylinders": nhtsa.get("engine_cylinders"),
            "engine_configuration": nhtsa.get("engine_configuration"),
            "fuel": nhtsa.get("fuel"),
            "drivetrain": nhtsa.get("drivetrain"),
            "body_style": nhtsa.get("body_style"),
            "source": "NHTSA vPIC",
        }

    # Enrich blanks (stock #, photo, mileage, condition, torque, towing) from the
    # vehicle's own detail page on the dealer site. Only runs when
    # something is actually still missing, or when explicitly refreshed.
    force_vdp = request.args.get("refresh_vdp") == "1"
    still_missing = not all([
        vehicle.get("stock_number"),
        vehicle.get("image_url"),
        vehicle.get("mileage"),
        vehicle.get("condition"),
        vehicle.get("torque"),
        vehicle.get("engine_hp"),
        vehicle.get("transmission"),
    ])
    listing_path = str(vehicle.get("listing_url") or "").lower()
    is_new_listing = str(vehicle.get("condition") or "").strip().lower() == "new" or "/new/" in listing_path
    # A previous CarDex version incorrectly stored the VIN's last 8 as the
    # stock number for some USED vehicles. Treat that exact pattern as stale
    # for used inventory so the public Lithia VDP gets a chance to replace it.
    listing_path = str(vehicle.get("listing_url") or "").lower()
    is_used_listing = str(vehicle.get("condition") or "").strip().lower() in ("used", "certified pre-owned", "cpo") or "/used/" in listing_path or "/certified/" in listing_path
    if is_used_listing and vehicle.get("vin") and vehicle.get("stock_number"):
        if str(vehicle["stock_number"]).strip().upper() == str(vehicle["vin"]).strip().upper()[-8:]:
            vehicle["stock_number"] = None

    if vehicle.get("listing_url") and (still_missing or force_vdp):
        try:
            from vdp_scraper import scrape_vdp
            vdp_data = scrape_vdp(vehicle["listing_url"], known_vin=vehicle.get("vin"))
        except Exception:
            vdp_data = {}
        # Always run the store cleanup path. This removes an old USED VIN-suffix
        # stock number even if a public VDP request temporarily returns no data.
        try:
            store.fill_vdp_fields(vehicle_id, vdp_data or {})
        except Exception:
            pass
        if vdp_data:
            # NEW Lithia rule: the stock number shown in CarDex is always
            # the last 8 characters of the VIN. Do not substitute a different
            # stock value for NEW vehicles. USED vehicles continue to use the
            # actual stock number found on the public Lithia VDP.
            condition_now = str(vdp_data.get("condition") or vehicle.get("condition") or "").strip().lower()
            listing_path = str(vehicle.get("listing_url") or "").lower()
            is_new = condition_now == "new" or "/new/" in listing_path
            if is_new and vehicle.get("vin"):
                vin_text = str(vehicle["vin"]).strip().upper()
                if len(vin_text) >= 8:
                    vdp_data["stock_number"] = vin_text[-8:]
                    vdp_data["condition"] = vdp_data.get("condition") or "New"

            store.fill_vdp_fields(vehicle_id, vdp_data)
            for f in ("stock_number", "image_url", "mileage", "condition", "torque", "engine_hp", "transmission", "engine", "towing_capacity", "flat_tow"):
                if vdp_data.get(f) is not None and vdp_data.get(f) != "":
                    vehicle[f] = vdp_data[f]
            # For NEW inventory, prefer the dealership website's mileage when
            # it explicitly publishes one. Do not invent a mileage value.
            if is_new and vdp_data.get("mileage") is not None:
                vehicle["mileage"] = vdp_data["mileage"]

    # Final NEW-vehicle stock fallback. If the public VDP did not expose a
    # stock number at all, Lithia's NEW stock number is the VIN's last 8.
    # USED vehicles intentionally do not use this fallback.
    # Final NEW-vehicle rule: always use VIN last 8 as stock number.
    # USED vehicles intentionally do not use this fallback.
    listing_path = str(vehicle.get("listing_url") or "").lower()
    if ((str(vehicle.get("condition") or "").strip().lower() == "new" or "/new/" in listing_path)
            and vehicle.get("vin")):
        vin_text = str(vehicle["vin"]).strip().upper()
        if len(vin_text) >= 8:
            vehicle["stock_number"] = vin_text[-8:]
            vehicle["condition"] = vehicle.get("condition") or "New"
            try:
                store.fill_vdp_fields(vehicle_id, {"stock_number": vehicle["stock_number"], "condition": vehicle["condition"]})
            except Exception:
                pass

    # Sales Brain is built server-side so the report uses the same logic for
    # every vehicle. Exact VIN/listing data wins; only stable same-year/model
    # fallback facts are added when the exact field is unavailable.
    # Sales Brain must never be able to take down the vehicle report.
    # If a scraped field has an unexpected type/value, return the vehicle
    # report with a safe fallback instead of a 500 error.
    try:
        vehicle["sales_brain"] = build_sales_brain(vehicle, nhtsa)
    except Exception as exc:
        vehicle["sales_brain"] = {
            "points": [],
            "objections": ["Sales Brain could not process this vehicle yet; verify the listing details before quoting configuration-specific claims."],
            "pitch": "Use the vehicle's verified listing details and ask the customer what matters most to them.",
            "competitors": [],
            "questions": ["What is the #1 thing this vehicle needs to do for you?"],
            "demo": ["Demonstrate the actual equipment shown on this VIN/listing."],
            "fallback": {},
            "resolved": {},
            "error": str(exc),
        }

    return jsonify({"vehicle": vehicle, "events": events, "nhtsa": nhtsa})


@app.get("/api/search")
def api_search():
    return api_vehicles()


@app.get("/api/events")
def api_events():
    dealership_id = request.args.get("dealership_id", type=int)
    limit = min(request.args.get("limit", 50, type=int), 200)
    events = store.recent_events(dealership_id=dealership_id, limit=limit)
    return jsonify({"events": events})


@app.get("/")
def index():
    return render_template_string(INDEX_HTML, version=__version__)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
