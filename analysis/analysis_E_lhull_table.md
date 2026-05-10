# lhull (신조 시 최대 내구도) 테이블 — 위치 재분석

## 결론

**lhull 단일 25-원소 ROM 테이블은 존재하지 않을 가능성이 매우 높음.**
이전 추정 `MAIN.EXE @ 0x424AE` (idx 16 = 20) 는 사용자 검증 (SHIP=81) 과 모순.

## 강한 증거

### 1. HORIEDIT.H 데이터 모델
`Ship4` ROM (12 byte × 25), `Ship5` ROM (25 byte × 25) 어디에도 **lhull 필드 없음**.

```
Ship4 = lrudder lsail lcrew dcrew capacity lnowea none[5]
```
lhull 은 오직 `Ship1` 의 4번째 byte (per-instance) 로만 존재.

### 2. HORIEDIT.C `org_ship_edit()` 의 7개 항목
lrudder/lsail/lcrew/dcrew/capacity/lnowea/name 만 편집. **lhull 없음**.

### 3. KOUKAI2.DAT 슬롯간 cross-correlation
같은 함선 종(SHIP) 인스턴스에 lhull 값 50/60/80/81/90 다양하게 등장 → ROM-fixed 라면 단일 값만 나와야 함.

### 4. MAIN.EXE 검색 결과
- uint16 LE × 25 idx16=81 + lhull 분포 만족: **0개**
- uint8 × 25 idx16=81 + lhull 분포 만족 단일 명료한 위치: 없음 (380개 후보 모두 x86 코드 또는 그래픽)

### 5. `0x42100~0x42800` 영역 추정
"항구 카탈로그(port shipyard catalog)" 영역으로 추정. 한 항구당 약 128 byte 블록, 각 블록 시작에 ship-index 리스트 + 0xFF 종결 마커.

## 0x424AE 의 정체 (한 줄 추정)

idx16=20, idx22(CHEO)=105, idx24(GWAN)=250 — 함선 크기 분포와 상관 있음. **chull(현재 선체 HP 신조 시작값)**, **신조 base 가격**, 또는 **항구 카탈로그의 한 stat 컬럼** 가능성.

## 가능성 있는 추가 후보 (실험 검증 필요)

| 위치 | idx16 | 차이 | 25개 값 |
|---|---|---|---|
| **MAIN.EXE `0x4252A`** | **82** | +1 | `[25,70,30,20,15,85,50,10,15,25,30,50,37,52,12,25,82,88,18,68,67,100,270,110,95]` |
| **MAIN.EXE `0x425AA`** | **80** | -1 | `[20,10,16,12,10,65,45,7,55,15,35,6,28,55,8,10,80,80,20,80,70,60,120,40,75]` |

두 후보 모두 0x424AE 와 인접(~125 byte 차이) — 동일 카탈로그의 다른 stat 컬럼일 가능성. 81 ≠ 82/80 인 것은 **항구별 lhull 차등화** 또는 **사용자 메모리 부정확** 가능성.

## 권장 코드 수정

### `horiedit_py/data/game.py` (신규 — 데이터 레이어)
```python
# lhull 은 horiedit.h Ship4 에 없고, KOUKAI2 슬롯 분석 결과 단일 글로벌 ROM
# 테이블로 보기 어렵다 (analysis_E_lhull_table.md 참조).
MAINEXE_LHULL_TABLE_ESTIMATED = None  # 미확인
```

### GUI
"신조 시 최대 내구도" 항목은 **비활성** 또는 **"위치 미확인 — analysis_E 참조"** 로 표시.

## 검증 단계 (사용자/추가 분석)

1. **DOSBox + IDA Free 디스어셈블** — 신조 함수 cross-reference. 사용자가 SHIP 신조 메뉴에서 81 보는 시점에 메모리 watchpoint → 81 을 읽는 메모리 주소 확인.
2. **DOSBox 메모리 덤프 diff** — 신조 메뉴 진입 전후 RAM diff → 81 등장 위치 좁히기.
3. **항구별 lhull 가설** — 사용자가 다른 항구에서 SHIP 신조 → lhull 변동 여부 확인.
4. **0x4252A / 0x425AA 직접 변경 실험** — idx 16 값 변경 후 게임 실행 → 반영 확인.

## 분석 도구

`analysis/find_lhull_table.py` ~ `find_lhull_table19.py` (19개 검색 스크립트). `.gitignore` 에 `analysis/find_*.py` 패턴으로 추적 제외됨.
