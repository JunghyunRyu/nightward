# nightward v0.2: LLM-as-judge 의미 diff 설계

> **날짜**: 2026-06-10
> **상태**: 구현 완료 (2026-06-10) — `judge.py` + `persona:*` 무키 백엔드 추가, 멀티 모델은
> `provider:model` spec으로 선택. acceptance는 `tests/test_judge.py` + 실데이터 A/B로 검증.
> **동기(정량)**: `docs/experiments/2026-06-10-web-data-gate-validation.md` — 자유텍스트 AI 출력은
> 동일 입력·동일 코드에서도 fingerprint 위양성 **25/25 (100%)**. field-scrub(`doctor`)로 구조화
> 레이어는 잔여 0까지 길들였지만, 자유텍스트는 v0 동등성 oracle로는 원리적으로 게이트 불가.

## 1. 목적

비결정적 *텍스트* 동작에 한해 동등성 oracle을 `sha256(canonical_json)` → **"의미가 같은가"** 로
교체할 수 있게 한다. 결정적 레이어는 절대 건드리지 않는다(비용·신뢰 양쪽 이유).

## 2. 게이트 원칙 (비협상 — CLAUDE.md §범위 가드레일)

- **judge는 동등성만 판단하고, 승인하지 않는다.** verdict SAME은 "변경 아님"으로 접는 것이지
  baseline을 바꾸는 게 아니다. baseline 변경은 여전히 사람 CLI `approve` 전용.
- **opt-in 명시.** `behavior(name, val, group=, semantic=True)`로 표시한 동작만 judge 경로를 탄다.
  기본값은 v0 fingerprint — 실험이 보여줬듯 결정적 레이어는 이미 깨끗하다.
- **judge 불능 시 보수적 폴백.** API key 없음/네트워크 실패/응답 파싱 실패 → fingerprint 비교로
  폴백(= breach 쪽으로 넘어짐). 게이트는 조용히 열리느니 시끄럽게 닫힌다.

## 3. 아키텍처

```
core/diff.py compare()
  └ fingerprint 불일치 & behavior.semantic=True
        └ judge.equivalent(old_text, new_text)   # 신규 judge.py
             ├ ledger hit (.nightward/judge_verdicts.json — 커밋 대상, key=old_fp:new_fp:spec) → 재판정 없음
             ├ SAME      → Change(kind=UNCHANGED, judged=True)  # report에 감사 표기
             └ DIFFERENT → Change(kind=CHANGED,  judged=True)
```

- **결정성 확보**: 같은 (old_fp, new_fp) 쌍은 캐시로 단 한 번만 판정 — judge 자체의 비결정성이
  게이트를 흔들지 못하게 한다. ledger는 **커밋 대상** — 새 클론/CI에서도 판정이 결정적으로 재생되고, PR diff에서 사람이 리뷰한다(2026-06-10 비평 라운드에서 transient 캐시의 일시성 모순을 교정).
- **프롬프트**: 보수적 기준 고정 — "사실 내용·수치·결론이 동일한 재표현인가? 불확실하면 DIFFERENT."
  temperature 0, 구조화 출력(JSON `{verdict, reason}`).
- **모델**: 기본 최신 소형 모델(비용), `--judge-model`로 교체 가능. optional extra `[judge]`
  (`anthropic` SDK), `mcp`와 동일 패턴 — SDK 없이도 코어 테스트 가능하게 judge 함수는 주입식.

## 4. 표면 변화

- `pytest_plugin`: `behavior(..., semantic=True)` → Behavior에 `semantic: bool = False` 필드 추가
  (스키마 하위호환: 기존 approved 파일은 semantic 부재 = False).
- `run`/`review`/`view`/`status --json`: judged 변경에 `judged: true` 표기(감사 가시성).
- MCP 표면 불변 — judge는 run 내부 동작, `_TOOLS`에 신규 노출 없음.

## 5. 위험과 한계 (문서화할 것)

- judge 오판(SAME인데 실제 회귀) = **게이트 구멍**. 그래서 기본 off, opt-in, 보수적 프롬프트,
  verdict 감사 기록. "의심스러우면 breach"가 항상 이긴다.
- 비용: CHANGED·semantic 동작 수 × 1회(캐시 후 0회). 실험 기준 run B 1회 = 25콜 상한.
- 실험의 `ai_run_a/b` 데이터가 그대로 acceptance fixture가 된다: A→B에서 semantic=True면
  위양성 25→0에 수렴해야 하고, 사실 왜곡을 주입한 B'는 DIFFERENT로 잡혀야 한다.

## 6. 범위 (YAGNI)

- **In**: semantic 플래그, judge.py(+캐시), 보수적 폴백, report 감사 표기, acceptance fixture.
- **Out**: 자동 승인(영구 OUT), 구조화/결정적 payload의 judge 적용 기본화, 멀티 프로바이더
  추상화, 의미 diff의 자연어 설명 생성.
