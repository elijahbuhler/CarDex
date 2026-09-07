"""
CarDex Sales Brain V2.2

Purpose:
- Turn vehicle data into salesperson-ready intelligence.
- Use exact listing/VIN data first.
- If a field is missing, use conservative same-year/model knowledge only
  when the value is not likely to vary by trim/configuration.
- Never invent trim-specific, VIN-specific, towing, flat-tow, or feature claims.
"""
from __future__ import annotations

from typing import Any, Dict, List


# Conservative model-level fallbacks. These are intentionally limited to
# facts that are stable across the model/engine and are useful to sales.
# Trim/configuration-dependent values are NOT filled here.
MODEL_FALLBACKS: Dict[tuple, Dict[str, Any]] = {
    (2025, "jeep", "grand cherokee"): {
        "engine": "3.6L V6",
        "engine_hp": 293,
        "torque": "260 lb-ft",
        "body_style": "SUV",
        "notes": "Model-level 3.6L V6 figures; exact trim/drivetrain still matters for some specs.",
    },
}

# Broad competitive map. This is deliberately model-level rather than
# VIN-to-VIN inventory matching.
COMPETITORS: Dict[str, List[str]] = {
    "jeep grand cherokee": ["Ford Explorer", "Toyota Highlander", "Honda Pilot", "Chevrolet Traverse"],
    "jeep grand cherokee l": ["Ford Explorer", "Toyota Grand Highlander", "Honda Pilot", "Chevrolet Traverse"],
    "jeep wrangler": ["Ford Bronco", "Toyota 4Runner"],
    "jeep compass": ["Ford Escape", "Honda CR-V", "Toyota RAV4"],
    "jeep gladiator": ["Ford Ranger", "Toyota Tacoma", "Chevrolet Colorado"],
    "ram 1500": ["Ford F-150", "Chevrolet Silverado 1500", "GMC Sierra 1500", "Toyota Tundra"],
    "ram 2500": ["Ford F-250", "Chevrolet Silverado 2500HD", "GMC Sierra 2500HD"],
    "ram 3500": ["Ford F-350", "Chevrolet Silverado 3500HD", "GMC Sierra 3500HD"],
}


def _clean(value: Any) -> str:
    return str(value or "").strip().lower()


def _model_key(vehicle: Dict[str, Any]) -> tuple | None:
    try:
        year = int(vehicle.get("year"))
    except (TypeError, ValueError):
        return None
    make = _clean(vehicle.get("make"))
    model = _clean(vehicle.get("model"))
    if not make or not model:
        return None
    return year, make, model


def resolve_fallbacks(vehicle: Dict[str, Any], nhtsa: Dict[str, Any] | None) -> Dict[str, Any]:
    """Return only conservative model-level values missing from the exact vehicle."""
    nhtsa = nhtsa or {}
    result: Dict[str, Any] = {}
    key = _model_key(vehicle)
    profile = MODEL_FALLBACKS.get(key, {}) if key else {}

    # Exact listing/VIN data always wins.
    if not vehicle.get("engine") and not nhtsa.get("engine") and profile.get("engine"):
        result["engine"] = profile["engine"]
    if not nhtsa.get("engine_hp") and not vehicle.get("engine_hp") and profile.get("engine_hp"):
        result["engine_hp"] = profile["engine_hp"]
    if not vehicle.get("torque") and profile.get("torque"):
        result["torque"] = profile["torque"]
    if not vehicle.get("body_style") and not nhtsa.get("body_style") and profile.get("body_style"):
        result["body_style"] = profile["body_style"]

    if profile:
        result["source"] = "CarDex model-level fallback"
        result["confidence"] = "high"
        result["note"] = profile.get("notes", "")
    return result


def competitor_list(vehicle: Dict[str, Any]) -> List[str]:
    make = _clean(vehicle.get("make"))
    model = _clean(vehicle.get("model"))
    key = f"{make} {model}".strip()
    if key in COMPETITORS:
        return COMPETITORS[key]

    # Helpful generic competitors by brand/model keywords.
    if "explorer" in model:
        return ["Jeep Grand Cherokee", "Toyota Highlander", "Honda Pilot", "Chevrolet Traverse"]
    if "highlander" in model:
        return ["Jeep Grand Cherokee", "Ford Explorer", "Honda Pilot", "Chevrolet Traverse"]
    if "pilot" in model:
        return ["Jeep Grand Cherokee", "Ford Explorer", "Toyota Highlander", "Chevrolet Traverse"]
    if "traverse" in model:
        return ["Jeep Grand Cherokee", "Ford Explorer", "Toyota Highlander", "Honda Pilot"]
    return []


def build_sales_brain(vehicle: Dict[str, Any], nhtsa: Dict[str, Any] | None = None) -> Dict[str, Any]:
    nhtsa = nhtsa or {}
    fallback = resolve_fallbacks(vehicle, nhtsa)

    make = _clean(vehicle.get("make"))
    model = _clean(vehicle.get("model"))
    trim = _clean(vehicle.get("trim"))
    title = " ".join(str(x) for x in [vehicle.get("year"), vehicle.get("make"), vehicle.get("model"), vehicle.get("trim")] if x)
    competitors = competitor_list(vehicle)

    engine = vehicle.get("engine") or nhtsa.get("engine") or fallback.get("engine")
    hp = nhtsa.get("engine_hp") or fallback.get("engine_hp")
    torque = vehicle.get("torque") or fallback.get("torque")
    drive = vehicle.get("drivetrain") or nhtsa.get("drivetrain")

    points: List[str] = []
    if engine:
        points.append(f"Powertrain: {engine}.")
    if hp:
        points.append(f"Factory horsepower: {hp} hp.")
    if torque:
        points.append(f"Factory torque: {torque}.")
    if drive:
        points.append(f"Drivetrain: {drive}.")
    if vehicle.get("condition", "").lower() == "new":
        points.append("New vehicle — lead with the factory-new condition and warranty coverage.")
    if make == "jeep":
        points.append("Jeep capability and brand identity are strong talking points when they match what the customer actually needs.")
    if make == "ram":
        points.append("For Ram buyers, connect ride quality, interior comfort and capability back to the customer's actual work/towing needs.")

    # Model-specific sales language.
    if "grand cherokee" in model:
        points.append("Grand Cherokee is a strong middle ground for buyers who want SUV comfort without giving up Jeep capability.")
    elif "wrangler" in model:
        points.append("Wrangler is a lifestyle/capability vehicle — demonstrate the features instead of overwhelming the customer with specs.")
    elif "1500" in model or "2500" in model or "3500" in model:
        points.append("Confirm towing, payload and trailer details before making capability promises.")

    objections: List[str] = []
    if vehicle.get("price"):
        objections.append("Price — move the conversation to what they are comparing and the payment/value difference, not just sticker price.")
    objections.append("Fuel economy — acknowledge the customer's concern, then connect fuel use to the capability and driving they told you they need.")
    if competitors:
        objections.append("Competitor shopping — ask what they like about the other vehicle, then compare those priorities directly rather than attacking the competitor.")
    objections.append("Towing / flat-tow — VERIFY the exact configuration before promising a capacity or tow-behind setup.")

    competitive: List[Dict[str, Any]] = []
    for rival in competitors:
        competitive.append({
            "name": rival,
            "angle": _competitive_angle(make, model, rival),
        })

    questions = [
        "What is the most important thing this vehicle needs to do for you?",
        "Are you comparing anything specific right now?",
        "Is winter traction, towing, passenger space, fuel economy, or price the biggest priority?",
    ]

    demo = [
        "Demonstrate the feature that directly matches the customer's stated priority.",
        "If capability matters, show the drivetrain/drive-mode controls and explain them in plain English.",
        "If comfort matters, let the customer spend time in the driver's seat and rear seating before talking numbers.",
    ]

    pitch = f"This is the {title or 'vehicle'}"
    if engine:
        pitch += f", powered by a {engine}"
    if hp:
        pitch += f" with {hp} horsepower"
    pitch += ". "
    if competitors:
        pitch += f"If you're comparing it with {competitors[0]} or something similar, let's focus on what matters most to you and compare those things directly. "
    pitch += "What is the main job you need this vehicle to do for you?"

    return {
        "points": points[:7],
        "objections": objections[:6],
        "pitch": pitch,
        "competitors": competitive,
        "questions": questions,
        "demo": demo,
        "fallback": fallback,
        "resolved": {
            "engine": engine,
            "engine_hp": hp,
            "torque": torque,
            "body_style": vehicle.get("body_style") or nhtsa.get("body_style") or fallback.get("body_style"),
        },
    }


def _competitive_angle(make: str, model: str, rival: str) -> str:
    if "grand cherokee" in model:
        if rival.lower().startswith("ford explorer"):
            return "Ask whether the customer values Jeep 4x4/capability character versus a more mainstream family-SUV approach."
        if rival.lower().startswith("toyota"):
            return "Ask whether they prioritize Toyota's reputation or Jeep's capability/4x4 character, then compare the features that matter to them."
        if rival.lower().startswith("honda"):
            return "Position the Grand Cherokee around capability and driving character while respecting Honda's family-focused strengths."
        if rival.lower().startswith("chevrolet"):
            return "Compare the customer's priorities around capability, space and powertrain rather than making blanket claims."
    return "Ask what the customer likes about this competitor and compare those exact priorities side by side."
