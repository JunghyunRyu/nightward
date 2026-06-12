# 게이트 품질 정량 검증: 실시간 웹 데이터 실험 결과 요약

> **날짜**: 2026-06-10
> **스펙**: `docs/superpowers/specs/2026-06-09-nightward-live-email-ai-experiment-design.md`의 프로토콜을 따름.
> 입력 소스만 변경: Gmail → **웹 검색 실데이터**(기술/세계뉴스/금융/과학/스포츠 5종, 24건 + 시장 지수 3종).
> 원본 스냅샷·캡처·상세 RESULTS.md는 `live-experiment/`(gitignore)에만 존재. 이 문서는 집계 수치만 담는다.

## 판정표

58개 동작(facts 8 · ai_text 25 · ai_struct 25)을 같은 파이프라인에 태운 결과:

| 레이어 | TP: 주입 회귀 | FP: 무변경 재실행 (A→A) | FP: AI drift (A→B) | 길들이기 후 잔여 | 판정 |
|---|---|---|---|---|---|
| `facts/*` 결정적 집계 | ✅ off-by-one → 정확히 1건 CHANGED | **0** | **0** | — | 깨끗한 게이트 |
| `ai_text` 자유텍스트 | — | 0 | **25/25** | 25 (감소 불가) | v0 범위 밖 |
| `ai_struct` 구조화 | — | 0 | **4/25** | **0** (안정 필드만 캡처) | 길들이기 가능 |

## 결론 (스펙 §8 성공 기준 전부 충족)

1. **게이트 검증**: 결정적 레이어에서 주입 회귀를 동작 1건 단위로 격리해 잡았고(blast radius가 해당 group만 breach), 재실행·AI-drift 양쪽 위양성 0.
2. **경계 실증**: AI 자유텍스트는 동일 입력에서도 위양성 100% — fingerprint 동등성으로 게이트 불가. **v0.2 LLM-as-judge의 동기를 정량 확인.**
3. **실용 타협**: 구조화 AI 출력의 drift는 경계선 판단 필드(priority/sentiment)에 집중. 안정 필드(topic 등)만 캡처하면 잔여 위양성 0 — v0 사용자 가이드: *AI 출력은 구조화하고, 흔들리는 필드는 캡처에서 빼라.*

## Phase 4b — `nightward doctor` 검증 (실험이 낳은 기능)

이 실험의 ai_struct 위양성 4건을 입력으로 `nightward doctor`(신규)를 검증:

- doctor가 drift 필드를 정확히 지목: `priority` 2건, `sentiment` 2건. 자유텍스트(`ai_text`)는 root(`$`) 변경으로 분류되어 **field 제안 없음**(정직한 한계 보고).
- 제안된 `scrub.register_field("priority")`/`("sentiment")`를 conftest.py에 적용 후 re-baseline → RUN=b 재실행: **ai_struct 잔여 위양성 4→0**, 필드를 캡처에서 빼지 않고도(STABLE_ONLY 방식과 달리 payload 형태 유지) 달성.
- 위양성 발견 → 진단 → 길들이기 → 재검증 루프가 CLI만으로 닫힘.

## 부수 발견

- behavior 이름 공백 금지(`validate_name`)에 첫 캡처가 걸림 — 에러 메시지 명확, `run`이 failed-test 경고 출력. 설계대로 동작.
- 날짜를 `YYYY-MM-DD`로 정규화한 덕에 scrubber 오발동 0 (스펙 §3의 함정 회피 확인).
