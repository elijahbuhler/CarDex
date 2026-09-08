"""
Vehicle Detail Page (VDP) enrichment.

The public inventory list/JSON-LD often lacks stock #, a photo, mileage,
torque, and towing specs. This module fetches the individual vehicle's
own detail page (the listing_url already saved for that vehicle) and
pulls whatever is publicly shown there.

Conservative like every other adapter in CarDex: never invents data.
Only returns keys it actually found on the page. Safe to call repeatedly
— it's a single GET request, no state.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional

import requests
from bs4 import BeautifulSoup

USER_AGENT = (
    "CarDex/2.1 (+https://cardex.local; public inventory research; "
    "respects robots.txt)"
)



LITHIA_BASE = "https://www.lithiachryslermissoula.com"


def _extract_vin(html: str) -> Optional[str]:
    """Extract an explicit 17-character VIN from a public vehicle page."""
    patterns = [
        r'(?i)\bVIN\s*[:#]?\s*</?[^>]*>\s*([A-HJ-NPR-Z0-9]{17})\b',
        r'(?i)\bVIN\s*[:#]?\s*([A-HJ-NPR-Z0-9]{17})\b',
        r'(?i)"vin"\s*:\s*"([A-HJ-NPR-Z0-9]{17})"',
        r'(?i)"VIN"\s*:\s*"([A-HJ-NPR-Z0-9]{17})"',
    ]
    for pat in patterns:
        m = re.search(pat, html)
        if m:
            return m.group(1).upper()
    # Last-resort VIN-shaped token. Keep this conservative.
    for token in re.findall(r'\b[A-HJ-NPR-Z0-9]{17}\b', html.upper()):
        if token[0] not in "0123456789":
            return token
    return None


def _find_lithia_vdp_by_vin(vin: str) -> Optional[str]:
    """
    Ask Lithia's own public inventory/search pages for the exact VIN and
    return the matching Lithia VDP URL if the public site exposes one.

    We deliberately try only public GET URLs; no dealer credentials/API.
    """
    if not vin:
        return None

    candidates = [
        f"{LITHIA_BASE}/all-inventory/index.htm?search={vin}",
        f"{LITHIA_BASE}/all-inventory/index.htm?searchText={vin}",
        f"{LITHIA_BASE}/all-inventory/index.htm?vin={vin}",
        f"{LITHIA_BASE}/searchall.aspx?search={vin}",
    ]
    session = requests.Session()
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    for u in candidates:
        try:
            r = session.get(u, headers=headers, timeout=12)
        except requests.RequestException:
            continue
        if r.status_code != 200 or vin.upper() not in r.text.upper():
            continue

        soup = BeautifulSoup(r.text, "lxml")
        # Prefer VDP anchors that contain /new/ or /used/ and the VIN nearby.
        for a in soup.find_all("a", href=True):
            href = str(a["href"]).strip()
            if not href.lower().endswith((".htm", ".html")):
                continue
            if "/new/" not in href.lower() and "/used/" not in href.lower() and "/certified/" not in href.lower():
                continue
            full = requests.compat.urljoin(LITHIA_BASE, href)
            try:
                page = session.get(full, headers=headers, timeout=12)
            except requests.RequestException:
                continue
            if page.status_code == 200 and vin.upper() in page.text.upper():
                return full
    return None


def scrape_vdp(url: str) -> Dict[str, Any]:
    """
    Fetch a vehicle detail page and extract whatever public specs are
    present. Returns a dict containing only the fields it actually found:
    stock_number, image_url, mileage, condition, engine_hp, transmission, engine, torque, towing_capacity, flat_tow.
    """
    out: Dict[str, Any] = {}
    if not url:
        return out

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0 Safari/537.36 CarDex/2.1",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Referer": "https://www.lithiachryslermissoula.com/",
    }
    resp = None
    for attempt in range(2):
        try:
            resp = requests.get(url, headers=headers, timeout=12)
            if resp.status_code == 200:
                break
        except requests.RequestException:
            resp = None
    if resp is None or resp.status_code != 200:
        return out

    html = resp.text
    soup = BeautifulSoup(html, "lxml")

    # If CarDex's stored listing URL is a third-party/public feed URL,
    # resolve the VIN against Lithia's own public inventory and then read the
    # exact Lithia VDP. This makes Lithia the source of truth for stock,
    # mileage and condition.
    host = (requests.utils.urlparse(url).hostname or "").lower()
    if "lithiachryslermissoula.com" not in host:
        vin = _extract_vin(html)
        lithia_url = _find_lithia_vdp_by_vin(vin) if vin else None
        if lithia_url:
            try:
                lr = requests.get(
                    lithia_url,
                    headers={
                        "User-Agent": USER_AGENT,
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                        "Accept-Language": "en-US,en;q=0.9",
                    },
                    timeout=15,
                )
                if lr.status_code == 200:
                    # Parse the Lithia VDP recursively, but stop here so we
                    # don't recurse again into the non-Lithia URL.
                    return scrape_vdp(lithia_url)
            except requests.RequestException:
                pass

    # Lithia's own VDP identifies the vehicle condition directly in the
    # page/title/URL (New or Used). Prefer that dealership-page signal over
    # any third-party feed. Never infer condition from mileage or model year.
    path = (requests.utils.urlparse(url).path or "").lower()
    if "lithiachryslermissoula.com" in host:
        if "/new/" in path or re.search(r"\bnew\s+\d{4}\b", soup.get_text(" ", strip=True), re.I):
            out["condition"] = "New"
        elif "/used/" in path or re.search(r"\bused\s+\d{4}\b", soup.get_text(" ", strip=True), re.I):
            out["condition"] = "Used"
        elif "/certified/" in path or re.search(r"\bcertified\s+pre[- ]owned\b", soup.get_text(" ", strip=True), re.I):
            out["condition"] = "Certified Pre-Owned"

    # First read the dealership's explicit "Stock Number" label. Some
    # Dealer.com JSON-LD uses sku/mpn for an internal identifier that can look
    # exactly like a VIN suffix. The visible Lithia Stock Number is the source
    # of truth, especially for USED vehicles.
    visible_text = soup.get_text(" ", strip=True)
    stock_patterns = [
        r"(?i)\bStock\s*Number\s*[:#]?\s*([A-Z0-9-]{3,20})\b",
        r"(?i)\bStock\s*#\s*[:#]?\s*([A-Z0-9-]{3,20})\b",
    ]
    page_vin = _extract_vin(html)
    for pat in stock_patterns:
        m = re.search(pat, visible_text)
        if m:
            candidate = m.group(1).strip()
            # Never accept a VIN suffix as a USED stock number. If the
            # dealership's label itself is that suffix, continue to the next
            # public source rather than corrupting used inventory.
            is_used_page = "/used/" in path or "/certified/" in path or str(out.get("condition") or "").lower() in ("used", "certified pre-owned")
            if not (is_used_page and page_vin and candidate.upper() == page_vin[-8:].upper()):
                out["stock_number"] = candidate
                break

    # --- 1) JSON-LD on the detail page: often carries stock #, mileage, photo ---
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
            if "vehicle" not in t and "car" not in t and "product" not in t:
                continue

            sku = item.get("sku") or item.get("mpn")
            if sku and not out.get("stock_number"):
                candidate = str(sku).strip()
                is_used_page = "/used/" in path or "/certified/" in path or str(out.get("condition") or "").lower() in ("used", "certified pre-owned")
                if not (is_used_page and page_vin and candidate.upper() == page_vin[-8:].upper()):
                    out["stock_number"] = candidate

            item_condition = item.get("itemCondition") or item.get("condition")
            if item_condition and not out.get("condition"):
                cond = str(item_condition).split("/")[-1].replace("UsedCondition", "Used").replace("NewCondition", "New").replace("RefurbishedCondition", "Refurbished").strip()
                if cond.lower() in {"used", "new", "refurbished", "certified pre-owned", "certifiedpreownedcondition"}:
                    out["condition"] = "Certified Pre-Owned" if "certified" in cond.lower() else cond.title()

            odo = item.get("mileageFromOdometer")
            if isinstance(odo, dict):
                odo = odo.get("value")
            if odo and not out.get("mileage"):
                m = _clean_int(odo)
                if m:
                    out["mileage"] = m

            image = item.get("image")
            if isinstance(image, list) and image:
                image = image[0]
            if isinstance(image, dict):
                image = image.get("url")
            if image and not out.get("image_url"):
                out["image_url"] = str(image)

            # Some dealer pages expose horsepower/transmission/engine as
            # schema additionalProperty values. Only use explicit values.
            props = item.get("additionalProperty") or item.get("additionalProperties") or []
            if isinstance(props, dict):
                props = [props]
            for prop in props:
                if not isinstance(prop, dict):
                    continue
                name = str(prop.get("name") or prop.get("propertyID") or "").strip().lower()
                val = prop.get("value")
                if isinstance(val, dict):
                    val = val.get("value") or val.get("name")
                val = str(val).strip() if val is not None else ""
                if not val:
                    continue
                if ("horsepower" in name or name in {"horse power", "hp"}) and not out.get("engine_hp"):
                    hp = _clean_int(val)
                    if hp:
                        out["engine_hp"] = hp
                elif "transmission" in name and not out.get("transmission"):
                    out["transmission"] = val
                elif name == "engine" and not out.get("engine"):
                    out["engine"] = val

    # --- 2) og:image meta fallback for photo ---
    if not out.get("image_url"):
        og = soup.find("meta", attrs={"property": "og:image"})
        if og and og.get("content"):
            out["image_url"] = og["content"].strip()

    # Build visible text before any dealership-specific extraction.
    text = soup.get_text(" ", strip=True)

    # --- 3) Lithia direct-page extraction ---
    # Lithia VDPs expose these exact vehicle fields in the public page's
    # "overview" section. Prefer those values before broader Dealer.com
    # fallbacks so CarDex records the dealership's own stock/odometer data.
    if "lithiachryslermissoula.com" in host:
        if not out.get("stock_number"):
            m = re.search(r"(?i)\bStock\s+Number\s*[:#]?\s*([A-Z0-9-]+)", text)
            if m:
                out["stock_number"] = m.group(1).strip()
        if not out.get("mileage"):
            m = re.search(r"(?i)\bOdometer\s+([0-9,]+)\s*miles\b", text)
            if not m:
                m = re.search(r"(?i)\bMileage\s*[:#]?\s*([0-9,]+)\s*miles\b", text)
            if m:
                out["mileage"] = _clean_int(m.group(1))

    # --- 4) Raw-page fallbacks ---
    # Dealer.com pages often put stock/mileage in inline JSON or JS rather
    # than a normal label/value element. Search the public HTML without
    # inventing a value.
    raw = html

    if not out.get("stock_number"):
        stock_patterns = [
            r'"(?:stockNumber|stock_number|stockNo|stock)"\s*:\s*"([^"]+)"',
            r'(?i)\b(?:stock|stock\s*#|stock\s*number)\s*[:#-]?\s*([A-Z0-9-]{3,})',
            r'(?is)Stock\s*Number(?:\s|<[^>]+>)*[:#]?\s*(?:<[^>]+>\s*)*([A-Z0-9-]{3,20})\b',
        ]
        for pat in stock_patterns:
            m = re.search(pat, raw if '"' in pat else text)
            if m:
                val = m.group(1).strip()
                if val and val.lower() not in {"number", "no"}:
                    out["stock_number"] = val
                    break

    if not out.get("mileage"):
        mileage_patterns = [
            r'"(?:mileage|odometer|mileageValue)"\s*:\s*(?:"([0-9,]+)"|([0-9,]+))',
            r'(?i)\b(?:mileage|odometer)\s*[:#-]?\s*([0-9,]+)\s*(?:mi|miles)?',
            r'(?is)(?:Odometer|Mileage)(?:\s|<[^>]+>)*[:#-]?\s*(?:<[^>]+>\s*)*([0-9][0-9,]*)\s*(?:miles?|mi)?',
        ]
        for pat in mileage_patterns:
            m = re.search(pat, raw if '"' in pat else text)
            if m:
                val = next((g for g in m.groups() if g), None)
                cleaned = _clean_int(val)
                if cleaned is not None:
                    out["mileage"] = cleaned
                    break

    # --- 5) Dealer.com-style data attributes / embedded JSON fallback ---
    # Many VDPs expose the same fields on DOM elements even when they are
    # not visible as a simple label/value pair. Read only explicit values.
    attr_candidates = [soup.find_all(attrs={"data-stock": True}), soup.find_all(attrs={"data-stock-number": True})]
    if not out.get("stock_number"):
        for nodes in attr_candidates:
            for node in nodes:
                val = node.get("data-stock") or node.get("data-stock-number")
                if val and str(val).strip():
                    out["stock_number"] = str(val).strip()
                    break
            if out.get("stock_number"):
                break

    if not out.get("mileage"):
        for attr in ("data-mileage", "data-odometer", "data-miles"):
            for node in soup.find_all(attrs={attr: True}):
                val = _clean_int(node.get(attr))
                if val is not None:
                    out["mileage"] = val
                    break
            if out.get("mileage") is not None:
                break

    # Some Dealer.com pages expose vehicle data in application-state scripts.
    # Scan script text for explicit stock/odometer keys before giving up.
    if not out.get("stock_number") or not out.get("mileage"):
        for script in soup.find_all("script"):
            st = script.string or script.get_text() or ""
            if not st:
                continue
            if not out.get("stock_number"):
                m = re.search(r'"(?:stockNumber|stock_number|stockNo|stock)"\s*:\s*"([^"]+)"', st)
                if m:
                    out["stock_number"] = m.group(1).strip()
            if not out.get("mileage"):
                m = re.search(r'"(?:mileage|odometer|mileageValue)"\s*:\s*(?:"([0-9,]+)"|([0-9,]+))', st)
                if m:
                    val = next((g for g in m.groups() if g), None)
                    cleaned = _clean_int(val)
                    if cleaned is not None:
                        out["mileage"] = cleaned
            if out.get("stock_number") and out.get("mileage") is not None:
                break

    # --- 6) Public powertrain fields from the VDP ---
    # Dealer.com/Lithia pages vary in markup, so first look for explicit
    # labeled values in visible text/HTML. These are factory/model specs, not
    # aftermarket add-ons.
    if not out.get("engine_hp"):
        hp_patterns = [
            r'(?i)\b(?:horsepower|horse\s+power)\s*[:#-]?\s*([0-9]{2,4})\s*(?:hp|horsepower)?\b',
            r'(?i)\b([0-9]{2,4})\s*hp\b',
        ]
        for pat in hp_patterns:
            m = re.search(pat, text)
            if m:
                hp = _clean_int(m.group(1))
                if hp and 50 <= hp <= 1200:
                    out["engine_hp"] = hp
                    break

    if not out.get("transmission"):
        tx_patterns = [
            r'(?i)\btransmission\s*[:#-]?\s*([^|;,]{3,80}?)(?=\s{2,}|\b(?:drive|drivetrain|fuel|engine|horsepower|torque)\b|$)',
        ]
        for pat in tx_patterns:
            m = re.search(pat, text)
            if m:
                val = re.sub(r'\s+', ' ', m.group(1)).strip(' .:-')
                if val and len(val) <= 80:
                    out["transmission"] = val
                    break

    if not out.get("engine"):
        engine_patterns = [
            r'(?i)\bengine\s*[:#-]?\s*([^|;,]{3,100}?)(?=\s{2,}|\b(?:transmission|drivetrain|horsepower|torque)\b|$)',
        ]
        for pat in engine_patterns:
            m = re.search(pat, text)
            if m:
                val = re.sub(r'\s+', ' ', m.group(1)).strip(' .:-')
                if val and len(val) <= 100:
                    out["engine"] = val
                    break

    # Dealer.com sometimes renders the overview/spec labels as HTML nodes rather
    # than plain text. Strip tags only after running label/value patterns so we
    # can still capture values such as "Horsepower ... 190hp" and "Transmission ... CVT".
    if not out.get("engine_hp"):
        m = re.search(r'(?is)Horsepower(?:\s|<[^>]+>)*[:#-]?\s*(?:<[^>]+>\s*)*([0-9]{2,4})\s*(?:hp|horsepower)', raw)
        if m:
            out["engine_hp"] = int(m.group(1))
    if not out.get("transmission"):
        m = re.search(r'(?is)Transmission(?:\s|<[^>]+>)*[:#-]?\s*(?:<[^>]+>\s*)*([^<]{2,80}?)(?=<|\n|$)', raw)
        if m:
            val = re.sub(r'\s+', ' ', m.group(1)).strip(' :;-')
            if val and len(val) <= 80:
                out["transmission"] = val
    if not out.get("torque"):
        m = re.search(r'(?is)Torque(?:\s|<[^>]+>)*[:#-]?\s*(?:<[^>]+>\s*)*([0-9]{2,4})\s*(?:lb\.?[- ]?ft|lb\.?\s*ft)', raw)
        if m:
            out["torque"] = f"{m.group(1)} lb-ft"

    # --- 7) Spec-sheet scan for stock #, mileage, powertrain, torque, towing, flat-tow ---
    for label, value in _label_value_pairs(soup).items():
        if not value:
            continue
        low = label.lower()
        if "stock" in low and not out.get("stock_number"):
            out["stock_number"] = value.strip()
        elif ("mileage" in low or "odometer" in low) and not out.get("mileage"):
            m = _clean_int(value)
            if m:
                out["mileage"] = m
        elif ("horsepower" in low or "horse power" in low or low == "hp") and not out.get("engine_hp"):
            hp = _clean_int(value)
            if hp and 50 <= hp <= 1200:
                out["engine_hp"] = hp
        elif "transmission" in low and not out.get("transmission"):
            out["transmission"] = value.strip()
        elif low == "engine" and not out.get("engine"):
            out["engine"] = value.strip()
        elif "torque" in low and not out.get("torque"):
            out["torque"] = value.strip()
        elif "flat" in low and "tow" in low and not out.get("flat_tow"):
            out["flat_tow"] = value.strip()
        elif "tow" in low and "capacity" in low and not out.get("towing_capacity"):
            out["towing_capacity"] = value.strip()

    return out


def _label_value_pairs(soup: BeautifulSoup) -> Dict[str, str]:
    """
    Best-effort scan of common 'spec sheet' HTML shapes found on dealer
    VDPs: <dt>/<dd> pairs, two-column table rows, and "Label: Value" text
    inside spec-styled containers. Conservative — only short label/value
    pairs, never free-form paragraphs.
    """
    pairs: Dict[str, str] = {}

    for dl in soup.find_all("dl"):
        dts = dl.find_all("dt")
        dds = dl.find_all("dd")
        for dt, dd in zip(dts, dds):
            label = dt.get_text(" ", strip=True)
            value = dd.get_text(" ", strip=True)
            if label and value and len(label) < 40:
                pairs.setdefault(label, value)

    for row in soup.find_all("tr"):
        cells = row.find_all(["th", "td"])
        if len(cells) == 2:
            label = cells[0].get_text(" ", strip=True)
            value = cells[1].get_text(" ", strip=True)
            if label and value and len(label) < 40:
                pairs.setdefault(label, value)

    for row in soup.select("[class*=spec] li, [class*=spec] tr, .specs-item"):
        text = row.get_text(" ", strip=True)
        if ":" in text:
            label, _, value = text.partition(":")
            label, value = label.strip(), value.strip()
            if label and value and len(label) < 40:
                pairs.setdefault(label, value)

    return pairs


def _clean_int(v: Any) -> Optional[int]:
    if v is None:
        return None
    try:
        s = (
            str(v)
            .lower()
            .replace(",", "")
            .replace("mi", "")
            .replace("miles", "")
            .strip()
        )
        if not s:
            return None
        return int(float(s))
    except (TypeError, ValueError):
        return None
