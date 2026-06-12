# nightward — MCP 에이전트 게이트: AI가 스스로 당기는 회귀 방화벽

**날짜:** 2026-06-07
**상태:** 브레인스토밍 도출 → 사용자 검토 대기.
**브레인스토밍 결정 (둘 다 사용자 선택):**
- 핵심 사용자 = **AI 에이전트가 스스로 트리거** (→ MCP가 surface).
- 사람의 위치 = **명시 승인 / AI는 breached면 멈추고 보고** (반자동 체크포인트).

**전제:** README/CLAUDE.md v0.2. 이 설계는 CLAUDE.md 범위 가드레일의 `gate → loop-signal 파이프라인`(명시적 *in-scope*)의 자연스러운 **출구**다 — 신규 방향이 아니라 코어가 이미 향하던 곳.

---

## 1. 목표

nightward를 **AI 코딩 에이전트가 도구로 직접 호출**하는 MCP 서버로 노출한다. 에이전트가 자기 변경 직후 `nightward_run`을 호출 → blast radius / boundary 신호를 받아 → intact면 진행, breached면 **멈추고 사람에게 보고**한다. 게이트의 심장인 `approve`/`reject`(= 경계를 이동시키는 결정)는 **사람 CLI에만** 남긴다.

한 줄: **"AI에겐 *뭐가 조용히 바뀌었나*를 비추는 거울만, *이건 괜찮다*는 도장은 사람에게."**

## 2. 핵심 설계 원칙 — 격리 = 게이트 생존

| 원칙 | 내용 | 근거 |
|------|------|------|
| **트리거 ≠ 승인** | AI는 run/status(읽기·실행)만. approve/reject(경계 이동)는 사람 CLI 전용. | 트리거 주체와 승인 주체가 같아지면 게이트가 자살 — "변경 로그"로 전락. **타협 불가.** |
| 거울만, 도장은 사람 | MCP는 *어디가* 흔들렸나(group/behavior 좌표)만 준다. 판단·승인은 사람. | `view` 보안 모델("읽기 전용, approve는 CLI만")의 동일 원리 확장. |
| breached = 정지 신호 | boundary breached는 에이전트 루프의 stop-condition이자 사람 보고 트리거. | `signal.py`가 이미 "stop-condition oracle for agent loops"로 설계됨. |
| 캡처 데이터 최소 노출 | MCP는 좌표만, diff(캡처 *내용*)는 안 준다. 상세는 사람이 CLI `review`로. | 민감 데이터 노출 표면 축소. |

이 네 줄이 깨지면 spec 전체가 무의미하다. 특히 1행이 무너지면 nightward가 아니다.

## 3. 아키텍처 — 얇은 어댑터 + 공유 로직 추출

MCP 서버는 신규 로직을 거의 안 만든다. 기존 코어를 호출하는 **얇은 어댑터**다. 단 한 가지 리팩터링이 선행된다.

**공유 run 로직 추출.** 현재 `cli.run`은 pytest subprocess 실행 + returncode 처리 + `_recompute` + 경고 메타 수집 + rich console 출력이 한 함수에 엉켜 있다. 이 중 *순수 로직*을 분리한다:

```
nightward/runner.py (신규):
    execute_run(path, dir) -> RunResult
        # pytest subprocess (-B -m pytest <path> --nightward-record --nightward-dir <dir> -q)
        # returncode 처리 (5/2 → NightwardError, 1 → failed 경고, 0 → 정상)
        # _recompute(store) → report
        # run_meta(skipped/failed) 수집
        # return {report, skipped, failed, pytest_returncode}   ← console 출력 없음

소비자 (둘 다 같은 진실, 다른 표면):
    cli.run            → execute_run() 호출 후 rich console로 예쁘게 출력 (기존 동작 보존)
    mcp.nightward_run  → execute_run() 호출 후 status_payload + 경고를 JSON 반환
```

→ CLI 동작은 그대로(회귀 0, 기존 `tests/` 보존), MCP는 같은 측정값을 다른 표면으로 내보낼 뿐.

### 3.1 MCP 도구 표면 (stdio 서버)

| 도구 | 노출 | 반환 | 부수효과 |
|------|------|------|----------|
| `nightward_run(path=".", dir=".nightward")` | ✅ | `{boundary, unapproved, changes[], warnings:{skipped, failed, pytest_returncode}}` | pytest 재실행 → report.json 갱신 (경계는 *측정*만, 이동 없음) |
| `nightward_status(dir=".nightward")` | ✅ | `{boundary, unapproved, changes[]}` (마지막 report) | 없음 (읽기 전용) |
| `approve` / `reject` / `init` / `view` | ❌ **미노출** | — | 사람 CLI 전용 |

- `changes[]` = `signal.status_payload`의 `[{name, kind, group}]` 그대로 (NEW/CHANGED/REMOVED = unapproved).
- **`nightward_run`은 경계를 읽지 이동시키지 않는다.** report.json 갱신은 "현재 상태 측정"이지 "승인"이 아니다. 오직 `approve`만 baseline(= 경계)을 움직인다. 이 구분이 "run은 AI에게 줘도 안전, approve는 안 됨"의 근거.

### 3.2 데이터 흐름 (브레인스토밍 그림의 구현)

```
에이전트 코드 변경
  → MCP nightward_run
      → execute_run: pytest --nightward-record (subprocess) → capture→compare→blast → report
      → status_payload(report) + warnings
  → boundary 분기:
      intact   → 에이전트 계속 (게이트 통과)
      breached → 에이전트 멈춤, changes[]를 사람에게 보고
                   ├ 의도된 변경 → 사람이 CLI `nightward approve` (MCP 아님!)
                   └ 회귀        → 에이전트에 "되돌려/고쳐" → 다시 nightward_run
```

## 4. 에러·인코딩

- 에이전트/사용자 유발 오류는 traceback이 아니라 **구조화된 도구 에러 + 명확한 메시지**(CLI의 `NightwardError`→exit 2 패턴을 MCP 에러 응답으로 변환). 예: `nightward_run`이 pytest 테스트 0개 수집(returncode 5) → "no tests under `<path>`". 반면 `nightward_status`는 report가 없어도 **에러가 아니라** `boundary:"unknown"`을 반환한다 — `status_payload`의 계약(측정 부재를 *상태*로 표현; report 부재에 에러로 멈추는 건 `gate`뿐).
- pytest returncode 매핑: `0`=정상, `1`=`warnings.failed`로 표기(차단 아님, 캡처 불완전 경고), `2`·`5`=도구 에러.
- 응답 JSON은 **UTF-8 / `ensure_ascii=False`**(한글 behavior 이름 보존) — `status --json`과 동일.
- **stdio 오염 금지:** MCP stdio는 프로토콜 채널이다. 진단/로그 출력은 **stderr로만** 보낸다(stdout에 한 줄이라도 새면 프로토콜이 깨짐). cp949 콘솔 함정과는 무관(rich console 경로를 안 탐).

## 5. 사용 시나리오 (반자동 체크포인트)

1. 에이전트가 기능 수정.
2. `nightward_run()` → `{boundary:"breached", changes:[{name:"checkout_total", kind:"CHANGED", group:"billing"}, {name:"points", kind:"CHANGED", group:"loyalty"}]}`.
3. 에이전트: **멈춤.** "내 변경이 billing·loyalty 2개 동작을 건드렸어 — checkout_total, points가 바뀜. 의도한 거야?" → 사람에게 보고.
4. 사람 판단:
   - 의도 → 터미널에서 `nightward approve checkout_total points`(또는 `--all`).
   - 회귀 → "loyalty는 건드리면 안 돼. 되돌려." → 에이전트가 코드 수정 → 2로.
5. 다시 `nightward_run()` → `{boundary:"intact"}` → 에이전트 완료.

→ AI 루프가 사람 체크포인트에서 멈추는 것은 *버그가 아니라 제품*이다. "AI가 조용히 부순 것을 사람 눈앞에 들이미는 순간"이 nightward의 가치다.

## 6. 테스트 (TDD)

`tests/test_mcp.py` (+ `tests/test_runner.py` for 추출 로직):

- **격리 가드 (핵심):** MCP 서버 도구 목록에 `nightward_run`/`nightward_status`는 **있고** `approve`/`reject`/`init`/`view`는 **없다.** (트리거≠승인 경계의 회귀 방지 — 누가 실수로 approve를 노출하면 빨강.)
- `nightward_run`이 intact/breached report에서 `status_payload` 구조를 정확히 반환.
- `warnings`에 skipped/failed/returncode 반영.
- `nightward_status`가 마지막 report를 부수효과 없이 반환; report 없으면 `boundary:"unknown"`(에러 아님 — `status_payload` 계약).
- 한글 behavior 이름이 응답 JSON에 UTF-8로 보존(`ensure_ascii=False`).
- pytest 0개 수집(returncode 5) → 구조화 에러.
- **추출 회귀 가드:** `execute_run` 분리 후 기존 `nightward run` CLI 동작/출력 불변(기존 테스트 통과 + 신규 `test_runner`).

## 7. 의존성·실행

- 신규 **optional** dep: 공식 MCP Python SDK. `[project.optional-dependencies]`에 `mcp = ["mcp"]` extra(버전 핀은 구현 시 lock). 코어 설치(`pip install nightward`)엔 영향 없음 — pytest/typer/rich 그대로.
- 실행: typer app에 `nightward mcp` 서브커맨드 추가 → **stdio** MCP 서버 시작. 에이전트(Claude Code 등)가 이 명령을 subprocess로 띄워 도구를 발견한다.
- transport는 **stdio만**(로컬). HTTP/SSE는 OUT.

## 8. 범위 (YAGNI)

**IN (MVP):**
- `nightward/runner.py`의 `execute_run` 공유 로직 추출 (CLI 회귀 0).
- `nightward mcp` stdio 서버 + `nightward_run` / `nightward_status` 2도구.
- 격리(approve/reject 미노출) + 격리 가드 테스트.

**OUT (의도적 제외 — 이번에 거른 것 포함):**
- `approve`/`reject`의 MCP 노출 ❌ (게이트 자살).
- 자동·정책 기반 승인 엔진 ❌ (브레인스토밍 옵션 3 거부).
- diff / 캡처 *내용* 노출 ❌ (좌표만; 상세는 사람 CLI `review`).
- HTTP/SSE transport, 멀티 워크스페이스, PR 코멘트 봇 ❌.

## 9. 비가역 제약 확인 (CLAUDE.md §비가역)

- MCP 추가는 **코어 코드 변경**일 뿐 — 레포 공개 여부와는 독립적인 결정이다.
- 캡처 데이터 *발행* 아님 — 오히려 표면을 좌표로 최소화(diff 비노출)해 노출을 **줄인다.**
- → 비가역 제약 **위반 없음.** §비가역 정신과 일관.
