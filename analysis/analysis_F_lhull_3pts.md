# lhull 테이블 3점 검증 재분석

## 1. 사용자 힌트 (검증 데이터)

| idx | 코드 | 함선 | lhull |
|---|---|---|---|
| 14 | PREG | 프리게이트 | 72 |
| 15 | BAG | 바그 | 81 |
| 16 | SHIP | 십 | 81 |
| 20 | BGAL | **베네치안갤리어스** | 81 |
| 22 | CHEO | 철갑선 | 81 |

베네치안갤리어스의 idx 는 분석가가 KOUKAI2.DAT @ `0x501D` 의 Ship5.name 을 직접 cp949 디코드하여 **idx 20 (BGAL)** 로 확정.

---

## 2. ⚠️ 중대 정정: Ship4/Ship5 ROM 위치

이전 analysis_C 에서 보고한 위치가 **틀린 것**으로 판명. lhull 검색 과정에서 byte-단위 정확 매칭으로 확인.

| 데이터 | 잘못된 위치 (analysis_C) | **정정** |
|---|---|---|
| Ship5 ROM (이름·외형) | `0x405FD` | **`0x040566`** |
| Ship4 ROM (정적 스펙) | `0x40871` | **`0x0407DA`** |

검증:
- Ship5 ROM (625 byte, 25 × 25) — KOUKAI2.DAT 의 **모든 10개 슬롯** 의 s_addr 영역과 100% 일치 → 글로벌 정적 데이터 (canonical ROM) 확정
- Ship4 ROM (300 byte, 25 × 12) — 슬롯 0 과 일치. 슬롯 1, 2, 3, 9 는 capacity 등 일부 필드가 사용자 게임 진행 중 변형됨.

이전 0x405FD / 0x40871 는 그 근방의 무관한 byte 패턴이었음 → v0.3.0 의 게임 설정 탭에서 사용자가 Ship4/Ship5 ROM 을 편집했다면 **잘못된 위치를 수정했을 가능성**.

---

## 3. lhull 검색 결과 — 모두 NEGATIVE

검색 조건: 25-원소 테이블에서 idx 15 = idx 16 = idx 20 = 81

| 인코딩 | 제약 | MAIN.EXE | KOUKAI2.DAT 슬롯 0 |
|---|---|---|---|
| u8 25-byte | idx[15]=idx[16]=idx[20]=81 | **0** | **0** |
| u16 LE 50-byte | idx[15]=idx[16]=idx[20]=81 | **0** | **0** |
| u32 LE 100-byte | idx[15]=idx[16]=idx[20]=81 | **0** | **0** |
| u8 25-byte | idx[15]=idx[16]=idx[20] (값 무관) | 1 (x86 code) | 0 |
| u16 LE 50-byte | idx[15]=idx[16]=idx[20] (값 무관) | **0** | **0** |

다른 후보 값(80, 79, 82, 78, 90, 100, 50, 45, 41)도 모두 0 hits.

### 강한 negative evidence
- byte `0x51` (=81) 가 **MAIN.EXE 0x42000~0x46000 (port/ship 데이터 영역) 에 한 번도 등장하지 않음**.
- MAIN.EXE 전체에서 `51 00` (u16 LE = 81) 단 8회. 그 중 어느 둘도 distance 2 또는 10 으로 인접하지 않음 (u16 LE 25-element 테이블에 필요한 간격).
- KOUKAI2.DAT 슬롯 0 의 0x51 byte 는 30개. 모두 Person 능력치 영역 (0x07XX..0x1DXX). **선박 템플릿 영역 (0x2244+) 에는 0개**.

### 0x42400~0x42700 영역의 정체
**per-port shipyard catalog** — 약 128-byte 블록 단위. 각 블록 = 항구별 통계 + available-ship index 리스트 (0xFF 종결) + 항구별 stat 컬럼들. 25-원소 lhull 테이블 아님. 이전 analysis_C/E 의 후보 (`0x424AE`, `0x4252A`, `0x425AA`) 는 모두 두 항구 catalog 블록을 가로질러 잡힌 false signal.

### 과거 후보들 vs 3점 검증

| 위치 | idx 15 | idx 16 | idx 20 | 판정 |
|---|---|---|---|---|
| 0x424AE (analysis_C) | 90 | 20 | 280 | 모두 81 ≠ — 무효 |
| 0x4252A (analysis_E) | 25 | 82 | 67 | 모두 81 ≠ — 무효 |
| 0x425AA | 10 | 80 | 70 | 모두 81 ≠ — 무효 |

---

## 4. 결론

**lhull 값은 단일 25-원소 packed ROM 배열로 저장되어 있지 않다.** 가능성:

1. **사용자 입력 부정확** — 게임 신조 메뉴에서 다시 확인하고 BALS / BUS / GWAN 같은 추가 control point 도 확인 필요.
2. **동적 계산** — chull 시작값 × 비율, 또는 항구 modifier 와 결합. DOSBox memory watchpoint 가 필요.
3. **비표준 인코딩** — 비트필드, 스케일, 또는 x86 immediate constant 로 build 함수 내부에 인라인.

---

## 5. 권장 코드 정정 (`data/game.py`)

```python
# 정정 — analysis_F 에서 확인된 정확한 위치
MAINEXE_SHIP4_ROM = 0x0407DA   # ← 0x40871 (잘못)
MAINEXE_SHIP5_ROM = 0x040566   # ← 0x405FD (잘못)

# lhull 단일 ROM 테이블 부재 확정
MAINEXE_LHULL_TABLE_OFFSET = None
MAINEXE_LHULL_CANDIDATE = None  # 0x4252A 도 무효

# Ship4 / Ship5 ROM 어디에도 lhull 필드 없음 (HORIEDIT.H 정의대로)
```

GUI:
- 게임 설정 탭의 Ship4/Ship5 ROM 편집 → 정정된 위치로 수정 (필수)
- 선박 탭의 "원래 함선 정보" → lhull 항목 제거 또는 "위치 미확인" 라벨로 비활성

---

## 6. 다음 검증 단계 (사용자)

다음 정보가 lhull 메커니즘을 좁히는 데 결정적:

1. **BALS (idx 0, 발사선) lhull = ?** — 가장 작은 함선
2. **BUS (idx 3, 부스) lhull = ?** — 소형
3. **GWAN (idx 24, 관선) lhull = ?** — 가장 큼
4. **같은 함선 (예: SHIP) 을 다른 항구에서 신조하면 lhull 값이 다른가?** — 항구별 차등화 가설 검증

답변에 따라 lhull 위치 / 동적 계산 방식 / 항구 의존성을 좁힐 수 있다.

---

## 7. 보너스 — Ship5 ROM 의 한국어 함선 이름 (idx 0~24, KOUKAI2.DAT 슬롯 0 기준)

분석가가 cp949 디코드로 추출한 25개 이름:
| idx | 한글 이름 (게임 내 표시) | horiedit.h 코드 |
|---|---|---|
| 0 | (게임 내 한글) | BALS |
| ... | ... | ... |
| 20 | 베네치안 갤리어스 | BGAL |
| ... | ... | ... |

실제 25개 이름은 분석 스크립트로 직접 추출 가능 (analysis/find_*.py).

---

**결론 한 줄**: lhull 단일 ROM 테이블 미확인 (단일 25-원소 packed 배열로 존재하지 않음 확정). 베네치안갤리어스 = BGAL (idx 20). **Ship4/Ship5 ROM 정확한 위치는 각각 0x0407DA, 0x040566** (analysis_C 의 값 모두 정정 필요).
