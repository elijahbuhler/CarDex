"""
CarDex V2.5.0 — vehicle list + clickable sales report.
Garage-door boot loader with neon pink sign, scroll-reveal report sections.
Replace app.py with this file on GitHub.
"""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from flask import Flask, jsonify, render_template_string, request

from scraper import InventoryEngine, list_adapters
from store import InventoryStore
from sales_brain import build_sales_brain

__version__ = "2.5.1-scan-fix"

# Edit this if your Lithia Missoula rooftop URL is different.
LITHIA_MISSOULA_URL = os.environ.get(
    "CARDEX_LITHIA_URL",
    "https://www.lithiachryslermissoula.com/all-inventory/index.htm",
)
LITHIA_MISSOULA_NAME = "Lithia Missoula"

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
  <title>CarDex — The Ultimate Car DataBase</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=JetBrains+Mono:wght@400;600;700&family=Monoton&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg: #05030a;
      --panel: rgba(15, 9, 24, 0.66);
      --ink: #ede8f7;
      --muted: #8f83ab;
      --dim: #6a5f85;
      --line: rgba(140, 92, 246, 0.16);
      --line-hot: rgba(178, 122, 255, 0.5);
      --violet: #a855f7;
      --violet-deep: #6d28d9;
      --magenta: #e879f9;
      --neon: #ff4fd8;
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
    body.booting { overflow: hidden; }

    /* ================= GARAGE DOOR BOOT LOADER ================= */
    #garage {
      position: fixed; inset: 0; z-index: 999;
      background: #030207;
      transition: opacity .7s ease .35s;
    }
    #garage.done { opacity: 0; pointer-events: none; }
    .garage-door {
      position: relative; width: 100%; height: 100%;
      display: flex; flex-direction: column;
      transform: translateY(0);
      transition: transform 2.4s cubic-bezier(.65,0,.35,1);
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
      box-shadow: 0 2px 24px 4px rgba(255,79,216,.55);
      border-top: 1px solid rgba(255,79,216,.6);
    }

    /* ---- Neon sign on the door ---- */
    .neon-sign {
      position: absolute; top: 46%; left: 50%; transform: translate(-50%,-50%);
      text-align: center; z-index: 3; padding: 2.2rem 3rem;
      border: 2px solid rgba(255,79,216,.35); border-radius: 14px;
      box-shadow: 0 0 26px rgba(255,79,216,.35), inset 0 0 34px rgba(255,79,216,.12);
      animation: signOn 3.2s ease-in-out infinite;
      max-width: 92vw;
    }
    .neon-sign .n-title {
      font-family: Monoton, Inter, cursive; font-weight: 400;
      font-size: clamp(2.6rem, 11vw, 6rem); line-height: 1; letter-spacing: .04em;
      color: #ffe3f8;
      text-shadow:
        0 0 6px #fff0fb, 0 0 14px var(--neon), 0 0 32px var(--neon),
        0 0 68px rgba(255,79,216,.85), 0 0 120px rgba(255,79,216,.55);
      animation: neonFlicker 5s linear infinite;
    }
    .neon-sign .n-sub {
      margin-top: .9rem; font-family: var(--mono); font-weight: 700;
      font-size: clamp(.72rem, 2.6vw, 1.05rem); letter-spacing: .34em; text-transform: uppercase;
      color: #ffd7f4;
      text-shadow: 0 0 6px rgba(255,79,216,.9), 0 0 18px rgba(255,79,216,.7), 0 0 40px rgba(255,79,216,.4);
    }
    .neon-sign .n-credit {
      position: absolute; right: -8px; bottom: -2.6rem;
      font-family: var(--mono); font-weight: 700;
      font-size: clamp(.6rem, 2vw, .8rem); letter-spacing: .28em; text-transform: uppercase;
      color: #ffc9ef; white-space: nowrap;
      text-shadow: 0 0 6px rgba(255,79,216,.9), 0 0 20px rgba(255,79,216,.6);
      animation: neonFlicker 6.4s linear infinite .4s;
    }
    @media (max-width: 720px) {
      .neon-sign { padding: 1.6rem 1.4rem; }
      .neon-sign .n-credit { right: 50%; transform: translateX(50%); }
    }
    @keyframes signOn { 0%,100% { box-shadow: 0 0 26px rgba(255,79,216,.35), inset 0 0 34px rgba(255,79,216,.12); }
                        50% { box-shadow: 0 0 44px rgba(255,79,216,.55), inset 0 0 46px rgba(255,79,216,.2); } }
    @keyframes neonFlicker {
      0%, 6.5%, 8%, 100% { opacity: 1; }
      7% { opacity: .5; }
      52% { opacity: 1; }
      52.6% { opacity: .65; }
      53.2% { opacity: 1; }
    }

    /* small persistent neon credit in the app */
    .neon-credit {
      position: fixed; right: 18px; bottom: 14px; z-index: 80;
      font-family: var(--mono); font-size: .68rem; font-weight: 700;
      letter-spacing: .22em; text-transform: uppercase;
      color: #ffd7f4; pointer-events: none; user-select: none;
      text-shadow: 0 0 6px rgba(255,79,216,.9), 0 0 18px rgba(255,79,216,.65), 0 0 42px rgba(255,79,216,.4);
      animation: neonFlicker 4.5s linear infinite;
    }
    .neon-credit::before {
      content: ""; position: absolute; inset: -8px -12px;
      border: 1px solid rgba(255,79,216,.28); border-radius: 4px;
      box-shadow: 0 0 18px rgba(255,79,216,.22), inset 0 0 14px rgba(255,79,216,.1);
    }

    /* ---------- Ambience ---------- */
    .amb { position: fixed; inset: 0; pointer-events: none; z-index: -1; }
    .amb-aurora {
      position: absolute; inset: -30%;
      background:
        radial-gradient(38% 28% at 16% 10%, rgba(168,85,247,.30), transparent 70%),
        radial-gradient(32% 24% at 84% 6%, rgba(232,121,249,.18), transparent 70%),
        radial-gradient(46% 30% at 62% 92%, rgba(109,40,217,.26), transparent 70%);
      filter: blur(6px);
      animation: aurora 22s ease-in-out infinite alternate;
    }
    @keyframes aurora {
      0% { transform: translate3d(-2%,0,0) scale(1); }
      50% { transform: translate3d(1%,1.5%,0) scale(1.05); }
      100% { transform: translate3d(2%,-1%,0) scale(1.08); }
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

    /* ---------- Header ---------- */
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
      opacity: .65; background-size: 200% 100%; animation: railShift 7s linear infinite;
    }
    @keyframes railShift { from { background-position: 0% 0; } to { background-position: 200% 0; } }
    .mark { display: flex; align-items: baseline; gap: .1rem; }
    .mark .slash {
      display: inline-block; width: 3px; height: 22px; margin-right: .55rem;
      background: linear-gradient(180deg, var(--magenta), var(--violet-deep));
      transform: skewX(-18deg); border-radius: 2px; box-shadow: 0 0 14px rgba(217,70,239,.7);
    }
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
    }
    .spacer { flex: 1; }
    .live { display: flex; align-items: center; gap: .45rem; font-family: var(--mono); font-size: .62rem; color: var(--muted); letter-spacing: .18em; text-transform: uppercase; }
    .dot { width: 6px; height: 6px; border-radius: 50%; background: var(--green); box-shadow: 0 0 10px var(--green); animation: blink 2s ease-in-out infinite; }
    @keyframes blink { 0%,100% { opacity: 1 } 50% { opacity: .3 } }

    main { max-width: 1180px; margin: 0 auto; padding: 1.6rem 1.25rem 4rem; }

    .card {
      position: relative; background: var(--panel); border: 1px solid var(--line);
      border-radius: 4px; padding: 1.25rem 1.4rem; margin-bottom: 1.1rem;
      backdrop-filter: blur(14px); -webkit-backdrop-filter: blur(14px);
      box-shadow: 0 22px 60px rgba(0,0,0,.55), inset 0 1px 0 rgba(255,255,255,.035);
      transition: border-color .25s ease, box-shadow .25s ease, transform .25s cubic-bezier(.2,.7,.3,1);
    }
    .card::before, .card::after {
      content: ""; position: absolute; width: 12px; height: 12px; pointer-events: none;
      border-color: var(--line-hot); opacity: .8;
    }
    .card::before { top: -1px; left: -1px; border-top: 1px solid; border-left: 1px solid; }
    .card::after { bottom: -1px; right: -1px; border-bottom: 1px solid; border-right: 1px solid; }
    .card:hover { border-color: rgba(178,122,255,.34); box-shadow: 0 28px 70px rgba(76,29,149,.4); transform: translateY(-2px); }

    h2 {
      font-family: var(--mono); font-size: .63rem; color: var(--muted); font-weight: 700;
      text-transform: uppercase; letter-spacing: .26em; margin-bottom: .95rem;
      display: flex; align-items: center; gap: .7rem;
    }
    h2::after { content: ""; flex: 1; height: 1px; background: linear-gradient(90deg, var(--line-hot), transparent); }

    .gauges { display: grid; grid-template-columns: repeat(4, 1fr); gap: .7rem; margin-bottom: 1.1rem; }
    @media (max-width: 760px) { .gauges { grid-template-columns: repeat(2, 1fr); } }
    .gauge {
      position: relative; overflow: hidden;
      background: linear-gradient(180deg, rgba(21,13,33,.8), rgba(10,6,17,.8));
      border: 1px solid var(--line); border-radius: 4px; padding: .85rem .95rem .95rem;
      transition: transform .22s ease, border-color .22s ease;
    }
    .gauge:hover { transform: translateY(-3px); border-color: var(--line-hot); }
    .gauge .k { font-family: var(--mono); font-size: .58rem; text-transform: uppercase; letter-spacing: .22em; color: var(--dim); }
    .gauge .v { font-family: var(--mono); font-size: 1.55rem; font-weight: 700; margin-top: .3rem; color: #fff; }
    .gauge .v.hot { background: linear-gradient(92deg, #f5d0fe, #a855f7); -webkit-background-clip: text; background-clip: text; color: transparent; }
    .ticks { display: flex; gap: 3px; margin-top: .6rem; }
    .ticks i { display: block; flex: 1; height: 4px; border-radius: 1px; background: rgba(168,85,247,.16); }
    .ticks i.on { background: linear-gradient(90deg, var(--violet), var(--magenta)); box-shadow: 0 0 8px rgba(168,85,247,.55); }

    .search-row { display: flex; gap: .6rem; }
    input[type="text"] {
      flex: 1; background: rgba(5,3,10,.9); border: 1px solid var(--line); border-radius: 4px;
      padding: .9rem 1rem; color: var(--ink); font-size: .98rem; outline: none; font-family: var(--mono);
      transition: border-color .2s ease, box-shadow .2s ease;
    }
    input[type="text"]::placeholder { color: #5d5378; }
    input[type="text"]:focus { border-color: var(--violet); box-shadow: 0 0 0 3px rgba(168,85,247,.16); }

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
    button:disabled { opacity: .45; cursor: not-allowed; }
    button.secondary { background: rgba(168,85,247,.08); border: 1px solid var(--line-hot); color: #e9d5ff; box-shadow: none; }
    button.ghost { background: transparent; border: 1px solid var(--line); color: var(--muted); box-shadow: none; }
    button.busy::after {
      content: ""; position: absolute; inset: 0;
      background: linear-gradient(90deg, transparent, rgba(255,255,255,.25), transparent);
      background-size: 200% 100%; animation: railShift 1.1s linear infinite;
    }
    .actions { display: flex; gap: .55rem; margin-top: .85rem; flex-wrap: wrap; }

    .status { font-family: var(--mono); font-size: .74rem; color: var(--muted); margin-top: .85rem; min-height: 1.3em; }
    .status.ok { color: var(--green); }
    .status.err { color: var(--red); }

    .vehicle {
      position: relative; display: flex; gap: 1rem; align-items: center; flex-wrap: wrap;
      background: linear-gradient(90deg, rgba(14,8,23,.85), rgba(9,5,15,.7));
      border: 1px solid var(--line); border-left: 2px solid rgba(168,85,247,.35);
      border-radius: 3px; padding: .9rem 1.1rem; margin-bottom: .55rem; cursor: pointer;
      transition: transform .2s cubic-bezier(.2,.7,.3,1), border-color .2s ease, background .2s ease, box-shadow .2s ease;
      animation: itemIn .4s cubic-bezier(.2,.7,.3,1) both;
    }
    .vehicle:hover { transform: translateX(6px); border-left-color: var(--magenta); border-color: var(--line-hot); box-shadow: 0 14px 34px rgba(76,29,149,.35); }
    @keyframes itemIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: none; } }
    .v-main { flex: 1; min-width: 210px; }
    .vehicle .title { font-size: 1.02rem; font-weight: 700; margin-bottom: .4rem; }
    .vehicle .meta { display: flex; flex-wrap: wrap; gap: .35rem; }
    .tagchip {
      font-family: var(--mono); font-size: .62rem; letter-spacing: .1em; text-transform: uppercase;
      color: var(--muted); background: rgba(168,85,247,.07);
      border: 1px solid var(--line); border-radius: 3px; padding: .18rem .45rem;
    }
    .vehicle .price {
      font-family: var(--mono); font-size: 1.22rem; font-weight: 700;
      background: linear-gradient(92deg, #f5d0fe, #c084fc); -webkit-background-clip: text; background-clip: text; color: transparent;
      text-align: right; min-width: 120px;
    }
    .empty { color: var(--muted); text-align: center; padding: 1.9rem 0; font-size: .9rem; font-family: var(--mono); }

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
    .report-photo:hover img { transform: scale(1.06); filter: saturate(1.15); }
    .report-title { font-size: 1.5rem; font-weight: 800; line-height: 1.2; }
    .report-price {
      font-family: var(--mono); font-size: 2rem; font-weight: 700; margin: .35rem 0 .2rem;
      background: linear-gradient(92deg, #f5d0fe, #a855f7); -webkit-background-clip: text; background-clip: text; color: transparent;
    }
    .report-sub { color: var(--muted); font-size: .88rem; font-family: var(--mono); }
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
    a.link { color: #e9d5ff; font-size: .84rem; font-family: var(--mono); text-decoration: none; border-bottom: 1px solid rgba(233,213,255,.35); }
    a.link:hover { color: var(--magenta); }

    /* ---------- SCROLL PERSONALITY ---------- */
    .reveal {
      opacity: 0; transform: translateY(34px) scale(.985);
      filter: blur(6px);
      transition: opacity .7s cubic-bezier(.2,.7,.3,1), transform .7s cubic-bezier(.2,.7,.3,1), filter .7s ease;
    }
    .reveal.in { opacity: 1; transform: none; filter: none; }
    .reveal.from-left { transform: translateX(-46px); }
    .reveal.from-right { transform: translateX(46px); }
    .reveal.tilt { transform: perspective(900px) rotateX(9deg) translateY(40px); transform-origin: top center; }
    .reveal.in.from-left, .reveal.in.from-right, .reveal.in.tilt { transform: none; }
    .reveal-stagger > * {
      opacity: 0; transform: translateY(20px);
      transition: opacity .55s ease, transform .55s cubic-bezier(.2,.7,.3,1);
    }
    .reveal-stagger.in > * { opacity: 1; transform: none; }
    .sec-glow { position: relative; }
    .sec-glow::after {
      content: ""; position: absolute; left: 0; right: 0; top: -1px; height: 1px;
      background: linear-gradient(90deg, transparent, var(--neon), transparent);
      opacity: 0; transition: opacity .8s ease;
    }
    .sec-glow.in::after { opacity: .8; }

    .loading-shimmer {
      background: linear-gradient(90deg, rgba(14,8,23,.7) 25%, rgba(46,26,72,.85) 37%, rgba(14,8,23,.7) 63%);
      background-size: 400% 100%; animation: shimmer 1.35s ease infinite;
      border-radius: 3px; height: 74px; margin-bottom: .55rem; border: 1px solid var(--line);
    }
    @keyframes shimmer { 0% { background-position: 100% 0 } 100% { background-position: -100% 0 } }

    @media (prefers-reduced-motion: reduce) {
      *, *::before, *::after { animation: none !important; transition: none !important; }
      .reveal, .reveal-stagger > * { opacity: 1 !important; transform: none !important; filter: none !important; }
      #garage { display: none !important; }
    }
  </style>
</head>
<body class="booting">

  <!-- GARAGE DOOR BOOT -->
  <div id="garage">
    <div class="garage-door">
      <div class="door-panel">
        <div class="neon-sign">
          <div class="n-title">CarDex</div>
          <div class="n-sub">The Ultimate Car DataBase</div>
          <div class="n-credit">Made By Elijah</div>
        </div>
      </div>
      <div class="door-panel"></div>
      <div class="door-panel"></div>
      <div class="door-panel"></div>
      <div class="door-seal"></div>
    </div>
  </div>

  <div class="neon-credit">Made by Elijah</div>

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
      <span class="tag">The Ultimate Car DataBase</span>
    </div>
    <span class="badge">V{{ version }}</span>
    <div class="spacer"></div>
    <div class="live"><span class="dot"></span> Online</div>
  </header>

  <main>
    <!-- GAUGES -->
    <div class="gauges" id="gauges">
      <div class="gauge"><div class="k">Units</div><div class="v hot" id="g-units">—</div><div class="ticks" id="t-units"></div></div>
      <div class="gauge"><div class="k">Avg price</div><div class="v" id="g-avg">—</div><div class="ticks" id="t-avg"></div></div>
      <div class="gauge"><div class="k">VIN verified</div><div class="v" id="g-vin">—</div><div class="ticks" id="t-vin"></div></div>
      <div class="gauge"><div class="k">Photographed</div><div class="v" id="g-pic">—</div><div class="ticks" id="t-pic"></div></div>
    </div>

    <!-- LIST VIEW -->
    <div id="list-view">
      <div class="card">
        <h2>Inventory Console</h2>
        <div class="search-row">
          <input type="text" id="q" placeholder="Search year, make, model, VIN, stock…" />
          <button id="btn-search">Search</button>
        </div>
        <div class="actions">
          <button id="btn-scan">Scan Lithia Missoula</button>
          <button class="secondary" id="btn-backfill">Backfill Data</button>
          <button class="ghost" id="btn-all">Show All Saved</button>
        </div>
        <div class="status" id="status"></div>
      </div>

      <div class="card">
        <h2>Bay — select a unit</h2>
        <div id="vehicles"><div class="empty">Search or scan to load inventory</div></div>
      </div>
    </div>

    <!-- REPORT VIEW -->
    <div id="report-view">
      <div class="back-row"><button class="ghost" id="btn-back">← Back to bay</button></div>
      <div id="report-body"><div class="loading-shimmer"></div></div>
    </div>
  </main>

<script>
/* ---------------- boot / garage door ---------------- */
(function boot() {
  var garage = document.getElementById('garage');
  if (!garage) return;
  setTimeout(function () { garage.classList.add('open'); }, 2100);   // sign lingers ~1s longer
  setTimeout(function () {
    garage.classList.add('done');
    document.body.classList.remove('booting');
  }, 4700);
  setTimeout(function () { if (garage.parentNode) garage.parentNode.removeChild(garage); }, 5600);
})();

/* ---------------- helpers ---------------- */
var $ = function (id) { return document.getElementById(id); };
function esc(s) {
  return String(s === null || s === undefined ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}
function money(n) {
  if (n === null || n === undefined || n === '' || isNaN(Number(n))) return '—';
  return '$' + Number(n).toLocaleString('en-US', { maximumFractionDigits: 0 });
}
function num(n) {
  if (n === null || n === undefined || n === '' || isNaN(Number(n))) return null;
  return Number(n).toLocaleString('en-US');
}
function setStatus(msg, kind) {
  var el = $('status');
  el.textContent = msg || '';
  el.className = 'status' + (kind ? ' ' + kind : '');
}
function busy(btn, on) {
  if (!btn) return;
  btn.disabled = !!on;
  btn.classList.toggle('busy', !!on);
}
function ticks(containerId, pct) {
  var el = $(containerId);
  if (!el) return;
  var total = 10, on = Math.max(0, Math.min(total, Math.round((pct || 0) / 10)));
  var html = '';
  for (var i = 0; i < total; i++) html += '<i class="' + (i < on ? 'on' : '') + '"></i>';
  el.innerHTML = html;
}
async function getJSON(url, opts) {
  var res = await fetch(url, opts);
  var text = await res.text();
  var data = {};
  try { data = text ? JSON.parse(text) : {}; } catch (e) { data = { ok: false, error: text.slice(0, 200) }; }
  if (!res.ok && !data.error) data.error = 'HTTP ' + res.status;
  data.__status = res.status;
  return data;
}

/* ---------------- scroll reveal ---------------- */
var revealObserver = null;
function initReveal(root) {
  if (!('IntersectionObserver' in window)) {
    (root || document).querySelectorAll('.reveal, .reveal-stagger').forEach(function (el) { el.classList.add('in'); });
    return;
  }
  if (!revealObserver) {
    revealObserver = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add('in');
          var kids = entry.target.classList.contains('reveal-stagger')
            ? entry.target.children : [];
          for (var i = 0; i < kids.length; i++) {
            kids[i].style.transitionDelay = (i * 70) + 'ms';
          }
          revealObserver.unobserve(entry.target);
        }
      });
    }, { threshold: 0.12, rootMargin: '0px 0px -8% 0px' });
  }
  (root || document).querySelectorAll('.reveal, .reveal-stagger').forEach(function (el) {
    revealObserver.observe(el);
  });
}

/* ---------------- inventory list ---------------- */
var currentVehicles = [];

function renderSummary(summary, vehicles) {
  summary = summary || {};
  var list = vehicles || [];
  var units = summary.total_vehicles || summary.count || list.length || 0;
  var prices = list.map(function (v) { return Number(v.price); }).filter(function (p) { return p > 0; });
  var avg = summary.avg_price;
  if ((avg === null || avg === undefined) && prices.length) {
    avg = prices.reduce(function (a, b) { return a + b; }, 0) / prices.length;
  }
  var vin = list.filter(function (v) { return v.vin; }).length;
  var pic = list.filter(function (v) { return v.image_url; }).length;

  $('g-units').textContent = units ? units.toLocaleString('en-US') : '—';
  $('g-avg').textContent = avg ? money(avg) : '—';
  $('g-vin').textContent = list.length ? Math.round((vin / list.length) * 100) + '%' : '—';
  $('g-pic').textContent = list.length ? Math.round((pic / list.length) * 100) + '%' : '—';

  ticks('t-units', list.length ? 100 : 0);
  ticks('t-avg', avg ? 70 : 0);
  ticks('t-vin', list.length ? (vin / list.length) * 100 : 0);
  ticks('t-pic', list.length ? (pic / list.length) * 100 : 0);
}

function vehicleTitle(v) {
  return [v.year, v.make, v.model, v.trim].filter(Boolean).join(' ') || ('Vehicle #' + v.id);
}

function renderVehicles(list) {
  var box = $('vehicles');
  currentVehicles = list || [];
  if (!currentVehicles.length) {
    box.innerHTML = '<div class="empty">No vehicles yet — hit “Scan Lithia Missoula” to pull inventory.</div>';
    return;
  }
  box.innerHTML = currentVehicles.map(function (v, i) {
    var chips = [];
    if (v.condition) chips.push(v.condition);
    if (v.mileage !== null && v.mileage !== undefined && v.mileage !== '') chips.push(num(v.mileage) + ' mi');
    if (v.stock_number) chips.push('Stock ' + v.stock_number);
    if (v.vin) chips.push('VIN ' + String(v.vin).slice(-8));
    if (v.drivetrain) chips.push(v.drivetrain);
    return '' +
      '<div class="vehicle" role="button" tabindex="0" data-id="' + esc(v.id) + '" style="animation-delay:' + Math.min(i * 35, 600) + 'ms">' +
        '<div class="v-main">' +
          '<div class="title">' + esc(vehicleTitle(v)) + '</div>' +
          '<div class="meta">' + chips.map(function (c) { return '<span class="tagchip">' + esc(c) + '</span>'; }).join('') + '</div>' +
        '</div>' +
        '<div class="price">' + money(v.price) + '</div>' +
      '</div>';
  }).join('');

  Array.prototype.forEach.call(box.querySelectorAll('.vehicle'), function (el) {
    var open = function () { openReport(el.getAttribute('data-id')); };
    el.addEventListener('click', open);
    el.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); open(); }
    });
  });
}

async function loadVehicles(q) {
  var box = $('vehicles');
  box.innerHTML = '<div class="loading-shimmer"></div><div class="loading-shimmer"></div><div class="loading-shimmer"></div>';
  var url = '/api/vehicles?limit=200' + (q ? '&q=' + encodeURIComponent(q) : '');
  try {
    var data = await getJSON(url);
    var list = data.vehicles || [];
    renderVehicles(list);
    renderSummary(data.summary, list);
    return list.length;
  } catch (err) {
    box.innerHTML = '<div class="empty">Could not load vehicles: ' + esc(err.message || err) + '</div>';
    return 0;
  }
}

/* ---------------- actions ---------------- */
$('btn-search').addEventListener('click', async function () {
  busy(this, true);
  setStatus('Searching saved inventory…');
  var n = await loadVehicles($('q').value.trim());
  setStatus(n + ' vehicle' + (n === 1 ? '' : 's') + ' found.', n ? 'ok' : null);
  busy(this, false);
});
$('q').addEventListener('keydown', function (e) { if (e.key === 'Enter') $('btn-search').click(); });

$('btn-all').addEventListener('click', async function () {
  busy(this, true);
  $('q').value = '';
  setStatus('Loading everything saved…');
  var n = await loadVehicles('');
  setStatus(n + ' vehicles in the database.', n ? 'ok' : null);
  busy(this, false);
});

$('btn-scan').addEventListener('click', async function () {
  var btn = this;
  busy(btn, true);
  setStatus('Scanning Lithia Missoula… this can take up to a minute.');
  var result = {};
  try {
    result = await getJSON('/api/scan/lithia-missoula', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ force: true })
    });
  } catch (err) {
    result = { ok: false, error: String(err && err.message ? err.message : err) };
  }

  // ALWAYS refresh the list, even if the scan partially failed —
  // this is what used to leave the bay empty.
  var n = await loadVehicles('');
  if (result.ok) {
    var added = result.vehicles_found || result.added || result.count || n;
    setStatus('Scan complete — ' + added + ' listings processed, ' + n + ' vehicles in the bay.', 'ok');
  } else if (n) {
    setStatus('Scan reported: ' + (result.error || 'unknown issue') + ' — showing ' + n + ' saved vehicles.', 'err');
  } else {
    setStatus('Scan failed: ' + (result.error || 'unknown issue'), 'err');
  }
  busy(btn, false);
});

$('btn-backfill').addEventListener('click', async function () {
  var btn = this;
  busy(btn, true);
  setStatus('Backfilling VIN + listing data…');
  var data = {};
  try {
    data = await getJSON('/api/backfill_nhtsa', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ limit: 24 })
    });
  } catch (err) {
    data = { ok: false, error: String(err) };
  }
  await loadVehicles($('q').value.trim());
  if (data.ok) {
    setStatus('Enriched ' + (data.updated || 0) + ' of ' + (data.checked || 0) + ' — ' + (data.remaining || 0) + ' still queued.', 'ok');
  } else {
    setStatus('Backfill error: ' + (data.error || 'unknown'), 'err');
  }
  busy(btn, false);
});

$('btn-back').addEventListener('click', function () {
  $('report-view').style.display = 'none';
  $('list-view').style.display = '';
  window.scrollTo({ top: 0, behavior: 'smooth' });
});

/* ---------------- report ---------------- */
function specBlock(label, value) {
  var v = (value === null || value === undefined || value === '') ? 'Verify on listing' : value;
  var cls = (value === null || value === undefined || value === '') ? ' verify' : '';
  return '<div class="spec"><div class="label">' + esc(label) + '</div><div class="value' + cls + '">' + esc(v) + '</div></div>';
}

function renderReport(v, brain) {
  brain = brain || {};
  var title = vehicleTitle(v);
  var photo = v.image_url
    ? '<img src="' + esc(v.image_url) + '" alt="' + esc(title) + '" />'
    : 'No photo on file';

  var chips = [];
  if (v.condition) chips.push('<span class="chip ' + (String(v.condition).toLowerCase() === 'new' ? 'ok' : '') + '">' + esc(v.condition) + '</span>');
  if (v.vin) chips.push('<span class="chip ok">VIN ' + esc(v.vin) + '</span>');
  if (v.stock_number) chips.push('<span class="chip">Stock ' + esc(v.stock_number) + '</span>');
  if (v.mileage !== null && v.mileage !== undefined && v.mileage !== '') chips.push('<span class="chip">' + esc(num(v.mileage)) + ' mi</span>');
  if (!v.image_url) chips.push('<span class="chip warn">Photo missing</span>');

  function bullets(arr, cls) {
    if (!arr || !arr.length) return '<div class="empty">Nothing here yet.</div>';
    return arr.map(function (b) {
      var text = typeof b === 'string' ? b : (b.text || b.title || JSON.stringify(b));
      return '<div class="bullet ' + (cls || '') + '">' + esc(text) + '</div>';
    }).join('');
  }

  var html = '' +
  '<div class="card reveal tilt">' +
    '<div class="report-hero">' +
      '<div class="report-photo">' + photo + '</div>' +
      '<div style="flex:1;min-width:240px">' +
        '<div class="report-title">' + esc(title) + '</div>' +
        '<div class="report-price">' + money(v.price) + '</div>' +
        '<div class="report-sub">' + esc([v.body_style, v.drivetrain, v.transmission].filter(Boolean).join(' • ') || 'Specs pending') + '</div>' +
        '<div class="chips">' + chips.join('') + '</div>' +
        (v.listing_url ? '<div style="margin-top:.9rem"><a class="link" href="' + esc(v.listing_url) + '" target="_blank" rel="noopener">Open dealer listing ↗</a></div>' : '') +
      '</div>' +
    '</div>' +
  '</div>' +

  '<div class="card reveal from-left sec-glow">' +
    '<div class="section-title">Vehicle Specs</div>' +
    '<div class="grid2 reveal-stagger">' +
      specBlock('Engine', v.engine) +
      specBlock('Horsepower', v.engine_hp) +
      specBlock('Torque', v.torque) +
      specBlock('Transmission', v.transmission) +
      specBlock('Drivetrain', v.drivetrain) +
      specBlock('Body style', v.body_style) +
      specBlock('Towing', v.towing_capacity) +
      specBlock('Flat tow', v.flat_tow) +
    '</div>' +
  '</div>' +

  '<div class="card reveal from-right sec-glow">' +
    '<div class="section-title">Selling Points</div>' +
    '<div class="reveal-stagger">' + bullets(brain.points) + '</div>' +
  '</div>' +

  '<div class="card reveal tilt sec-glow">' +
    '<div class="section-title">Objection Handling</div>' +
    '<div class="reveal-stagger">' + bullets(brain.objections, 'warn') + '</div>' +
  '</div>' +

  '<div class="card reveal from-left sec-glow">' +
    '<div class="section-title">Comparison</div>' +
    '<div class="reveal-stagger">' + bullets(brain.competitors) + '</div>' +
  '</div>' +

  '<div class="card reveal from-right sec-glow">' +
    '<div class="section-title">Discovery Questions</div>' +
    '<div class="reveal-stagger">' + bullets(brain.questions) + '</div>' +
  '</div>' +

  '<div class="card reveal tilt sec-glow">' +
    '<div class="section-title">Demo Route</div>' +
    '<div class="reveal-stagger">' + bullets(brain.demo) + '</div>' +
  '</div>' +

  '<div class="card reveal sec-glow">' +
    '<div class="section-title">The Pitch</div>' +
    '<div class="pitch">' + esc(brain.pitch || 'Lead with what the customer told you matters most, then prove it on this exact VIN.') + '</div>' +
  '</div>';

  $('report-body').innerHTML = html;
  requestAnimationFrame(function () { initReveal($('report-body')); });
}

async function openReport(id) {
  $('list-view').style.display = 'none';
  $('report-view').style.display = 'block';
  $('report-body').innerHTML = '<div class="loading-shimmer"></div><div class="loading-shimmer"></div><div class="loading-shimmer"></div>';
  window.scrollTo({ top: 0, behavior: 'smooth' });
  try {
    var data = await getJSON('/api/vehicles/' + encodeURIComponent(id));
    if (!data.vehicle) throw new Error(data.error || 'Vehicle not found');
    renderReport(data.vehicle, data.vehicle.sales_brain);
  } catch (err) {
    $('report-body').innerHTML = '<div class="card"><div class="empty">Could not load this report: ' + esc(err.message || err) + '</div></div>';
  }
}

/* ---------------- init ---------------- */
initReveal(document);
loadVehicles('').then(function (n) {
  if (n) setStatus(n + ' vehicles loaded from the database.', 'ok');
});
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


@app.post("/api/scan/lithia-missoula")
def api_scan_lithia_missoula():
    """One-click scan used by the Scan Lithia Missoula button.

    Never 500s on the UI: any scraper failure is returned as JSON so the
    front end can still fall back to showing whatever is already saved.
    """
    data = request.get_json(silent=True) or {}
    force = bool(data.get("force", True))
    url = (data.get("inventory_url") or LITHIA_MISSOULA_URL).strip()
    try:
        result = engine.discover(url, dealership_name=LITHIA_MISSOULA_NAME, force=force)
    except Exception as exc:
        result = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

    if not isinstance(result, dict):
        result = {"ok": True, "result": result}
    result.setdefault("ok", True)
    result["inventory_url"] = url

    try:
        summary = store.inventory_summary(None)
        result["summary"] = summary
        result["saved_total"] = (summary or {}).get("total_vehicles")
    except Exception:
        pass

    # Always 200 — the UI reads result.ok and refreshes the list either way.
    return jsonify(result), 200


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
    try:
        vehicles = store.search_vehicles(
            dealership_id=dealership_id, q=q, year=year, make=make, model=model,
            condition=condition, min_price=min_price, max_price=max_price,
            max_mileage=max_mileage, active_only=active_only, limit=limit, offset=offset,
        )
    except Exception as exc:
        return jsonify({"vehicles": [], "summary": {}, "count": 0, "error": str(exc)}), 200
    try:
        summary = store.inventory_summary(dealership_id)
    except Exception:
        summary = {}
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
        if vdp_data:
            condition_now = str(vdp_data.get("condition") or vehicle.get("condition") or "").strip().lower()
            listing_path = str(vehicle.get("listing_url") or "").lower()
            is_new = condition_now == "new" or "/new/" in listing_path
            if is_new and vehicle.get("vin"):
                vin_text = str(vehicle["vin"]).strip().upper()
                if len(vin_text) >= 8:
                    vdp_data["stock_number"] = vin_text[-8:]
                    vdp_data["condition"] = vdp_data.get("condition") or "New"

            try:
                store.fill_vdp_fields(vehicle_id, vdp_data)
            except Exception:
                pass
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
