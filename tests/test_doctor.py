"""doctor must name the volatile field behind a CHANGED behavior — and never
suggest scrubbing a structural (real-shape) change."""
from nightward.core.behavior import Behavior
from nightward.core.doctor import changed_paths, diagnose


def _b(name: str, payload, group=None) -> Behavior:
    return Behavior(name=name, payload=payload, group=group)


def test_changed_paths_flags_volatile_scalar():
    volatile, structural = changed_paths({"at": "run-1", "total": 5}, {"at": "run-2", "total": 5})
    assert volatile == ["at"]
    assert structural == []


def test_changed_paths_nested_and_list_index():
    old = {"order": {"created_at": 1, "items": [{"ts": 10, "qty": 2}]}}
    new = {"order": {"created_at": 2, "items": [{"ts": 99, "qty": 2}]}}
    volatile, structural = changed_paths(old, new)
    assert volatile == ["order.created_at", "order.items[0].ts"]
    assert structural == []


def test_changed_paths_structural_not_volatile():
    # added key, list growth, container-type flip: real shape changes
    volatile, structural = changed_paths(
        {"a": 1, "items": [1], "meta": {"x": 1}},
        {"a": 1, "b": 2, "items": [1, 2], "meta": [1]},
    )
    assert volatile == []
    assert structural == ["b", "items[]", "meta"]


def test_changed_paths_root_scalar():
    volatile, structural = changed_paths("hello", "world")
    assert volatile == ["$"]
    assert structural == []


def test_diagnose_suggests_register_field_ranked_by_frequency():
    baseline = {
        "checkout": _b("checkout", {"created_at": 1, "total": 10}),
        "refund": _b("refund", {"created_at": 2, "amount": 3}),
        "stable": _b("stable", {"v": 1}),
    }
    pending = {
        "checkout": _b("checkout", {"created_at": 9, "total": 11}),
        "refund": _b("refund", {"created_at": 8, "amount": 3}),
        "stable": _b("stable", {"v": 1}),
    }
    diag = diagnose(baseline, pending)
    assert diag["changed"] == ["checkout", "refund"]
    assert diag["volatile_fields"] == {"created_at": 2, "total": 1}
    assert diag["suggestions"][0] == 'scrub.register_field("created_at")'
    assert "stable" not in diag["behaviors"]


def test_diagnose_ignores_new_and_removed():
    diag = diagnose({"gone": _b("gone", 1)}, {"fresh": _b("fresh", 2)})
    assert diag["changed"] == []
    assert diag["suggestions"] == []


def test_diagnose_root_change_yields_no_field_suggestion():
    diag = diagnose({"greeting": _b("greeting", "hi")}, {"greeting": _b("greeting", "yo")})
    assert diag["behaviors"]["greeting"]["volatile"] == ["$"]
    assert diag["suggestions"] == []
