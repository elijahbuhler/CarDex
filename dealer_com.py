"""
Dealer.com-style public inventory adapter.

Many Lithia, AutoNation, and independent stores use Dealer.com platforms.
This adapter looks for common Dealer.com patterns:
- JSON-LD
- data-vehicle / data-vin attributes
- inventory tracking endpoints that are publicly referenced
- vehicle detail page link patterns

Still conservative: never invents values.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from base import BaseAdapter, VehicleRecord
from generic import GenericAdapter


class DealerComAdapter(BaseAdapter):
    key = "dealer_com"
    display_name = "Dealer.com Style"
    description = "Public inventory pages built on Dealer.com / similar platforms."

    USER_AGENT = (
        "CarDex/2.1 (+https://cardex.local; public inventory research; "
        "respects robots.txt)"
    )

    # Common host / path signals
    HOST_HINTS = (
        "dealer.com",
        "ddc",
        "lithia",
    )
    PATH_HINTS = (
        "/all-inventory",
        "/new-inventory",
        "/used-inventory",
        "/inventory",
        "/vehicle-details",
        "/auto/",
    )

    @classmethod
    def can_handle(cls, inventory_url: str) -> bool:
        url = (inventory_url or "").lower()
        if any(h in url for h in cls.HOST_HINTS):
            return True
        if any(p in url for p in cls.PATH_HINTS):
            return True
        # Many dealer.com sites are on custom domains; Generic will still catch them.
        return False

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
        """
        Dealer.com inventory is often paginated with ?start=0, ?start=24, etc.
        We walk pages until we stop finding new vehicles (or hit a safety limit).
        """
        session = self._session()
        generic = GenericAdapter()
        records: List[VehicleRecord] = []
        seen_vins: set = set()

        # Base URL without query string for pagination
        from urllib.parse import urlparse, urlunparse, parse_qs, urlencode

        parsed = urlparse(inventory_url)
        base_no_query = urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))

        page_size = 24
        max_pages = 15  # safety: ~360 vehicles max for now
        empty_streak = 0

        for page in range(max_pages):
            start = page * page_size
            if page == 0:
                page_url = inventory_url
            else:
                page_url = f"{base_no_query}?start={start}"

            try:
                resp = session.get(page_url, timeout=30)
                if resp.status_code != 200:
                    break
            except requests.RequestException:
                break

            html = resp.text
            soup = BeautifulSoup(html, "lxml")
            page_records: List[VehicleRecord] = []

            # JSON-LD + embedded vehicle blobs (via Generic)
            page_records.extend(generic.discover_vehicles(page_url))

            # data-* attributes
            page_records.extend(self._from_data_attributes(soup, page_url))

            # embedded JSON
            page_records.extend(self._from_embedded_json(html, page_url))

            new_on_page = 0
            for r in page_records:
                vin = (r.vin or "").upper()
                key = vin or (r.listing_url or "") or (r.stock_number or "")
                if not key or key in seen_vins:
                    continue
                seen_vins.add(key)
                records.append(r)
                new_on_page += 1

            if new_on_page == 0:
                empty_streak += 1
                if empty_streak >= 2:
                    break
            else:
                empty_streak = 0

            # Be polite between pages
            import time
            time.sleep(0.6)

        return self._dedupe(records)

    def _from_data_attributes(self, soup: BeautifulSoup, base_url: str) -> List[VehicleRecord]:
        records: List[VehicleRecord] = []
        # Common patterns: data-vin, data-vehicle-id, data-year, etc.
        candidates = soup.find_all(
            attrs={
                "data-vin": True,
            }
        )
        candidates += soup.find_all(attrs={"data-vehicle": True})
        candidates += soup.select("[data-year][data-make], .vehicle-card, .inventory-item")

        seen = set()
        for el in candidates:
            vin = (el.get("data-vin") or "").strip().upper()
            if not vin:
                # try nested
                vin_el = el.find(attrs={"data-vin": True})
                if vin_el:
                    vin = (vin_el.get("data-vin") or "").strip().upper()
            if vin and vin in seen:
                continue
            if vin:
                seen.add(vin)

            year = self.normalize_year(el.get("data-year"))
            make = el.get("data-make")
            model = el.get("data-model")
            trim = el.get("data-trim")
            price = self.normalize_price(el.get("data-price") or el.get("data-internet-price"))
            mileage = self.normalize_mileage(el.get("data-mileage") or el.get("data-odometer"))
            stock = el.get("data-stock") or el.get("data-stock-number")
            condition = el.get("data-type") or el.get("data-condition")
            if condition:
                condition = condition.lower()
                if "new" in condition:
                    condition = "new"
                elif "used" in condition or "pre" in condition:
                    condition = "used"

            href = None
            a = el.find("a", href=True) if el.name != "a" else el
            if a and a.get("href"):
                href = urljoin(base_url, a["href"])

            img = None
            img_el = el.find("img")
            if img_el and img_el.get("src"):
                img = urljoin(base_url, img_el["src"])
            elif img_el and img_el.get("data-src"):
                img = urljoin(base_url, img_el["data-src"])

            rec = VehicleRecord(
                vin=vin or None,
                stock_number=stock,
                year=year,
                make=make,
                model=model,
                trim=trim,
                price=price,
                mileage=mileage,
                condition=condition,
                listing_url=href,
                image_url=img,
                extra={"source": "dealer_com_data_attrs"},
            )
            if rec.is_minimally_valid():
                records.append(rec)
        return records

    def _from_embedded_json(self, html: str, base_url: str) -> List[VehicleRecord]:
        records: List[VehicleRecord] = []
        # Look for common embedded JSON blobs
        patterns = [
            r"window\.__INITIAL_STATE__\s*=\s*(\{.+?\});\s*</script>",
            r"window\.DDC\.InvData\s*=\s*(\{.+?\});\s*</script>",
            r'"vehicles"\s*:\s*(\[[^\]]+\])',
        ]
        for pat in patterns:
            for m in re.finditer(pat, html, re.DOTALL):
                try:
                    blob = m.group(1)
                    data = json.loads(blob)
                except (json.JSONDecodeError, IndexError):
                    continue
                items = []
                if isinstance(data, list):
                    items = data
                elif isinstance(data, dict):
                    for key in ("vehicles", "inventory", "items", "results"):
                        if key in data and isinstance(data[key], list):
                            items = data[key]
                            break
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    rec = self._record_from_dict(item, base_url)
                    if rec and rec.is_minimally_valid():
                        records.append(rec)
        return records

    def _record_from_dict(self, item: Dict[str, Any], base_url: str) -> Optional[VehicleRecord]:
        vin = (
            item.get("vin")
            or item.get("VIN")
            or item.get("vehicleIdentificationNumber")
        )
        if vin:
            vin = str(vin).strip().upper()

        return VehicleRecord(
            vin=vin,
            stock_number=item.get("stockNumber") or item.get("stock") or item.get("stock_number"),
            year=self.normalize_year(item.get("year") or item.get("modelYear")),
            make=item.get("make") or item.get("Make"),
            model=item.get("model") or item.get("Model"),
            trim=item.get("trim") or item.get("Trim") or item.get("trimName"),
            price=self.normalize_price(
                item.get("price")
                or item.get("internetPrice")
                or item.get("salePrice")
                or item.get("askingPrice")
            ),
            mileage=self.normalize_mileage(
                item.get("mileage") or item.get("odometer") or item.get("miles")
            ),
            condition=(item.get("type") or item.get("condition") or item.get("newUsed") or "").lower() or None,
            exterior_color=item.get("exteriorColor") or item.get("extColor"),
            interior_color=item.get("interiorColor") or item.get("intColor"),
            listing_url=urljoin(base_url, item["url"]) if item.get("url") else None,
            image_url=item.get("image") or item.get("photo") or item.get("thumbnail"),
            body_style=item.get("bodyStyle") or item.get("bodyType"),
            drivetrain=item.get("drivetrain") or item.get("driveTrain"),
            engine=item.get("engine"),
            transmission=item.get("transmission"),
            extra={"source": "embedded_json"},
        )

    def _find_vdp_links(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        links = set()
        for a in soup.find_all("a", href=True):
            href = a["href"]
            full = urljoin(base_url, href)
            low = full.lower()
            # Typical Dealer.com VDP patterns
            if any(
                p in low
                for p in (
                    "/vehicle-details/",
                    "/inventory/",
                    "/auto/",
                    "vin=",
                    "/new/",
                    "/used/",
                )
            ):
                # Prefer detail-looking paths
                if re.search(r"/\d{4}-", low) or "vin=" in low or "/vehicle" in low:
                    links.add(full.split("#")[0])
        return list(links)

    def _fetch_vdp_light(self, session: requests.Session, url: str) -> Optional[VehicleRecord]:
        try:
            resp = session.get(url, timeout=15)
            if resp.status_code != 200:
                return None
        except requests.RequestException:
            return None

        soup = BeautifulSoup(resp.text, "lxml")
        # Prefer JSON-LD on the detail page
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or "")
            except (json.JSONDecodeError, TypeError):
                continue
            items = data if isinstance(data, list) else [data]
            for item in items:
                if not isinstance(item, dict):
                    continue
                t = str(item.get("@type", "")).lower()
                if "vehicle" in t or "car" in t or "product" in t:
                    generic = GenericAdapter()
                    rec = generic._from_jsonld(item, url)
                    if rec:
                        rec.listing_url = rec.listing_url or url
                        return rec
        return None

    def _dedupe(self, records: List[VehicleRecord]) -> List[VehicleRecord]:
        seen = set()
        out: List[VehicleRecord] = []
        for r in records:
            key = (r.vin or "").upper() or (r.listing_url or "") or (r.stock_number or "")
            if not key or key in seen:
                continue
            seen.add(key)
            out.append(r)
        return out
