"""A tiny pet-shop checkout — a REAL system with REAL coupling.

The point of this example: loyalty points AND shipping are both *derived from the
order total*. So a one-line tweak to the tax rule does not stay local — it moves
three customer-facing behaviors at once. nightward captures that real cascade from
real execution; nothing here is hand-authored expected output.
"""

TAX_RATE = 0.10        # ← the single line an AI later "tweaks" to be more precise
LOYALTY_PER = 10.0     # 1 loyalty point per $10 of order total
FREE_SHIP_AT = 30.0    # free shipping (and silver tier) at/above this total


def checkout_total(items):
    subtotal = round(sum(i["price"] * i["qty"] for i in items), 2)
    tax = round(subtotal * TAX_RATE, 2)
    return {"subtotal": subtotal, "tax": tax, "total": round(subtotal + tax, 2)}


def loyalty_points(items):
    total = checkout_total(items)["total"]            # derived from total
    return {
        "points": int(total // LOYALTY_PER),
        "tier": "silver" if total >= FREE_SHIP_AT else "bronze",
    }


def shipping_fee(items):
    total = checkout_total(items)["total"]            # derived from total
    free = total >= FREE_SHIP_AT
    return {"fee": 0.0 if free else 3.5, "free_shipping": free}
