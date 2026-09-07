"""
Base adapter contract.

Every dealership source implements this interface.
Adapters must NEVER invent data — leave fields blank when unsure.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


@dataclass
class VehicleRecord:
    """
    Normalized vehicle data extracted from a public page.
    All fields are optional. Blank = unknown / not verified.
    """

    vin: Optional[str] = None
    stock_number: Optional[str] = None
    year: Optional[int] = None
    make: Optional[str] = None
    model: Optional[str] = None
    trim: Optional[str] = None
    price: Optional[float] = None
    mileage: Optional[int] = None
    condition: Optional[str] = None  # new / used / cpo
    exterior_color: Optional[str] = None
    interior_color: Optional[str] = None
    listing_url: Optional[str] = None
    image_url: Optional[str] = None
    body_style: Optional[str] = None
    drivetrain: Optional[str] = None
    engine: Optional[str] = None
    transmission: Optional[str] = None
    fuel_economy: Optional[str] = None
    # Extra free-form data the adapter found (kept for later use)
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        # Flatten extra into top level only if needed by callers;
        # store keeps the full original via raw_json.
        return d

    def is_minimally_valid(self) -> bool:
        """At least a VIN or a stock number plus year/make/model is useful."""
        has_id = bool(self.vin or self.stock_number)
        has_ymm = bool(self.year and self.make and self.model)
        return has_id or has_ymm


class BaseAdapter(ABC):
    """
    Contract every inventory source must follow.
    """

    key: str = "base"
    display_name: str = "Base"
    description: str = ""

    @classmethod
    @abstractmethod
    def can_handle(cls, inventory_url: str) -> bool:
        """Return True if this adapter should handle the given URL."""
        ...

    @abstractmethod
    def discover_vehicles(self, inventory_url: str) -> List[VehicleRecord]:
        """
        Fetch the public inventory page(s) and return a list of VehicleRecord.
        Must be conservative: never invent values.
        Respect robots.txt and rate limits.
        """
        ...

    def normalize_price(self, raw: Any) -> Optional[float]:
        if raw is None:
            return None
        try:
            s = str(raw).replace("$", "").replace(",", "").strip()
            if not s:
                return None
            return float(s)
        except (TypeError, ValueError):
            return None

    def normalize_mileage(self, raw: Any) -> Optional[int]:
        if raw is None:
            return None
        try:
            s = str(raw).lower().replace(",", "").replace("mi", "").replace("miles", "").strip()
            if not s:
                return None
            return int(float(s))
        except (TypeError, ValueError):
            return None

    def normalize_year(self, raw: Any) -> Optional[int]:
        if raw is None:
            return None
        try:
            y = int(str(raw).strip()[:4])
            if 1980 <= y <= 2035:
                return y
            return None
        except (TypeError, ValueError):
            return None
