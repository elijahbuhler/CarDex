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


def scrape_vdp(url: str) -> Dict[str, Any]:
    """
    Fetch a vehicle detail page and extract whatever public specs are
    present. Returns a dict containing only the fields it actually found:
    stock_number, image_url, mileage, torque, towing_capacity, flat_tow.
    """
    out: Dict[str, Any] = {}
    if not url:
        return out

    try:
        resp = requests.get(
            url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            },
            timeout=15,
        )
        if resp.status_code != 200:
            return out
    except requests.RequestException:
        return out

    html = resp.text
    soup = BeautifulSoup(html, "lxml")

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
                out["stock_number"] = str(sku).strip()

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

    # --- 2) og:image meta fallback for photo ---
    if not out.get("image_url"):
        og = soup.find("meta", attrs={"property": "og:image"})
        if og and og.get("content"):
            out["image_url"] = og["content"].strip()

    # --- 3) Raw-page fallbacks ---
    # Dealer.com pages often put stock/mileage in inline JSON or JS rather
    # than a normal label/value element. Search the public HTML without
    # inventing a value.
    text = soup.get_text(" ", strip=True)
    raw = html

    if not out.get("stock_number"):
        stock_patterns = [
            r'"(?:stockNumber|stock_number|stockNo|stock)"\\s*:\\s*"([^"]+)"',
            r"(?i)\\b(?:stock|stock\\s*#|stock\\s*number)\\s*[:#-]?\\s*([A-Z0-9-]{3,})",
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
            r'"(?:mileage|odometer|mileageValue)"\\s*:\\s*(?:"([0-9,]+)"|([0-9,]+))',
            r"(?i)\\b(?:mileage|odometer)\\s*[:#-]?\\s*([0-9,]+)\\s*(?:mi|miles)?",
        ]
        for pat in mileage_patterns:
            m = re.search(pat, raw if '"' in pat else text)
            if m:
                val = next((g for g in m.groups() if g), None)
                cleaned = _clean_int(val)
                if cleaned is not None:
                    out["mileage"] = cleaned
                    break

    # --- 4) Spec-sheet scan for stock #, mileage, torque, towing, flat-tow ---
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
