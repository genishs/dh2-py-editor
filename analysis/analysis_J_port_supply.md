# 항구 공급 수치 (Supply Level) — 물가 간접 편집

(analysis_I 의 §3.1 후속. 사용자 anchor 4개 항구 × 14 commodity 검증.)

## 1. 사용자 anchor (게임 표시 가격, slot 0)

| 항구 (idx) | 무역품 | 가격 |
|---|---|---|
| 함부르크 (35) | 도자기 | 104 |
| 함부르크 (35) | 철광석 | 132 |
| 함부르크 (35) | 염료 | 98 |
| 리스본 (0) | 돌소금 | 45 |
| 리스본 (0) | 염료 | 138 |
| 리스본 (0) | 무기 | 138 |
| 리스본 (0) | 벨벳 | 92 |
| 세빌리아 (1) | 무기 | 147 |
| 세빌리아 (1) | 도자기 | 123 |
| 세빌리아 (1) | 염료 | 147 |
| 세빌리아 (1) | 와인 | 43 |
| 마데이라 (57) | 금 | 814 |
| 마데이라 (57) | 호박 | 266 |
| 마데이라 (57) | 카카오 | 60 |

## 2. 가격이 직접 저장되지 않음 확정

| 검색 영역 | u16 LE 직접 hit |
|---|---|
| slot 0 (33340 byte) | 104, 123, 147 등 0건 |
| MAIN.EXE (288 KB) | 다수 hit — 대부분 x86 코드 상수 (`b8 xx xx` = mov ax) 오탐 |
| DATA1.LZW (104 KB) | 전 anchor 0건 (LZW 압축) |
| COLONY.DAT | 0건 (랜드마크 데이터, analysis 별도) |

- 130-stride per-commodity 테이블 가설 (염료 가격표 등) — 3-anchor (염료: 0,1,35) 로 slot 전체 검색 0건
- 4-byte stride (port,cmd,price) packed 가설 — 명확한 정렬 0건

→ **가격은 base × supply 형태로 derived**. base 는 MAIN.EXE ROM, supply 는 slot 내 per-port 영역.

## 3. 공급 수치 (Supply Level) — 확정 (ports 0..99)

항구 경제 record (37 byte, base `0x5DE3`) 의 **+14..+23 10 byte 영역** = 10 개 commodity slot 의 supply level.

### 3-1. ports 0..99 의 byte 범위 (100% 일치)

모든 100 개 표준 항구의 +14..+23 byte 가 **ASCII digit / dot 범위 (0x2E..0x39)**:
- `0x2E ('.')` = 빈 슬롯 (commodity 없음)
- `0x2F ('/')` = supply 0 (sold out / 매우 낮음)
- `0x30 ('0')` = supply 1
- `0x31 ('1')` = supply 2
- ...
- `0x39 ('9')` = supply 10

검증 결과:
- 100/100 항구 모두 byte 가 위 범위 안. 0 outlier.
- 항구마다 commodity 개수: 7..10 (나머지 슬롯은 `.` 로 비어있음).

### 3-2. ports 100..129 의 다른 포맷

원거리/숨겨진 항구 (헤클라, 케이프타운 등 30 항구) 는 +14..+23 가 u16 LE pair 같은 다른 구조:
- 예: 헤클라 `c8 00 05 00 69 00 2d 00 14 00` → u16 LE [200, 5, 105, 45, 20]

해석 미정. 본 에디터에서는 raw byte 로 노출.

### 3-3. 사용자 anchor 와 일치 sanity check

마데이라(57) bytes `36 33 30 32 2f 33 2f 32 30 32` → supply (7, 4, 1, 3, 0, 4, 0, 3, 1, 3).
- 2 개 슬롯이 supply 0 (`/`). 사용자 가격 anchor 에서 금=814 (매우 비싼)은 supply 0 슬롯에 해당할 가능성 매우 높음.

리스본(0) bytes `34 35 32 35 2f 34 33 2e 2e 2e` → supply (5, 6, 3, 6, 0, 5, 4, -, -, -).
- 7 슬롯 active. 사용자 anchor 4 개와 일치 (사용자가 listed 안한 3 개가 더 있을 가능성).

## 4. base price (commodity 종류별 ROM 가격)

미확정. MAIN.EXE 안에 commodity 종류별 base price + 가격 공식이 박혀있을 것으로 추정.

가격 공식 추정 (DH2 일반 게임 메커닉):
```
displayed_price ≈ base_price(commodity_type) × f(supply_level)
```
- f 는 단조 감소 (supply 높음 → 가격 낮음)

base price + f 식 동시 역공학에는 anchor 수십 개 + MAIN.EXE 디스어셈 필요. 비용 큼.

## 5. 본 에디터의 타협안

**공급 수치 (supply level) 직접 편집** 만 노출:
- 항구당 10 byte (+14..+23) raw u8 Spinbox.
- ports 0..99 는 0x2E..0x39 권장 범위 안내.
- ports 100..129 는 "구조 미해석" 라벨로 raw byte 만 노출.

가격이 정확한 숫자 (예: "마데이라 금값 = 420") 로 입력되진 않지만, supply 를 낮추면 가격 상승 / 높이면 하락하는 효과는 즉시 확인 가능. 사용자가 byte 0..10 정도 범위 내에서 슬롯을 조정해 가며 원하는 가격에 접근.

## 6. 후속 분석 과제

1. **commodity slot ↔ commodity name 매핑** — 각 port 의 10 slot 이 어느 무역품에 대응하는지. MAIN.EXE 의 port-commodity assignment 테이블 위치 탐색.
2. **base price + f(supply) 공식** — MAIN.EXE 디스어셈 또는 다량 anchor (10 항구 × 모든 commodity) 회귀분석.
3. **ports 100..129 의 +14..+23 의미** — u16 LE 인 듯한 pair 들이 무엇인지.
4. 위 3 가지가 풀리면 supply 가 아닌 **가격 직접 입력 UI** 로 업그레이드.
