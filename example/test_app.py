"""Behavior captures. Note: no expected values are hand-written here —
we capture what the system *does*, then approve it once via the CLI.
"""
from app import checkout_total, user_login

CART = [{"price": 10.0, "qty": 2}, {"price": 5.5, "qty": 1}]


def test_checkout(behavior):
    behavior("checkout_total", checkout_total(CART), group="billing")


def test_login(behavior):
    behavior("user_login", user_login("alice"), group="auth")
