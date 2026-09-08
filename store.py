"""
CarDex inventory store.

Uses SQLite to keep snapshots of dealership inventory over time.
This is the foundation for detecting NEW, PRICE CHANGE, and REMOVED vehicles.
"""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Prefer CARDEX_DB_PATH env var (useful on Render). Fall back to app folder, then /tmp.
_APP_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = Path(os.environ.get("CARDEX_DB_PATH", str(_APP_DIR / "cardex_inventory.db")))


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class InventoryStore:
    def __init__(self, db_path: Optional[Path | str] = None):
        path = Path(db_path) if db_path else DEFAULT_DB_PATH
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            probe = path.parent / ".cardex_write_probe"
            probe.write_text("ok")
            probe.unlink(missing_ok=True)
            self.db_path = path
        except OSError:
            self.db_path = Path("/tmp/cardex_inventory.db")
        self._ensure_schema()

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _ensure_schema(self) -> None:
        with self._conn() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS dealerships (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    name            TEXT NOT NULL,
                    inventory_url   TEXT NOT NULL UNIQUE,
                    adapter_key     TEXT NOT NULL DEFAULT 'generic',
                    created_at      TEXT NOT NULL,
                    last_scanned_at TEXT
                );

                CREATE TABLE IF NOT EXISTS snapshots (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    dealership_id   INTEGER NOT NULL,
                    scanned_at      TEXT NOT NULL,
                    vehicle_count   INTEGER NOT NULL DEFAULT 0,
                    FOREIGN KEY (dealership_id) REFERENCES dealerships(id)
                );

                CREATE TABLE IF NOT EXISTS vehicles (
                    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                    dealership_id       INTEGER NOT NULL,
                    vin                 TEXT,
                    stock_number        TEXT,
                    year                INTEGER,
                    make                TEXT,
                    model               TEXT,
                    trim                TEXT,
                    price               REAL,
                    mileage             INTEGER,
                    condition           TEXT,          -- new / used / cpo
                    exterior_color      TEXT,
                    interior_color      TEXT,
                    listing_url         TEXT,
                    image_url           TEXT,
                    body_style          TEXT,
                    drivetrain          TEXT,
                    engine              TEXT,
                    transmission        TEXT,
                    fuel_economy        TEXT,
                    raw_json            TEXT,          -- original extracted data
                    first_seen_at       TEXT NOT NULL,
                    last_seen_at        TEXT NOT NULL,
                    last_price          REAL,
                    is_active           INTEGER NOT NULL DEFAULT 1,
                    UNIQUE(dealership_id, vin),
                    FOREIGN KEY (dealership_id) REFERENCES dealerships(id)
                );

                CREATE TABLE IF NOT EXISTS vehicle_events (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    vehicle_id      INTEGER NOT NULL,
                    event_type      TEXT NOT NULL,   -- NEW, PRICE_CHANGE, REMOVED, REAPPEARED
                    old_value       TEXT,
                    new_value       TEXT,
                    created_at      TEXT NOT NULL,
                    FOREIGN KEY (vehicle_id) REFERENCES vehicles(id)
                );

                CREATE INDEX IF NOT EXISTS idx_vehicles_dealership
                    ON vehicles(dealership_id);
                CREATE INDEX IF NOT EXISTS idx_vehicles_vin
                    ON vehicles(vin);
                CREATE INDEX IF NOT EXISTS idx_vehicles_active
                    ON vehicles(is_active);
                CREATE INDEX IF NOT EXISTS idx_events_vehicle
                    ON vehicle_events(vehicle_id);
                """
            )
            # Migrations for columns added after the initial release.
            # Safe to run every startup — no-ops once the column exists.
            self._add_column_if_missing(conn, "vehicles", "engine_hp", "INTEGER")
            self._add_column_if_missing(conn, "vehicles", "torque", "TEXT")
            self._add_column_if_missing(conn, "vehicles", "towing_capacity", "TEXT")
            self._add_column_if_missing(conn, "vehicles", "flat_tow", "TEXT")
            self._add_column_if_missing(conn, "vehicles", "vdp_enriched_at", "TEXT")

    def _add_column_if_missing(self, conn: sqlite3.Connection, table: str, column: str, coltype: str) -> None:
        cols = [r["name"] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
        if column not in cols:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {coltype}")

    # ------------------------------------------------------------------
    # Dealership helpers
    # ------------------------------------------------------------------

    def upsert_dealership(
        self,
        name: str,
        inventory_url: str,
        adapter_key: str = "generic",
    ) -> int:
        now = _utcnow()
        with self._conn() as conn:
            row = conn.execute(
                "SELECT id FROM dealerships WHERE inventory_url = ?",
                (inventory_url,),
            ).fetchone()
            if row:
                conn.execute(
                    """
                    UPDATE dealerships
                    SET name = ?, adapter_key = ?, last_scanned_at = ?
                    WHERE id = ?
                    """,
                    (name, adapter_key, now, row["id"]),
                )
                return int(row["id"])
            cur = conn.execute(
                """
                INSERT INTO dealerships (name, inventory_url, adapter_key, created_at, last_scanned_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (name, inventory_url, adapter_key, now, now),
            )
            return int(cur.lastrowid)

    def list_dealerships(self) -> List[Dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM dealerships ORDER BY name"
            ).fetchall()
            return [dict(r) for r in rows]

    def get_dealership(self, dealership_id: int) -> Optional[Dict[str, Any]]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM dealerships WHERE id = ?", (dealership_id,)
            ).fetchone()
            return dict(row) if row else None

    # ------------------------------------------------------------------
    # Snapshot + change detection
    # ------------------------------------------------------------------

    def start_snapshot(self, dealership_id: int) -> int:
        now = _utcnow()
        with self._conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO snapshots (dealership_id, scanned_at, vehicle_count)
                VALUES (?, ?, 0)
                """,
                (dealership_id, now),
            )
            return int(cur.lastrowid)

    def finish_snapshot(self, snapshot_id: int, vehicle_count: int) -> None:
        with self._conn() as conn:
            conn.execute(
                "UPDATE snapshots SET vehicle_count = ? WHERE id = ?",
                (vehicle_count, snapshot_id),
            )

    def apply_inventory(
        self,
        dealership_id: int,
        vehicles: List[Dict[str, Any]],
    ) -> Dict[str, int]:
        """
        Compare the latest scraped list against what we already know.
        Returns counts of NEW / PRICE_CHANGE / REMOVED / UNCHANGED.
        """
        now = _utcnow()
        stats = {"new": 0, "price_change": 0, "removed": 0, "unchanged": 0, "reappeared": 0}

        with self._conn() as conn:
            # Current active vehicles for this dealership
            existing = conn.execute(
                """
                SELECT id, vin, stock_number, price, is_active
                FROM vehicles
                WHERE dealership_id = ?
                """,
                (dealership_id,),
            ).fetchall()

            # Key by VIN when available, otherwise stock number
            by_key: Dict[str, sqlite3.Row] = {}
            for row in existing:
                key = (row["vin"] or "").strip().upper() or f"STOCK:{(row['stock_number'] or '').strip()}"
                if key and key != "STOCK:":
                    by_key[key] = row

            seen_keys = set()

            for v in vehicles:
                vin = (v.get("vin") or "").strip().upper()
                stock = (v.get("stock_number") or "").strip()
                key = vin or (f"STOCK:{stock}" if stock else "")
                if not key:
                    continue
                seen_keys.add(key)

                price = v.get("price")
                try:
                    price = float(price) if price is not None else None
                except (TypeError, ValueError):
                    price = None

                raw = json.dumps(v, default=str)

                if key in by_key:
                    old = by_key[key]
                    vehicle_id = int(old["id"])

                    if old["is_active"] == 0:
                        # Came back
                        conn.execute(
                            """
                            UPDATE vehicles
                            SET is_active = 1, last_seen_at = ?, last_price = ?,
                                price = ?, mileage = ?, listing_url = ?, image_url = ?,
                                year = ?, make = ?, model = ?, trim = ?, condition = ?,
                                raw_json = ?
                            WHERE id = ?
                            """,
                            (
                                now, price, price, v.get("mileage"),
                                v.get("listing_url"), v.get("image_url"),
                                v.get("year"), v.get("make"), v.get("model"),
                                v.get("trim"), v.get("condition"), raw,
                                vehicle_id,
                            ),
                        )
                        conn.execute(
                            """
                            INSERT INTO vehicle_events
                            (vehicle_id, event_type, old_value, new_value, created_at)
                            VALUES (?, 'REAPPEARED', ?, ?, ?)
                            """,
                            (vehicle_id, None, str(price), now),
                        )
                        stats["reappeared"] += 1
                    else:
                        # Still active — check price
                        old_price = old["price"]
                        if (
                            price is not None
                            and old_price is not None
                            and abs(float(old_price) - float(price)) > 0.5
                        ):
                            conn.execute(
                                """
                                UPDATE vehicles
                                SET last_seen_at = ?, last_price = price, price = ?,
                                    mileage = ?, listing_url = ?, image_url = ?,
                                    year = ?, make = ?, model = ?, trim = ?,
                                    condition = ?, raw_json = ?
                                WHERE id = ?
                                """,
                                (
                                    now, price, v.get("mileage"),
                                    v.get("listing_url"), v.get("image_url"),
                                    v.get("year"), v.get("make"), v.get("model"),
                                    v.get("trim"), v.get("condition"), raw,
                                    vehicle_id,
                                ),
                            )
                            conn.execute(
                                """
                                INSERT INTO vehicle_events
                                (vehicle_id, event_type, old_value, new_value, created_at)
                                VALUES (?, 'PRICE_CHANGE', ?, ?, ?)
                                """,
                                (vehicle_id, str(old_price), str(price), now),
                            )
                            stats["price_change"] += 1
                        else:
                            conn.execute(
                                """
                                UPDATE vehicles
                                SET last_seen_at = ?, mileage = ?, listing_url = ?,
                                    image_url = ?, raw_json = ?
                                WHERE id = ?
                                """,
                                (
                                    now, v.get("mileage"),
                                    v.get("listing_url"), v.get("image_url"),
                                    raw, vehicle_id,
                                ),
                            )
                            stats["unchanged"] += 1
                else:
                    # Brand new
                    cur = conn.execute(
                        """
                        INSERT INTO vehicles (
                            dealership_id, vin, stock_number, year, make, model, trim,
                            price, mileage, condition, exterior_color, interior_color,
                            listing_url, image_url, body_style, drivetrain, engine,
                            transmission, fuel_economy, raw_json,
                            first_seen_at, last_seen_at, last_price, is_active
                        ) VALUES (
                            ?, ?, ?, ?, ?, ?, ?,
                            ?, ?, ?, ?, ?,
                            ?, ?, ?, ?, ?,
                            ?, ?, ?,
                            ?, ?, ?, 1
                        )
                        """,
                        (
                            dealership_id,
                            vin or None,
                            stock or None,
                            v.get("year"),
                            v.get("make"),
                            v.get("model"),
                            v.get("trim"),
                            price,
                            v.get("mileage"),
                            v.get("condition"),
                            v.get("exterior_color"),
                            v.get("interior_color"),
                            v.get("listing_url"),
                            v.get("image_url"),
                            v.get("body_style"),
                            v.get("drivetrain"),
                            v.get("engine"),
                            v.get("transmission"),
                            v.get("fuel_economy"),
                            raw,
                            now,
                            now,
                            price,
                        ),
                    )
                    vehicle_id = int(cur.lastrowid)
                    conn.execute(
                        """
                        INSERT INTO vehicle_events
                        (vehicle_id, event_type, old_value, new_value, created_at)
                        VALUES (?, 'NEW', NULL, ?, ?)
                        """,
                        (vehicle_id, str(price) if price is not None else None, now),
                    )
                    stats["new"] += 1

            # Anything we knew about that was not in this scrape → mark REMOVED
            for key, old in by_key.items():
                if key not in seen_keys and old["is_active"] == 1:
                    vehicle_id = int(old["id"])
                    conn.execute(
                        "UPDATE vehicles SET is_active = 0, last_seen_at = ? WHERE id = ?",
                        (now, vehicle_id),
                    )
                    conn.execute(
                        """
                        INSERT INTO vehicle_events
                        (vehicle_id, event_type, old_value, new_value, created_at)
                        VALUES (?, 'REMOVED', ?, NULL, ?)
                        """,
                        (vehicle_id, str(old["price"]), now),
                    )
                    stats["removed"] += 1

            # Update dealership last_scanned_at
            conn.execute(
                "UPDATE dealerships SET last_scanned_at = ? WHERE id = ?",
                (now, dealership_id),
            )

        return stats

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def search_vehicles(
        self,
        dealership_id: Optional[int] = None,
        q: Optional[str] = None,
        year: Optional[int] = None,
        make: Optional[str] = None,
        model: Optional[str] = None,
        condition: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        max_mileage: Optional[int] = None,
        active_only: bool = True,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        clauses = []
        params: List[Any] = []

        if dealership_id is not None:
            clauses.append("v.dealership_id = ?")
            params.append(dealership_id)
        if active_only:
            clauses.append("v.is_active = 1")
        if year is not None:
            clauses.append("v.year = ?")
            params.append(year)
        if make:
            clauses.append("LOWER(v.make) = LOWER(?)")
            params.append(make)
        if model:
            clauses.append("LOWER(v.model) LIKE LOWER(?)")
            params.append(f"%{model}%")
        if condition:
            clauses.append("LOWER(v.condition) = LOWER(?)")
            params.append(condition)
        if min_price is not None:
            clauses.append("v.price >= ?")
            params.append(min_price)
        if max_price is not None:
            clauses.append("v.price <= ?")
            params.append(max_price)
        if max_mileage is not None:
            clauses.append("v.mileage <= ?")
            params.append(max_mileage)
        if q:
            clauses.append(
                """(
                    LOWER(v.vin) LIKE LOWER(?)
                    OR LOWER(v.stock_number) LIKE LOWER(?)
                    OR LOWER(v.make) LIKE LOWER(?)
                    OR LOWER(v.model) LIKE LOWER(?)
                    OR LOWER(v.trim) LIKE LOWER(?)
                )"""
            )
            like = f"%{q}%"
            params.extend([like, like, like, like, like])

        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        sql = f"""
            SELECT v.*, d.name AS dealership_name, d.inventory_url AS dealership_url
            FROM vehicles v
            JOIN dealerships d ON d.id = v.dealership_id
            {where}
            ORDER BY v.last_seen_at DESC
            LIMIT ? OFFSET ?
        """
        params.extend([limit, offset])

        with self._conn() as conn:
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]

    def fill_vdp_fields(self, vehicle_id: int, data: Dict[str, Any]) -> None:
        """
        Fill in stock #/photo/mileage/torque/towing fields pulled from the
        vehicle detail page — but ONLY where we don't already have a value.
        Never overwrites something we already trust (e.g. a listing price
        or a value the list scan already found).
        """
        now = _utcnow()
        with self._conn() as conn:
            conn.execute(
                """
                UPDATE vehicles SET
                    stock_number = CASE WHEN (stock_number IS NULL OR stock_number = '') THEN ? ELSE stock_number END,
                    image_url = CASE WHEN (image_url IS NULL OR image_url = '') THEN ? ELSE image_url END,
                    mileage = CASE WHEN mileage IS NULL THEN ? ELSE mileage END,
                    condition = CASE WHEN (condition IS NULL OR condition = '') THEN ? ELSE condition END,
                    engine_hp = CASE WHEN (engine_hp IS NULL OR engine_hp = '') THEN ? ELSE engine_hp END,
                    transmission = CASE WHEN (transmission IS NULL OR transmission = '') THEN ? ELSE transmission END,
                    engine = CASE WHEN (engine IS NULL OR engine = '') THEN ? ELSE engine END,
                    torque = CASE WHEN (torque IS NULL OR torque = '') THEN ? ELSE torque END,
                    towing_capacity = CASE WHEN (towing_capacity IS NULL OR towing_capacity = '') THEN ? ELSE towing_capacity END,
                    flat_tow = CASE WHEN (flat_tow IS NULL OR flat_tow = '') THEN ? ELSE flat_tow END,
                    vdp_enriched_at = ?
                WHERE id = ?
                """,
                (
                    data.get("stock_number"),
                    data.get("image_url"),
                    data.get("mileage"),
                    data.get("condition"),
                    data.get("engine_hp"),
                    data.get("transmission"),
                    data.get("engine"),
                    data.get("torque"),
                    data.get("towing_capacity"),
                    data.get("flat_tow"),
                    now,
                    vehicle_id,
                ),
            )

    def vehicles_missing_ymm(self, limit: int = 40) -> List[Dict[str, Any]]:
        """Active vehicles that have a VIN but are missing year/make/model."""
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT id, vin FROM vehicles
                WHERE is_active = 1 AND vin IS NOT NULL AND vin != ''
                  AND (year IS NULL OR make IS NULL OR make = '' OR model IS NULL OR model = '')
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]

    def count_missing_ymm(self) -> int:
        with self._conn() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) FROM vehicles
                WHERE is_active = 1 AND vin IS NOT NULL AND vin != ''
                  AND (year IS NULL OR make IS NULL OR make = '' OR model IS NULL OR model = '')
                """
            ).fetchone()
            return int(row[0])

    def fill_nhtsa_fields(self, vehicle_id: int, nhtsa: Dict[str, Any]) -> None:
        """Permanently fill year/make/model/trim/etc. from NHTSA — blanks only."""
        with self._conn() as conn:
            conn.execute(
                """
                UPDATE vehicles SET
                    year = CASE WHEN year IS NULL THEN ? ELSE year END,
                    make = CASE WHEN (make IS NULL OR make = '') THEN ? ELSE make END,
                    model = CASE WHEN (model IS NULL OR model = '') THEN ? ELSE model END,
                    trim = CASE WHEN (trim IS NULL OR trim = '') THEN ? ELSE trim END,
                    body_style = CASE WHEN (body_style IS NULL OR body_style = '') THEN ? ELSE body_style END,
                    drivetrain = CASE WHEN (drivetrain IS NULL OR drivetrain = '') THEN ? ELSE drivetrain END,
                    transmission = CASE WHEN (transmission IS NULL OR transmission = '') THEN ? ELSE transmission END,
                    engine = CASE WHEN (engine IS NULL OR engine = '') THEN ? ELSE engine END
                WHERE id = ?
                """,
                (
                    nhtsa.get("year"),
                    nhtsa.get("make"),
                    nhtsa.get("model"),
                    nhtsa.get("trim"),
                    nhtsa.get("body_style"),
                    nhtsa.get("drivetrain"),
                    nhtsa.get("transmission"),
                    nhtsa.get("engine"),
                    vehicle_id,
                ),
            )

    def get_vehicle(self, vehicle_id: int) -> Optional[Dict[str, Any]]:
        with self._conn() as conn:
            row = conn.execute(
                """
                SELECT v.*, d.name AS dealership_name, d.inventory_url AS dealership_url
                FROM vehicles v
                JOIN dealerships d ON d.id = v.dealership_id
                WHERE v.id = ?
                """,
                (vehicle_id,),
            ).fetchone()
            return dict(row) if row else None

    def get_vehicle_events(self, vehicle_id: int, limit: int = 20) -> List[Dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM vehicle_events
                WHERE vehicle_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (vehicle_id, limit),
            ).fetchall()
            return [dict(r) for r in rows]

    def recent_events(
        self,
        dealership_id: Optional[int] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        clauses = []
        params: List[Any] = []
        if dealership_id is not None:
            clauses.append("v.dealership_id = ?")
            params.append(dealership_id)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        sql = f"""
            SELECT e.*, v.year, v.make, v.model, v.trim, v.vin, v.stock_number,
                   v.price, d.name AS dealership_name
            FROM vehicle_events e
            JOIN vehicles v ON v.id = e.vehicle_id
            JOIN dealerships d ON d.id = v.dealership_id
            {where}
            ORDER BY e.created_at DESC
            LIMIT ?
        """
        params.append(limit)
        with self._conn() as conn:
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]

    def inventory_summary(self, dealership_id: Optional[int] = None) -> Dict[str, Any]:
        with self._conn() as conn:
            if dealership_id is not None:
                active = conn.execute(
                    "SELECT COUNT(*) FROM vehicles WHERE dealership_id = ? AND is_active = 1",
                    (dealership_id,),
                ).fetchone()[0]
                total = conn.execute(
                    "SELECT COUNT(*) FROM vehicles WHERE dealership_id = ?",
                    (dealership_id,),
                ).fetchone()[0]
            else:
                active = conn.execute(
                    "SELECT COUNT(*) FROM vehicles WHERE is_active = 1"
                ).fetchone()[0]
                total = conn.execute("SELECT COUNT(*) FROM vehicles").fetchone()[0]
            return {"active": active, "total_ever_seen": total}
