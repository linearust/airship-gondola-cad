# 임시 AI 인계 — 2026-09-30

**인수 확인 후 이 파일을 삭제한다.** 상시 지침은 [README](README.md)다.
아래는 BL 설계의 인계용 요약이며, 이후 사용자 지시와 실제 저장소 상태를 우선한다.
요구사항·치수·검증 결과를 이 문서에서 별도로 유지하지 않는다.

## 인수 순서

1. 저장소 `/home/h/cad/airship-gondola-cad`에서 Git 상태·최근 커밋·원격을 확인한다.
   원격은 `https://github.com/linearust/airship-gondola-cad.git`이며, 인계 작성 시 작업
   브랜치는 `codex/square-carriers`였다. 다른 작업과 미저장 CAD를 보존한다.
2. `python3 -m gondola status`와 [검증 기록](references/design_verification.json)을 읽는다.
   기록의 source/CAD/fixture 해시를 실제 파일과 비교한다. 비교 함수는
   [provenance.py](gondola/provenance.py)에 있다. tests/tools 변경은 fingerprint와 별도로 확인한다.
3. 아래 주의점과 관련 소스를 파악한 뒤 인수 완료를 알리고 이 문서만 삭제한다.

## 현재 상태를 오해하기 쉬운 지점

현재 상태는 **fit_prototype**, `production_released = false`다.
형상 검증 통과와 실물 제작·전원·비행 검증은 다르다.

| 영역 | 현재 선택 및 구분 |
| --- | --- |
| 레일 | 300 mm, 테이프 날개 7쌍. 340 mm는 제조 크기 상한. 베이스/날개는 업체 검토에 따른 nominal 1.5 mm |
| 모듈 분리 | 두 서보/입력 기어의 교체 모듈과 출력축/추진기 프레임은 의도적으로 분리 |
| 구동 | KST X06, metric m0.5의 **48T 입력 → 16T 출력**, 보어 Ø3 mm. 각도비 −3, 목표 bounded ±180°. 연속 회전 또는 임의 기어비 선택 구조가 아님 |
| 서보혼 | 제조사 기본 **half arm 1**. 과거 금속혼 여러 종류를 받는 안이 아님. 기존 공장 구멍 두 개의 확대 가공은 여전히 필요하며, 어댑터의 원형 홀/짧은 슬롯은 조립 공차를 받음 |
| 베어링 | 구매한 generic **3×6×2.5 mm** 네 개. 고정 seat/shoulder와 분리형 keeper 사용. 비교용 NSK/ISC 자료가 구매품의 제조사·공차를 보증하지 않음 |
| 장착판 | 배터리/FC/항법장비가 같은 출력 캐리어 계열을 사용. 카본 어댑터·튜브 레일 안은 현재 채택하지 않음. 슬롯 배열은 X500 공통 규격이 아닌 프로젝트 인터페이스 |
| 전자장비 | FC **H743V2 AIO 45A AM32**, 2S 지원은 사용자 확인. 기본 항법 P-AS, 광학 MTF-02P, 기체 radio LR24-F-Mini |
| 교체 장비 | MG-A01/M10 Ultra 또는 MG-F10-A는 P-AS와 교체, MTF-01P는 MTF-02P와 교체. 동시 설치 전제가 아님. LR900-A는 제외 |
| 광학센서 | 기존 캐리어에 붙는 수동 pitch 한 축. 자동 수평이 아니며 위치 변경 후 시야·배선·간섭을 재검증 |
| 전원 | 기본 배터리. 선택 계류안은 24 V → BEC12S-PRO **한 개의 8 V** → 주전원 및 SVPDB 입력; SVPDB **5 V**가 서보 전원. SVPDB 5 V와 FC 5 V 출력 양극은 분리 |

세부 치수·가공·체결·분해 순서는 아래 소스가 기준이다. 이 표를 새 구매 목록이나
실물 호환 인증으로 쓰지 않는다. 과거 Notion 계획도 현재 CAD와 동기화되었다고 가정하지 않는다.

## 남은 불확실성

전체 목록은 [design.py](gondola/contracts/design.py)의 `release_status()`에 있다.
특히 다음 구분을 유지한다.

- 레일 끝의 항법 슈 여유는 nominal **1 mm**이고 FC 지지는 테이프 중심과 일치하지 않는다.
  실제 곡률·전체 물림·테이프 접착·PA12 크리프는 미검증이다. 쿠폰은 생산 조건과 맞춘다.
- 제조사 혼 CAD는 실제 spline seating·편심·체결 하중을 보증하지 않는다. 베어링 실드/외륜,
  축 맞춤, 기어 고정과 서보 허용 측하중도 실물 확인 대상이다. M3 기어 고정나사 형상은 미모델링이다.
- 회전하는 모터선, 실제 커넥터와 FC/P-AS 체결 stack은 공간 예약만으로 검증되지 않는다.
  RC 설치, heading reference, 원격 GPS 안테나, 계류선 고정·전류·열도 완성된 통합으로 간주하지 않는다.
- CAD 질량은 부분 추정값이다. 미확인 질량·CG·관성·추력을 실측값으로 제시하거나 unknown을 0으로 채우지 않는다.
  native CAD 좌표와 CV/CG·FRD를 구분하고 [simulation exporter](tools/simulation/export_parameters.py)의 좌표 정의를 따른다.

## 근거와 구현 위치

| 찾을 내용 | 파일 |
| --- | --- |
| 선택·범위·제조·미확정점 | [설계 계약](gondola/contracts/design.py) 및 `status` |
| 기어·혼·전원 선택 | [drive.py](gondola/contracts/drive.py), [servo_horns.py](gondola/contracts/servo_horns.py), [power_options.py](gondola/contracts/power_options.py) |
| 혼 원본과 가공/분해 | [원본 provenance](references/manufacturer/kst_x06_servo_horns_2026-09-28.json), [servo_coupling.py](gondola/parts/servo_coupling.py), [horn_coupling.py](gondola/validation/horn_coupling.py) |
| 레일·마운트·베어링 등 형상 | [parts](gondola/parts/); 조립 위치는 [assembly.py](gondola/assembly.py) |
| 구매 선택·원본 도면 | [sources.json](references/sources.json), [최종 카트 기록](references/cart_selected_parts_2026-09-29.json) |
| 과거 실행·fixture 승인 근거 | [검증 기록](references/design_verification.json), [승인 기록](tests/fixtures/review.json), 상세 `references/design_checks.json.gz` |

검증 기록은 실행 당시 입력에 묶인다. 압축 기록 속 예전 경로·임시 스크립트를
현재 실행 환경으로 가정하지 않는다. 원본 자료와 기계 검증 근거는 보존하되,
삭제된 장황한 설명·검수표를 인수 과정에서 다시 만들 필요는 없다.

## 산출물과 실행

- CAD: `build/gondola.FCStd`
- 출력물·BOM·검증: `build/gondola_print_parts.zip`; 수량은 `build/gondola_print_parts/print_manifest.json`
- 시뮬레이션 입력: `build/simulation_parameters.json`
- Blender: `build/blender_review/cad_review.blend`
- 이 PC의 BL 가견적: `/home/h/Downloads/Airship_Gondola_BL_PA12_Quote.zip`

`build/`와 Downloads는 clone에 포함되지 않는다. 파일이 없거나 검증과 맞지 않으면
README 절차로 재생성·검증한다. STL/STEP은 같은 부품의 대체 형식이며 수량을 중복 합산하지 않는다.
선택 power 출력물도 baseline에 무조건 추가하지 않는다.

CAD를 보여 달라는 요청에는 저장된 FCStd를 GUI에서 연다. build 매크로는 재생성하고,
`preview`는 CAD를 저장한 뒤 자체 창을 닫으므로 단순 보기와 다르다.
FreeCAD 탐색·native Python 실행은 [runtime launcher](gondola/freecad_runtime.py)를 따른다.
시스템 Python에서 생략된 테스트나 CI portable 검사만으로 CAD 검증을 통과했다고 말하지 않는다.
문서 수정만으로 CAD를 다시 생성하거나 과거 검증 결과를 새 실행처럼 기록하지 않는다.
