"""
CarDex V2.1 (flat layout) — Flask application entry point.
Works with all files at the top level of the repository.
"""

from __future__ import annotations

import os
from flask import Flask, jsonify, render_template_string, request

from scraper import InventoryEngine, list_adapters
from store import InventoryStore

__version__ = "2.1.0-flat"

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
  <title>CarDex V{{ version }}</title>
  <style>
    :root {
      --bg: #0b0f14; --card: #141a22; --border: #1e2833;
      --text: #e8eef5; --muted: #8b9bb0; --accent: #3b82f6; --green: #22c55e;
    }
    * { box-sizing: border-box; }
    body { margin: 0; font-family: Inter, system-ui, sans-serif; background: var(--bg); color: var(--text); min-height: 100vh; }
    header { border-bottom: 1px solid var(--border); padding: 1rem 1.5rem; display: flex; align-items: center; gap: 1rem; }
    header h1 { margin: 0; font-size: 1.25rem; }
    .badge { background: var(--accent); color: white; font-size: 0.7rem; padding: 0.15rem 0.5rem; border-radius: 999px; }
    main { max-width: 960px; margin: 0 auto; padding: 2rem 1.5rem; }
    .card { background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 1.25rem 1.5rem; margin-bottom: 1.25rem; }
    h2 { margin: 0 0 0.75rem; font-size: 1rem; color: var(--muted); font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; }
    p, ul { color: var(--muted); line-height: 1.5; }
    code { background: #0d1218; padding: 0.15rem 0.4rem; border-radius: 4px; font-size: 0.85em; }
    .ok { color: var(--green); }
  </style>
</head>
<body>
  <header>
    <h1>CarDex</h1>
    <span class="badge">V{{ version }}</span>
  </header>
  <main>
    <div class="card">
      <h2>Status</h2>
      <p>Backend is running.</p>
      <p class="ok" id="health">Checking health…</p>
    </div>
    <div class="card">
      <h2>Key API endpoints</h2>
      <ul>
        <li><code>GET /api/health</code></li>
        <li><code>GET /api/adapters</code></li>
        <li><code>POST /api/discover</code> — scan a public inventory URL</li>
        <li><code>GET /api/vehicles</code></li>
        <li><code>GET /api/events</code></li>
      </ul>
    </div>
  </main>
  <script>
    fetch("/api/health").then(r => r.json()).then(d => {
      document.getElementById("health").textContent = "OK — " + d.service + " " + d.version;
    }).catch(() => {
      document.getElementById("health").textContent = "Health check failed";
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
