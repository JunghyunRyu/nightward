# petshop — a real cascade in 30 seconds

A tiny pet-shop checkout where **loyalty points and shipping both derive from the
order total**. That coupling is real (see `shop.py`), so a one-line tweak to the
tax rule moves three customer-facing behaviors at once — and your unit tests stay
green the whole time. This is the example used in the demo GIF; nothing is
hand-authored.

## Run it

```bash
cd examples/petshop

# 1. the approved baseline is already committed (.nightward/baseline). Confirm intact:
nightward run .            # boundary intact — code matches the baseline

# 2. play the "AI fix": change ONE line in shop.py
#      TAX_RATE = 0.10   ->   TAX_RATE = 0.095

# 3. re-run — tests pass, but nightward shows the blast radius:
pytest -q                 # 3 passed   (looks fine!)
nightward run .            # boundary BREACHED — 3 behaviors changed
nightward gate             # exit 1      (the agent/CI stop-signal)
nightward view             # see it in the browser
```

## What actually moves (real captured values)

| behavior | before (approved) | after the one-line change |
|---|---|---|
| `checkout_total` | total **30.03** | total **29.89** |
| `loyalty_points` | **silver** · 3p | **bronze** · 2p |
| `shipping_fee`   | **free shipping** | **+$3.50** |

One 0.5%-point tax change quietly drops the customer below the $30 threshold, so
they lose silver tier *and* free shipping. No test fails. nightward is the thing
that makes it visible.

> nightward doesn't decide whether bronze is "wrong" — it has no correctness
> oracle. It just refuses to let any change pass silently, so the side effect
> can't hide. You approve it (intended) or fix the code (regression).
