# 실험: 이종 문서 포맷 입력의 게이트 처리 가능성

> **날짜**: 2026-06-10
> **입력**: 실사용 환경에서 수집한 실제 문서 5개 포맷 5파일
> (PDF 183KB · XLSX 92KB · DOCX 145KB · **HWP** 207KB · TXT 678B cp949).
> 원본 파일·캡처는 gitignore된 `live-experiment/docs-input/`에만 존재(비커밋).
> **질문**: "PDF/XLSX/이미지 같은 다양한 데이터를 입력받았을 때 처리가 가능한가?"

## 방법

코어는 건드리지 않았다. 약 70줄짜리 어댑터 프로토타입(`adapters.py`)이 각 포맷을
안정적인 JSON payload로 변환하고, 그 위는 기존 파이프라인 그대로:

| 어댑터 | payload | 전략 |
|---|---|---|
| `from_file` | sha256 + size | **모든 포맷**(파서 없는 HWP 포함) — artifact 게이트 |
| `from_pdf` | pages + 추출텍스트 길이/해시 | content 게이트 (바이트 노이즈에 강건) |
| `from_docx` | 문단/표 수 + 텍스트 해시 | content 게이트 |
| `from_xlsx` | 시트별 rows/cols + 셀값 해시 | content 게이트 |
| `from_text` | 인코딩 감지(utf-8→cp949) + 텍스트 해시 | 레거시 한국어 인코딩 대응 |

## 결과

| 단계 | 결과 |
|---|---|
| 캡처/승인 (6 behaviors, 5 포맷) | ✅ 전부 성공 — 한글 파일명을 behavior 이름으로 그대로 사용 가능 |
| 무변경 재실행 (FP) | ✅ **0건** — cp949 TXT 포함 6/6 unchanged |
| XLSX 셀 1개 변조 (TP) | ✅ 정확히 해당 behavior **1건만** breach, 나머지 4개 포맷 무결 |
| `doctor` 진단 | ✅ 드리프트 필드(`content_sha256`)를 정확히 지목 + "회귀라면 scrub 금지" 경고 |
| PDF 재저장 (내용 동일, 바이트만 변경) | ✅ artifact 게이트만 breach, **content 게이트는 무결** — 메타데이터 노이즈와 실제 변경을 분리 |

## 결론

1. **가능하다 — 코어 변경 없이.** nightward는 JSON을 게이트하므로, 포맷 지원의 본질은
   "안정적 JSON으로의 변환"이고 이는 얇은 어댑터의 일이다. 파서가 없는 포맷(HWP)도
   `from_file` 해시로 오늘 즉시 게이트된다.
2. **artifact vs content 2단 전략이 핵심 설계.** 바이트 해시는 만능이지만 재저장
   노이즈에 위양성을 내고, content 추출은 강건하지만 포맷별 파서가 필요하다.
   둘을 모두 캡처하면 "파일이 바뀌었다"와 "내용이 바뀌었다"를 분리해 보고할 수 있다.
3. **레거시 인코딩(cp949)은 어댑터 계층에서 처리** — 코어는 이미 유니코드 안전.
4. **제품화 권고**: `nightward.adapters` 모듈로 승격할 가치 확인.
   `from_file`은 stdlib-only라 코어 동승 가능, pdf/docx/xlsx는 optional extra
   (`nightward[docs]`)로. 단, 이미지(perceptual hash)는 시각 회귀 도구와의 경계
   문제가 있어 수요 확인 후.
