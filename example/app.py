"""A tiny sample system whose behavior we want to lock down."""


def checkout_total(items):
    subtotal = sum(i["price"] * i["qty"] for i in items)
    tax = round(subtotal * 0.1, 2)
    return {"subtotal": subtotal, "tax": tax, "total": round(subtotal + tax, 2)}


def user_login(username):
    return {"user": username, "status": "ok", "roles": ["member"]}
