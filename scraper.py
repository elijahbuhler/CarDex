"""
Public inventory scraper facade.

Chooses the right adapter, runs discovery, and writes results into the store.
Respects robots.txt at a basic level and never invents data.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests

from base import VehicleRecord, BaseAdapter
from generic import GenericAdapter
from dealer_com import DealerComAdapter
from lithia import LithiaAdapter
from store import InventoryStore


ADAPTER_REGISTRY = [
    LithiaAdapter,
    DealerComAdapter,
    GenericAdapter,
]


def choose_adapter(inventory_url: str) -> BaseAdapter:
    url = (inventory_url or "").strip().lower()
    for cls in ADAPTER_REGISTRY:
        if cls.can_handle(url):
            return cls()
    return GenericAdapter()


def list_adapters() -> List[Dict[str, str]]:
    return [
        {"key": cls.key, "name": cls.display_name, "description": cls.description}
        for cls in ADAPTER_REGISTRY
    ]


class InventoryEngine:
    def __init__(self, store: Optional[InventoryStore] = None):
        self.store = store or InventoryStore()

    def check_robots_allowed(self, inventory_url: str, user_agent: str = "CarDex") -> bool:
        """
        Basic robots.txt check. If robots.txt cannot be fetched we allow
        the request but still stay conservative on rate.
        """
        try:
            parsed = urlparse(inventory_url)
            robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
            rp = RobotFileParser()
            rp.set_url(robots_url)
            rp.read()
            return rp.can_fetch(user_agent, inventory_url)
        except Exception:
            # Fail open for public pages (still polite on rate limits)
            return True

    def discover(
        self,
        inventory_url: str,
        dealership_name: Optional[str] = None,
        force: bool = False,
    ) -> Dict[str, Any]:
        """
        Run a public inventory discovery and save a snapshot.
        """
        inventory_url = (inventory_url or "").strip()
        if not inventory_url.startswith("http"):
            return {"ok": False, "error": "URL must start with http or https"}

        if not force and not self.check_robots_allowed(inventory_url):
            return {
                "ok": False,
                "error": "robots.txt disallows fetching this URL for CarDex. Not proceeding.",
            }

        adapter = choose_adapter(inventory_url)
        name = dealership_name or self._guess_name(inventory_url, adapter.key)

        dealership_id = self.store.upsert_dealership(
            name=name,
            inventory_url=inventory_url,
            adapter_key=adapter.key,
        )

        snapshot_id = self.store.start_snapshot(dealership_id)

        # Small polite pause
        time.sleep(0.5)

        try:
            records: List[VehicleRecord] = adapter.discover_vehicles(inventory_url)
        except Exception as exc:
            self.store.finish_snapshot(snapshot_id, 0)
            return {
                "ok": False,
                "error": f"Adapter failed: {type(exc).__name__}: {exc}",
                "adapter": adapter.key,
                "dealership_id": dealership_id,
            }

        vehicles = [r.to_dict() for r in records if r.is_minimally_valid()]
        stats = self.store.apply_inventory(dealership_id, vehicles)
        self.store.finish_snapshot(snapshot_id, len(vehicles))

        return {
            "ok": True,
            "adapter": adapter.key,
            "adapter_name": adapter.display_name,
            "dealership_id": dealership_id,
            "dealership_name": name,
            "snapshot_id": snapshot_id,
            "vehicles_found": len(vehicles),
            "stats": stats,
            "sample": vehicles[:3],
        }

    def _guess_name(self, url: str, adapter_key: str) -> str:
        host = urlparse(url).netloc.replace("www.", "")
        if "lithiachryslermissoula" in host:
            return "Lithia Chrysler Jeep Dodge Ram Missoula"
        if adapter_key == "lithia":
            return f"Lithia ({host})"
        return host or "Unknown Dealership"

    def list_adapters(self) -> List[Dict[str, str]]:
        return list_adapters()
