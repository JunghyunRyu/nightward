# nightward v0.2 — `nightward view`: 정적 blast-radius 대시보드

**날짜:** 2026-06-05
**상태:** 5-페르소나 패널 검증 완료 (4 GO-WITH-FIXES, 1 NO-GO=법적/배포 한정). 구현 승인.
**승인 게이트:** 사용자 자율 위임 → 5 가상 페르소나 패널(P1 솔로개발자 / P2 CI / P9 신규 / P6 한글 / 보안·리스크). 자세한 검토는 세션 로그 참조.

## 1. 목표

nightward가 만든 회귀 경계(blast radius)를 **브라우저에서 본다.** README의 v1 OUT 항목 "web UI"를 v0.2로 당겨, 정적·자기완결·읽기전용 대시보드로 구현한다. 상태변경(approve/reject)은 CLI에 남긴다 — "UI로 *볼 수 있는* 시스템".

## 2. 아키텍처 (GitHub Pages = 정적 호스팅이 강제)

- 새 CLI: `nightward view` (별칭 의미의 `build-site`). `.nightward/`를 읽어 **백엔드 없는 정적 사이트**를 출력 디렉터리에 생성.
- **보안 결정 (보안 페르소나 P0):** 데이터를 HTML에 인라인 주입하지 **않는다.** 생성기는 정적 `index.html` + `app.js` + `style.css`를 복사하고, 데이터는 별도 `data.json`으로 emit. 페이지는 `fetch('./data.json')` 후 **`textContent`/DOM API로만 렌더**(`innerHTML` 금지). → 서버측 템플릿 주입이 0이라 stored XSS 표면이 사라진다. 이스케이프 부담이 JS의 textContent로 이동(브라우저가 안전 보장).
- `fetch`는 `file://`에서 CORS로 막히므로 **로컬 열람은 `--serve`(로컬 HTTP + 브라우저 오픈)로 제공** — P1의 "로컬 즉시성" 요구와 정확히 맞물림. GitHub Pages(https)에서는 fetch 정상.

### 2.1 출력 레이아웃
```
<out>/
  index.html     # 데이터 없음. <meta charset> + CSP. app.js/style.css 링크
  app.js         # fetch('./data.json') → textContent 렌더
  style.css
  data.json      # { report, meta }  ← 유일한 데이터 파일
```

### 2.2 `data.json` 스키마
```json
{
  "report": { "boundary": "...", "unapproved": N, "counts": {...}, "blast_radius": {...} } | null,
  "meta": {
    "skipped": N, "failed": N,        // run_meta.json
    "baseline_count": N,              // store.load_baseline() 크기 (no-baseline 구분용)
    "pending_count": N,
    "source": ".nightward",
    "generated": "ISO8601"            // 표시용. 테스트는 값이 아닌 키 존재만 검증
  }
}
```

## 3. 화면 사양 (페르소나 MUST-FIX 반영)

### 상태 분기 (P9 M1 — 1급 시민)
- **no-report** (`report == null`): 중립 안내 + 복사용 `nightward run example`. 빨강/깨진 카드 금지.
- **no-baseline** (`baseline_count == 0`): "아직 승인된 기준선이 없습니다 — `nightward approve --all`로 현재 동작을 기준선으로." 중립색.
- **intact** (변경 0): 초록 배너 + "마지막 승인 기준선과 동일."
- **breached**: 빨강 배너 + 카드.

### 헤더 (P1 — 재현성)
- `generated` 시각 + `source` 경로 + boundary 상태 한눈 표시.

### 배너
- intact=초록 / breached=빨강 + unapproved 수. **평이한 한 줄 설명**(P9 M2): intact="승인된 기준선 이후 바뀐 동작 없음", breached="승인되지 않은 변경 N개 — 검토 필요".
- **skipped/failed 경고**(P1·P9): 숫자 + "skipped 동작은 REMOVED로 오인될 수 있음" 설명.
- **데이터 노출 경고 배너**(보안 P1): "이 페이지는 캡처된 시스템 출력을 포함할 수 있습니다. 공개 배포 전 검토하세요."

### counts 스트립
- unchanged/changed/new/removed + 한글 부제(그대로/바뀜/신규/사라짐).

### blast radius (P1 M2/M4, P9 M3)
- 그룹별 섹션, **접기/펴기**. **필터**: kind·group, "unapproved만" 토글.
- 카드: kind 배지 + name + diff. **REMOVED 시각적 분리/강조**(P1). kind 범례+툴팁(NEW/CHANGED/REMOVED, REMOVED는 skip 가능성 명시 — P9).
- diff: 색칠된 +/− (이스케이프됨). 헤더 라벨 사람말로: approved→"기준선(전)", received→"이번 실행(후)"(P9 M4).
- **결정 양갈래 + 일괄**(P9 M3, P1 M2): 카드마다 복사용 `nightward approve <name>` **및** `nightward reject <name>`. 그룹 헤더에 "이 그룹 전체 승인", 배너에 "전체 승인" 묶음 명령(+ "전체 승인은 회귀까지 묻힘" 경고).

## 4. 보안/인코딩 강제 (P6·보안 — 테스트로 박제)
- 모든 파일 쓰기 `encoding="utf-8"`. `index.html`에 `<meta charset="utf-8">`.
- CSP 메타: `default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'` — inline script 금지(그래서 app.js 외부 분리).
- JS 렌더는 `textContent`/`createTextNode`만. `innerHTML`/`insertAdjacentHTML` 금지.
- `data.json`은 `ensure_ascii=False`(한글 보존) + `application/json`으로 서빙(HTML 파서 안 탐).
- stdout 출력은 기존 utf-8 reconfigure 콘솔 사용.

## 5. 배포 (P2 — gate/view 분리)
- `pr.yml` (on PR): **gate 잡**(run+gate, required, 의존성0) + **test 잡**(pytest, required) + **preview 잡**(view→`upload-artifact`, non-blocking).
- `pages.yml` (on push main / manual): **클린룸 `example`만** 빌드 → Pages 발행. `concurrency: pages`, 최소 권한, `environment: github-pages`.
- **실 데이터 비발행 제약 → 합성 데모 한정 발행**(P2·보안 M3). 데모 사이트에는 클린룸 합성 데이터(`scripts/build_demo.py`)만 push.

## 6. 법적·비가역 결정 (보안 페르소나 → 사용자 보고 필수)
실 데이터가 담긴 `.nightward/` 스토어는 절대 공개 발행하지 않는다. 발행 경로는 **클린룸 합성 데이터**(`scripts/build_demo.py`) 한정 — 실제 공개 클릭은 메인테이너 명시 승인 후.

## 7. 테스트 (TDD, 페르소나 가드)
`tests/test_view.py`:
- `build_site`가 index.html/app.js/style.css/data.json을 UTF-8로 emit.
- index.html bytes에 `<meta charset="utf-8">` + CSP 포함.
- app.js에 `innerHTML` 미존재(정적 가드).
- data.json이 report+meta 구조, 한글 behavior 이름이 UTF-8 바이트로 보존.
- no-report / no-baseline / intact / breached 4상태에서 크래시 없이 생성.
- cp949 불가 문자(이모지) + 한글 혼합 report로 크래시 없이 생성.
- CLI `nightward view` 통합(서브프로세스), cp949 stdout 무사고.

## 8. v0.2 OUT (이후)
LLM-as-judge 의미 diff, PR 코멘트 봇 요약, 델타 뷰(이전 baseline 대비), 다크모드, 검색.
