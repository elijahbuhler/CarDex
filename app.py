"""
CarDex V2.1.3 — vehicle list + clickable sales report.
Replace app.py with this file on GitHub.
"""

from __future__ import annotations

import os
from flask import Flask, jsonify, render_template_string, request

from scraper import InventoryEngine, list_adapters
from store import InventoryStore

__version__ = "2.1.3-flat"

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
  <title>CarDex</title>
  <style>
    :root {
      --bg: #0b0f14; --card: #141a22; --border: #1e2833;
      --text: #e8eef5; --muted: #8b9bb0; --accent: #3b82f6;
      --green: #22c55e; --amber: #f59e0b; --red: #ef4444;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: Inter, system-ui, sans-serif; background: var(--bg); color: var(--text); min-height: 100vh; }
    header { border-bottom: 1px solid var(--border); padding: 1rem 1.5rem; display: flex; align-items: center; gap: 0.75rem; }
    header h1 { font-size: 1.35rem; font-weight: 700; }
    .badge { background: var(--accent); color: #fff; font-size: 0.7rem; padding: 0.2rem 0.55rem; border-radius: 999px; font-weight: 600; }
    main { max-width: 980px; margin: 0 auto; padding: 1.5rem 1.25rem 3rem; }
    .card { background: var(--card); border: 1px solid var(--border); border-radius: 14px; padding: 1.25rem 1.4rem; margin-bottom: 1.15rem; }
    h2 { font-size: 0.72rem; color: var(--muted); font-weight: 600; text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 0.85rem; }
    .search-row { display: flex; gap: 0.6rem; }
    input[type="text"] { flex: 1; background: #0d1218; border: 1px solid var(--border); border-radius: 10px; padding: 0.85rem 1rem; color: var(--text); font-size: 1rem; outline: none; }
    input[type="text"]:focus { border-color: var(--accent); }
    button { background: var(--accent); color: #fff; border: none; border-radius: 10px; padding: 0.85rem 1.2rem; font-size: 0.95rem; font-weight: 600; cursor: pointer; white-space: nowrap; }
    button:hover { filter: brightness(1.08); }
    button:disabled { opacity: 0.5; cursor: not-allowed; }
    button.secondary { background: #1e2833; color: var(--text); }
    button.ghost { background: transparent; border: 1px solid var(--border); color: var(--muted); }
    .actions { display: flex; gap: 0.6rem; margin-top: 0.85rem; flex-wrap: wrap; }
    .status { font-size: 0.9rem; color: var(--muted); margin-top: 0.7rem; min-height: 1.3em; }
    .status.ok { color: var(--green); }
    .status.err { color: var(--red); }
    .vehicle { background: #0d1218; border: 1px solid var(--border); border-radius: 12px; padding: 1rem 1.15rem; margin-bottom: 0.7rem; cursor: pointer; }
    .vehicle:hover { border-color: var(--accent); }
    .vehicle .title { font-size: 1.08rem; font-weight: 650; margin-bottom: 0.3rem; }
    .vehicle .meta { color: var(--muted); font-size: 0.88rem; display: flex; flex-wrap: wrap; gap: 0.65rem 1.1rem; }
    .vehicle .price { font-size: 1.2rem; font-weight: 700; color: var(--green); margin-top: 0.45rem; }
    .empty { color: var(--muted); text-align: center; padding: 1.5rem 0; }
    #report-view { display: none; }
    .back-row { margin-bottom: 1rem; }
    .report-hero { display: flex; gap: 1.25rem; flex-wrap: wrap; align-items: flex-start; }
    .report-photo { width: 220px; height: 150px; background: #0d1218; border: 1px solid var(--border); border-radius: 12px; display: flex; align-items: center; justify-content: center; color: var(--muted); font-size: 0.85rem; overflow: hidden; }
    .report-photo img { width: 100%; height: 100%; object-fit: cover; }
    .report-title { font-size: 1.45rem; font-weight: 700; line-height: 1.25; }
    .report-price { font-size: 2rem; font-weight: 800; color: var(--green); margin: 0.4rem 0 0.2rem; }
    .report-sub { color: var(--muted); font-size: 0.95rem; }
    .chips { display: flex; flex-wrap: wrap; gap: 0.45rem; margin-top: 0.75rem; }
    .chip { background: #0d1218; border: 1px solid var(--border); border-radius: 999px; padding: 0.25rem 0.7rem; font-size: 0.8rem; color: var(--muted); }
    .chip.ok { border-color: #166534; color: var(--green); }
    .chip.warn { border-color: #92400e; color: var(--amber); }
    .grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem; }
    @media (max-width: 640px) { .grid2 { grid-template-columns: 1fr; } }
    .spec { background: #0d1218; border: 1px solid var(--border); border-radius: 10px; padding: 0.75rem 0.9rem; }
    .spec .label { font-size: 0.72rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.04em; }
    .spec .value { font-size: 1.05rem; font-weight: 600; margin-top: 0.2rem; }
    .spec .value.verify { color: var(--amber); font-weight: 700; }
    .section-title { font-size: 0.72rem; color: var(--muted); font-weight: 600; text-transform: uppercase; letter-spacing: 0.06em; margin: 1.15rem 0 0.6rem; }
    .bullet { background: #0d1218; border-left: 3px solid var(--accent); border-radius: 0 8px 8px 0; padding: 0.7rem 0.9rem; margin-bottom: 0.5rem; font-size: 0.95rem; line-height: 1.45; }
    .bullet.warn { border-left-color: var(--amber); }
    .pitch { background: #0d1218; border: 1px solid var(--border); border-radius: 12px; padding: 1rem 1.1rem; font-size: 1rem; line-height: 1.55; }
    a.link { color: var(--accent); font-size: 0.9rem; }
  </style>
</head>
<body>
  <header>
    <h1>CarDex</h1>
    <span class="badge">V{{ version }}</span>
  </header>
  <main>
    <div id="list-view">
      <div class="card">
        <h2>Search inventory</h2>
        <div class="search-row">
          <input type="text" id="q" placeholder="VIN, stock #, year, make, model…" />
          <button id="btn-search" onclick="doSearch()">Search</button>
        </div>
        <div class="actions">
          <button class="secondary" id="btn-scan" onclick="doScan()">Scan Lithia Missoula Inventory</button>
          <button class="secondary" onclick="loadAll()">Show all saved</button>
        </div>
        <div class="status" id="status"></div>
      </div>
      <div class="card">
        <h2>Results — click a vehicle</h2>
        <div id="results"><div class="empty">Search or scan to see vehicles here.</div></div>
      </div>
    </div>
    <div id="report-view">
      <div class="back-row"><button class="ghost" onclick="showList()">← Back to list</button></div>
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
    function money(n) {
      if (n == null || n === "") return "—";
      return "$" + Number(n).toLocaleString();
    }
    function titleOf(v) {
      const t = [v.year, v.make, v.model, v.trim].filter(Boolean).join(" ");
      return t || (v.vin ? ("VIN " + v.vin) : "Vehicle");
    }
    function renderVehicles(vehicles) {
      if (!vehicles || !vehicles.length) {
        resultsEl.innerHTML = '<div class="empty">No vehicles found yet.</div>';
        return;
      }
      resultsEl.innerHTML = vehicles.map(v => {
        const miles = v.mileage != null ? Number(v.mileage).toLocaleString() + " mi" : "—";
        return '<div class="vehicle" onclick="openReport(' + v.id + ')">' +
          '<div class="title">' + titleOf(v) + '</div>' +
          '<div class="meta"><span>VIN: ' + (v.vin||"—") + '</span><span>Stock: ' + (v.stock_number||"—") +
          '</span><span>' + miles + '</span><span>' + (v.condition||"—") + '</span></div>' +
          '<div class="price">' + money(v.price) + '</div></div>';
      }).join("");
    }
    async function doSearch() {
      const q = document.getElementById("q").value.trim();
      setStatus("Searching…");
      document.getElementById("btn-search").disabled = true;
      try {
        let url = "/api/vehicles?limit=500";
        if (q) url += "&q=" + encodeURIComponent(q);
        const r = await fetch(url);
        const data = await r.json();
        renderVehicles(data.vehicles || []);
        const total = (data.summary && data.summary.active) || data.count || 0;
        setStatus(total + " vehicle(s)", "ok");
      } catch (e) { setStatus("Search failed", "err"); }
      document.getElementById("btn-search").disabled = false;
    }
    async function loadAll() {
      document.getElementById("q").value = "";
      await doSearch();
    }
    async function doScan() {
      setStatus("Scanning Lithia public inventory… this can take up to a minute.");
      document.getElementById("btn-scan").disabled = true;
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
      document.getElementById("btn-scan").disabled = false;
    }
    function showList() {
      reportView.style.display = "none";
      listView.style.display = "block";
    }
    function showReport() {
      listView.style.display = "none";
      reportView.style.display = "block";
      window.scrollTo(0, 0);
    }
    function chip(text, kind) {
      return '<span class="chip ' + (kind || "") + '">' + text + "</span>";
    }
    function specRow(label, value) {
      const display = value != null && value !== "" ? value : "VERIFY";
      const cls = value != null && value !== "" ? "" : "verify";
      return '<div class="spec"><div class="label">' + label + '</div><div class="value ' + cls + '">' + display + "</div></div>";
    }
    function buildSales(v) {
      const title = titleOf(v);
      const isNew = (v.condition || "").toLowerCase() === "new";
      const make = (v.make || "").toLowerCase();
      const model = ((v.model || "") + " " + (v.trim || "")).toLowerCase();
      const points = [];
      if (isNew) points.push("This is a new vehicle — full factory warranty and no previous-owner history to explain.");
      if (v.price) points.push("Priced at " + money(v.price) + " on our lot today.");
      if (make.includes("jeep")) points.push("Jeep brand strength: capability, residual value, and a loyal owner base in this market.");
      if (make.includes("ram")) points.push("Ram trucks sell on ride quality, towing, and interior comfort.");
      if (model.includes("grand")) points.push("Grand Cherokee sits in a sweet spot: family-friendly size with real capability.");
      if (model.includes("wrangler")) points.push("Wrangler is an emotion buy — lifestyle and identity.");
      if (points.length < 3) points.push("Be ready with payment options and trade appraisal — those close more deals than feature lists.");
      const objections = [];
      objections.push("Price — be ready with payment examples and why this unit is priced where it is.");
      if (make.includes("jeep") || make.includes("ram")) objections.push("Fuel economy — acknowledge it early if they commute long distances; pivot to capability and value.");
      if (model.includes("wrangler")) objections.push("Daily comfort / noise — be honest about on-road manners; sell the experience.");
      objections.push("Inventory alternatives — know 1–2 similar units on the lot so you control the comparison.");
      objections.push("Timing / payment — many customers stall here; have terms ready before you need them.");
      let pitch = "This is the " + title + ".";
      if (v.price) pitch += " It's marked at " + money(v.price) + ".";
      if (isNew) pitch += " Brand new, full warranty.";
      pitch += " What matters most to you on this one — payment, features, or how you'll use it day to day?";
      return { points: points.slice(0, 5), objections, pitch };
    }
    async function openReport(id) {
      showReport();
      reportBody.innerHTML = '<div class="empty">Loading report…</div>';
      try {
        const r = await fetch("/api/vehicles/" + id);
        const data = await r.json();
        if (!data.vehicle) {
          reportBody.innerHTML = '<div class="empty">Vehicle not found.</div>';
          return;
        }
        const v = data.vehicle;
        const sales = buildSales(v);
        const title = titleOf(v);
        const photo = v.image_url
          ? '<div class="report-photo"><img src="' + v.image_url + '" alt="" /></div>'
          : '<div class="report-photo">No photo yet</div>';
        const chips = [];
        if (v.condition) chips.push(chip(v.condition, "ok"));
        if (v.vin) chips.push(chip("VIN verified", "ok"));
        else chips.push(chip("VIN missing", "warn"));
        if (!v.year || !v.make || !v.model) chips.push(chip("Y/M/M incomplete", "warn"));
        if (!v.trim) chips.push(chip("Trim VERIFY", "warn"));
        reportBody.innerHTML =
          '<div class="report-hero">' + photo +
          '<div style="flex:1;min-width:200px;">' +
          '<div class="report-title">' + title + '</div>' +
          '<div class="report-price">' + money(v.price) + '</div>' +
          '<div class="report-sub">' + (v.dealership_name || "Lithia Missoula") + '</div>' +
          '<div class="chips">' + chips.join("") + '</div>' +
          (v.listing_url ? '<div style="margin-top:0.75rem;"><a class="link" href="' + v.listing_url + '" target="_blank" rel="noopener">Open listing on dealership site →</a></div>' : "") +
          '</div></div>' +
          '<div class="section-title">Basics</div><div class="grid2">' +
          specRow("VIN", v.vin) + specRow("Stock #", v.stock_number) +
          specRow("Mileage", v.mileage != null ? Number(v.mileage).toLocaleString() + " mi" : null) +
          specRow("Condition", v.condition) +
          specRow("Year", v.year) + specRow("Make", v.make) +
          specRow("Model", v.model) + specRow("Trim", v.trim) +
          '</div>' +
          '<div class="section-title">Specs (only when verified)</div><div class="grid2">' +
          specRow("Engine", v.engine) + specRow("Drivetrain", v.drivetrain) +
          specRow("Transmission", v.transmission) + specRow("Fuel economy", v.fuel_economy) +
          '</div>' +
          '<div class="section-title">Best selling points</div>' +
          sales.points.map(function(p){ return '<div class="bullet">' + p + '</div>'; }).join("") +
          '<div class="section-title">Customer pitch</div><div class="pitch">' + sales.pitch + '</div>' +
          '<div class="section-title">Know before you sell</div>' +
          sales.objections.map(function(p){ return '<div class="bullet warn">' + p + '</div>'; }).join("");
      } catch (e) {
        reportBody.innerHTML = '<div class="empty">Failed to load report.</div>';
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
    return jsonify({"vehicle": vehicle, "events": events})


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
