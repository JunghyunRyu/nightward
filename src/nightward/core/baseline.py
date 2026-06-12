"""Store — the on-disk golden set.

Layout (git-native, approvaltests-style):
    .nightward/
      baseline/<name>.approved.json    # committed — the regression boundary
      pending/<name>.received.json     # gitignored — this run's observed behavior
      rejected/<name>.rejected.json    # audit trail of confirmed regressions
      report.json                      # last blast radius
"""
from __future__ import annotations

import json
from pathlib import Path

from ..errors import NightwardError
from .behavior import Behavior, canonical_json


class Store:
    def __init__(self, root: Path | str):
        self.root = Path(root)
        self.baseline_dir = self.root / "baseline"
        self.pending_dir = self.root / "pending"
        self.rejected_dir = self.root / "rejected"
        self.report_path = self.root / "report.json"
        self.meta_path = self.root / "run_meta.json"

    def ensure(self) -> None:
        self.baseline_dir.mkdir(parents=True, exist_ok=True)
        self.pending_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _file(dir_: Path, name: str, suffix: str) -> Path:
        return dir_ / f"{name}.{suffix}.json"

    # ---- pending (this run) --------------------------------------------
    def write_pending(self, b: Behavior) -> None:
        self.pending_dir.mkdir(parents=True, exist_ok=True)
        self._file(self.pending_dir, b.name, "received").write_text(
            canonical_json(b.to_dict()), encoding="utf-8"
        )

    def clear_pending(self) -> None:
        if self.pending_dir.exists():
            for f in self.pending_dir.glob("*.received.json"):
                f.unlink()

    # ---- loading -------------------------------------------------------
    def _load_dir(self, dir_: Path, suffix: str) -> dict[str, Behavior]:
        out: dict[str, Behavior] = {}
        if not dir_.exists():
            return out
        for f in sorted(dir_.glob(f"*.{suffix}.json")):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                b = Behavior.from_dict(data)
            except (json.JSONDecodeError, KeyError) as exc:
                raise NightwardError(f"corrupt behavior file {f}: {exc}") from exc
            out[b.name] = b
        return out

    def load_baseline(self) -> dict[str, Behavior]:
        return self._load_dir(self.baseline_dir, "approved")

    def load_pending(self) -> dict[str, Behavior]:
        return self._load_dir(self.pending_dir, "received")

    # ---- decisions -----------------------------------------------------
    def approve(self, name: str) -> None:
        """Promote a pending behavior into the baseline (add or change)."""
        src = self._file(self.pending_dir, name, "received")
        if not src.exists():
            raise NightwardError(f"no pending behavior named {name!r} to approve")
        self.baseline_dir.mkdir(parents=True, exist_ok=True)
        self._file(self.baseline_dir, name, "approved").write_text(
            src.read_text(encoding="utf-8"), encoding="utf-8"
        )

    def approve_removal(self, name: str) -> None:
        """Accept that a behavior is gone: drop it from the baseline."""
        dst = self._file(self.baseline_dir, name, "approved")
        if not dst.exists():
            raise NightwardError(f"no baseline behavior named {name!r} to remove")
        dst.unlink()

    def mark_rejected(self, name: str) -> None:
        src = self._file(self.pending_dir, name, "received")
        self.rejected_dir.mkdir(parents=True, exist_ok=True)
        payload = src.read_text(encoding="utf-8") if src.exists() else "{}"
        self._file(self.rejected_dir, name, "rejected").write_text(payload, encoding="utf-8")

    # ---- report --------------------------------------------------------
    def write_report(self, report: dict) -> None:
        self.report_path.parent.mkdir(parents=True, exist_ok=True)
        self.report_path.write_text(
            json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def load_report(self) -> dict | None:
        if not self.report_path.exists():
            return None
        try:
            return json.loads(self.report_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise NightwardError(f"corrupt report file {self.report_path}: {exc}") from exc

    # ---- run metadata (skipped/failed counts from the last run) ---------
    def write_run_meta(self, meta: dict) -> None:
        self.meta_path.parent.mkdir(parents=True, exist_ok=True)
        self.meta_path.write_text(json.dumps(meta), encoding="utf-8")

    def load_run_meta(self) -> dict:
        if not self.meta_path.exists():
            return {}
        try:
            return json.loads(self.meta_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
