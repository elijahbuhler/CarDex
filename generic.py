"""
Generic public-page adapter.

Falls back to JSON-LD + simple HTML patterns when no specialized adapter matches.
Never invents data.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from base import BaseAdapter, VehicleRecord


class GenericAdapter(BaseAdapter):
    key = "generic"
    display_name = "Generic Public Page"
    description = "Best-effort extraction from any public inventory HTML / JSON-LD."

    USER_AGENT = (
        "CarDex/2.1 (+https://cardex.local; public inventory research; "
        "respects robots.txt)"
    )

    @classmethod
    def can_handle(cls, inventory_url: str) -> bool:
        # Always available as fallback
        return True

    def _session(self) -> requests.Session:
        s = requests.Session()
        s.headers.update(
            {
                "User-Agent": self.USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            }
        )
        return s

    def discover_vehicles(self, inventory_url: str) -> List[VehicleRecord]:
        session = self._session()
        try:
            resp = session.get(inventory_url, timeout=25)
            resp.raise_for_status()
        except requests.RequestException:
            return []

        html = resp.text
        soup = BeautifulSoup(html, "lxml")
        records: List[VehicleRecord] = []

        # 1) JSON-LD Vehicle / Car / Product
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or "")
            except (json.JSONDecodeError, TypeError):
                continue
            items = data if isinstance(data, list) else [data]
            for item in items:
                if not isinstance(item, dict):
                    continue
                # Sometimes nested under @graph
                if "@graph" in item:
                    items.extend(item["@graph"])
                    continue
                t = item.get("@type", "")
                if isinstance(t, list):
                    t = " ".join(t)
                if any(x in str(t).lower() for x in ("vehicle", "car", "product")):
                    rec = self._from_jsonld(item, inventory_url)
                    if rec and rec.is_minimally_valid():
                        records.append(rec)

        # 2) Very light HTML fallback — look for common data attributes / VIN patterns
        if not records:
            records.extend(self._from_html_hints(soup, inventory_url))

        # Deduplicate by VIN or listing_url
        seen = set()
        unique: List[VehicleRecord] = []
        for r in records:
            key = (r.vin or "").upper() or (r.listing_url or "")
            if key and key not in seen:
                seen.add(key)
                unique.append(r)
        return unique

    def _from_jsonld(self, item: Dict[str, Any], base_url: str) -> Optional[VehicleRecord]:
        vin = item.get("vehicleIdentificationNumber") or item.get("sku")
        name = item.get("name") or ""
        year = self.normalize_year(item.get("modelDate") or item.get("vehicleModelDate"))
        make = None
        model = None
        trim = None

        brand = item.get("brand")
        if isinstance(brand, dict):
            make = brand.get("name")
        elif isinstance(brand, str):
            make = brand

        model = item.get("model")
        if isinstance(model, dict):
            model = model.get("name")

        # Try to parse year/make/model from name if missing
        if name and (not year or not make or not model):
            m = re.match(r"(\d{4})\s+(\w+)\s+(.+)", name.strip())
            if m:
                year = year or self.normalize_year(m.group(1))
                make = make or m.group(2)
                model = model or m.group(3).split()[0] if m.group(3) else None

        offers = item.get("offers") or {}
        if isinstance(offers, list) and offers:
            offers = offers[0]
        price = None
        if isinstance(offers, dict):
            price = self.normalize_price(offers.get("price") or offers.get("lowPrice"))

        mileage = None
        odo = item.get("mileageFromOdometer")
        if isinstance(odo, dict):
            mileage = self.normalize_mileage(odo.get("value"))
        elif odo is not None:
            mileage = self.normalize_mileage(odo)

        image = item.get("image")
        if isinstance(image, list) and image:
            image = image[0]
        if isinstance(image, dict):
            image = image.get("url")

        url = item.get("url")
        if url:
            url = urljoin(base_url, url)

        condition = None
        item_cond = item.get("itemCondition") or item.get("vehicleCondition")
        if item_cond:
            c = str(item_cond).lower()
            if "new" in c:
                condition = "new"
            elif "used" in c or "pre-owned" in c:
                condition = "used"

        return VehicleRecord(
            vin=str(vin).strip().upper() if vin else None,
            year=year,
            make=make,
            model=model,
            trim=trim,
            price=price,
            mileage=mileage,
            condition=condition,
            listing_url=url,
            image_url=str(image) if image else None,
            body_style=item.get("bodyType"),
            drivetrain=item.get("driveWheelConfiguration") or item.get("vehicleDriveType"),
            engine=item.get("vehicleEngine") if isinstance(item.get("vehicleEngine"), str) else None,
            transmission=item.get("vehicleTransmission"),
            fuel_economy=None,
            extra={"source": "json-ld"},
        )

    def _from_html_hints(self, soup: BeautifulSoup, base_url: str) -> List[VehicleRecord]:
        """Very conservative HTML scan — only high-confidence patterns."""
        records: List[VehicleRecord] = []
        # Look for VIN-looking strings near links
        vin_re = re.compile(r"\b([A-HJ-NPR-Z0-9]{17})\b")
        for a in soup.find_all("a", href=True):
            href = a["href"]
            text = a.get_text(" ", strip=True)
            combined = f"{href} {text}"
            m = vin_re.search(combined)
            if not m:
                continue
            vin = m.group(1).upper()
            url = urljoin(base_url, href)
            # Skip non-vehicle links
            if any(x in url.lower() for x in ("javascript:", "mailto:", "#")):
                continue
            records.append(
                VehicleRecord(
                    vin=vin,
                    listing_url=url,
                    extra={"source": "html-vin-hint"},
                )
            )
        return records
