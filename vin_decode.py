"""
Public VIN decode via NHTSA vPIC (no credentials, no guessing).
https://vpic.nhtsa.dot.gov/api/
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import requests

NHTSA_URL = "https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVinValues/{vin}?format=json"


def decode_vin(vin: str) -> Optional[Dict[str, Any]]:
    vin = (vin or "").strip().upper()
    if len(vin) != 17:
        return None
    try:
        resp = requests.get(NHTSA_URL.format(vin=vin), timeout=12)
        if resp.status_code != 200:
            return None
        data = resp.json()
        results = data.get("Results") or []
        if not results:
            return None
        row = results[0]
        # ErrorCode 0 = clean decode
        err = str(row.get("ErrorCode") or "")
        if err and not err.startswith("0"):
            # Still return partial if useful fields exist
            pass
        out: Dict[str, Any] = {
            "source": "NHTSA vPIC",
            "vin": vin,
            "year": _int(row.get("ModelYear")),
            "make": _clean(row.get("Make")),
            "model": _clean(row.get("Model")),
            "trim": _clean(row.get("Trim") or row.get("Series")),
            "body_style": _clean(row.get("BodyClass")),
            "doors": _clean(row.get("Doors")),
            "drivetrain": _clean(row.get("DriveType")),
            "transmission": _clean(row.get("TransmissionStyle")),
            "fuel": _clean(row.get("FuelTypePrimary")),
            "engine_displacement_l": _clean(row.get("DisplacementL")),
            "engine_cylinders": _clean(row.get("EngineCylinders")),
            "engine_configuration": _clean(row.get("EngineConfiguration")),
            "engine_hp": _int(row.get("EngineHP")),
            "engine_kw": _clean(row.get("EngineKW")),
            "electrification": _clean(row.get("ElectrificationLevel")),
            "vehicle_type": _clean(row.get("VehicleType")),
            "plant_city": _clean(row.get("PlantCity")),
            "error_code": err,
            "error_text": _clean(row.get("ErrorText")),
        }
        # Build a readable engine string
        parts = []
        if out["engine_displacement_l"]:
            parts.append(f'{out["engine_displacement_l"]}L')
        if out["engine_configuration"]:
            cfg = out["engine_configuration"]
            if out["engine_cylinders"]:
                if "V" in cfg.upper():
                    parts.append(f'V{out["engine_cylinders"]}')
                else:
                    parts.append(f'{out["engine_cylinders"]}-cyl {cfg}')
            else:
                parts.append(cfg)
        elif out["engine_cylinders"]:
            parts.append(f'{out["engine_cylinders"]}-cyl')
        if out["engine_hp"]:
            parts.append(f'{out["engine_hp"]} hp')
        if out["fuel"]:
            parts.append(out["fuel"])
        out["engine"] = " ".join(parts) if parts else None
        return out
    except Exception:
        return None


def _clean(v: Any) -> Optional[str]:
    if v is None:
        return None
    s = str(v).strip()
    if not s or s.lower() in ("null", "none", "not applicable", "n/a", ""):
        return None
    return s


def _int(v: Any) -> Optional[int]:
    try:
        if v is None or str(v).strip() == "":
            return None
        return int(float(str(v).strip()))
    except (TypeError, ValueError):
        return None
