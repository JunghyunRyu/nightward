"""Behavior captures for the pet-shop checkout.

No expected values are hand-written. We capture what the system actually returns
for one real cart, approve it once as the baseline, then let nightward gate every
later change against it.
"""
from shop import checkout_total, loyalty_points, shipping_fee

# A real cart sitting just above the free-shipping / silver threshold.
CART = [
    {"sku": "dog-food", "price": 8.50, "qty": 3},
    {"sku": "leash", "price": 1.80, "qty": 1},
]


def test_checkout_total(behavior):
    behavior("checkout_total", checkout_total(CART), group="billing")


def test_loyalty_points(behavior):
    behavior("loyalty_points", loyalty_points(CART), group="loyalty")


def test_shipping_fee(behavior):
    behavior("shipping_fee", shipping_fee(CART), group="fulfillment")
