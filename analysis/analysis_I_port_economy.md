# 항구 경제 테이블 — 상업치/공업치/물가 위치

## 1. 사용자 앵커 (slot 0, 게임 표시값)

| 항구 (idx) | 상업치 | 공업치 |
|---|---|---|
| 런던 (29) | 720 | 740 |
| 엔트워프 (32) | 660 | 670 |
| 암스테르담 (33) | 700 | 730 |
| 함부르크 (35) | 600 | 620 |

## 2. 확정 — 항구 경제 테이블

- **base**: `slot + 0x5DE3`
- **stride**: 37 byte per port
- **size**: 130 × 37 = 4810 byte (slot 내 0x5DE3..0x70AC)
- **commerce (상업치)**: u16 LE @ record +0
- **industry (공업치)**: u16 LE @ record +4

### 2-1. 검증

4개 앵커 모두 `commerce_addr = 0x5DE3 + idx*37`, `industry_addr = commerce_addr + 4` 에 u16 LE 정확 일치:

| idx | 항구 | c offset | c 값 | i offset | i 값 |
|---|---|---|---|---|---|
| 29 | 런던 | 0x6214 | 720 | 0x6218 | 740 |
| 32 | 엔트워프 | 0x6283 | 660 | 0x6287 | 670 |
| 33 | 암스테르담 | 0x62A8 | 700 | 0x62AC | 730 |
| 35 | 함부르크 | 0x62F2 | 600 | 0x62F6 | 620 |

### 2-2. 값 분포 (slot 0, 130 ports)

- commerce: min 0, max 810, 평균 ~100, 77 unique 값
- industry: min 0, max 810, 평균 ~100, 83 unique 값
- 0xF000 초과 이상치 2/260 — 모두 idx 100+ (북극/숨겨진 항구 영역)

### 2-3. 슬롯별 변동

| 비교 | byte diff |
|---|---|
| slot 0 vs 1 | 22.9% |
| slot 0 vs 2 | 24.6% |
| slot 0 vs 8 | 16.9% |

→ 슬롯별 동적 데이터. ROM 정적 사본 아님. 편집 시 슬롯별 저장.

## 3. record 37 byte 내부 분석 (slot 0, ports 0..99 기준)

| offset | size | 추정 의미 | 비고 |
|---|---|---|---|
| +0..1 | u16 LE | **상업치** ★ | 확정 |
| +2..3 | u16 LE | 0 (padding) | 100+ 일부 ports 에서 nonzero — 다른 의미 가능 |
| +4..5 | u16 LE | **공업치** ★ | 확정 |
| +6..7 | u16 LE | 0 (padding) | |
| +8..13 | 6 byte | misc | 0x14/0x5A/0x64 등 — 영주국 / 영주값 등 가설 |
| **+14..23** | **10 byte u8** | **물가? (10 무역품 가격)** | **미확정 — 앵커 필요**. 값 범위 46..55 (digit 영역). |
| +24..36 | 13 byte | misc | 다양한 의미 가능 (인구, 방어력, 군대, 사건 플래그 등) |

### 3-1. +14..+23 물가 가설

DH2 의 무역품 10종에 1:1 대응할 가능성. 모든 ports 0..99 에서 byte 값이 0x2E~0x37 (46..55) 좁은 범위 — 가격이 좁은 분포를 가지는 것과 일치. 사용자가 게임에서 특정 항구의 무역품 가격을 확인해 줘야 확정 가능.

### 3-2. ports 100..129 의 다른 layout

ports 100+ (헤클라, 나르비크, 케이프타운 등 — 숨겨진/원거리 항구) 는 record 안 byte 분포가 다름:
- +2..3 nonzero (e.g., 헤클라 record `8c 00 78 00 50 00 ...`)
- +14..+23 도 ASCII-digit 범위 벗어남

가설: 메인 항구(0..99) 와 다른 카테고리 (탐험 가능 항구 vs 발견된 항구). commerce/industry 편집은 동일하게 동작하지만, +14..+23 물가는 ports 100+ 에서는 별도 매핑 필요할 수 있음.

## 4. base 0x5DE3 와 port struct array 의 overlap

port_addr (0x53BF) + 130 × 20 (sizeof Port) = 0x5DE7 이지만 econ table base 는 0x5DE3 → **4 byte overlap**.

| 영역 | 의미 |
|---|---|
| 0x5DD3..0x5DE1 | port[129] (페어웰) name 15B |
| 0x5DE2 | port[129] none[5][0] = region/flag |
| **0x5DE3..0x5DE6** | port[129] none[5][1..4] = port[129] mapX/Y **AND** port[0] econ +0..+3 |
| 0x5DE7+ | port[0] econ +4..+36 |

해석: 마지막 port (idx 129) 의 mapX/mapY 좌표 4 byte 가 동시에 첫 port (idx 0, 리스본) 의 commerce + padding 영역에 해당. data overlap.

**Implication**:
- 리스본 commerce 편집 → port[129] mapX 변경 (값이 같은 0x030C=780 이므로 게임이 페어웰을 좌표 780,? 에 그릴 수 있음)
- 페어웰 (port[129]) 의 none[5] 는 본 에디터에서 편집 안 함 → 단방향 영향 (commerce edit → mapX edit) 만 발생
- 리스본 commerce 를 매우 작은 값 (예: 1) 으로 바꾸면 페어웰이 지도상 (1, ?) 위치로 이동할 가능성 → 실제 게임에서 문제 발생 여부 사용자 검증 필요

**Conservative 권장**: 일단 commerce 편집을 허용하되 README/UI 에 caveat 명시. 사용자 검증 결과 게임 깨지면 별도 처리 (예: 페어웰 좌표 보존 안전장치).

## 5. Python 구현 가이드

```python
PORT_ECON_BASE = 0x5DE3
PORT_ECON_STRIDE = 37
NUM_PORTS = 130

def read_port_econ(state, idx: int) -> tuple[int, int]:
    """반환: (commerce, industry) u16 LE"""
    state.fp.seek(state.page + PORT_ECON_BASE + idx * PORT_ECON_STRIDE)
    return struct.unpack("<HxxH", state.fp.read(6))  # +0 commerce, +2 skip, +4 industry

def write_port_econ(state, idx: int, commerce: int, industry: int) -> None:
    base = state.page + PORT_ECON_BASE + idx * PORT_ECON_STRIDE
    state.fp.seek(base)
    state.fp.write(struct.pack("<H", commerce & 0xFFFF))
    state.fp.seek(base + 4)
    state.fp.write(struct.pack("<H", industry & 0xFFFF))
    state.fp.flush()
```

값 범위 검증: 0..65535. 게임 내 자연 범위는 0..1000 정도지만 u16 max 까지 허용.

## 6. 후속 분석 과제

1. **물가 (+14..+23) 확정** — 사용자 anchor 필요. 게임 내 특정 항구의 무역품 10종 가격 표시값.
2. **ports 100..129 다른 layout 의미** — 별도 카테고리인지, 어떤 필드들이 있는지.
3. **+8..13 / +24..36 의 의미** — 영주국, 인구, 방어력, 군대 등 다른 항구 stat.
4. **base 0x5DE3 overlap 안전성** — 리스본 commerce 극단값 편집 시 페어웰 위치/존재 영향 확인.
