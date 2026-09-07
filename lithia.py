"""
Lithia Motors public inventory adapter.

Specialized for Lithia dealership public sites (including the Missoula
Chrysler Jeep Dodge Ram store). Lithia sites are typically Dealer.com based,
so this adapter inherits that logic and adds Lithia-specific host matching
and naming.
"""

from __future__ import annotations

from dealer_com import DealerComAdapter


class LithiaAdapter(DealerComAdapter):
    key = "lithia"
    display_name = "Lithia Motors"
    description = "Public inventory pages for Lithia dealerships (Dealer.com based)."

    LITHIA_HOST_HINTS = (
        "lithia",
        "lithiachryslermissoula",
        "lithia.com",
    )

    @classmethod
    def can_handle(cls, inventory_url: str) -> bool:
        url = (inventory_url or "").lower()
        return any(h in url for h in cls.LITHIA_HOST_HINTS)
