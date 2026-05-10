# 함선 record 구조 — 확정

## 결론 (한 줄)

함선당 **12 byte record × 25** 가 `MAIN.EXE @ 0x0407D8` 와 `KOUKAI2.DAT 슬롯N + 0x528F` 에 존재. 사용자 검증 7-point 모두 100% 일치 — **확정**.

- **kogyo (요구공업치)**: 각 record 의 +0 (u8, 표시 = 저장 × 10)
- **lhull (최대 내구도)**: 각 record 의 +1 (u8 직접)

이 record 는 horiedit.h `ship4_addr = 0x5291` 보다 **2 byte 앞에서 시작**. horiedit.h 의 Ship4 정의는 **off-by-2** 였음.

## Record 레이아웃 (12 byte)

| offset | size | 필드 | 비고 |
|---|---|---|---|
| +0 | 1 | `kogyo_stored` | 요구공업치. **저장값 × 10 = 표시값** |
| +1 | 1 | `lhull` | 최대 내구도 (u8 직접) |
| +2 | 1 | `lrudder` | 선회력 (= 기존 Ship4.lrudder) |
| +3 | 1 | `lsail` | 추진력 (= 기존 Ship4.lsail) |
| +4 | 1 | `lcrew_stored` | 최대 승무원 / 10 (= 기존 Ship4.lcrew) |
| +5 | 1 | `dcrew` | 필요 승무원 |
| +6 | 2 | `capacity` | u16 LE 적재량 |
| +8 | 1 | `lnowea` | 최대 무기수 |
| +9 | 3 | `none[3]` | 보존 |

기존 `Ship4` (12 byte, +2 부터 시작 = lrudder ~ none[5]) 의 마지막 2 byte 가 실제로는 **다음 함선의 [kogyo, lhull]**. read-modify-write 시 보존 필요.

## 7-point 검증

| idx | 코드 | kogyo (계산) | lhull | 사용자 일치 |
|---|---|---|---|---|
| 11 | JEBE | 500 | 70 | ✓ |
| 12 | PANE | 550 | 40 | ✓ |
| 13 | SLOO | 850 | 50 | ✓ |
| 14 | PREG | 1000 | 80 | ✓ |
| 15 | BAG | 1000 | 90 | ✓ |
| 16 | SHIP | 1000 | 90 | ✓ |
| 17 | JUNK | 300 | 80 | ✓ |

mismatch: **0 / 7**

## 위치 (확정)

| 데이터 | 위치 |
|---|---|
| MAIN.EXE record ROM | **`0x0407D8`** (12 × 25 = 300 byte) |
| KOUKAI2.DAT 슬롯 N | **N × 33340 + `0x528F`** |

DAT 슬롯별 절대 offset:
- slot 0: `0x528F`, slot 1: `0x015707`, slot 2: `0x025B7F`, slot 3: `0x02DDBB`,
- slot 4: `0x035FF7`, slot 5: `0x03E233`, slot 6: `0x04646F`, slot 7: `0x04E6AB`

## 25개 함선 전체 record 값 (slot 0 / MAIN.EXE ROM 동일)

| idx | code | kogyo | lhull | lrudder | lsail | lcrew(×10) | dcrew | capacity | lnowea | none[3] |
|---|---|---|---|---|---|---|---|---|---|---|
| 0 | BALS | 100 | 30 | 70 | 80 | 20 | 5 | 50 | 10 | 04 78 00 |
| 1 | HANJ | 100 | 20 | 65 | 85 | 20 | 5 | 60 | 10 | 04 82 00 |
| 2 | DAWO | 300 | 30 | 90 | 75 | 20 | 5 | 70 | 15 | 04 B4 00 |
| 3 | BUS | 700 | 70 | 50 | 60 | 200 | 50 | 500 | 40 | 00 D0 07 |
| 4 | TARE | 200 | 20 | 70 | 95 | 20 | 5 | 80 | 15 | 04 8C 00 |
| 5 | RATI | 200 | 30 | 90 | 75 | 40 | 10 | 120 | 20 | 05 F0 00 |
| 6 | REDO | 200 | 30 | 70 | 90 | 40 | 10 | 120 | 20 | 04 F0 00 |
| 7 | BRIG | 400 | 40 | 90 | 70 | 60 | 15 | 180 | 20 | 05 E8 03 |
| 8 | NAO | 500 | 50 | 65 | 85 | 120 | 25 | 450 | 40 | 02 B8 0B |
| 9 | KARA | 600 | 50 | 60 | 80 | 160 | 30 | 600 | 50 | 02 A0 0F |
| 10 | GAL | 800 | 80 | 60 | 65 | 200 | 45 | 800 | 70 | 00 70 17 |
| **11** | **JEBE** | **500** | **70** | 80 | 70 | 300 | 25 | 600 | 40 | 03 30 11 |
| **12** | **PANE** | **550** | **40** | 95 | 85 | 60 | 5 | 150 | 20 | 05 58 02 |
| **13** | **SLOO** | **850** | **50** | 95 | 85 | 60 | 5 | 250 | 40 | 05 40 06 |
| **14** | **PREG** | **1000** | **80** | 60 | 85 | 300 | 20 | 650 | 70 | 04 80 57 |
| **15** | **BAG** | **1000** | **90** | 50 | 65 | 450 | 40 | 1000 | 120 | 02 30 75 |
| **16** | **SHIP** | **1000** | **90** | 50 | 65 | 500 | 45 | 1200 | 150 | 02 00 7D |
| **17** | **JUNK** | **300** | **80** | 80 | 70 | 100 | 25 | 500 | 40 | 03 40 06 |
| 18 | LGAL | 100 | 40 | 100 | 85 | 20 | 5 | 120 | 10 | 05 8C 00 |
| 19 | PGAL | 400 | 80 | 75 | 80 | 200 | 40 | 500 | 30 | 01 48 0D |
| 20 | BGAL | 500 | 90 | 70 | 70 | 400 | 60 | 950 | 50 | 01 00 19 |
| 21 | RA | 600 | 60 | 95 | 100 | 250 | 30 | 450 | 40 | 03 A0 0F |
| 22 | CHEO | 1000 | 90 | 80 | 85 | 300 | 45 | 1100 | 100 | 02 B0 36 |
| 23 | AN | 400 | 60 | 95 | 95 | 200 | 20 | 500 | 40 | 02 78 05 |
| 24 | GWAN | 200 | 30 | 100 | 100 | 60 | 10 | 250 | 20 | 05 C8 00 |

## 슬롯간 비교

MAIN.EXE record ROM = canonical, KOUKAI2.DAT 슬롯 = 게임 시작 시 복사된 사본:
- 슬롯 0, 4, 5, 6, 7, 8: ROM 과 byte-level identical
- 슬롯 1, 2, 3, 9: SHIP record byte 일부 변경 (사용자가 게임 진행 중 수정)

## 폐기되는 이전 추정값

| 이전 추정 | 출처 | 정정 |
|---|---|---|
| `MAINEXE_KOGYO_TABLE_ESTIMATED = 0x42722` | analysis_C | 폐기 — 항구 카탈로그의 한 stat 컬럼 |
| `KOGYO_OFFSET_IN_SLOT = 0x06FEB` | analysis_D | 폐기 — 해당 위치 값 ×10 ≠ 사용자 검증 |
| `MAINEXE_LHULL_TABLE_ESTIMATED = 0x424AE` | analysis_C | 폐기 |
| `MAINEXE_LHULL_CANDIDATE = 0x4252A` | analysis_E | 폐기 |
| `MAINEXE_SHIP4_ROM = 0x40871` | analysis_C | 폐기 — 정정: `0x0407DA` (= 0x0407D8 + 2, lrudder 시작) |
| `MAINEXE_SHIP5_ROM = 0x405FD` | analysis_C | 폐기 — 정정: `0x040566` (analysis_F) |

## Python 구현 가이드

### `data/game.py` 추가
```python
MAINEXE_SHIP_RECORD_ROM = 0x0407D8
SHIP_RECORD_OFFSET_IN_SLOT = 0x528F
SHIP_RECORD_SIZE = 12

# (기존 폐기)
# MAINEXE_KOGYO_TABLE_ESTIMATED, KOGYO_OFFSET_IN_SLOT, MAINEXE_LHULL_*

def load_record(state, ship_type) -> bytes:
    """슬롯 N 의 함선 record 12 byte (raw)."""
    off = state.page + SHIP_RECORD_OFFSET_IN_SLOT + ship_type * SHIP_RECORD_SIZE
    return state.read(off, SHIP_RECORD_SIZE)

def save_record_kogyo(state, ship_type, kogyo_stored):
    """record 의 +0 byte (kogyo) 만 갱신."""
    off = state.page + SHIP_RECORD_OFFSET_IN_SLOT + ship_type * SHIP_RECORD_SIZE
    state.write(off, bytes([kogyo_stored & 0xFF]))

def save_record_lhull(state, ship_type, lhull):
    """record 의 +1 byte (lhull) 만 갱신."""
    off = state.page + SHIP_RECORD_OFFSET_IN_SLOT + ship_type * SHIP_RECORD_SIZE + 1
    state.write(off, bytes([lhull & 0xFF]))

# MAIN.EXE ROM 도 같은 방식 (record 시작 0x0407D8)
```

### GUI 변경

`ship_tab.py` 의 "원래 함선 정보" 폼에 두 필드 추가:
- 등장공업치 (kogyo, ×10 표시)
- 최대 내구도 (lhull, u8 직접)

`settings_tab.py` 의 등장공업치 메뉴 (analysis_D 추정 위치 기반) → **제거 또는 비활성**.

## 분석 스크립트

- `analysis/find_record_structure.py` (1차)
- `analysis/verify_hit_and_extend.py` (검증·확장)
- `analysis/verify_full.py` (전체 25 + 슬롯 비교)
