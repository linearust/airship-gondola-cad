# 임시 인계문서 — airship-gondola-cad

**2026-09-30 작성. 다음 AI의 인수 확인 후 이 파일만 삭제한다.**
사용자가 이번 인계를 위해 별도로 요청한 일회성 문서다. 상시 지침은
[README.md](README.md)이며, 이 내용을 README나 다른 문서에 통째로 옮기지 않는다.
아래 수치는 인계 시점의 스냅샷이다. 이후 사용자 지시와 변경된 코드가 우선한다.

## 1. 지금 무엇이 완료되었는가

이 프로젝트는 실내 LTA 비행선의 곤돌라를 Python/FreeCAD로 생성한다.
설계 리비전은 **BL**, 상태는 **fit_prototype**, `production_released = false`다.
최근 형상 개선과 검증, 이어서 문서 정리가 완료되어 GitHub에 반영되었다.
진행 중인 CAD 수정이나 승인 대기 작업은 없다. 이번 요청은 **인계문서 작성만**이다.
인계 자체를 새로운 설계 변경이나 제조 승인 요청으로 해석하지 않는다.

| 항목 | 인계문서 작성 직전 확인한 상태 |
| --- | --- |
| 작업 경로 | `/home/h/cad/airship-gondola-cad` |
| 원격 | `https://github.com/linearust/airship-gondola-cad.git` |
| 작업 브랜치 | `codex/square-carriers` |
| 최근 설계 변경 | `3edb2fd483082aef84b3f098ea89132eb8deb20a` — 레일 단축·경량화 |
| 최근 문서 정리 | `15e2084bdbfba0dbd0023cf8424c6517fdc61f31` |
| 인계 작성 전 작업 트리 | 깨끗함 |

위 커밋은 이 문서가 추가되기 **전** 기준이다. 인계문서 추가 커밋을 별도로 만들면
HEAD가 달라지는 것이 정상이다. 기존 `main`과 작업 브랜치는 문서 정리 커밋까지
동일하게 push되어 있었다. 인수 시 원격 상태는 다시 확인한다.

## 2. 인수 직후 할 일

1. README와 이 문서를 읽고 `git status`, 최근 커밋, 원격 상태를 확인한다.
   사용자나 다른 AI의 변경·열린 FreeCAD의 미저장 작업을 덮어쓰지 않는다.
2. 저장소에서 `python3 -m gondola status`를 실행한다. 이는 FreeCAD 없이 현재 선택,
   범위, 수량, 미확정 인터페이스를 보여준다. 아래 요약보다 현재 코드의 결과를 우선한다.
3. [검증 기록](references/design_verification.json)의 source fingerprint 및 CAD/fixture
   해시를 실제 파일과 비교한다. 코드·파일이 다르면 이전 통과 기록을 현재 검증으로 쓰지 않는다.
4. 원본·설계·검증의 위치를 파악하고 인수 완료를 사용자에게 알린 뒤 **HANDOFF.md를 삭제**한다.
   영구적으로 필요한 새 결정만 해당 소스 계약 또는 원본 출처 기록에 반영한다.

간단한 읽기 전용 확인 예:

```sh
python3 - <<'PY'
import json
from pathlib import Path
from gondola.provenance import source_fingerprint, file_sha256
r = json.loads(Path('references/design_verification.json').read_text())
assert source_fingerprint() == r['source_fingerprint']
assert file_sha256(r['fixture']['path']) == r['fixture']['sha256']
p = Path('build/gondola.FCStd')
if p.exists():
    assert file_sha256(p) == r['cad_sha256']
    print('Source, fixture and saved CAD match the recorded execution.')
else:
    print('Generated CAD is absent; rebuild and validate before presenting it.')
PY
```

## 3. 사용자의 핵심 의도와 이미 정해진 경계

- 초경량 실내 비행선이다. 무게를 줄이되, 작은 감량을 위해 복잡한 형상·얇은 취약부·
  많은 볼트·특수 부품·조립 난도를 추가하는 것은 원하지 않는다. 약간 무거워져도
  단순하고 튼튼하며 검수·가공·교체가 쉬운 구조를 선호한다.
- 분리할 이유가 없는 것은 일체화한다. **두 서보와 입력 기어를 담은 교체 모듈과
  추진기 출력축/지지 프레임의 분리는 의도적**이므로 임의로 합치지 않는다.
- 기성 metric 부품을 우선하고 나사·너트 종류를 줄인다. 일반 기어 보어를 서보 스플라인에
  직접 맞는 것으로 취급하지 않는다. 모듈/보어 외 판매자별 치수 차이도 구분한다.
- 공차는 단순한 여유·짧은 슬롯·교체 부품으로 대응하되 작동 중 헐거움은 허용하지 않는다.
  조절 기능을 많이 넣는 것 자체가 목적은 아니다. 기존 설계를 유지하려고 더 나은 안을 배제하지 않는다.
- 레일은 기낭에 테이프로 붙인다. 별도 케이블타이 구멍이나 F-Mini 전용 장착판 등
  기존 구조로 대체할 수 있는 기능을 추가하지 않는다.
- 추진기, 배터리, FC와 주변 전자장비라는 세 질량 영역을 고려한다. 실제 CG 균형은 미검증이다.
  광학센서는 위치를 옮길 수 있어야 하고, 실제 수직 아래로 정렬하며 시야가 가려지지 않아야 한다.
- 범위는 곤돌라·두 주추진기·탑재부다. **fin 및 후방 yaw motor 하드웨어는 범위 밖**이다.
- 사용자는 Creallo를 기준으로 제작한다. PA12가 설계 기준이지만 **SLS/MJF·등급·후처리는
  미확정**이다. 출력 부품은 로컬/출력 방향의 각 축 모두 최대 340 mm 이내이며,
  업체 검토를 반영한 레일 테이프 부착부 두께는 최소 1.5 mm nominal이다.
- 이미 답변받은 구매·선택 사항을 다시 묻지 않는다. 과거의 “몇 분 이내 질문” 또는
  “자리를 비움”은 당시 작업 맥락이다. 새 작업의 범위·최신 지시는 그때 다시 판단한다.
- 과거 Notion 계획과 초기 BOM은 보조 자료다. 현재 CAD와 자동으로 동기화된 문서로
  취급하지 않는다. 최근 작업과 이번 인계에서는 Notion의 실시간 일치 여부를 확인하지 않았다.
- 사용자는 간결한 한국어 결과 보고를 선호한다. 기존에는 검토한 변경의 GitHub push를
  요청했으며 최근 작업도 실제 push 후 원격 커밋을 확인했다. 이후 지시가 있으면 그것을 우선한다.

## 4. 현재 형상과 최근 변경 — 과거안과 혼동하지 말 것

### 레일·배치

- 레일은 **300 mm**다. 340 mm는 현재 길이가 아니라 제조 크기 상한이다.
- 테이프 부착부는 **7쌍**, 45 mm 간격이다. 중심 X는 −135, −90, −45, 0, 45, 90, 135 mm.
  테이프 참조는 양쪽 합계 14개다. 이전 340 mm / 10쌍 / 36 mm 간격은 폐기되었다.
- 연속 베이스와 날개는 1.5 mm를 유지한다. T-head/슈의 맞춤과 기존 클램프 방식은 유지했다.
  테이프는 측면 날개 위에서 기낭으로 이어지며 중앙 주행면·flex gap을 덮지 않는다.
- 기본 레일 방향 위치: 추진기 X0, 배터리 X+90, FC X−54, 항법장비 X−140 mm.
  FC/항법 캐리어는 각각 Z축 180° 방향이다. 실제 객체의 placement를 확인한다.
- 배터리·FC·항법 캐리어는 동일한 64 mm 정사각형 계열 출력물이다.
  슬롯 배열은 프로젝트 인터페이스이며 **Holybro X500과 동일한 규격 또는 업계 공통
  브레드보드가 아니다**. 모든 슬롯/호스트에 모든 모듈을 동시에 설치할 수 있다는 뜻도 아니다.
  과거 기성 카본 어댑터 중심의 레일 재설계나 나일론 튜브 레일은 현재 채택한 안이 아니다.
- F-Mini는 항법 캐리어의 레일 쪽 면, 슈 바깥쪽을 사용한다. 별도 긴 radio plate는 없다.
- 항법 캐리어는 이전 X−158에서 안쪽으로 18 mm 옮겼다. FC와 데크 사이 간격은 22 mm.
  그 슈는 길이 18 mm이며 레일 끝 여유가 **명목상 1 mm**뿐이다. 이를 충분한 제조공차
  여유로 해석하지 말고 실제 끝단·전체 물림·곡면 슬라이딩을 확인해야 한다.
- FC는 가까운 날개 중심에서 9 mm 벗어나고, 슈와 날개는 7 mm 겹친다.
  지지·클램프가 모두 테이프 중심에 있다는 가정은 틀리다. 날개 사이 빈 길이는 31 mm다.
  접착력, 비틀림, 굽힘, 크리프와 실제 곡률은 아직 실물 검증 대상이다.
- 더 줄인 5/6쌍 레일이나 더 얇고 작은 캐리어도 검토했지만 추가 감량에 비해 지지나
  슬롯 주변 재료 여유가 줄어 이번에는 채택하지 않았다. 이를 영구 금지 규칙으로 보지는 않는다.

이번 BL 변경의 체적 기반 PA12 예상 출력물 질량은 약 **91.79 → 88.50 g**,
레일은 약 **19.40 → 16.11 g**이다. 1.01 g/cm³ 가정이며 테이프 감량은 제외한다.
이는 **실측값·전체 곤돌라 무게·비행체 무게가 아니다**. 현재 설치 출력물 16개,
모델링된 구매 하드웨어 70개라는 수량도 전체 구매 목록의 완전성을 뜻하지 않는다.

### 추진·기어·샤프트·베어링

- KST X06 두 개로 독립 벡터링한다. **48T가 입력, 16T가 출력**이다.
  선택된 Kailash 판매자 기어의 모듈은 0.5, 압력각 20°, 두 보어 모두 3 mm이다.
  nominal 중심거리 16 mm, 각도비 −3, 목표는 입력 ±60°에 출력 **bounded ±180°**다.
  무한 회전·슬립링·자동 wraparound는 설계하지 않았다. 부하 상태의 실제 끝점은 미검증이다.
- 현재 소스는 48/16만 지원한다. GUI 속성으로 임의 기어비를 고르는 범용 메커니즘이 아니다.
  다른 서보/비율에는 교체 입력 모듈을 다시 설계하고 검증해야 한다.
- 각도 3배 증폭은 이상적인 출력 토크를 1/3로 줄이며 손실은 별도다.
  입력 기어의 측력이 서보 출력축 지지에 전달되지만 허용 측하중은 확인되지 않았다.
- 양쪽 주추진기 회전축 중심 간격은 정확히 **150 mm**, 레일 접촉면부터 높이는 **50 mm**다.
- 현재 프로펠러는 Gemfan 1610 40 mm, 1.5 mm 보어 옵션이고 모터는 RS1102 10000KV다.
  현재 guard는 내경 46 / 외경 50 mm로 **50 mm 프로펠러용이 아니다**.
  향후 50 mm로 바꾸려면 여유 영역을 이용하는 별도 rotor/carrier 교체 설계가 필요하다.
- 축 재료 선택은 nominal Ø3 mm 304 봉이다. 출력 구동측 34 mm와 반대측 20 mm,
  입력 stub 18 mm가 각각 양쪽에 있다. flat 가공 위치·길이는 코드와 BOM을 따른다.
  이전 6061/미스미 샤프트 제안을 현재 구매 규격으로 되살리지 않는다.
- 이미 구매한 **generic 3×6×2.5 mm 베어링 4개**를 유지한다. 각 추진기를 두 개로
  지지하며 중심 간격은 70 mm다. ISC/NSK 자료는 비교 근거일 뿐 구매품 제조사나 등급이 아니다.
- 현재 베어링 고정은 Ø6.1 nominal 고정 원형 seat와 뒤 shoulder, 앞쪽의 분리 가능한
  keyed keeper다. keeper 한 개당 M2×6 + 일반 M2 너트 하나다. keeper는 프레임에
  닿도록 조이며 베어링을 압착해 유격을 없애는 구조가 아니다. nominal inward float는 0.5 mm다.
- 과거의 latch 고정이나 다규격 베어링 호환 구조가 아니다. 구매 spacer/push-on ring도 없고,
  입력축용 추가 베어링도 없다. 실제 외륜·실드·축 맞춤을 생산 조건의 쿠폰으로 확인한다.
- 기어 M3 무두나사의 길이·끝·돌출과 실제 공구 접근은 완전히 확정되지 않았으며,
  해당 나사 솔리드는 아직 모델링하지 않았다. 움직임 검증을 이 미모델링 나사까지
  포함한 실물 간섭 보증으로 확대하지 않는다.

### 서보혼 — 가장 혼동하기 쉬운 변경

이제 알리 금속혼 3종을 동시에 받는 과거 all-in-one 안이 아니다.
제조사가 제공한 **X06半臂1.STEP / 기본 플라스틱 half arm 1**을 양쪽에 사용한다.

- 원본 선택 STEP: [gondola/data/kst_x06_half_arm_1.step](gondola/data/kst_x06_half_arm_1.step).
  전체 수신 RAR와 출처·원본 이름·해시는 [제조사 기록](references/manufacturer/kst_x06_servo_horns_2026-09-28.json)에 있다.
  원본 바이트는 그대로 보존하고 loader는 좌표계만 변환한다.
- 조립용 혼 모델에서는 기존 Ø1 mm 구멍 중 중심 반경 6.8 / 13.2 mm의 두 개만
  Ø1.5 mm로 넓힌다. 임의 새 중심을 옮겨 그려 구멍을 뚫는 방식이 아니다.
  나머지 구멍과 spline 및 OEM 중앙 체결나사는 유지한다.
- 혼 하나당 뒤에서 M1.4×8 두 개, 앞 M1.4 너트 두 개를 사용한다.
  원래 플라스틱 구멍은 M1.6 나사홀이 아니다. OEM 중앙 나사의 나사산도 이 규격으로 추정하지 않는다.
- 어댑터는 가까운 Ø1.8 원형 구멍 + 먼 1.8×2.4 mm 짧은 radial slot,
  열린 root seat로 공차를 받아준다. 양쪽 체결 후에는 움직이지 않아야 한다.
  긴 슬롯만으로 축을 자동 중심맞춤시키거나 운전 중 헛돌게 만드는 설계가 아니다.
- 실제 spline seating, 혼과 케이스 간격, 편심, 플라스틱 가공 품질, 나사머리/너트 외형은
  미검증이다. 정확한 제조사 nominal CAD를 얻었다고 실제 조립 공차가 사라진 것은 아니다.
- 귀 고정 볼트를 혼 옆으로 무리하게 뽑는 과거 경로를 쓰지 않는다. 조립할 때 귀 볼트를
  먼저 넣고, 분해할 때 뒤 귀 너트를 풀되 귀 볼트는 서보에 남겨 전체 유닛과 함께 뺀다.
  자세한 순서는 `validation/horn_coupling.py`, `validation/servo_module.py` 및 해당 검사 결과를 따른다.

## 5. 전자장비·광학·선택 전원

| 항목 | 현재 선택과 범위 |
| --- | --- |
| FC | MicoAir H743V2 AIO **45A AM32**. 과거 35A Bluejay가 아님. **2S 구동은 사용자 확인 완료**. 정확한 revision/minimum voltage나 실제 전력 여유를 추정하지 않음 |
| FC 장착 | 보드 홀 25.5 mm pattern. 하부 배선 공간 8 mm를 계획에 반영했지만 받은 댐퍼의 눌린 높이·PCB 접촉면·최종 볼트 길이는 미확정 |
| 배터리 | Tattu 2S 450 mAh 75C XT30 long pack 기준. 실제 질량 미확정 |
| 항법 | 기본 P-AS, 같은 영역에서 MG-A01/M10 Ultra 또는 MG-F10-A로 교체. 동시 설치 전제가 아님 |
| 통신 | 기체 **LR24-F-Mini**, 지상 LR24-F. LR900-A는 제외 |
| 광학 | 기본 MTF-02P, MTF-01P 대체 가능. 한 개만 설치. 공통 adhesive tray 사용 |

광학센서는 별도 레일 없이 캐리어의 side slot에 붙는 foot + 수동 pitch head다.
기본 host는 배터리 캐리어의 +X 쪽, pitch 높이는 35 mm이다. pitch 한 축만 조절하고
roll 보정·자동 수평·추가 무게에 의한 자동 수직 안정화는 구현하지 않았다.
다른 host/edge로 옮길 수 있는 인터페이스지만 실제 장착 조합별 시야·간섭·분해 검증이 필요하다.

MG-F10-A는 직결 및 분리 SMA 안테나 배치를 고려한다. 현재 곤돌라 패드에서 직결
안테나는 기낭 반대 방향, 즉 아래를 향하므로 기계적 공간 통과가 GPS 수신 적합성을
뜻하지 않는다. 실외 수신을 위한 위쪽 원격 안테나의 실제 위치·케이블·고정은 미모델링이다.

현재 기본 전원은 `BATTERY`다. 선택안은 `contracts/power_options.py`를 따른다:

- `TETHER_BEC_SVPDB`: 외부 24 V → **BEC12S-PRO 한 개를 8 V로 설정** →
  FC/주추진 전원과 SVPDB 입력으로 분기 → **SVPDB-8S 한 개의 5 V**로 서보 전원 공급.
  BEC 두 개나 BEC 한 개의 독립 8 V/5.2 V 동시 출력 구조가 아니다.
- `BATTERY_SVPDB`: 2S 입력에서 선택적으로 SVPDB를 사용한다.
- 별도 서보 전원을 쓰면 FC 5 V와 SVPDB 5 V의 **양극 출력을 묶지 않는다**.
  GND와 각 서보 신호는 공유/유지한다. 상위 BEC 전류 한도를 모든 하위 부하가 공유한다.
- direct tether 배치는 비운 배터리 캐리어를 재사용하므로 추가 출력물이 없다.
  이 조합의 광학 foot는 **항법 캐리어 −X side**로 옮긴다. FC로 옮기는 과거 설명은 잘못되었다.
- `PORTAL`은 선택형 추가 플랫폼이며 출력물 1개와 M2 체결 2쌍이 추가된다.
  baseline에 무조건 포함하거나 direct 구성과 중복 구매/출력하지 않는다.
- 배터리/계류는 여기서는 선택 관계다. 자동 전환·병렬 연결·충전 회로는 설계하지 않았다.
  계류선 정격 고정점이나 완성 하네스, 열·전류·전압 검증 역시 완료하지 않았다.

## 6. 아직 실제로 확인해야 하는 것

정확한 전체 목록은 `release_status()`가 기준이다. 특히 다음을 놓치지 않는다.

- 생산 소재·공정·방향에 맞춘 레일/슈와 베어링 seat/keeper의 실물 맞춤.
  직선 쿠폰 통과는 곡면 레일 전체 슬라이딩·접착·하중 수명을 보증하지 않는다.
- 1 mm 레일 끝 여유와 FC의 비중앙 지지, 테이프 박리/비틀림 및 PA12 크리프.
- 혼/입력축의 편심과 체결, 실제 servo loaded travel, gear backlash와 고정,
  shaft journals/실드/외륜 간섭 및 출력축 axial stop.
- ±180° 회전 중 모터선 loop, 실제 커넥터 XYZ·굽힘·strain relief.
  CAD 예약 공간은 실제 연결 하네스의 증명이 아니다.
- FC/P-AS spacer·damper·나사 stack과 OEM motor/중앙 horn screw 일부는
  완전히 규격화/모델링되지 않았다. 구매 BOM 전체가 완성됐다고 말하지 않는다.
- XR2 receiver는 카트에 있지만 설치 형상/하네스는 현재 CAD에 반영되지 않았다.
  P-AS 기본안의 heading reference, GPS compass 배선·보정·간섭도 별도 통합 사항이다.
- 실측 질량/CG/관성, 기낭·헬륨·전체 CV, 추력·전력·열·전원 안정성·비행 적합성.
  unknown/null 값을 0으로 바꾸거나 외형 중심을 실제 무게중심으로 쓰지 않는다.

## 7. 검증·산출물의 정확한 상태

BL에서 FreeCAD native 테스트 **577개, 실패/오류/생략 0개**를 통과했다.
본체·기구·레일·전자장비·선택전원·기준 fixture의 검증 6개가 통과했다.
Blender 검증은 6개 scene, 1,349 sampled frames, 108,266 matrix checks,
불일치 0건이다. 이는 **규정한 강체 운동**이며 동역학/유연 배선/구조 해석이 아니다.
문서 정리 이후 CAD·소스·fixture·상세 검증 archive가 동일함을 다시 확인했다.
인계문서 작성 때문에 전체 CAD 테스트를 새로 실행한 것은 아니다.

[design_verification.json](references/design_verification.json)은 과거 실행의
파일/소스 결합 기록이다. [design_checks.json.gz](references/design_checks.json.gz)에
상세 결과와 독립 형상/제어 비교 근거가 있고, [fixture 승인 기록](tests/fixtures/review.json)이
기준 CAD 교체 이유를 남긴다. 이 기계 검증 자료는 폐기 대상 사람이 보는 검수표와 다르다.
압축 archive 내 이전 경로·임시 스크립트는 당시 실행 근거이지 현재 문서나 실행 명령이 아니다.

`source_fingerprint()`의 범위는 `gondola`의 Python, 루트 `.FCMacro`, `gondola/data`다.
**tests·tools·문서는 이 fingerprint에 포함되지 않는다.** 이들도 바뀌었다면 별도 Git diff와
실행 당시 파일 해시/결과를 확인해야 한다. fingerprint 일치만으로 변경된 테스트나 exporter가
과거에 실행·검증되었다고 주장하지 않는다. 상세 archive에는 실행 당시 Python 파일 해시도 있다.

인계 작성 시 재확인한 식별값:

```text
source fingerprint
5a252cb9a488a597a9c02ca1d8d36ac74b5ad38060857122d0f121121af5e9b6
build/gondola.FCStd
526d46d7a03463bd6652a7876cdd39119ad24e9b6b3d6e303ef53b3249abd85c
tests/fixtures/geometry.FCStd
13afa4689da8d6645d4db1dd6a1afc2860dd7f65a599d5043e89a650cdd7637f
build/gondola_print_parts.zip
a355be9a388756868af0468a83be0ad8d37f26bf3dcd7f5a3386ebf174fedf9f
```

| 산출물 | 현재 로컬 경로 및 의미 |
| --- | --- |
| FreeCAD assembly | `build/gondola.FCStd` |
| 현재 보기 | `build/gondola_preview.png` 등 affected detail 이미지 |
| 출력물·BOM·검증 ZIP | `build/gondola_print_parts.zip` |
| 개별 출력물/수량 | `build/gondola_print_parts/print_manifest.json` 및 같은 디렉토리의 STL/STEP |
| 시뮬레이션 기하 입력 | `build/simulation_parameters.json` |
| Blender | `build/blender_review/cad_review.blend` 및 `verification.json` |
| Creallo 가견적 | `/home/h/Downloads/Airship_Gondola_BL_PA12_Quote.zip` 및 같은 이름의 폴더 |

견적 ZIP SHA256은 `c9b619a5aa81454266e2c6389e3cc9e6986b7f104232b100a240c421f8ac061c`다.
이 ZIP은 설치 출력물 16개, fit coupon 4개와 별도 선택 power part 1개를 구분한다.
동일 part의 STL/STEP은 대체 파일 형식이며 둘 다 수량으로 합산하지 않는다.
견적 요청용이지 생산 승인·발주 완료 증거가 아니다. 예전 BK/BI 견적은 현재 설계와 다르다.

**build와 Downloads는 Git에 포함되지 않는다.** 같은 PC/디렉토리를 인계하면 존재하지만,
새 clone에서 존재한다고 가정하지 않는다. 이 경우 소스로 재생성하고 검증한다.
검증 뒤 CAD를 수동 저장하면 바이트가 바뀔 수 있으므로 재확인 없이 이전 결과를 붙이지 않는다.

시뮬레이션 좌표의 특별 주의점: native CAD는 CV/CG나 FRD가 아니다. 현재 native pivot
Y는 +75.1/−74.9 mm이며 공통 +0.1 mm 배치는 실제 clamp seating에서 온다.
쌍의 중점으로 옮긴 `propulsion_reference`에서는 정확히 ±75 mm다.
이를 native 좌표를 임의 반올림할 이유로 쓰지 않는다. 필요한 좌표 변환은 exporter 결과를 따른다.

## 8. 어디를 수정·검토해야 하는가

| 주제 | 소스/근거 |
| --- | --- |
| 전체 선택·제조·배치·미확정점 | [contracts/design.py](gondola/contracts/design.py), `python3 -m gondola status` |
| 실제 기어 입력값 | [contracts/drive.py](gondola/contracts/drive.py), [판매자 발췌](references/kailash_gears_selected_evidence.md) |
| OEM 혼 원본/가공/어댑터 | [parts/oem_servo_horn.py](gondola/parts/oem_servo_horn.py), [contracts/servo_horns.py](gondola/contracts/servo_horns.py), [parts/servo_coupling.py](gondola/parts/servo_coupling.py) |
| 레일·마운트 | [parts/rail.py](gondola/parts/rail.py), `mounting_plate.py`, `mounting_slots.py`, `equipment_mounts.py` |
| 프레임·베어링·서보 bridge | [parts/propulsion.py](gondola/parts/propulsion.py), [parts/bearing_retention.py](gondola/parts/bearing_retention.py), [parts/servo_bridge.py](gondola/parts/servo_bridge.py) |
| 장비/배선/광학 | `contracts/equipment_interfaces.py`, `equipment_options.py`, `optical_sensors.py`; `parts/optical_interface.py`, `propulsion_wiring.py`, `wiring_reserves.py` |
| 전원 선택안 | [contracts/power_options.py](gondola/contracts/power_options.py), [power_export.py](gondola/power_export.py), `parts/power_mount.py` |
| 저장 assembly 및 placement | [assembly.py](gondola/assembly.py), [cad.py](gondola/cad.py) |
| 원본과 구매 선택 | [sources.json](references/sources.json), [최종 카트](references/cart_selected_parts_2026-09-29.json) |
| 생성·검증·패키징 | [cli.py](gondola/cli.py), [validation](gondola/validation/), [bundle.py](gondola/bundle.py), [tests](tests/) |

표에서 생략한 파일은 직전에 적은 동일 디렉토리 기준이다. 코드 값은 설계값인지,
실제 자료에서 온 값인지, 공간 예약인지 해당 주석/계약의 범위를 함께 읽는다.

## 9. 실행·표시·수정 시의 주의점

이 PC에서 확인한 실행 파일:

- FreeCAD: `/home/h/Applications/FreeCAD_1.1.3-Linux-x86_64-py311.AppImage`
- Blender: `/home/h/Applications/blender-5.2.2-linux-x64/blender`

다른 환경에서는 [runtime launcher](gondola/freecad_runtime.py)의 탐색 또는
`FREECAD_APPIMAGE` 설정을 사용한다. `/tmp/.mount_*` 경로는 프로세스 수명에 종속되므로
하드코딩하지 않는다. 시스템 Python만으로는 FreeCAD geometry 테스트가 생략될 수 있다.
CI의 portable 검사 통과는 native CAD 검사 통과와 다르다.

현재 CAD를 **보여 달라**는 요청에는 저장된 `build/gondola.FCStd`를 FreeCAD GUI에서 연다.
`build_gondola.FCMacro`는 새로 생성/저장하는 매크로이며 단순 보기 명령이 아니다.
`python3 -m gondola preview`도 표시 속성을 저장하고 자체 GUI 프로세스를 종료하므로
사용자에게 계속 열린 CAD 창을 보여주는 명령과 구분한다.

설계 변경 시 README의 절차를 따른다. source를 고정한 뒤 순서는
`build → preview → compare → validate → bundle`이다. preview가 CAD를 저장하므로
파일 해시에 묶인 검증보다 먼저 실행한다. 이후 Blender와 simulation을 갱신한다.
`--output-dir PATH`는 gondola subcommand **앞**에 쓰고 전 단계에서 동일하게 유지한다.
실패한 단계나 source 변경이 있으면 이전 보고서를 재사용해 통과한 것으로 만들지 않는다.

기준 fixture를 바꾸려면 변경 의도에 맞는 독립적인 old/new 형상·placement·controls·
metadata 검토가 먼저 필요하다. `config.py`의 해시만 바꿔 compare를 통과시키면 안 된다.
BL에서는 독립 비교로 레일과 tape references, 항법 모듈 이동만 의도된 차이임을 검토한 뒤
fixture를 승격했다. 이 근거가 현재 압축 archive에 남아 있다.

문서만 바뀌면 링크·JSON·출처 해시·Git diff 검사를 하고, CAD를 재생성하지 않는다.
코드 변경이면 Ruff와 영향 테스트, CAD release이면 native 세 폴더 전체를 생략 없이 실행한다.
다음은 저장소 루트에서 native tests를 실행하는 방법이며 **시간이 오래 걸릴 수 있다**:

```sh
python3 - <<'PY'
import os
import subprocess
from pathlib import Path
from gondola.freecad_runtime import locate_appimage, mounted_appimage
root = Path.cwd()
runner = '''import sys, unittest
suite = unittest.defaultTestLoader.discover(sys.argv[1])
r = unittest.TextTestRunner(verbosity=2).run(suite)
if not r.testsRun or not r.wasSuccessful() or r.skipped or r.expectedFailures:
    raise SystemExit(1)
'''
with mounted_appimage(locate_appimage()) as mount:
    env = os.environ.copy()
    env['PYTHONPATH'] = os.pathsep.join((str(root), str(mount / 'usr/lib')))
    env['QT_QPA_PLATFORM'] = 'offscreen'
    for folder in ('tests', 'tools/blender_review', 'tools/simulation'):
        subprocess.run([str(mount / 'AppRun'), 'python', '-c', runner, folder],
                       cwd=root, env=env, check=True)
PY
```

검증은 수십 분 걸릴 수 있다. 최근 실행에서는 병렬 native 테스트 약 14분,
최종 validate 약 21분이었으나 다음 환경의 시간 보장은 아니다. 실행 로그·종료 코드와
검증 전후 source/CAD 해시를 확인하고, 진행 중 source를 바꾸지 않는다.
`/tmp/bl-*` 등의 당시 작업 스크립트는 영구 도구가 아니므로 인수 환경에 있다고 가정하지 않는다.

## 10. 직전 문서 정리의 의도

사용자는 사람이 읽는 검수표를 더 이상 쓰지 않으며, 중복 설명의 정합성·노후화 위험을
줄이라고 했다. 이에 설명 Markdown 16개를 README 포함 4개로 줄였고,
파생 베어링 검수 이미지 및 `references/simulation_parameters.json` 중복본도 삭제했다.
시뮬레이션 exporter와 실제 build 산출물은 유지했다.

실제 삭제 문서에서는 광학센서를 FC/항법 중 어디에 옮기는지 상충했고,
portal 분해의 이전 23 mm / X−181 값도 남아 있었다. 이를 수치표로 또 복제하지 말고
현재 계약·생성된 검사 결과를 사용한다. BL의 상세 portal 경로 근거는 검증 archive에 있다.

- [sources.json](references/sources.json)은 보존된 원본 그림/PDF 35개의 출처·해시와
  별도 카트/KST/제조 피드백 기록을 연결한다. URL만 남기고 원본을 버리지 않았다.
- 최종 카트의 38개 관련 항목은 제목·옵션·수량·판매자·링크의 원문을 보존했다.
  중복 CAD 해석은 제거했다. 카트는 결제·수령·실물 공차나 필요한 모든 물품의 증명이 아니다.
- 혼/마운트 설명 파일 두 개는 현재 계약 메타데이터에서 참조하므로 짧은 source map으로
  남겼다. 기어 문서는 원본 48T 페이지 대신 남아 있는 판매자 발췌 근거다.
- `design_verification.json`은 문서 해시 목록을 없애고 과거 CAD 실행의 불변 근거를
  가리키도록 줄였다. 이후 문서가 바뀌었다고 이전 CAD 테스트를 새로 실행했다고 주장하지 않는다.
- 삭제된 장황한 문서나 오래된 수치를 복원하지 않는다. 이 HANDOFF도 예외적으로 요청된
  일회성 설명이며, **인수 후 삭제하고 상시 문서로 유지하지 않는다**.

인수 시점에 새 사용자의 작업 요청이 없다면 현재 상태를 이해했다고 알리면 된다.
실물 검증이 남아 있다는 이유만으로 임의로 구매품을 바꾸거나 CAD를 다시 설계하지 않는다.
