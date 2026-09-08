"""
CarDex Sales Brain V2.3 — competitive knowledge layer.

Rules:
- Exact listing/VIN data wins.
- Same-year/model fallback is used only for stable, high-confidence facts.
- Competitive numbers are model-level reference data, not VIN-to-VIN matches.
- Configuration-dependent claims are labeled as such.
- Never invent a trim-specific feature or towing/flat-tow capability.
"""
from __future__ import annotations
from typing import Any, Dict, List

MODEL_FALLBACKS: Dict[tuple, Dict[str, Any]] = {
    (2025, "jeep", "grand cherokee"): {
        "engine": "3.6L V6",
        "engine_hp": 293,
        "torque": "260 lb-ft",
        "body_style": "SUV",
        "notes": "2025 Grand Cherokee model-level V6 figures. Exact trim/drivetrain still matters for equipment and towing.",
    },
    (2025, "jeep", "grand cherokee l"): {
        "engine": "3.6L V6",
        "engine_hp": 293,
        "torque": "260 lb-ft",
        "body_style": "3-row SUV",
        "notes": "2025 Grand Cherokee L model-level V6 figures. Exact trim/drivetrain still matters for equipment and towing.",
    },
}

# Same-year model-level competitive reference data. These are intentionally
# kept separate from the actual vehicle so CarDex never pretends it found a
# competitor VIN with matching equipment.
COMPETITIVE_DATA: Dict[tuple, Dict[str, Dict[str, Any]]] = {
    (2025, "jeep", "grand cherokee"): {
        "Jeep Grand Cherokee": {"hp": 293, "torque": 260, "engine": "3.6L V6", "max_towing": 6200, "source": "Edmunds / manufacturer model specs"},
        "Ford Explorer": {"hp": 300, "torque": 310, "engine": "2.3L EcoBoost I-4", "max_towing": 5000, "source": "Ford 2025 Explorer specs"},
        "Toyota Highlander": {"hp": 265, "torque": 310, "engine": "2.4L turbo I-4", "max_towing": 5000, "source": "Toyota 2025 Highlander specs"},
        "Honda Pilot": {"hp": 285, "torque": 262, "engine": "3.5L V6", "max_towing": 5000, "source": "Honda 2025 Pilot specs"},
        "Chevrolet Traverse": {"hp": 328, "torque": 326, "engine": "2.5L turbo I-4", "max_towing": 5000, "source": "Chevrolet 2025 Traverse specs"},
    },
}

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
    make = _clean(vehicle.get("make")); model = _clean(vehicle.get("model"))
    return (year, make, model) if make and model else None


def resolve_fallbacks(vehicle: Dict[str, Any], nhtsa: Dict[str, Any] | None) -> Dict[str, Any]:
    nhtsa = nhtsa or {}; result: Dict[str, Any] = {}
    profile = MODEL_FALLBACKS.get(_model_key(vehicle), {})
    if not vehicle.get("engine") and not nhtsa.get("engine") and profile.get("engine"):
        result["engine"] = profile["engine"]
    if not nhtsa.get("engine_hp") and not vehicle.get("engine_hp") and profile.get("engine_hp"):
        result["engine_hp"] = profile["engine_hp"]
    if not vehicle.get("torque") and profile.get("torque"):
        result["torque"] = profile["torque"]
    if not vehicle.get("body_style") and not nhtsa.get("body_style") and profile.get("body_style"):
        result["body_style"] = profile["body_style"]
    if profile:
        result.update(source="CarDex model-level fallback", confidence="high", note=profile.get("notes", ""))
    return result


def competitor_list(vehicle: Dict[str, Any]) -> List[str]:
    key = f"{_clean(vehicle.get('make'))} {_clean(vehicle.get('model'))}".strip()
    if key in COMPETITORS: return COMPETITORS[key]
    model = _clean(vehicle.get("model"))
    if "explorer" in model: return ["Jeep Grand Cherokee", "Toyota Highlander", "Honda Pilot", "Chevrolet Traverse"]
    if "highlander" in model: return ["Jeep Grand Cherokee", "Ford Explorer", "Honda Pilot", "Chevrolet Traverse"]
    if "pilot" in model: return ["Jeep Grand Cherokee", "Ford Explorer", "Toyota Highlander", "Chevrolet Traverse"]
    if "traverse" in model: return ["Jeep Grand Cherokee", "Ford Explorer", "Toyota Highlander", "Honda Pilot"]
    return []


def _competitive_numbers(year: Any, make: str, model: str, rival: str) -> Dict[str, Any] | None:
    data = COMPETITIVE_DATA.get((int(year), make, model), {}) if str(year).isdigit() else {}
    return data.get(rival)


def _comparison(vehicle_data: Dict[str, Any], rival_data: Dict[str, Any] | None, rival: str) -> Dict[str, Any]:
    """Build a safe model-level competitor comparison. Never let bad/missing data crash a report."""
    if not rival_data or not vehicle_data:
        return {
            "name": rival,
            "data_available": False,
            "angle": "Ask what the customer likes about this competitor, then compare those priorities against this vehicle's verified equipment.",
            "comparison": [
                f"Competitor reference: {rival}.",
                "Exact competitor trim/equipment is not being represented as a VIN-to-VIN match.",
                "Use the customer's stated priority (price, power, space, fuel economy, towing, technology or capability) for the side-by-side comparison.",
            ],
        }

    def num(value):
        try:
            return float(value) if value is not None and str(value).strip() != "" else None
        except (TypeError, ValueError):
            return None

    hp = num(vehicle_data.get("hp")); rhp = num(rival_data.get("hp"))
    tq = num(vehicle_data.get("torque")); rtq = num(rival_data.get("torque"))
    tow = num(vehicle_data.get("max_towing")); rtow = num(rival_data.get("max_towing"))
    lines = []

    def fmt_num(v):
        if v is None: return "VERIFY"
        return f"{int(v) if float(v).is_integer() else v:g}"

    if hp is not None and rhp is not None:
        delta = hp - rhp
        lines.append(f"Power: {fmt_num(hp)} hp vs {fmt_num(rhp)} hp ({'+' if delta >= 0 else ''}{fmt_num(delta)} hp for this Jeep reference).")
    if tq is not None and rtq is not None:
        delta = tq - rtq
        lines.append(f"Torque: {fmt_num(tq)} lb-ft vs {fmt_num(rtq)} lb-ft ({'+' if delta >= 0 else ''}{fmt_num(delta)} lb-ft for this Jeep reference).")
    if tow is not None and rtow is not None:
        lines.append(f"Max towing: up to {int(tow):,} lbs vs up to {int(rtow):,} lbs — verify exact configuration before quoting.")

    wins = []
    if hp is not None and rhp is not None and hp > rhp: wins.append("horsepower")
    if tq is not None and rtq is not None and tq > rtq: wins.append("torque")
    if tow is not None and rtow is not None and tow > rtow: wins.append("maximum listed towing")
    if wins:
        edge = "Jeep edge: " + ", ".join(wins) + "."
    else:
        edge = "Do not sell this as a raw power advantage; sell the Jeep's overall fit, capability character and the verified equipment on this actual vehicle."

    return {
        "name": rival,
        "data_available": True,
        "engine": rival_data.get("engine"),
        "hp": int(rhp) if rhp is not None and rhp.is_integer() else rhp,
        "torque": int(rtq) if rtq is not None and rtq.is_integer() else rtq,
        "max_towing": int(rtow) if rtow is not None and rtow.is_integer() else rtow,
        "source": rival_data.get("source"),
        "comparison": lines or [f"Compare the verified {rival} equipment against this vehicle based on the customer's priorities."],
        "edge": edge,
        "angle": _competitive_angle("jeep", "grand cherokee", rival),
    }


def _competitive_angle(make: str, model: str, rival: str) -> str:
    r = rival.lower()
    if "grand cherokee" in model:
        if r.startswith("ford explorer"): return "Explorer has a power advantage in the base 2.3L, so don't claim otherwise. Sell the Grand Cherokee on the customer's desired mix of Jeep capability, design, ride and equipment."
        if r.startswith("toyota"): return "Highlander has strong efficiency/family positioning. Ask whether the customer wants that or the Grand Cherokee's Jeep capability character and available 4x4-oriented positioning."
        if r.startswith("honda"): return "Pilot is a strong family-focused V6 competitor. Find out whether the customer values its family packaging or the Grand Cherokee's Jeep character and capability."
        if r.startswith("chevrolet"): return "Traverse has a power/cargo-focused value story. Win by matching the customer's needs to this Grand Cherokee's actual equipment, size and capability."
    return "Ask what the customer likes about this competitor and compare those exact priorities side by side."


def build_sales_brain(vehicle: Dict[str, Any], nhtsa: Dict[str, Any] | None = None) -> Dict[str, Any]:
    nhtsa = nhtsa or {}; fallback = resolve_fallbacks(vehicle, nhtsa)
    make = _clean(vehicle.get("make")); model = _clean(vehicle.get("model"))
    title = " ".join(str(x) for x in [vehicle.get("year"), vehicle.get("make"), vehicle.get("model"), vehicle.get("trim")] if x)
    competitors = competitor_list(vehicle)
    engine = vehicle.get("engine") or nhtsa.get("engine") or fallback.get("engine")
    hp = nhtsa.get("engine_hp") or fallback.get("engine_hp")
    torque_raw = vehicle.get("torque") or fallback.get("torque")
    try: torque_num = int(str(torque_raw).split()[0]) if torque_raw else None
    except ValueError: torque_num = None
    drive = vehicle.get("drivetrain") or nhtsa.get("drivetrain")

    points = []
    if engine: points.append(f"Powertrain: {engine}.")
    if hp: points.append(f"Horsepower: {hp} hp.")
    if torque_raw: points.append(f"Torque: {torque_raw}.")
    if drive: points.append(f"Drivetrain: {drive}.")
    if vehicle.get("condition", "").lower() == "new": points.append("New vehicle — lead with factory-new condition and applicable factory warranty coverage.")
    if make == "jeep": points.append("Jeep identity and capability are strong talking points when they match the customer's actual use.")
    if "grand cherokee" in model: points += [
        "Grand Cherokee is the middle-ground choice for customers who want SUV comfort with a stronger capability-focused identity.",
        "Use the customer's lifestyle to sell it: winter driving, road trips, family use, recreation and available 4x4 capability.",
        "Don't rely on the badge alone — demonstrate the actual equipment on this VIN.",
    ]
    elif "wrangler" in model: points.append("Wrangler is best sold through lifestyle and capability demonstrations, not a wall of specifications.")
    elif make == "ram": points.append("Connect ride quality, interior comfort and truck capability directly to the customer's work and towing needs.")
    points += [
        "If a customer mentions a competitor, ask what they like about it before responding.",
        "Use exact VIN/listing equipment for feature claims; use model-level data only as a clearly labeled reference.",
    ]

    objections = [
        "Price — ask what they are comparing and whether the concern is payment, total price or equipment/value.",
        "Fuel economy — acknowledge it, then connect fuel use to the customer's actual driving and capability needs.",
        "Competitor shopping — compare the specific priorities instead of attacking the other brand.",
        "Towing — max ratings vary by configuration; VERIFY the exact vehicle before quoting a number.",
        "Flat-tow — VERIFY the exact year, drivetrain and owner's-manual requirements before promising it.",
        "Feature questions — if the VIN/listing does not prove the feature, tell the customer you will verify it rather than guessing.",
    ]

    vehicle_data = None
    key = _model_key(vehicle)
    if key in COMPETITIVE_DATA:
        vehicle_data = COMPETITIVE_DATA[key].get("Jeep Grand Cherokee")
    competitive = [_comparison(vehicle_data or {}, _competitive_numbers(vehicle.get("year"), make, model, rival), rival) for rival in competitors]

    questions = [
        "What is the #1 thing this vehicle needs to do for you?",
        "What other vehicles are you comparing it to?",
        "Is winter traction, passenger space, towing, fuel economy, technology, performance or payment the biggest priority?",
        "How often do you tow or haul, and what are you towing?",
        "What feature did you see in the other vehicle that you don't want to give up?",
    ]
    demo = [
        "Put the customer in the driver's seat and demonstrate the feature tied to their #1 priority.",
        "If 4x4/capability matters, demonstrate the actual drive-mode/traction controls present on this VIN.",
        "If family space matters, have the customer sit in every row and open the cargo area themselves.",
        "If technology matters, demonstrate the actual screen, phone integration and driver-assistance controls on this vehicle.",
        "Finish the walkaround by tying three demonstrated features directly to what the customer told you they need.",
    ]
    pitch = f"This is the {title or 'vehicle'}"
    if engine: pitch += f", powered by a {engine}"
    if hp: pitch += f" with {hp} horsepower"
    pitch += ". "
    if competitors: pitch += f"If you're also looking at something like the {competitors[0]}, I can show you exactly where the two differ instead of giving you a generic sales pitch. "
    pitch += "What matters most to you in the vehicle?"

    return {
        "points": points,
        "objections": objections,
        "pitch": pitch,
        "competitors": competitive,
        "questions": questions,
        "demo": demo,
        "fallback": fallback,
        "resolved": {"engine": engine, "engine_hp": hp, "torque": torque_raw, "body_style": vehicle.get("body_style") or nhtsa.get("body_style") or fallback.get("body_style")},
    }
