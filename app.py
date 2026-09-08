"""
CarDex V2.4.1 — vehicle list + clickable sales report.
Garage-door boot loader, neon credit, ambient bay animation.
Replace app.py with this file on GitHub.
"""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from flask import Flask, jsonify, render_template_string, request

from scraper import InventoryEngine, list_adapters
from store import InventoryStore
from sales_brain import build_sales_brain

__version__ = "2.4.1-garage-boot"

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
      --neon: #ff4fd8;
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

    /* ================= GARAGE DOOR BOOT LOADER ================= */
    #garage {
      position: fixed; inset: 0; z-index: 999;
      display: flex; flex-direction: column; justify-content: flex-end;
      background: #030207;
      transition: opacity .6s ease .1s;
    }
    #garage.done { opacity: 0; pointer-events: none; }
    .garage-glow {
      position: absolute; left: 0; right: 0; bottom: 0; height: 0;
      background: linear-gradient(180deg, transparent, rgba(168,85,247,.35));
      transition: height .8s ease;
      pointer-events: none;
    }
    #garage.open .garage-glow { height: 100%; }
    .garage-door {
      position: relative; width: 100%; height: 100%;
      display: flex; flex-direction: column;
      transform: translateY(0);
      transition: transform 1.9s cubic-bezier(.65,0,.35,1);
      will-change: transform;
    }
    #garage.open .garage-door { transform: translateY(-104%); }
    .door-panel {
      flex: 1; position: relative;
      background: linear-gradient(180deg, #16101f 0%, #0d0916 55%, #090512 100%);
      border-bottom: 2px solid rgba(0,0,0,.7);
      box-shadow: inset 0 1px 0 rgba(178,122,255,.14), inset 0 -1px 0 rgba(0,0,0,.8);
    }
    .door-panel::after {
      content: ""; position: absolute; inset: 10% 6%;
      border: 1px solid rgba(168,85,247,.12); border-radius: 3px;
    }
    .door-seal {
      height: 10px; flex: none;
      background: linear-gradient(180deg, #241733, #120a1e);
      box-shadow: 0 2px 24px 4px rgba(232,121,249,.55);
      border-top: 1px solid rgba(232,121,249,.5);
    }
    .garage-label {
      position: absolute; top: 50%; left: 50%; transform: translate(-50%,-50%);
      font-family: var(--mono); font-size: .72rem; letter-spacing: .5em;
      text-transform: uppercase; color: var(--muted); text-align: center;
    }
    .garage-label b {
      display: block; font-size: 1.9rem; letter-spacing: -.02em; margin-bottom: .8rem;
      background: linear-gradient(92deg, #f5d0fe, #a855f7 55%, #67e8f9);
      -webkit-background-clip: text; background-clip: text; color: transparent;
      font-family: Inter, sans-serif; font-weight: 900;
    }
    .garage-label .hint { animation: blink 1.6s ease-in-out infinite; color: var(--dim); }

    /* ================= NEON "MADE BY ELIJAH" ================= */
    .neon-credit {
      position: fixed; right: 18px; bottom: 14px; z-index: 80;
      font-family: var(--mono); font-size: .68rem; font-weight: 700;
      letter-spacing: .22em; text-transform: uppercase;
      color: #ffd7f4; pointer-events: none; user-select: none;
      text-shadow:
        0 0 6px rgba(255,79,216,.9),
        0 0 18px rgba(255,79,216,.65),
        0 0 42px rgba(255,79,216,.4);
      animation: neonFlicker 4.5s linear infinite;
    }
    .neon-credit::before {
      content: ""; position: absolute; inset: -8px -12px;
      border: 1px solid rgba(255,79,216,.28); border-radius: 4px;
      box-shadow: 0 0 18px rgba(255,79,216,.22), inset 0 0 14px rgba(255,79,216,.1);
    }
    @keyframes neonFlicker {
      0%, 6.5%, 8%, 100% { opacity: 1; }
      7% { opacity: .55; }
      52% { opacity: 1; }
      52.6% { opacity: .7; }
      53.2% { opacity: 1; }
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

    /* ================= SIGNATURE BAY RADAR =================
       One clean animated element: a slow light pulse that travels
       around the console card border, like a shop bay sensor loop. */
    @property --bayAngle { syntax: "<angle>"; initial-value: 0deg; inherits: false; }
    .bay-frame { position: relative; border-radius: 5px; padding: 1px; margin-bottom: 1.1rem; }
    .bay-frame::before {
      content: ""; position: absolute; inset: 0; border-radius: 5px; padding: 1px;
      background: conic-gradient(from var(--bayAngle),
        transparent 0deg, transparent 300deg,
        rgba(232,121,249,.05) 320deg, rgba(232,121,249,.85) 348deg,
        rgba(103,232,249,.9) 356deg, transparent 360deg);
      -webkit-mask: linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0);
      -webkit-mask-composite: xor; mask-composite: exclude;
      animation: bayOrbit 7s linear infinite;
      pointer-events: none;
    }
    @keyframes bayOrbit { to { --bayAngle: 360deg; } }
    .bay-frame .card { margin-bottom: 0; animation: none; }

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
      #garage { display: none !important; }
    }
  </style>
</head>
<body>

  <!-- Garage door boot loader -->
  <div id="garage" aria-hidden="true">
    <div class="garage-glow"></div>
    <div class="garage-door">
      <div class="garage-label">
        <b>CarDex</b>
        <span class="hint">Opening bay door…</span>
      </div>
      <div class="door-panel"></div>
      <div class="door-panel"></div>
      <div class="door-panel"></div>
      <div class="door-panel"></div>
      <div class="door-seal"></div>
    </div>
  </div>

  <!-- Neon credit -->
  <div class="neon-credit">Made by Elijah</div>

  <!-- Ambience -->
  <div class="amb">
    <div class="amb-aurora"></div>
    <div class="amb-grid"></div>
    <div class="amb-scan"></div>
    <div class="amb-sweep"></div>
  </div>

  <header>
    <div class="mark">
      <span class="slash"></span>
      <span class="car">Car</span><span class="dex">Dex</span>
      <span class="tag">Midnight Performance Desk</span>
    </div>
    <span class="badge">V{{ version }}</span>
    <div class="spacer"></div>
    <div class="live"><span class="dot"></span> Online</div>
  </header>

  <main>
    <!-- Gauges -->
    <div class="gauges" id="gauges">
      <div class="gauge" style="animation-delay:.05s">
        <div class="k">Units</div><div class="v" id="g-units">—</div>
        <div class="ticks" data-ticks></div>
      </div>
      <div class="gauge" style="animation-delay:.12s">
        <div class="k">Avg price</div><div class="v hot" id="g-avg">—</div>
        <div class="ticks" data-ticks></div>
      </div>
      <div class="gauge" style="animation-delay:.19s">
        <div class="k">VIN verified</div><div class="v" id="g-vin">—</div>
        <div class="ticks" data-ticks></div>
      </div>
      <div class="gauge" style="animation-delay:.26s">
        <div class="k">Photographed</div><div class="v" id="g-photo">—</div>
        <div class="ticks" data-ticks></div>
      </div>
    </div>

    <!-- List view -->
    <div id="list-view">
      <div class="bay-frame">
        <div class="card">
          <h2>Inventory Console</h2>
          <div class="search-row">
            <input type="text" id="q" placeholder="Search year / make / model / VIN / stock #…" />
            <button id="btn-search">Search</button>
          </div>
          <div class="actions">
            <button class="secondary" id="btn-scan">Scan Lithia Missoula</button>
            <button class="secondary" id="btn-backfill">Backfill Data</button>
            <button class="ghost" id="btn-all">Show All Saved</button>
          </div>
          <div class="status" id="status"></div>
        </div>
      </div>

      <div class="card" style="animation-delay:.3s">
        <h2>Bay — select a unit</h2>
        <div id="vehicles">
          <div class="empty">Search or scan to load inventory</div>
        </div>
      </div>
    </div>

    <!-- Report view -->
    <div id="report-view">
      <div class="back-row">
        <button class="ghost" id="btn-back">← Back to bay</button>
      </div>
      <div id="report-body">
        <div class="card"><div class="empty">Loading…</div></div>
      </div>
    </div>
  </main>

  <script>
    const $ = (s) => document.querySelector(s);
    const statusEl = $("#status");

    /* ---------- Garage door boot ---------- */
    window.addEventListener("load", () => {
      setTimeout(() => {
        const g = $("#garage");
        g.classList.add("open");
        setTimeout(() => g.classList.add("done"), 2000);
        setTimeout(() => g.remove(), 2800);
      }, 650);
    });

    /* ---------- Ticks decoration ---------- */
    document.querySelectorAll("[data-ticks]").forEach((el) => {
      for (let i = 0; i < 12; i++) {
        const t = document.createElement("i");
        if (Math.random() > 0.45) t.classList.add("on");
        el.appendChild(t);
      }
    });

    /* ---------- Helpers ---------- */
    const fmtMoney = (n) =>
      n == null || isNaN(n) ? "—" : "$" + Number(n).toLocaleString(undefined, { maximumFractionDigits: 0 });
    const setStatus = (msg, cls = "") => { statusEl.textContent = msg; statusEl.className = "status " + cls; };
    const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

    async function api(path, opts) {
      const r = await fetch(path, opts);
      const j = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(j.error || ("HTTP " + r.status));
      return j;
    }

    /* ---------- Gauges ---------- */
    function renderGauges(summary) {
      if (!summary) return;
      $("#g-units").textContent = summary.units ?? summary.count ?? "—";
      $("#g-avg").textContent = fmtMoney(summary.avg_price);
      $("#g-vin").textContent = summary.vin_verified ?? summary.with_vin ?? "—";
      $("#g-photo").textContent = summary.photographed ?? summary.with_photo ?? "—";
    }

    /* ---------- Vehicle list ---------- */
    function renderVehicles(vehicles) {
      const box = $("#vehicles");
      if (!vehicles || !vehicles.length) {
        box.innerHTML = '<div class="empty">No units found</div>';
        return;
      }
      box.innerHTML = vehicles.map((v, i) => `
        <div class="vehicle" style="animation-delay:${Math.min(i * 0.04, 0.5)}s"
             tabindex="0" role="button" data-id="${v.id}">
          <div class="v-main">
            <div class="title">${esc([v.year, v.make, v.model].filter(Boolean).join(" ")) || "Unknown unit"}${v.trim ? " " + esc(v.trim) : ""}</div>
            <div class="meta">
              ${v.condition ? `<span class="tagchip">${esc(v.condition)}</span>` : ""}
              ${v.stock_number ? `<span class="tagchip">STK ${esc(v.stock_number)}</span>` : ""}
              ${v.vin ? `<span class="tagchip">VIN ${esc(v.vin)}</span>` : ""}
              ${v.mileage != null ? `<span class="tagchip">${Number(v.mileage).toLocaleString()} mi</span>` : ""}
              ${v.exterior_color ? `<span class="tagchip">${esc(v.exterior_color)}</span>` : ""}
            </div>
          </div>
          <div class="price">${fmtMoney(v.price)}</div>
        </div>`).join("");
      box.querySelectorAll(".vehicle").forEach((el) => {
        const open = () => openReport(el.dataset.id);
        el.addEventListener("click", open);
        el.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); open(); } });
      });
    }

    async function loadVehicles(params = "") {
      $("#vehicles").innerHTML = '<div class="loading-shimmer"></div>'.repeat(4);
      try {
        const j = await api("/api/vehicles" + params);
        renderVehicles(j.vehicles);
        renderGauges(j.summary);
        setStatus(j.count + " unit(s) on the board", "ok");
      } catch (e) {
        $("#vehicles").innerHTML = '<div class="empty">Load failed</div>';
        setStatus(e.message, "err");
      }
    }

    /* ---------- Report ---------- */
    function spec(label, value, verify = false) {
      const show = value == null || value === "" ? "—" : esc(value);
      return `<div class="spec"><div class="label">${label}</div>
        <div class="value${verify && (value == null || value === "") ? " verify" : ""}">${verify && (value == null || value === "") ? "Verify" : show}</div></div>`;
    }

    function renderReport(v, events) {
      const sb = v.sales_brain || {};
      const title = [v.year, v.make, v.model].filter(Boolean).join(" ") || "Vehicle";
      $("#report-body").innerHTML = `
        <div class="card">
          <div class="report-hero">
            <div class="report-photo">
              ${v.image_url ? `<img src="${esc(v.image_url)}" alt="${esc(title)}" loading="lazy">` : "No photo"}
            </div>
            <div style="flex:1;min-width:240px">
              <div class="report-title">${esc(title)}${v.trim ? " " + esc(v.trim) : ""}</div>
              <div class="report-price">${fmtMoney(v.price)}</div>
              <div class="report-sub">${esc(v.condition || "")} ${v.stock_number ? "· STK " + esc(v.stock_number) : ""}</div>
              <div class="chips">
                ${v.vin ? `<span class="chip ok">VIN ${esc(v.vin)}</span>` : `<span class="chip warn">No VIN</span>`}
                ${v.mileage != null ? `<span class="chip">${Number(v.mileage).toLocaleString()} mi</span>` : ""}
                ${v.dealership_name ? `<span class="chip">${esc(v.dealership_name)}</span>` : ""}
              </div>
              ${v.listing_url ? `<p style="margin-top:.8rem"><a class="link" href="${esc(v.listing_url)}" target="_blank" rel="noopener">View dealer listing ↗</a></p>` : ""}
            </div>
          </div>
        </div>

        <div class="card">
          <h2>Specification</h2>
          <div class="grid2">
            ${spec("Engine", v.engine)}
            ${spec("Horsepower", v.engine_hp ? v.engine_hp + " hp" : null)}
            ${spec("Torque", v.torque)}
            ${spec("Transmission", v.transmission)}
            ${spec("Drivetrain", v.drivetrain)}
            ${spec("Body style", v.body_style)}
            ${spec("Fuel", v.fuel || (v.nhtsa && v.nhtsa.fuel))}
            ${spec("Towing", v.towing_capacity)}
            ${spec("Exterior", v.exterior_color)}
            ${spec("Interior", v.interior_color)}
          </div>
        </div>

        ${(sb.points && sb.points.length) ? `<div class="card"><h2>Selling Points</h2>${sb.points.map(p => `<div class="bullet">${esc(p)}</div>`).join("")}</div>` : ""}
        ${sb.pitch ? `<div class="card"><h2>Elevator Pitch</h2><div class="pitch">${esc(sb.pitch)}</div></div>` : ""}
        ${(sb.objections && sb.objections.length) ? `<div class="card"><h2>Objection Handling</h2>${sb.objections.map(o => `<div class="bullet warn">${esc(o)}</div>`).join("")}</div>` : ""}
        ${(sb.questions && sb.questions.length) ? `<div class="card"><h2>Ask the Customer</h2>${sb.questions.map(q => `<div class="bullet">${esc(q)}</div>`).join("")}</div>` : ""}
        ${(events && events.length) ? `<div class="card"><h2>History</h2>${events.map(e => `<div class="bullet">${esc(e.event_type || e.type || "event")} — ${esc(e.created_at || "")}</div>`).join("")}</div>` : ""}
      `;
      $("#list-view").style.display = "none";
      $("#report-view").style.display = "block";
      window.scrollTo({ top: 0, behavior: "smooth" });
    }

    async function openReport(id) {
      $("#list-view").style.display = "none";
      $("#report-view").style.display = "block";
      $("#report-body").innerHTML = '<div class="card"><div class="loading-shimmer"></div><div class="loading-shimmer"></div><div class="loading-shimmer"></div></div>';
      try {
        const j = await api("/api/vehicles/" + id);
        renderReport(j.vehicle, j.events);
      } catch (e) {
        $("#report-body").innerHTML = `<div class="card"><div class="empty">Report failed: ${esc(e.message)}</div></div>`;
      }
    }

    $("#btn-back").addEventListener("click", () => {
      $("#report-view").style.display = "none";
      $("#list-view").style.display = "block";
    });

    /* ---------- Actions ---------- */
    $("#btn-search").addEventListener("click", () => {
      const q = $("#q").value.trim();
      loadVehicles(q ? "?q=" + encodeURIComponent(q) : "");
    });
    $("#q").addEventListener("keydown", (e) => { if (e.key === "Enter") $("#btn-search").click(); });
    $("#btn-all").addEventListener("click", () => { $("#q").value = ""; loadVehicles(); });

    $("#btn-scan").addEventListener("click", async (e) => {
      const btn = e.currentTarget;
      btn.disabled = true; btn.classList.add("busy");
      setStatus("Scanning Lithia Missoula…");
      try {
        const j = await api("/api/discover", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ inventory_url: "https://www.lithia.com/inventory.htm", name: "Lithia Missoula" }),
        });
        setStatus(j.ok ? "Scan complete" : (j.error || "Scan finished"), j.ok ? "ok" : "err");
        loadVehicles();
      } catch (err) { setStatus(err.message, "err"); }
      finally { btn.disabled = false; btn.classList.remove("busy"); }
    });

    $("#btn-backfill").addEventListener("click", async (e) => {
      const btn = e.currentTarget;
      btn.disabled = true; btn.classList.add("busy");
      setStatus("Backfilling public data…");
      try {
        const j = await api("/api/backfill_nhtsa", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
        setStatus(`Backfill: ${j.updated} updated, ${j.remaining} remaining`, "ok");
        loadVehicles($("#q").value.trim() ? "?q=" + encodeURIComponent($("#q").value.trim()) : "");
      } catch (err) { setStatus(err.message, "err"); }
      finally { btn.disabled = false; btn.classList.remove("busy"); }
    });

    /* ---------- Initial load ---------- */
    loadVehicles();
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
        fill_map = {
            "year": "year", "make": "make", "model": "model", "trim": "trim",
            "body_style": "body_style", "drivetrain": "drivetrain",
            "transmission": "transmission", "engine": "engine",
        }
        for src, dest in fill_map.items():
            if nhtsa.get(src) and not vehicle.get(dest):
                vehicle[dest] = nhtsa[src]
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

    force_vdp = request.args.get("refresh_vdp") == "1"
    still_missing = not all([
        vehicle.get("stock_number"), vehicle.get("image_url"), vehicle.get("mileage"),
        vehicle.get("condition"), vehicle.get("torque"), vehicle.get("engine_hp"),
        vehicle.get("transmission"),
    ])
    listing_path = str(vehicle.get("listing_url") or "").lower()
    is_used_listing = (
        str(vehicle.get("condition") or "").strip().lower() in ("used", "certified pre-owned", "cpo")
        or "/used/" in listing_path or "/certified/" in listing_path
    )
    if is_used_listing and vehicle.get("vin") and vehicle.get("stock_number"):
        if str(vehicle["stock_number"]).strip().upper() == str(vehicle["vin"]).strip().upper()[-8:]:
            vehicle["stock_number"] = None

    if vehicle.get("listing_url") and (still_missing or force_vdp):
        try:
            from vdp_scraper import scrape_vdp
            vdp_data = scrape_vdp(vehicle["listing_url"], known_vin=vehicle.get("vin"))
        except Exception:
            vdp_data = {}
        try:
            store.fill_vdp_fields(vehicle_id, vdp_data or {})
        except Exception:
            pass
        if vdp_data:
            condition_now = str(vdp_data.get("condition") or vehicle.get("condition") or "").strip().lower()
            listing_path = str(vehicle.get("listing_url") or "").lower()
            is_new = condition_now == "new" or "/new/" in listing_path
            if is_new and vehicle.get("vin"):
                vin_text = str(vehicle["vin"]).strip().upper()
                if len(vin_text) >= 8:
                    vdp_data["stock_number"] = vin_text[-8:]
                    vdp_data["condition"] = vdp_data.get("condition") or "New"

            store.fill_vdp_fields(vehicle_id, vdp_data)
            for f in ("stock_number", "image_url", "mileage", "condition", "torque",
                      "engine_hp", "transmission", "engine", "towing_capacity", "flat_tow"):
                if vdp_data.get(f) is not None and vdp_data.get(f) != "":
                    vehicle[f] = vdp_data[f]
            if is_new and vdp_data.get("mileage") is not None:
                vehicle["mileage"] = vdp_data["mileage"]

    # Final NEW-vehicle rule: always use VIN last 8 as stock number.
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

    # Sales Brain must never take down the vehicle report.
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
