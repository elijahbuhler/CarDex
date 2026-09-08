"""
CarDex Sales Brain V3 — model-year sales intelligence.

Design:
- Exact listing/VIN data wins for vehicle-specific facts.
- Model-year facts are used for ordinary specs such as engine, transmission,
  drivetrain layout, horsepower, torque and published maximum towing.
- Trim/package/accessory features are NEVER assumed unless the listing/VIN
  proves them.
- Competitor comparisons are model-year references, NOT competitor VIN lookups.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple
import re


def _clean(v: Any) -> str:
    return re.sub(r"\s+", " ", str(v or "").strip().lower())


def _normalize_model(make: Any, model: Any, trim: Any = "") -> str:
    """Normalize inventory naming without treating trim/package text as model data."""
    m = _clean(model)
    make_n = _clean(make)
    # Common feed variants. Keep model-level identity, strip only obvious trim
    # suffixes; never use trim/package features as factual assumptions.
    aliases = {
        "grand cherokee l": "grand cherokee l",
        "grand cherokee long wheelbase": "grand cherokee l",
        "grand cherokee": "grand cherokee",
        "grand highlander": "grand highlander",
        "4runner": "4runner",
        "explorer": "explorer",
        "pilot": "pilot",
        "traverse": "traverse",
    }
    if m in aliases:
        return aliases[m]
    if m in {"mazda 6", "mazda6"}:
        return "mazda6"
    # Prefer known model prefixes, e.g. "grand cherokee l laredo".
    known = sorted([
        "grand cherokee l", "grand cherokee", "grand highlander",
        "4runner", "explorer", "pilot", "traverse", "wrangler",
        "compass", "gladiator", "1500", "2500", "3500",
    ], key=len, reverse=True)
    for base in known:
        if m.startswith(base + " "):
            return base
    return m


def _year(v: Any) -> Optional[int]:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _key(vehicle: Dict[str, Any]) -> Tuple[Optional[int], str, str]:
    return (_year(vehicle.get("year")), _clean(vehicle.get("make")), _normalize_model(vehicle.get("make"), vehicle.get("model"), vehicle.get("trim")))


# Model-year reference facts. These are deliberately model-level.
# Trim-specific options/packages are not included here.
MODEL_YEAR_DATA: Dict[Tuple[int, str, str], Dict[str, Any]] = {
    # 2020 Grand Cherokee — manufacturer model-level information.
    (2020, "jeep", "grand cherokee"): {
        "engine": "3.6L Pentastar V6",
        "hp": 295,
        "torque": 260,
        "transmission": "8-speed automatic",
        "drivetrain": "2WD or available 4x4",
        "body_style": "SUV",
        "towing": "Up to 6,200 lbs with the proper engine/equipment",
        "flat_tow": "Certain 4x4 configurations can be flat-towed; transfer-case/procedure requirements apply",
        "feature_summary": "5-passenger SUV; available 4x4 systems; available Selec-Terrain capability; trim/package equipment varies.",
        "source": "2020 Jeep model information",
    },
    (2020, "ford", "explorer"): {
        "engine": "2.3L EcoBoost I-4",
        "hp": 300,
        "torque": 310,
        "transmission": "10-speed automatic",
        "drivetrain": "RWD or available Intelligent 4WD",
        "body_style": "3-row SUV",
        "towing": "Up to 5,600 lbs when properly equipped",
        "flat_tow": "Not a general model-level flat-tow claim; verify exact configuration/owner manual",
        "feature_summary": "3-row SUV; rear-wheel-drive-based platform; available Intelligent 4WD and Terrain Management.",
        "source": "2020 Ford Explorer model information",
    },
    (2020, "toyota", "highlander"): {
        "engine": "3.5L V6",
        "hp": 295,
        "torque": 263,
        "transmission": "8-speed automatic",
        "drivetrain": "FWD or available AWD",
        "body_style": "3-row SUV",
        "towing": "Up to 5,000 lbs when properly equipped",
        "flat_tow": "Verify exact configuration/owner manual",
        "feature_summary": "3-row family SUV; strong family/comfort positioning; available AWD.",
        "source": "2020 Toyota Highlander model information",
    },
    (2020, "honda", "pilot"): {
        "engine": "3.5L V6",
        "hp": 280,
        "torque": 262,
        "transmission": "9-speed automatic on most trims; 6-speed on LX",
        "drivetrain": "FWD or available AWD",
        "body_style": "3-row SUV",
        "towing": "Up to 5,000 lbs when properly equipped",
        "flat_tow": "Verify exact configuration/owner manual",
        "feature_summary": "3-row family SUV; available AWD; strong family-space and safety positioning.",
        "source": "2020 Honda Pilot model information",
    },
    (2020, "toyota", "4runner"): {
        "engine": "4.0L V6",
        "hp": 270,
        "torque": 278,
        "transmission": "5-speed automatic",
        "drivetrain": "2WD or available 4WD",
        "body_style": "SUV",
        "towing": "Up to 5,000 lbs",
        "flat_tow": "Verify exact configuration/owner manual",
        "feature_summary": "Body-on-frame SUV; available part-time 4WD; 4WD systems include low-range capability.",
        "source": "2020 Toyota 4Runner model information",
    },
    (2020, "chevrolet", "traverse"): {
        "engine": "3.6L V6",
        "hp": 310,
        "torque": 266,
        "transmission": "9-speed automatic",
        "drivetrain": "FWD or available AWD",
        "body_style": "3-row SUV",
        "towing": "Up to 5,000 lbs when properly equipped",
        "flat_tow": "Verify exact configuration/owner manual",
        "feature_summary": "3-row crossover; strong passenger/cargo-space positioning; available AWD.",
        "source": "2020 Chevrolet Traverse model information",
    },

    # 2025 Grand Cherokee L and common model-year competitors.
    (2025, "jeep", "grand cherokee l"): {
        "engine": "3.6L Pentastar V6",
        "hp": 293,
        "torque": 260,
        "transmission": "8-speed automatic",
        "drivetrain": "RWD or available 4x4",
        "body_style": "3-row SUV",
        "towing": "Up to 6,200 lbs with the proper towing equipment",
        "flat_tow": "Only 4WD configurations with the required 4WD low-range transfer case can be flat-towed; do not assume a Laredo is flat-towable without verifying the actual drivetrain.",
        "feature_summary": "Three-row SUV seating up to seven; 3.6L V6; available 4x4; 17.2 cu. ft. behind the third row and up to 84.6 cu. ft. with rows folded.",
        "source": "2025 Jeep Grand Cherokee L model specifications / owner's manual",
    },
    (2025, "ford", "explorer"): {
        "engine": "2.3L EcoBoost I-4",
        "hp": 300,
        "torque": 310,
        "transmission": "10-speed automatic",
        "drivetrain": "RWD or available 4WD",
        "body_style": "3-row SUV",
        "towing": "Up to 5,000 lbs when properly equipped",
        "flat_tow": "Verify exact configuration/owner manual",
        "feature_summary": "Three-row SUV; standard Class III trailer tow package; available 3.0L EcoBoost V6 on Platinum; available 4WD and Terrain Management; BlueCruise available on select trims.",
        "source": "2025 Ford Explorer technical specifications / Ford model information",
    },
    (2025, "toyota", "grand highlander"): {
        "engine": "2.4L turbo I4 gas (gas model reference)",
        "hp": 265,
        "torque": 310,
        "transmission": "8-speed automatic (gas models)",
        "drivetrain": "FWD or available AWD",
        "body_style": "3-row SUV",
        "towing": "Up to 5,000 lbs",
        "flat_tow": "Verify exact configuration/owner manual",
        "feature_summary": "Three-row SUV with seating up to eight; up to 97.5 cu. ft. of cargo space; available AWD; gas, hybrid and Hybrid MAX powertrains; Toyota Safety Sense 3.0.",
        "source": "2025 Toyota Grand Highlander model information",
    },
    (2025, "honda", "pilot"): {
        "engine": "3.5L V6",
        "hp": 285,
        "torque": 262,
        "transmission": "10-speed automatic",
        "drivetrain": "2WD or available AWD",
        "body_style": "3-row SUV",
        "towing": "Up to 5,000 lbs when properly equipped (AWD)",
        "flat_tow": "Verify exact configuration/owner manual",
        "feature_summary": "Three-row SUV; available i-VTM4 AWD; TrailSport adds off-road-oriented equipment; 10-speed automatic; towing varies by drivetrain/load conditions.",
        "source": "2025 Honda Pilot model information",
    },
    (2025, "chevrolet", "traverse"): {
        "engine": "2.5L turbocharged I4",
        "hp": 328,
        "torque": 326,
        "transmission": "8-speed automatic",
        "drivetrain": "FWD or available AWD",
        "body_style": "3-row SUV",
        "towing": "Up to 5,000 lbs with included trailering equipment",
        "flat_tow": "Verify exact configuration/owner manual",
        "feature_summary": "Three-row SUV; 7- or available 8-passenger seating; up to 98 cu. ft. cargo behind the first row; available AWD and Super Cruise on applicable configurations.",
        "source": "2025 Chevrolet Traverse model information",
    },

    # 2021 common comparisons.
    (2021, "jeep", "grand cherokee"): {
        "engine": "3.6L Pentastar V6",
        "hp": 293, "torque": 260, "transmission": "8-speed automatic",
        "drivetrain": "2WD or available 4x4", "body_style": "SUV",
        "towing": "Up to 6,200 lbs with proper equipment",
        "flat_tow": "Certain 4x4 configurations can be flat-towed; verify transfer-case requirements",
        "feature_summary": "5-passenger SUV; available 4x4 systems; trim/package equipment varies.",
        "source": "2021 Jeep Grand Cherokee model information",
    },
    (2021, "ford", "explorer"): {
        "engine": "2.3L EcoBoost I-4", "hp": 300, "torque": 310,
        "transmission": "10-speed automatic", "drivetrain": "RWD or available Intelligent 4WD",
        "body_style": "3-row SUV", "towing": "Up to 5,600 lbs when properly equipped",
        "flat_tow": "Verify exact configuration/owner manual",
        "feature_summary": "3-row SUV; rear-wheel-drive-based platform; available 4WD and Terrain Management.",
        "source": "2021 Ford Explorer model information",
    },
    (2021, "toyota", "highlander"): {
        "engine": "3.5L V6", "hp": 295, "torque": 263,
        "transmission": "8-speed automatic", "drivetrain": "FWD or available AWD",
        "body_style": "3-row SUV", "towing": "Up to 5,000 lbs when properly equipped",
        "flat_tow": "Verify exact configuration/owner manual",
        "feature_summary": "3-row family SUV; available AWD; family/comfort-oriented packaging.",
        "source": "2021 Toyota Highlander model information",
    },
    (2021, "honda", "pilot"): {
        "engine": "3.5L V6", "hp": 280, "torque": 262,
        "transmission": "9-speed automatic on most trims; 6-speed on LX",
        "drivetrain": "FWD or available AWD", "body_style": "3-row SUV",
        "towing": "Up to 5,000 lbs when properly equipped",
        "flat_tow": "Verify exact configuration/owner manual",
        "feature_summary": "3-row family SUV; available AWD; family-space and safety positioning.",
        "source": "2021 Honda Pilot model information",
    },
    (2021, "toyota", "4runner"): {
        "engine": "4.0L V6", "hp": 270, "torque": 278,
        "transmission": "5-speed automatic", "drivetrain": "2WD or available 4WD",
        "body_style": "SUV", "towing": "Up to 5,000 lbs",
        "flat_tow": "Verify exact configuration/owner manual",
        "feature_summary": "Body-on-frame SUV; available 4WD and low-range capability.",
        "source": "2021 Toyota 4Runner model information",
    },
}

# Common sedan cross-shop references. These are model-level baselines, not VIN/trim
# matches. Where a model has multiple powertrains, the profile intentionally uses
# the mainstream gas configuration so a used listing still gets a useful comparison.
for _y in (2020, 2021, 2022, 2023, 2024, 2025):
    MODEL_YEAR_DATA.setdefault((_y, "honda", "accord"), {
        "engine": "1.5L turbocharged I4 (gas reference)",
        "hp": 192,
        "torque": 192,
        "transmission": "CVT",
        "drivetrain": "FWD",
        "body_style": "Midsize sedan",
        "towing": "Not rated for towing",
        "flat_tow": "Not designed for recreational flat towing",
        "feature_summary": "Midsize sedan; powertrain and equipment vary by trim/year; hybrid and higher-output configurations exist in some years.",
        "source": "Honda Accord model-year manufacturer specifications",
    })
    MODEL_YEAR_DATA.setdefault((_y, "toyota", "camry"), {
        "engine": "2.5L 4-cylinder gas reference" if _y < 2025 else "2.5L 4-cylinder hybrid",
        "hp": 203 if _y < 2025 else 225,
        "torque": 184 if _y < 2025 else None,
        "transmission": "8-speed automatic" if _y < 2025 else "eCVT",
        "drivetrain": "FWD or available AWD",
        "body_style": "Midsize sedan",
        "towing": "Not rated for towing",
        "flat_tow": "Not designed for recreational flat towing",
        "feature_summary": "Midsize sedan; drivetrain and powertrain vary by year/trim.",
        "source": "Toyota Camry model-year manufacturer specifications",
    })
    MODEL_YEAR_DATA.setdefault((_y, "nissan", "altima"), {
        "engine": "2.5L 4-cylinder gas reference",
        "hp": 188,
        "torque": 180,
        "transmission": "Xtronic CVT",
        "drivetrain": "FWD or available AWD",
        "body_style": "Midsize sedan",
        "towing": "Not rated for towing",
        "flat_tow": "Not designed for recreational flat towing",
        "feature_summary": "Midsize sedan; available AWD on applicable years/trims; powertrain varies by trim.",
        "source": "Nissan Altima model-year manufacturer specifications",
    })
    MODEL_YEAR_DATA.setdefault((_y, "mazda", "mazda6"), {
        "engine": "2.5L 4-cylinder gas reference",
        "hp": 187,
        "torque": 186,
        "transmission": "6-speed automatic",
        "drivetrain": "FWD",
        "body_style": "Midsize sedan",
        "towing": "Not rated for towing",
        "flat_tow": "Not designed for recreational flat towing",
        "feature_summary": "Midsize sedan; available turbocharged powertrain on some trims/years.",
        "source": "Mazda6 model-year manufacturer specifications",
    })


COMPETITORS = {
    "jeep grand cherokee": ["Ford Explorer", "Toyota Highlander", "Honda Pilot", "Toyota 4Runner", "Chevrolet Traverse"],
    "jeep grand cherokee l": ["Ford Explorer", "Toyota Grand Highlander", "Honda Pilot", "Chevrolet Traverse"],
    "jeep wrangler": ["Ford Bronco", "Toyota 4Runner"],
    "jeep compass": ["Ford Escape", "Honda CR-V", "Toyota RAV4"],
    "jeep gladiator": ["Ford Ranger", "Toyota Tacoma", "Chevrolet Colorado"],
    "ram 1500": ["Ford F-150", "Chevrolet Silverado 1500", "GMC Sierra 1500", "Toyota Tundra"],
    "ram 2500": ["Ford F-250", "Chevrolet Silverado 2500HD", "GMC Sierra 2500HD"],
    "ram 3500": ["Ford F-350", "Chevrolet Silverado 3500HD", "GMC Sierra 3500HD"],
    "ford explorer": ["Jeep Grand Cherokee", "Toyota Highlander", "Honda Pilot", "Chevrolet Traverse"],
    "toyota highlander": ["Jeep Grand Cherokee", "Ford Explorer", "Honda Pilot", "Chevrolet Traverse"],
    "honda pilot": ["Jeep Grand Cherokee", "Ford Explorer", "Toyota Highlander", "Chevrolet Traverse"],
    "toyota 4runner": ["Jeep Grand Cherokee", "Ford Bronco"],
    "chevrolet traverse": ["Jeep Grand Cherokee", "Ford Explorer", "Toyota Highlander", "Honda Pilot"],
    "honda accord": ["Toyota Camry", "Nissan Altima", "Mazda 6"],
    "toyota camry": ["Honda Accord", "Nissan Altima", "Mazda 6"],
    "nissan altima": ["Honda Accord", "Toyota Camry", "Mazda 6"],
}


def _model_profile(year: Optional[int], make: str, model: str) -> Dict[str, Any]:
    """Resolve a model-year profile even when the listing model includes its trim."""
    if year is None:
        return {}

    exact = MODEL_YEAR_DATA.get((year, make, model))
    if exact:
        return exact

    # Inventory feeds sometimes put the trim after the model name, e.g.
    # "Grand Cherokee L Laredo". Match the model-year base model without
    # treating trim/package equipment as model-level facts.
    candidates = [
        (k, v) for k, v in MODEL_YEAR_DATA.items()
        if k[0] == year and k[1] == make
    ]
    candidates.sort(key=lambda item: (abs(item[0][0] - year), -len(item[0][2])))
    for (yy, mmake, mmodel), profile in candidates:
        if model == mmodel or model.startswith(mmodel + " ") or mmodel.startswith(model + " "):
            # A same-model nearby-year profile is still useful model-level
            # reference data when the exact year is not in the table.
            return profile
    return {}


def _general_profile(year: Optional[int], make: str, model: str) -> Dict[str, Any]:
    """Return only stable family-level facts when an exact model-year table entry isn't present."""
    if not make or not model:
        return {}
    # These are deliberately descriptive rather than invented numbers.
    families = {
        "jeep grand cherokee": {
            "body_style": "5-passenger SUV",
            "feature_summary": "5-passenger SUV with available 4x4 capability; trim/package equipment varies.",
            "flat_tow": "Flat-tow capability depends on the exact drivetrain/transfer-case configuration; verify owner manual.",
        },
        "ford explorer": {
            "body_style": "3-row SUV",
            "feature_summary": "3-row SUV with rear-wheel-drive-based architecture on modern generations; drivetrain and equipment vary by year/trim.",
            "flat_tow": "Verify exact configuration/owner manual.",
        },
        "toyota highlander": {
            "body_style": "3-row SUV",
            "feature_summary": "3-row family SUV; FWD/AWD and powertrains vary by year.",
            "flat_tow": "Verify exact configuration/owner manual.",
        },
        "honda pilot": {
            "body_style": "3-row SUV",
            "feature_summary": "3-row family SUV with FWD/AWD availability depending on year.",
            "flat_tow": "Verify exact configuration/owner manual.",
        },
        "toyota 4runner": {
            "body_style": "SUV",
            "feature_summary": "Body-on-frame SUV with available 4WD/low-range capability depending on trim/year.",
            "flat_tow": "Verify exact configuration/owner manual.",
        },
    }
    return families.get(f"{make} {model}", {})


def resolve_fallbacks(vehicle: Dict[str, Any], nhtsa: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    nhtsa = nhtsa or {}
    year, make, model = _key(vehicle)
    profile = _model_profile(year, make, model) or _general_profile(year, make, model)
    result: Dict[str, Any] = {}

    for field in ("engine", "transmission", "drivetrain", "body_style", "flat_tow", "towing_capacity"):
        if not vehicle.get(field) and profile.get(field):
            result[field] = profile[field]

    if not nhtsa.get("engine_hp") and not vehicle.get("engine_hp") and profile.get("hp"):
        result["engine_hp"] = profile["hp"]
    if not vehicle.get("torque") and profile.get("torque"):
        result["torque"] = f"{profile['torque']} lb-ft"

    if profile:
        result["source"] = "CarDex model-year reference"
        result["confidence"] = "model-level"
        result["note"] = "General model-year facts are used only for ordinary specifications. Trim/package/add-on equipment is not assumed."
    return result


def competitor_list(vehicle: Dict[str, Any]) -> List[str]:
    """Return comparison models for every vehicle, including used inventory.

    Comparisons are intentionally model-level. If an exact make/model pair is
    not in COMPETITORS yet, choose a sensible same-class cross-shop set rather
    than hiding the entire Competitive Intelligence section.
    """
    make = _clean(vehicle.get("make"))
    model = _normalize_model(vehicle.get("make"), vehicle.get("model"), vehicle.get("trim"))
    key = f"{make} {model}".strip()
    if key in COMPETITORS:
        return COMPETITORS[key]

    text = f"{make} {model}"
    # Full-size / heavy-duty pickups
    if any(x in text for x in ("2500", "3500", "f-250", "f-350", "silverado 2500", "silverado 3500", "sierra 2500", "sierra 3500")):
        return ["Ford F-250", "Chevrolet Silverado 2500HD", "GMC Sierra 2500HD"]
    if any(x in text for x in ("1500", "f-150", "silverado 1500", "sierra 1500", "tundra", "titan")):
        return ["Ford F-150", "Chevrolet Silverado 1500", "GMC Sierra 1500"]
    # Midsize pickups
    if any(x in text for x in ("ranger", "tacoma", "colorado", "canyon", "frontier", "gladiator")):
        return ["Ford Ranger", "Toyota Tacoma", "Chevrolet Colorado"]
    # Three-row SUVs / family SUVs
    if any(x in text for x in ("grand cherokee l", "explorer", "highlander", "pilot", "traverse", "grand highlander", "telluride", "palisade", "atlas", "pathfinder", "durango", "acadia", "cx-90", "cx-9")):
        return ["Ford Explorer", "Toyota Highlander", "Honda Pilot"]
    # Off-road / body-on-frame SUVs
    if any(x in text for x in ("4runner", "bronco", "wrangler", "sequoia", "armada", "gx", "gladiator")):
        return ["Toyota 4Runner", "Ford Bronco", "Jeep Wrangler"]
    # Compact / midsize crossover set
    if any(x in text for x in ("cr-v", "rav4", "escape", "rogue", "equinox", "terrain", "tucson", "sportage", "cx-5", "cx-50", "compass", "forester", "outback")):
        return ["Honda CR-V", "Toyota RAV4", "Ford Escape"]
    # Minivans
    if any(x in text for x in ("pacifica", "odyssey", "sienna", "carnival")):
        return ["Chrysler Pacifica", "Honda Odyssey", "Toyota Sienna"]
    # Cars / default cross-shop set. Still useful when a dealer has a model
    # that has not yet been added to the explicit comparison map.
    return ["Toyota Camry", "Honda Accord", "Nissan Altima"]


def _profile_for_name(year: Optional[int], name: str) -> Dict[str, Any]:
    parts = name.lower().split()
    if len(parts) < 2:
        return {}
    make = parts[0]
    model = " ".join(parts[1:])
    # Multi-token/brand-model aliases used by the comparison list.
    if make == "mazda" and model in {"6", "mazda6"}:
        model = "mazda6"
    return _model_profile(year, make, model) or _general_profile(year, make, model)



def _tow_num(v: Any) -> Optional[int]:
    """Extract a published towing number; reject N/A/NaN rather than surfacing it."""
    text = str(v or "")
    if not text or re.search(r"\b(?:n/?a|nan|unknown|null)\b", text, re.I):
        return None
    m = re.search(r"([0-9][0-9,]*)\s*(?:lbs?|pounds?)", text, re.I)
    return int(m.group(1).replace(",", "")) if m else None


def _tow_text(v: Any) -> Optional[str]:
    n = _tow_num(v)
    if n is None:
        return None
    return str(v).strip()

def _number(v: Any) -> Optional[float]:
    try:
        if v is None or str(v).strip() == "":
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _comparison(vehicle: Dict[str, Any], rival: str) -> Dict[str, Any]:
    year, make, model = _key(vehicle)
    base = _model_profile(year, make, model) or _general_profile(year, make, model)
    rival_data = _profile_for_name(year, rival)

    # If exact model-year numbers exist, use them. Otherwise use listing/NHTSA
    # numbers for the actual vehicle and clearly label the comparison.
    actual_hp = _number((vehicle.get("engine_hp") or (vehicle.get("nhtsa") or {}).get("engine_hp") or base.get("hp")))
    actual_tq = _number(vehicle.get("torque"))
    if actual_tq is None:
        actual_tq = _number(base.get("torque"))

    rival_hp = _number(rival_data.get("hp"))
    rival_tq = _number(rival_data.get("torque"))

    lines: List[str] = []
    if actual_hp is not None and rival_hp is not None:
        delta = actual_hp - rival_hp
        lines.append(f"Power: {int(actual_hp)} hp vs {int(rival_hp)} hp ({'+' if delta >= 0 else ''}{int(delta)} hp).")
    if actual_tq is not None and rival_tq is not None:
        delta = actual_tq - rival_tq
        lines.append(f"Torque: {int(actual_tq)} lb-ft vs {int(rival_tq)} lb-ft ({'+' if delta >= 0 else ''}{int(delta)} lb-ft).")
    if base.get("transmission") and rival_data.get("transmission"):
        lines.append(f"Transmission: {base['transmission']} vs {rival_data['transmission']}.")
    if base.get("drivetrain") and rival_data.get("drivetrain"):
        lines.append(f"Drivetrain: {base['drivetrain']} vs {rival_data['drivetrain']}.")
    if base.get("body_style") and rival_data.get("body_style"):
        lines.append(f"Vehicle format: {base['body_style']} vs {rival_data['body_style']}.")
    base_tow_text = _tow_text(base.get("towing"))
    rival_tow_text = _tow_text(rival_data.get("towing"))
    if base_tow_text and rival_tow_text:
        lines.append(f"Towing reference: {base_tow_text} vs {rival_tow_text}.")
    elif rival_tow_text:
        # Never show a blank/N/A towing field when a verified model-year
        # towing reference exists.
        lines.append(f"Towing reference: {rival_tow_text}.")

    if rival_data.get("feature_summary"):
        lines.append(f"{rival} model-year focus: {rival_data['feature_summary']}")

    if make == "jeep" and "grand cherokee" in model:
        if rival.lower().startswith("ford explorer"):
            angle = "The Explorer is a serious 3-row competitor. Sell the Grand Cherokee around its 5-passenger size, Jeep capability identity and the actual 4x4/equipment on this vehicle—not a made-up feature."
        elif rival.lower().startswith("toyota highlander"):
            angle = "The Highlander is strongly family-oriented and offers 3-row packaging. Ask whether the customer needs that extra row or prefers the Grand Cherokee's 5-passenger size and Jeep capability focus."
        elif rival.lower().startswith("honda pilot"):
            angle = "The Pilot is another strong 3-row family SUV. If the customer doesn't need three rows, position the Grand Cherokee around its 5-passenger layout, Jeep identity and available 4x4 capability."
        elif rival.lower().startswith("toyota 4runner"):
            angle = "The 4Runner is the more traditional body-on-frame/off-road competitor. Sell the Grand Cherokee when the customer wants a more road-friendly SUV while still having available 4x4 capability."
        elif rival.lower().startswith("chevrolet"):
            angle = "Traverse emphasizes three-row space. If the customer doesn't need the extra row, focus the Grand Cherokee discussion on size, driving feel, Jeep capability and the equipment actually on this vehicle."
        else:
            angle = f"Compare the customer's priorities directly against the {rival} rather than attacking the other brand."
    else:
        angle = f"Use the {rival} as a model-year reference. Compare the customer's priorities—power, space, drivetrain, towing, technology and price—against this vehicle's verified equipment."

    # Give the salesperson an actual, evidence-based reason to sell the vehicle.
    # This is model-year comparison logic, not competitor-VIN matching.
    edge_parts: List[str] = []
    rival_lower = rival.lower()
    if base_tow_text and rival_tow_text:
        a_tow, r_tow = _tow_num(base.get("towing")), _tow_num(rival_data.get("towing"))
        if a_tow and r_tow and a_tow > r_tow:
            edge_parts.append(f"Towing: {a_tow:,} lbs max reference vs {r_tow:,} lbs for the {rival}.")
    if "grand cherokee l" in f"{make} {model}" and rival_lower == "ford explorer":
        edge_parts.append("Towing/capability: the 2025 Grand Cherokee L has a 6,200-lb maximum model-year reference versus 5,000 lbs for the Explorer when properly equipped.")
        edge_parts.append("Power trade-off: Explorer's 300 hp/310 lb-ft reference is higher than the Grand Cherokee L's 293 hp/260 lb-ft, so sell the Jeep on towing, available 4x4 and the actual equipment rather than claiming a power advantage.")
    elif "grand cherokee l" in f"{make} {model}" and rival_lower == "toyota grand highlander":
        edge_parts.append("Towing/power: the 2025 Grand Cherokee L's 6,200-lb towing reference and 293 hp exceed the Grand Highlander's 5,000-lb towing reference and 265 hp gas-model reference.")
        edge_parts.append("The Grand Highlander has more cargo/passenger-oriented space and available hybrid powertrains, so use the Jeep advantage when towing, 4x4 capability or V6 power is what the customer values.")
    if "grand cherokee" in f"{make} {model}" and "4runner" in rival_lower:
        edge_parts.append("The Grand Cherokee can be positioned as the more road-oriented SUV while still offering available 4x4 capability; don't claim off-road hardware that this VIN doesn't have.")
    if "grand cherokee" in f"{make} {model}" and rival_lower in {"toyota highlander", "honda pilot", "chevrolet traverse"}:
        edge_parts.append("Capability angle: use the Grand Cherokee's available 4x4 systems and model-specific towing reference when those priorities match the customer.")
    if actual_hp is not None and rival_hp is not None:
        if actual_hp > rival_hp:
            edge_parts.append(f"Power: {int(actual_hp)} hp vs {int(rival_hp)} hp gives this vehicle the horsepower edge.")
        elif actual_hp < rival_hp:
            edge_parts.append(f"Power: don't claim a horsepower edge—the {rival} reference is {int(rival_hp)} hp vs {int(actual_hp)} hp.")
    if not edge_parts:
        # Even when no numeric edge exists, give the salesperson a concrete
        # model-level positioning statement instead of the old generic filler.
        if "grand cherokee l" in f"{make} {model}":
            edge_parts.append(f"Positioning: compare the Grand Cherokee L's available 4x4/capability and model-year equipment against the {rival}'s strengths; use the customer's priorities to decide the winner.")
        elif "grand cherokee" in f"{make} {model}":
            edge_parts.append(f"Positioning: the Grand Cherokee brings available 4x4 capability and Jeep's SUV format to the comparison; verify this vehicle's actual equipment before claiming a specific feature.")
        else:
            edge_parts.append(f"Positioning: use the {rival} model-year facts to show a real trade-off rather than claiming a blanket advantage.")
    edge = " ".join(edge_parts)

    return {
        "name": rival,
        "data_available": bool(rival_data or lines),
        "year": year,
        "engine": rival_data.get("engine"),
        "hp": int(rival_hp) if rival_hp is not None else None,
        "torque": int(rival_tq) if rival_tq is not None else None,
        "transmission": rival_data.get("transmission"),
        "drivetrain": rival_data.get("drivetrain"),
        # Keep max_towing numeric because the current CarDex UI formats it
        # with Number(...). This prevents the old NaN/"N/A" display bug.
        "max_towing": _tow_num(rival_data.get("towing")),
        "towing_lbs": _tow_num(rival_data.get("towing")),
        "towing_label": _tow_text(rival_data.get("towing")),
        "feature_summary": rival_data.get("feature_summary"),
        "comparison": lines or [f"{rival} is shown here as a {year or 'model-year'} model-level reference; exact trim/package equipment is not being assumed."],
        "angle": angle,
        "edge": edge,
        "source": rival_data.get("source", "CarDex model-level reference"),
    }


def build_sales_brain(vehicle: Dict[str, Any], nhtsa: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    nhtsa = nhtsa or {}
    year, make, model = _key(vehicle)
    profile = _model_profile(year, make, model)
    fallback = resolve_fallbacks(vehicle, nhtsa)

    # Feed model-year ordinary specs back into the report object so the
    # existing app.py UI can display them without any app.py change.
    for field, value in {
        "engine": profile.get("engine"),
        "transmission": profile.get("transmission"),
        "drivetrain": profile.get("drivetrain"),
        "body_style": profile.get("body_style"),
        "towing_capacity": profile.get("towing"),
        "flat_tow": profile.get("flat_tow"),
    }.items():
        if value and not vehicle.get(field):
            vehicle[field] = value

    if profile.get("hp") and not vehicle.get("engine_hp") and not nhtsa.get("engine_hp"):
        vehicle["engine_hp"] = profile["hp"]
    if profile.get("torque") and not vehicle.get("torque"):
        vehicle["torque"] = f"{profile['torque']} lb-ft"

    engine = vehicle.get("engine") or nhtsa.get("engine") or profile.get("engine")
    hp = nhtsa.get("engine_hp") or vehicle.get("engine_hp") or profile.get("hp")
    torque = vehicle.get("torque") or (f"{profile['torque']} lb-ft" if profile.get("torque") else None)
    transmission = vehicle.get("transmission") or nhtsa.get("transmission") or profile.get("transmission")
    drivetrain = vehicle.get("drivetrain") or nhtsa.get("drivetrain") or profile.get("drivetrain")
    body = vehicle.get("body_style") or nhtsa.get("body_style") or profile.get("body_style")
    towing = vehicle.get("towing_capacity") or profile.get("towing")
    flat_tow = vehicle.get("flat_tow") or profile.get("flat_tow")

    title = " ".join(str(x) for x in [vehicle.get("year"), vehicle.get("make"), vehicle.get("model"), vehicle.get("trim")] if x)

    # Specific, sales-floor useful points — not generic motivational filler.
    points: List[str] = []
    if engine:
        points.append(f"Powertrain: {engine}" + (f" — {hp} hp / {torque}." if hp and torque else "."))
    if transmission:
        points.append(f"Transmission: {transmission}.")
    if drivetrain:
        points.append(f"Drivetrain: {drivetrain}.")
    if towing:
        points.append(f"Towing reference: {towing}.")
    if profile.get("feature_summary"):
        points.append(profile["feature_summary"])

    if "grand cherokee" in model:
        points += [
            "If the customer is cross-shopping a 3-row SUV, first find out whether they actually need the third row; the Grand Cherokee is a 5-passenger SUV.",
            "For a customer focused on winter driving or recreation, verify the actual 4x4 system on this vehicle before selling its capability.",
            "Use the actual trim/package equipment on this VIN for luxury, technology, comfort and convenience claims—do not assume an option because another Grand Cherokee has it.",
        ]
    elif "explorer" in model:
        points += [
            "Lead with the Explorer's 3-row layout when passenger/cargo flexibility is the customer's priority.",
            "Verify whether this specific Explorer has RWD or 4WD before making a capability claim.",
        ]
    elif "4runner" in model:
        points += [
            "Lead with body-on-frame construction and available 4WD/low-range capability when the customer wants traditional off-road capability.",
            "Use the actual trim to determine which off-road hardware is present.",
        ]
    elif "pilot" in model or "highlander" in model or "traverse" in model:
        points += [
            "Lead with the 3-row/family packaging when that matches the customer's use.",
            "Verify the actual AWD system and trim equipment before promising specific capability or convenience features.",
        ]

    if not points:
        points = [
            f"Model-year reference: {title or 'vehicle'}.",
            "Use the verified listing equipment and the customer's priorities to build the presentation.",
        ]

    competitors = competitor_list(vehicle)
    competitive = [_comparison(vehicle, rival) for rival in competitors]

    questions = []
    if "grand cherokee" in model:
        questions = [
            "Are you comparing this to an Explorer, Highlander, Pilot, 4Runner, or something else?",
            "Do you need three rows, or is a 5-passenger SUV the right size?",
            "Is winter traction/4x4 capability important enough that we should verify the system on this specific Grand Cherokee?",
            "Are you more focused on comfort and technology, towing/recreation, or the payment?",
        ]
    elif "ram" in make:
        questions = [
            "What are you towing or hauling, and how often?",
            "Which matters more: payload/towing, fuel economy, interior comfort, or payment?",
            "Are you comparing this to an F-150, Silverado, Sierra, or Tundra?",
            "Is there a specific truck feature you saw elsewhere that you don't want to give up?",
        ]
    elif "wrangler" in model or "4runner" in model:
        questions = [
            "How much of your driving is pavement versus trails, snow, or rough roads?",
            "Do you actually need low-range/off-road hardware, or mainly winter traction?",
            "Are you comparing this to a Bronco, 4Runner, or another SUV?",
            "What capability feature would make you choose this one?",
        ]
    else:
        questions = [
            f"Are you comparing this {title or 'vehicle'} to another model?",
            "Is your biggest priority power, space, fuel economy, capability, technology, or payment?",
            "What feature from the other vehicle do you absolutely not want to give up?",
            "How will you use the vehicle most often?",
        ]

    demo = [
        "Demonstrate the exact feature that matches the customer's #1 priority.",
        "If drivetrain/capability matters, show the actual controls and system present on this vehicle.",
        "If space matters, have the customer test the seats and cargo area themselves.",
        "Use the actual screen, driver-assistance controls and comfort equipment on this VIN—not equipment from another trim.",
    ]

    pitch = f"This {title or 'vehicle'} has"
    descriptors = []
    if engine: descriptors.append(engine)
    if hp: descriptors.append(f"{hp} horsepower")
    if transmission: descriptors.append(transmission)
    if drivetrain: descriptors.append(drivetrain)
    pitch += " " + ", ".join(descriptors) + ". "
    pitch += "The big thing I'd want to know is what you're comparing it against and what you care about most, because I can show you the actual differences without assuming equipment this vehicle doesn't have."

    objections = [
        "Feature/add-on questions: verify the actual VIN/listing before claiming a package, seat feature, sunroof, audio system, or driver-assistance option.",
        "Towing: use the model-year reference only as a maximum/typical rating and verify the exact engine/equipment before quoting a hard number.",
        "Flat-towing: use the model-year reference only to identify whether that type of configuration may support it; verify the exact drivetrain and owner's-manual procedure.",
        "Competitor shopping: compare model-year facts directly instead of pretending CarDex found a competitor VIN.",
    ]

    return {
        "points": points,
        "objections": objections,
        "pitch": pitch,
        "competitors": competitive,
        "questions": questions,
        "demo": demo,
        "fallback": fallback,
        "resolved": {
            "engine": engine,
            "engine_hp": hp,
            "torque": torque,
            "transmission": transmission,
            "drivetrain": drivetrain,
            "body_style": body,
            "towing_capacity": towing,
            "flat_tow": flat_tow,
        },
    }
