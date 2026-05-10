# 선박 가격 + 선박 분류 — 위치 분석 (record 내부)

## 결론

가격은 **별도 테이블이 아니라 함선 record 내 +10..+11** (uint16 LE, ×10 스케일) 에 있다.
사용자 5-point 검증 100% 일치 — **확정**.

추가로 record **+9** byte 는 **선박 분류** (0..5 의 6가지) 임을 확인.

따라서 analysis_G 의 `none[3]` 은 사실:
- **+9** (1 byte) = ship_type / hull family
- **+10..+11** (2 byte) = price_stored (×10 표시)

→ record 12 byte 의 모든 byte 가 의미 있음. unknown 영역 0.

## 정정된 record 레이아웃 (12 byte, 최종)

| offset | size | 필드 | 비고 |
|---|---|---|---|
| +0 | 1 | kogyo_stored | u8, ×10 표시 (요구 공업) |
| +1 | 1 | lhull | u8 직접 (최대 내구도) |
| +2 | 1 | lrudder | u8 (선회력) |
| +3 | 1 | lsail | u8 (추진력) |
| +4 | 1 | lcrew_stored | u8, ×10 표시 (최대 선원) |
| +5 | 1 | dcrew | u8 (필요 선원) |
| +6 | 2 | capacity | u16 LE (최대 적재량) |
| +8 | 1 | lnowea | u8 (최대 포문수) |
| **+9** | **1** | **ship_class** | **u8 분류 0..5 (선박 family)** |
| **+10** | **2** | **price_stored** | **u16 LE, ×10 표시 (선박 가격)** |

## 위치 (확정)

| 데이터 | 위치 |
|---|---|
| MAIN.EXE 가격 byte | `0x0407E2` (= record ROM `0x0407D8` + 10) |
| KOUKAI2.DAT 슬롯 N | `N × 33340 + 0x5299` (= 슬롯 record `0x528F` + 10) |
| MAIN.EXE 분류 byte | `0x0407E1` (= record ROM `0x0407D8` + 9) |
| KOUKAI2.DAT 슬롯 N 분류 | `N × 33340 + 0x5298` (= 슬롯 record `0x528F` + 9) |

## 25개 함선 가격 + 분류 표

| idx | code | 분류 (+9) | 가격 stored | 가격 표시 | 검증 |
|---|---|---|---|---|---|
| 0 | BALS | 4 | 120 | 1,200 | ✓ |
| 1 | HANJ | 4 | 130 | 1,300 | |
| 2 | DAWO | 4 | 180 | 1,800 | ✓ |
| 3 | BUS | 0 | 2,000 | 20,000 | |
| 4 | TARE | 4 | 140 | 1,400 | |
| 5 | RATI | 5 | 240 | 2,400 | |
| 6 | REDO | 4 | 240 | 2,400 | |
| 7 | BRIG | 5 | 1,000 | 10,000 | |
| 8 | NAO | 2 | 3,000 | 30,000 | |
| 9 | KARA | 2 | 4,000 | 40,000 | |
| 10 | GAL | 0 | 6,000 | 60,000 | |
| 11 | JEBE | 3 | 4,400 | 44,000 | ✓ |
| 12 | PANE | 5 | 600 | 6,000 | |
| 13 | SLOO | 5 | 1,600 | 16,000 | |
| 14 | PREG | 4 | 22,400 | 224,000 | |
| 15 | BAG | 2 | 30,000 | 300,000 | |
| 16 | SHIP | 2 | 32,000 | 320,000 | ✓ |
| 17 | JUNK | 3 | 1,600 | 16,000 | |
| 18 | LGAL | 1 | 140 | 1,400 | |
| 19 | PGAL | 1 | 3,400 | 34,000 | |
| 20 | BGAL | 1 | 6,400 | 64,000 | |
| 21 | RA | 3 | 4,000 | 40,000 | |
| 22 | CHEO | 2 | 14,000 | 140,000 | ✓ |
| 23 | AN | 2 | 1,400 | 14,000 | |
| 24 | GWAN | 5 | 200 | 2,000 | |

mismatch: **0 / 5**

## 분류 (+9) 추정 의미

25개 함선의 +9 byte 가 0..5 의 6 가지로 분리. 가격대/등급과 강한 상관:

| 분류 | 함선 | 추측 |
|---|---|---|
| 0 | BUS, GAL | 대형 화물선 |
| 1 | PGAL, BGAL, LGAL | 대형 갤리(이베리아·지중해 군용) |
| 2 | NAO, KARA, BAG, SHIP, CHEO, AN | 대양 항해/전투 대형선 |
| 3 | JEBE, JUNK, RA | 지역 전통선 (지중해/아시아) |
| 4 | BALS, HANJ, DAWO, TARE, REDO, PREG | 소형 다우 계열 (작은 무역선) |
| 5 | RATI, BRIG, PANE, SLOO, GWAN | 소형 쾌속선 |

게임 내부에서 항구 카탈로그 분류, 그래픽 그룹, 함대 제약 조건 등에 쓰일 것으로 추정.

## Python 구현 가이드 (`data/game.py`)

```python
PRICE_OFFSET_IN_RECORD = 10
PRICE_SCALE = 10  # stored * 10 = 표시 가격
SHIP_CLASS_OFFSET_IN_RECORD = 9

def load_price(state, ship_type: int) -> int:
    """슬롯 record +10..+11 의 u16 LE × 10 = 표시 가격."""
    off = (state.page + SHIP_RECORD_OFFSET_IN_SLOT
           + ship_type * SHIP_RECORD_SIZE + PRICE_OFFSET_IN_RECORD)
    return int.from_bytes(state.read(off, 2), "little") * PRICE_SCALE

def save_price(state, ship_type: int, price: int) -> None:
    if price % PRICE_SCALE != 0:
        raise ValueError("가격은 10 의 배수여야 합니다")
    stored = price // PRICE_SCALE
    if not (0 <= stored <= 0xFFFF):
        raise ValueError("가격 범위 초과 (0..655,350)")
    off = (state.page + SHIP_RECORD_OFFSET_IN_SLOT
           + ship_type * SHIP_RECORD_SIZE + PRICE_OFFSET_IN_RECORD)
    state.write(off, stored.to_bytes(2, "little"))

def load_ship_class(state, ship_type: int) -> int:
    """슬롯 record +9 의 u8 (분류 0..5)."""
    off = (state.page + SHIP_RECORD_OFFSET_IN_SLOT
           + ship_type * SHIP_RECORD_SIZE + SHIP_CLASS_OFFSET_IN_RECORD)
    return state.read(off, 1)[0]

# MAIN.EXE ROM 도 동일 (record ROM = 0x0407D8)
```

## 슬롯 비교

- slot 0, 1, 2, 4, 5, 6, 7, 8, 9: ROM 과 byte-level 동일
- **slot 3**: SHIP (idx 16) record `+10..+11` 만 변경 — 사용자가 게임 진행 중 SHIP 가격을 변경한 흔적 (32,000 → 6,416). analysis_G 에서 발견된 slot 3 의 SHIP record 변경과 일치.

## 분석 스크립트
- `analysis/find_ship_price.py` (1차 — uint32 LE 가설, 0건)
- `analysis/find_ship_price2.py` (stride/encoding 확장, **stride=12 u16 LE ÷10 hit**)
- `analysis/find_ship_price3.py` (25개 dump + 10 슬롯 비교)
- `analysis/find_ship_byte9.py` (분류 byte 분석)
