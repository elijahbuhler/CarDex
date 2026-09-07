"""
CarDex V2.1 (flat layout) — Flask application entry point.
Simple usable UI for the dealership floor.
"""

from __future__ import annotations

import os
from flask import Flask, jsonify, render_template_string, request

from scraper import InventoryEngine, list_adapters
from store import InventoryStore

__version__ = "2.1.2-flat"

app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False

store = InventoryStore()
engine = InventoryEngine(store=store)

INDEX_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>CarDex</title>
  <style>
    :root {
      --bg: #0b0f14;
      --card: #141a22;
      --border: #1e2833;
      --text: #e8eef5;
      --muted: #8b9bb0;
      --accent: #3b82f6;
      --green: #22c55e;
      --amber: #f59e0b;
      --red: #ef4444;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: Inter, system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
      background: var(--bg);
      color: var(--text);
      min-height: 100vh;
    }
    header {
      border-bottom: 1px solid var(--border);
      padding: 1rem 1.5rem;
      display: flex;
      align-items: center;
      gap: 0.75rem;
    }
    header h1 { font-size: 1.35rem; font-weight: 700; letter-spacing: 0.02em; }
    .badge {
      background: var(--accent);
      color: white;
      font-size: 0.7rem;
      padding: 0.2rem 0.55rem;
      border-radius: 999px;
      font-weight: 600;
    }
    main { max-width: 900px; margin: 0 auto; padding: 1.75rem 1.25rem 3rem; }
    .card {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 1.35rem 1.5rem;
      margin-bottom: 1.25rem;
    }
    h2 {
      font-size: 0.75rem;
      color: var(--muted);
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      margin-bottom: 0.9rem;
    }
    .search-row {
      display: flex;
      gap: 0.6rem;
    }
    input[type="text"] {
      flex: 1;
      background: #0d1218;
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 0.85rem 1rem;
      color: var(--text);
      font-size: 1rem;
      outline: none;
    }
    input[type="text"]:focus { border-color: var(--accent); }
    button {
      background: var(--accent);
      color: white;
      border: none;
      border-radius: 10px;
      padding: 0.85rem 1.25rem;
      font-size: 0.95rem;
      font-weight: 600;
      cursor: pointer;
      white-space: nowrap;
    }
    button:hover { filter: brightness(1.1); }
    button:disabled { opacity: 0.5; cursor: not-allowed; }
    button.secondary {
      background: #1e2833;
      color: var(--text);
    }
    .actions { display: flex; gap: 0.6rem; margin-top: 0.9rem; flex-wrap: wrap; }
    .status {
      font-size: 0.9rem;
      color: var(--muted);
      margin-top: 0.75rem;
      min-height: 1.3em;
    }
    .status.ok { color: var(--green); }
    .status.err { color: var(--red); }
    .vehicle {
      background: #0d1218;
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 1rem 1.15rem;
      margin-bottom: 0.75rem;
    }
    .vehicle .title {
      font-size: 1.1rem;
      font-weight: 650;
      margin-bottom: 0.35rem;
    }
    .vehicle .meta {
      color: var(--muted);
      font-size: 0.9rem;
      display: flex;
      flex-wrap: wrap;
      gap: 0.75rem 1.25rem;
    }
    .vehicle .price {
      font-size: 1.25rem;
      font-weight: 700;
      color: var(--green);
      margin-top: 0.5rem;
    }
    .empty {
      color: var(--muted);
      text-align: center;
      padding: 1.5rem 0;
    }
    a { color: var(--accent); }
  </style>
</head>
<body>
  <header>
    <h1>CarDex</h1>
    <span class="badge">V{{ version }}</span>
  </header>

  <main>
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
      <h2>Results</h2>
      <div id="results">
        <div class="empty">Search or scan to see vehicles here.</div>
      </div>
    </div>
  </main>

  <script>
    const statusEl = document.getElementById("status");
    const resultsEl = document.getElementById("results");

    function setStatus(msg, type) {
      statusEl.textContent = msg || "";
      statusEl.className = "status" + (type ? " " + type : "");
    }

    function money(n) {
      if (n == null || n === "") return "—";
      return "$" + Number(n).toLocaleString();
    }

    function renderVehicles(vehicles) {
      if (!vehicles || vehicles.length === 0) {
        resultsEl.innerHTML = '<div class="empty">No vehicles found yet.</div>';
        return;
      }
      resultsEl.innerHTML = vehicles.map(v => {
        const title = [v.year, v.make, v.model, v.trim].filter(Boolean).join(" ") || "Vehicle";
        const miles = v.mileage != null ? Number(v.mileage).toLocaleString() + " mi" : "—";
        const cond = v.condition || "—";
        const vin = v.vin || "—";
        const stock = v.stock_number || "—";
        return `
          <div class="vehicle">
            <div class="title">${title}</div>
            <div class="meta">
              <span>VIN: ${vin}</span>
              <span>Stock: ${stock}</span>
              <span>${miles}</span>
              <span>${cond}</span>
            </div>
            <div class="price">${money(v.price)}</div>
          </div>
        `;
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
      } catch (e) {
        setStatus("Search failed", "err");
      }
      document.getElementById("btn-search").disabled = false;
    }

    async function loadAll() {
      document.getElementById("q").value = "";
      await doSearch();
    }

    async function doScan() {
      setStatus("Scanning Lithia public inventory… this can take 20–60 seconds.");
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
          setStatus(
            "Scan complete — found " + (data.vehicles_found || 0) +
            " vehicles. New: " + (data.stats && data.stats.new || 0) +
            ", price changes: " + (data.stats && data.stats.price_change || 0),
            "ok"
          );
          await loadAll();
        } else {
          setStatus("Scan problem: " + (data.error || "unknown"), "err");
        }
      } catch (e) {
        setStatus("Scan failed — " + e.message, "err");
      }
      document.getElementById("btn-scan").disabled = false;
    }

    document.getElementById("q").addEventListener("keydown", (e) => {
      if (e.key === "Enter") doSearch();
    });

    // Load any already-saved vehicles on open
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
    status = 200 if result.get("ok") else 400
    return jsonify(result), status


@app.post("/api/discover")
def api_discover():
    data = request.get_json(silent=True) or {}
    url = (data.get("inventory_url") or data.get("url") or "").strip()
    name = (data.get("name") or "").strip() or None
    force = bool(data.get("force", False))
    if not url:
        return jsonify({"ok": False, "error": "inventory_url is required"}), 400
    result = engine.discover(url, dealership_name=name, force=force)
    status = 200 if result.get("ok") else 400
    return jsonify(result), status


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
