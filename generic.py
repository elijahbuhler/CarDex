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
            resp = session.get(inventory_url, timeout=30)
            resp.raise_for_status()
        except requests.RequestException:
            return []

        html = resp.text
        soup = BeautifulSoup(html, "lxml")
        records: List[VehicleRecord] = []

        # 1) JSON-LD — walk the whole tree looking for Vehicle / Car / Product nodes
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or "")
            except (json.JSONDecodeError, TypeError):
                continue
            for item in self._walk_jsonld(data):
                rec = self._from_jsonld(item, inventory_url)
                if rec and rec.is_minimally_valid():
                    records.append(rec)

        # 2) Also scan raw HTML for Dealer.com-style embedded vehicle JSON blobs
        if len(records) < 5:
            records.extend(self._from_embedded_vehicle_blobs(html, inventory_url))

        # 3) Very light HTML fallback
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

    def _walk_jsonld(self, node) -> List[Dict[str, Any]]:
        """Recursively find dicts that look like vehicles."""
        found: List[Dict[str, Any]] = []
        if isinstance(node, list):
            for item in node:
                found.extend(self._walk_jsonld(item))
            return found
        if not isinstance(node, dict):
            return found

        t = node.get("@type", "")
        if isinstance(t, list):
            t = " ".join(str(x) for x in t)
        t = str(t).lower()
        if any(x in t for x in ("vehicle", "car", "product")) and (
            node.get("vehicleIdentificationNumber") or node.get("sku") or node.get("name")
        ):
            found.append(node)

        # Common Dealer.com nesting: CollectionPage -> about -> offers -> itemOffered
        for key in ("@graph", "about", "offers", "itemOffered", "itemListElement", "mainEntity"):
            if key in node:
                found.extend(self._walk_jsonld(node[key]))

        # Also walk every value
        for v in node.values():
            if isinstance(v, (dict, list)):
                found.extend(self._walk_jsonld(v))
        return found

    def _from_embedded_vehicle_blobs(self, html: str, base_url: str) -> List[VehicleRecord]:
        """Pull vehicles from inline JSON that contains vehicleIdentificationNumber."""
        records: List[VehicleRecord] = []
        # Find every VIN occurrence and try to expand a nearby JSON object
        for m in re.finditer(r'"vehicleIdentificationNumber"\s*:\s*"([A-HJ-NPR-Z0-9]{17})"', html):
            vin = m.group(1).upper()
            # Walk backward to a likely object start that contains "name" or "@type"
            start = m.start()
            window = html[max(0, start - 2500): m.end() + 1200]
            # Prefer an object that has both name and vehicleIdentificationNumber
            obj_match = re.search(
                r'\{[^{}]*?"(?:name|@type)"[^{}]*?"vehicleIdentificationNumber"\s*:\s*"' + re.escape(vin) + r'"[^{}]*?\}',
                window,
                re.DOTALL,
            )
            if not obj_match:
                # Broader fallback
                obj_match = re.search(
                    r'\{[^{}]*?"vehicleIdentificationNumber"\s*:\s*"' + re.escape(vin) + r'"[^{}]*?\}',
                    window,
                    re.DOTALL,
                )
            if not obj_match:
                # Minimal record from VIN alone + nearby price if present
                price_m = re.search(r'"price"\s*:\s*"?([\d.]+)"?', window)
                name_m = re.search(r'"name"\s*:\s*"([^"]{5,80})"', window)
                url_m = re.search(r'"url"\s*:\s*"(https?://[^"]+)"', window)
                rec = VehicleRecord(
                    vin=vin,
                    price=self.normalize_price(price_m.group(1) if price_m else None),
                    listing_url=url_m.group(1) if url_m else None,
                    extra={"source": "vin-blob"},
                )
                if name_m:
                    name = name_m.group(1)
                    ym = re.match(r"(?:New|Used)?\s*(\d{4})\s+(\w+)\s+(.+)", name.strip())
                    if ym:
                        rec.year = self.normalize_year(ym.group(1))
                        rec.make = ym.group(2)
                        rest = ym.group(3).strip()
                        # crude model/trim split
                        parts = rest.split()
                        rec.model = parts[0] if parts else None
                        if len(parts) > 1:
                            rec.trim = " ".join(parts[1:])
                if rec.is_minimally_valid():
                    records.append(rec)
                continue
            try:
                obj = json.loads(obj_match.group(0))
            except json.JSONDecodeError:
                continue
            rec = self._from_jsonld(obj, base_url)
            if rec and rec.is_minimally_valid():
                records.append(rec)
        return records

    def _from_jsonld(self, item: Dict[str, Any], base_url: str) -> Optional[VehicleRecord]:
        vin = item.get("vehicleIdentificationNumber") or item.get("sku")
        name = item.get("name") or ""
        year = self.normalize_year(item.get("modelDate") or item.get("vehicleModelDate"))
        make = None
        model = None
        trim = None
        condition = None

        brand = item.get("brand")
        if isinstance(brand, dict):
            make = brand.get("name")
        elif isinstance(brand, str):
            make = brand

        model = item.get("model")
        if isinstance(model, dict):
            model = model.get("name")

        # Condition from schema fields
        item_cond = item.get("itemCondition") or item.get("vehicleCondition")
        if item_cond:
            c = str(item_cond).lower()
            if "new" in c:
                condition = "new"
            elif "used" in c or "pre-owned" in c:
                condition = "used"

        # Try to parse year/make/model/trim from name if missing
        # Examples: "New 2025 Jeep Grand Cherokee L ALTITUDE 4X4"
        if name and (not year or not make or not model):
            m = re.match(
                r"(?:New|Used|Certified)?\s*(\d{4})\s+(\w+)\s+(.+)",
                name.strip(),
                re.IGNORECASE,
            )
            if m:
                year = year or self.normalize_year(m.group(1))
                make = make or m.group(2)
                rest = m.group(3).strip()
                known_multi = [
                    "grand cherokee", "grand wagoneer", "wrangler unlimited",
                    "ram 1500", "ram 2500", "ram 3500",
                ]
                rest_lower = rest.lower()
                matched_model = None
                for km in known_multi:
                    if rest_lower.startswith(km):
                        matched_model = rest[: len(km)]
                        trim = rest[len(km):].strip() or None
                        break
                if matched_model:
                    model = model or matched_model
                else:
                    parts = rest.split()
                    model = model or (parts[0] if parts else None)
                    if len(parts) > 1 and not trim:
                        trim = " ".join(parts[1:])
            if not condition and name:
                nl = name.lower()
                if nl.startswith("new"):
                    condition = "new"
                elif nl.startswith("used") or "pre-owned" in nl:
                    condition = "used"

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
