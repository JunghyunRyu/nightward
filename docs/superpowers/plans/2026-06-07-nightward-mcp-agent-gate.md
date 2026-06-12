# nightward MCP Agent Gate — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** AI 에이전트가 `nightward_run`/`nightward_status`를 MCP 도구로 직접 호출해 회귀 경계를 측정하되, `approve`/`reject`(경계 이동)는 사람 CLI에만 남긴다.

**Architecture:** (1) `cli.run`의 캡처 로직을 `runner.py:execute_run`으로 추출해 CLI와 MCP가 *같은 측정값*을 공유한다(CLI 동작 회귀 0). (2) `mcp_server.py`의 도구 함수는 `mcp` 패키지를 import하지 않는 순수 함수라 optional dep 없이도 테스트된다 — `build_server`만 lazy import로 FastMCP에 등록한다. (3) `nightward mcp` 서브커맨드가 stdio 서버를 띄운다.

**Tech Stack:** Python 3.10+, pytest(서브프로세스 캡처), typer(CLI), MCP Python SDK(FastMCP, optional extra), subprocess.

**근거 spec:** `docs/superpowers/specs/2026-06-07-nightward-mcp-agent-gate-design.md`

---

## File Structure

| 파일 | 책임 | 신규/수정 |
|------|------|-----------|
| `src/nightward/runner.py` | `execute_run`(pytest 캡처+recompute, console 무출력) + `recompute`. CLI/MCP 공유. | **Create** |
| `src/nightward/cli.py` | `run`을 `execute_run` 사용으로, `approve`를 `recompute` 사용으로 교체. `_recompute` 제거. `mcp` 서브커맨드 추가. | Modify |
| `src/nightward/mcp_server.py` | `run_tool`/`status_tool`(순수) + `_TOOLS`(에이전트 표면) + `build_server`/`serve`(lazy FastMCP). approve/reject 미등록. | **Create** |
| `pyproject.toml` | `mcp` optional extra 추가, `dev` extra에 `mcp` 추가(테스트용). | Modify |
| `tests/test_runner.py` | `execute_run` 캡처·에러 단위 테스트(추출 회귀 가드). | **Create** |
| `tests/test_mcp.py` | **격리 가드**(approve 미노출) + run/status 동작 + stdout 오염 방지(capfd) + 한글. | **Create** |

**경계 원칙(spec §2, 타협 불가):** `_TOOLS`에 `approve`/`reject`가 들어가면 게이트가 자살한다. `build_server`는 `_TOOLS`만 등록하므로 `_TOOLS` 검사 = 노출 표면 검사 — 이게 격리 가드의 축.

---

## Task 1: `runner.py` 추출 + `cli.py` 리팩터링 (CLI 회귀 0)

**Files:**
- Create: `src/nightward/runner.py`
- Test: `tests/test_runner.py`
- Modify: `src/nightward/cli.py` (import, `_recompute` 제거, `run` 본문, `approve`의 호출부)

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_runner.py`

```python
"""runner.execute_run — shared capture logic behind CLI run and the MCP server."""
import pytest

from nightward.errors import NightwardError
from nightward.runner import execute_run

SAMPLE = '''
def test_a(behavior):
    behavior("a", {"v": 1}, group="g1")
'''


def test_execute_run_captures_and_reports(tmp_path):
    (tmp_path / "test_s.py").write_text(SAMPLE, encoding="utf-8")
    result = execute_run(str(tmp_path / "test_s.py"), str(tmp_path / ".nightward"))
    assert result["pytest_returncode"] == 0
    assert result["report"]["boundary"] == "breached"   # first capture -> all NEW
    assert result["report"]["counts"]["new"] == 1
    assert result["skipped"] == 0
    assert result["failed"] == 0


def test_execute_run_no_tests_raises(tmp_path):
    (tmp_path / "test_empty.py").write_text("# nothing here\n", encoding="utf-8")
    with pytest.raises(NightwardError, match="no tests"):
        execute_run(str(tmp_path / "test_empty.py"), str(tmp_path / ".nightward"))
```

- [ ] **Step 2: 실패 확인**

Run: `pytest tests/test_runner.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'nightward.runner'`

- [ ] **Step 3: `runner.py` 구현**

```python
"""Shared run logic: capture behaviors via pytest, recompute the blast radius.

Used by both `cli.run` (rich console) and the MCP server (JSON) so the two
surfaces report the same measurement. No console output here.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from .core.baseline import Store
from .core.blast import aggregate
from .core.diff import compare
from .errors import NightwardError


def recompute(store: Store) -> dict:
    """Compare pending against baseline, aggregate, persist, and return the report."""
    report = aggregate(compare(store.load_baseline(), store.load_pending()))
    store.write_report(report)
    return report


def _pytest_cmd(path: str, dir: str) -> list[str]:
    # -B: no bytecode cache. Rewriting a test file between runs can otherwise
    # re-import a stale .pyc and silently capture OLD behavior (flaky in CI).
    return [sys.executable, "-B", "-m", "pytest", path,
            "--nightward-record", "--nightward-dir", dir, "-q"]


def execute_run(path: str = ".", dir: str = ".nightward", *,
                capture_output: bool = False) -> dict:
    """Run pytest in a subprocess to capture behaviors, then recompute.

    capture_output=True keeps pytest's stdout off this process's stdout — required
    when called from the MCP stdio server (any stray stdout breaks the protocol).
    Returns {report, skipped, failed, pytest_returncode}.
    """
    result = subprocess.run(_pytest_cmd(path, dir), capture_output=capture_output)
    if result.returncode == 5:
        raise NightwardError(f"pytest collected no tests under {path!r}")
    if result.returncode not in (0, 1):
        raise NightwardError(f"pytest exited with code {result.returncode}; aborting")
    store = Store(Path(dir))
    report = recompute(store)
    meta = store.load_run_meta()
    return {
        "report": report,
        "skipped": meta.get("skipped", 0),
        "failed": meta.get("failed", 0),
        "pytest_returncode": result.returncode,
    }
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `pytest tests/test_runner.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: `cli.py`를 `runner` 사용으로 리팩터링**

5a. import 교체 — `from .core.blast import aggregate` 줄을 제거하고 `from .runner import execute_run, recompute`를 추가. 결과 import 블록(파일 상단):

```python
from .core.baseline import Store
from .core.diff import UNCHANGED, compare
from .errors import NightwardError
from .runner import execute_run, recompute
from .signal import status_payload
from .view import build_site
```

5b. `_recompute` 헬퍼 정의(현재 `cli.py:71-74`)를 **삭제**:

```python
def _recompute(store: Store) -> dict:
    report = aggregate(compare(store.load_baseline(), store.load_pending()))
    store.write_report(report)
    return report
```

5c. `run` 명령 본문(현재 `cli.py:114-142`)을 아래로 **교체**:

```python
@app.command()
@handle_errors
def run(path: str = typer.Argument(".", help="Path passed to pytest"),
        dir: str = typer.Option(DEFAULT_DIR, help="Nightward storage dir")):
    """Re-run tests, capture behaviors, compute the blast radius."""
    _check_dir(dir)
    console.print(f"[dim]$ pytest {path} --nightward-record --nightward-dir {dir}[/dim]")
    result = execute_run(path, dir)
    if result["pytest_returncode"] == 1:
        err_console.print("[yellow]warning:[/yellow] some tests failed - captured "
                          "behaviors may be incomplete; blast radius may be unreliable")
    if result["skipped"]:
        err_console.print(f"[yellow]warning:[/yellow] {result['skipped']} test(s) skipped - "
                          "skipped behaviors appear as REMOVED; blast radius may show "
                          "false positives")
    _print_summary(result["report"])
```

5d. `approve` 명령의 마지막 줄(현재 `cli.py:195`) `_print_summary(_recompute(store))`를 `recompute`로:

```python
    _print_summary(recompute(store))
```

- [ ] **Step 6: 전체 테스트로 CLI 회귀 0 확인**

Run: `pytest -q`
Expected: PASS — 기존 `tests/test_integration.py`(run/approve/gate/status 사이클, no-tests=exit 2, 한글 review)가 전부 그대로 통과. `ruff check .`도 통과(미사용 `aggregate` import 제거됨).

- [ ] **Step 7: 커밋**

```bash
git add src/nightward/runner.py src/nightward/cli.py tests/test_runner.py
git commit -m "refactor: extract execute_run/recompute into runner.py (CLI behavior unchanged)"
```

---

## Task 2: `mcp_server.py` — 도구 함수 + 격리 가드 + stdout 오염 방지

**Files:**
- Create: `src/nightward/mcp_server.py`
- Test: `tests/test_mcp.py`

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_mcp.py`

```python
"""MCP adapter — the agent-facing surface.

The isolation guard is the load-bearing test: approve/reject MUST NOT be
reachable through MCP, or the gate self-approves and dies (spec §2).
"""
import pytest

from nightward import mcp_server
from nightward.core.baseline import Store

SAMPLE = '''
def test_a(behavior):
    behavior("a", {"v": 1}, group="g1")
'''
KOR = '''
def test_k(behavior):
    behavior("결제", {"v": 1}, group="빌링")
'''


def test_isolation_no_approve_reject_exposed():
    names = set(mcp_server._TOOLS)
    assert names == {"nightward_run", "nightward_status"}
    assert "approve" not in names
    assert "reject" not in names


def test_status_tool_reads_last_report(tmp_path):
    tw = tmp_path / ".nightward"
    store = Store(tw)
    store.ensure()
    store.write_report({"boundary": "intact", "unapproved": 0,
                        "counts": {"total": 0, "unchanged": 0, "new": 0,
                                   "changed": 0, "removed": 0},
                        "blast_radius": {}})
    out = mcp_server.status_tool(str(tw))
    assert out["boundary"] == "intact"


def test_status_tool_no_report_is_unknown(tmp_path):
    out = mcp_server.status_tool(str(tmp_path / "nope"))
    assert out["boundary"] == "unknown"


def test_run_tool_captures_and_signals(tmp_path):
    (tmp_path / "test_s.py").write_text(SAMPLE, encoding="utf-8")
    out = mcp_server.run_tool(str(tmp_path / "test_s.py"), str(tmp_path / ".nightward"))
    assert out["boundary"] == "breached"
    assert out["warnings"]["skipped"] == 0
    assert out["warnings"]["pytest_returncode"] == 0


def test_run_tool_does_not_pollute_stdout(tmp_path, capfd):
    (tmp_path / "test_s.py").write_text(SAMPLE, encoding="utf-8")
    mcp_server.run_tool(str(tmp_path / "test_s.py"), str(tmp_path / ".nightward"))
    out, _err = capfd.readouterr()
    assert out == ""   # pytest subprocess stdout captured, not leaked to fd 1


def test_run_tool_preserves_hangul(tmp_path):
    (tmp_path / "test_k.py").write_text(KOR, encoding="utf-8")
    out = mcp_server.run_tool(str(tmp_path / "test_k.py"), str(tmp_path / ".nightward"))
    assert "결제" in [c["name"] for c in out["changes"]]
```

- [ ] **Step 2: 실패 확인**

Run: `pytest tests/test_mcp.py -v`
Expected: FAIL — `ImportError: cannot import name 'mcp_server'`

- [ ] **Step 3: `mcp_server.py` 구현**

```python
"""MCP server — let an AI agent trigger the gate, but never approve it.

Exposes run/status (read·execute). approve/reject live only in the human CLI:
trigger != approval, or the gate is dead (spec §2). The tool functions below do
NOT import mcp, so the gate logic stays testable without the optional dependency.
"""
from __future__ import annotations

from pathlib import Path

from .core.baseline import Store
from .errors import NightwardError
from .runner import execute_run
from .signal import status_payload


def run_tool(path: str = ".", dir: str = ".nightward") -> dict:
    """Capture behaviors, recompute the blast radius, return the boundary signal."""
    result = execute_run(path, dir, capture_output=True)
    payload = status_payload(result["report"])
    payload["warnings"] = {
        "skipped": result["skipped"],
        "failed": result["failed"],
        "pytest_returncode": result["pytest_returncode"],
    }
    return payload


def status_tool(dir: str = ".nightward") -> dict:
    """Read the last boundary status without re-running (report absent -> unknown)."""
    return status_payload(Store(Path(dir)).load_report())


# The agent-facing surface. approve / reject / init / view are intentionally ABSENT.
_TOOLS = {
    "nightward_run": run_tool,
    "nightward_status": status_tool,
}


def build_server():
    """Build the FastMCP server with only the read/execute tools registered."""
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:
        raise NightwardError(
            "MCP support not installed - run: pip install 'nightward[mcp]'"
        ) from exc
    server = FastMCP("nightward")
    for name, fn in _TOOLS.items():
        server.tool(name=name)(fn)
    return server


def serve() -> None:
    """Start the stdio MCP server (blocks). FastMCP defaults to stdio transport."""
    build_server().run()
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `pytest tests/test_mcp.py -v`
Expected: PASS (6 passed) — `build_server`/`serve`는 아직 호출 안 하므로 `mcp` 미설치여도 통과.

- [ ] **Step 5: 커밋**

```bash
git add src/nightward/mcp_server.py tests/test_mcp.py
git commit -m "feat(mcp): agent-facing run/status tools with approve/reject isolation"
```

---

## Task 3: `nightward mcp` 서브커맨드 + `mcp` optional extra + 서버 빌드 검증

**Files:**
- Modify: `pyproject.toml` (`[project.optional-dependencies]`)
- Modify: `src/nightward/cli.py` (`mcp` 서브커맨드)
- Test: `tests/test_mcp.py` (build_server smoke 추가)

- [ ] **Step 1: 실패하는 테스트 추가** — `tests/test_mcp.py` 끝에 append

```python
def test_build_server_registers_without_error():
    pytest.importorskip("mcp")
    server = mcp_server.build_server()
    assert server is not None   # builds with FastMCP; tool set fixed by _TOOLS


def test_cli_exposes_mcp_subcommand():
    import subprocess
    import sys
    r = subprocess.run([sys.executable, "-m", "nightward", "--help"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert r.returncode == 0
    assert "mcp" in r.stdout
```

- [ ] **Step 2: 실패 확인**

Run: `pytest tests/test_mcp.py::test_build_server_registers_without_error tests/test_mcp.py::test_cli_exposes_mcp_subcommand -v`
Expected: `test_build_server...` SKIP(미설치 시) 또는 FAIL(설치됐는데 API 안 맞을 때); `test_cli_exposes_mcp_subcommand` FAIL — help에 `mcp` 없음.

- [ ] **Step 3: `pyproject.toml`에 의존성 추가**

`[project.optional-dependencies]` 블록(현재 `dev = ["pytest>=7", "ruff>=0.5"]` 한 줄)을 아래로 교체:

```toml
[project.optional-dependencies]
dev = ["pytest>=7", "ruff>=0.5", "mcp>=1.0"]
mcp = ["mcp>=1.0"]
```

그리고 설치: `pip install -e ".[dev]"` (FastMCP를 dev 환경에 들임 → smoke test가 SKIP이 아니라 실제 실행됨).

- [ ] **Step 4: `cli.py`에 `mcp` 서브커맨드 추가**

`status` 명령 정의 다음, `if __name__ == "__main__":` 앞에 추가:

```python
@app.command("mcp")
@handle_errors
def mcp_cmd():
    """Start the MCP server (stdio) for AI agents - exposes run/status, NOT approve."""
    from .mcp_server import serve
    serve()
```

(`mcp` 미설치 시 `serve()` 내부 `build_server`가 `NightwardError`를 던지고 `handle_errors`가 exit 2 + 안내 메시지로 변환한다.)

- [ ] **Step 5: 테스트 통과 확인**

Run: `pytest tests/test_mcp.py -v`
Expected: PASS — `test_build_server_registers_without_error` 포함 통과(dev에 mcp 설치됨), `test_cli_exposes_mcp_subcommand` 통과.

- [ ] **Step 6: 전체 게이트**

Run: `pytest -q` 그리고 `ruff check .`
Expected: 모두 통과.

- [ ] **Step 7: 커밋**

```bash
git add pyproject.toml src/nightward/cli.py tests/test_mcp.py
git commit -m "feat(mcp): nightward mcp stdio subcommand + mcp optional extra"
```

---

## Self-Review

**1. Spec coverage:**
- spec §3 공유 로직 추출(`execute_run`) → Task 1 ✓
- spec §3.1 `nightward_run`/`nightward_status` 2도구 + 반환 형태(`status_payload` + `warnings`) → Task 2 `run_tool`/`status_tool` ✓
- spec §3.1 approve/reject/init/view 미노출 → Task 2 `_TOOLS` + 격리 가드 테스트 ✓
- spec §4 에러: no-tests → Task 1 `test_execute_run_no_tests_raises` ✓; status report 부재 → `unknown` → Task 2 `test_status_tool_no_report_is_unknown` ✓
- spec §4 stdio 오염 금지 → `capture_output=True` + Task 2 `test_run_tool_does_not_pollute_stdout`(capfd) ✓
- spec §4 인코딩(한글) → Task 2 `test_run_tool_preserves_hangul` ✓ (MCP transport의 `ensure_ascii=False`는 FastMCP가 JSON 직렬화 시 처리; 도구는 dict 반환까지 책임)
- spec §7 `mcp` optional extra + `nightward mcp` 실행 → Task 3 ✓
- spec §2 "트리거≠승인" 불변 → 격리 가드가 회귀 방지 ✓

**2. Placeholder scan:** TODO/TBD/"적절한 처리" 없음. 모든 코드 블록 완전. ✓

**3. Type consistency:** `execute_run` 반환 키(`report/skipped/failed/pytest_returncode`)를 Task 2 `run_tool`이 그대로 소비. `_TOOLS` 키(`nightward_run`/`nightward_status`)를 격리 테스트가 그대로 검사. `recompute`(public) 이름이 `runner.py` 정의와 `cli` import/호출에서 일치. ✓

**미해결 가정 1개:** FastMCP의 `server.tool(name=...)(fn)` 등록 API와 `server.run()`의 stdio 기본 transport는 MCP SDK 1.x 기준. `test_build_server_registers_without_error`가 이를 실제로 검증하므로, 버전이 어긋나면 Task 3 Step 5에서 빨강으로 드러난다(은폐되지 않음).
