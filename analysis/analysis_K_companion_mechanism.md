# 동료 메커니즘 — Person.pos = hero catalog ID

(analysis_A §8 Person struct 후속. 2026-05-23 agent + 사용자 save cross-slot 분석.)

## 1. 결론 (한 줄)

**`Person.pos` (byte +44) 1 개 byte 가 동료 소속을 결정한다.** 별도 companion list 없음. pos 값이 hero 의 "catalog ID" 와 같으면 그 hero 의 동료.

## 2. hero ↔ catalog ID 매핑

| Hero | c_hero idx | catalog_id (= pos 값) |
|---|---|---|
| JOAN (조안) | 0 | `0x00` |
| CAT (카탈리나) | 1 | `0x0a` (10) |
| OTTO (오토) | 2 | `0x1e` (30) |
| ROPEZ (로페즈) | 3 | `0x32` (50) |
| PIET (피에트로) | 4 | `0x28` (40) |
| AL (알) | 5 | `0x14` (20) |
| (예약) | — | `0x3d` (61) — 사용자 save p[114] 가 점유. 7번째 hero slot 추정. |

각 주인공 자신의 Person record 도 pos = 자기 catalog_id 로 설정되어 있음 (주인공 = 자기 자신의 동료).

## 3. pos 값 도메인

| pos 값 | 의미 |
|---|---|
| `0x00`, `0x0a`, `0x14`, `0x1e`, `0x28`, `0x32` | 해당 hero 의 동료 |
| `0x01..0x44` (위 6개 + `0x3d` 제외) | 다른 NPC 의 카탈로그 ID (고정 점유 — 변경 시 충돌) |
| `0xFE` | free (모집 가능 상태) |
| `0xFF` | 항구 정착민 (`Person.port` 가 위치 항구 0..129) |

## 4. 결정적 증거 — slot 0 ↔ slot 1 cross-slot 비교

사용자 save (`originalgame/C HDD/KOUKAI2.DAT`):
- slot 0: c_hero = `0x01` = CAT
- slot 1: c_hero = `0x00` = JOAN

slot 1 의 ship2 dump (JOAN active):
- entry 0: `captin=0x00` → 자기 자신 (JOAN)
- entry 1: `captin=0x45` → person index 69
- entry 2: `captin=0x46` → person index 70

같은 person index 가 슬롯에 따라 pos 만 변함:

| Person | slot 0 pos | slot 1 pos | 해석 |
|---|---|---|---|
| p[69] | `0xFE` (free) | `0x00` (JOAN 동료) | slot 1 에서 JOAN ship[1] 선장 |
| p[70] | `0xFE` (free) | `0x00` (JOAN 동료) | slot 1 에서 JOAN ship[2] 선장 |
| p[71] | `0xFE` (free) | `0x00` (JOAN 동료) | slot 1 에서 JOAN party (선장 X) |
| p[72] | **`0x0a` (CAT 동료)** | `0xFE` (free) | slot 0 에서 CAT party |
| p[116] | **`0x0a` (CAT 동료)** | `0xFF` (port 35 정착) | slot 0 에서 CAT party, slot 1 에서 함부르크 정착 |

→ pos 의 변화 = 동료 소속의 변화. 1:1 일치. **가설 확정 ★★★★★.**

## 5. 선장 배속 (party 가 아닌 ship captain 임명)

party 등록은 pos 변경만으로 충분. **선장 임명**은 추가로 다음이 동반:

1. **`Ship1[c_hero][slot].select`** 가 0xFF 가 아닌 ship3 index 를 가리켜야 함.
2. **`Ship3[ship1.select].ship_select`** 가 함선 종류 (0..24) 여야 함.
3. **`Ship2[slot].captin`** = person index.
4. **`Person.none2[0]`** = `0x02` (가설, §6 참조 — 미확정).

ship_num 의 카운트 로직은 `conferm_hero` (HORIEDIT.C:677-699) 와 동일.

## 6. none2[0] 의 역할 코드 (★★ 미확정)

agent 가 slot 0/1 비교에서 관찰한 패턴:

| Person | 역할 | none2[0] |
|---|---|---|
| p[69] (JOAN 선장) | 선장 | `0x02` |
| p[70] (JOAN 선장) | 선장 | `0x02` |
| p[71] (JOAN party) | party only | `0x06` |
| p[72] (CAT party) | party only | `0x03` |
| p[116] (CAT party) | party only | `0x06` |

추정:
- `0x02` = 선장 배속 marker
- `0x06` = party member 일반
- `0x03` = ? (다른 sub-role?)

**확정 검증 필요** — 사용자 측 절차 §8.2 참조.

## 7. 별도 companion list 부정 (★★★★)

- Person 영역 (0x06A9..0x1DE7) 자체에 동료 표시가 pos byte 로 인코딩되어 있음 → 별도 list 불필요
- Person 영역과 Ship1 영역 사이 (0x1DE8..0x2243) 의 미해석 영역에서도 "동료 인덱스 배열" 같은 패턴 발견 안 됨
- Ship2.none[27] 의 `14 14` 같은 패턴은 captin 과 무관 — cargo/f_crew 등 별도 데이터

## 8. 사용자 검증 절차

### 8.1 가설 A 검증 — pos 1 byte 만 변경

가장 단순. v0.4.8 의 인물 탭 pos Spinbox 로 바로 가능:

1. KOUKAI2.DAT 백업
2. p[73] (또는 다른 pos=`0xFE` free person) 의 pos 를 **10 (= 0x0a, CAT catalog_id)** 으로 변경
3. 저장 → 게임 진입 → 카탈리나 의 "동료/부하" 목록 메뉴에서 p[73] 가 보이는지 확인
   - 보임 → 가설 A 확정 → v0.4.9 의 combobox UI 즉시 구현 가능
   - 안 보임 → none2[0] 같은 추가 필드도 변경 필요 → 절차 8.2

### 8.2 none2[0] 의 역할 확정

절차 8.1 의 변경 후 추가로 p[73].none2[0] 를 0x02, 0x03, 0x06 로 따로 시도하여 game 내 표시 차이 관찰:
- 동료 목록에 표시되는 역할/직책
- 선장 임명 가능 여부

### 8.3 catalog ID 충돌 회피

`pos = 0x01..0x44 (6 hero + 0x3d 제외)` 는 NPC catalog 가 점유. 이 값으로 변경 시 game 이 두 명을 같은 catalog 로 인식해 한 명만 표시 / 충돌 가능.

**안전 변경 값**: `{0x00, 0x0a, 0x14, 0x1e, 0x28, 0x32, 0xFE, 0xFF}` 만.

## 9. 신규 UI 제안 (v0.4.9)

### 9.1 Person 데이터 레이어 (`horiedit_py/data/person.py`)

```python
HERO_CATALOG_ID = {
    0: 0x00,  # JOAN
    1: 0x0a,  # CAT
    2: 0x1e,  # OTTO
    3: 0x32,  # ROPEZ
    4: 0x28,  # PIET
    5: 0x14,  # AL
}
HERO_CATALOG_TO_IDX = {v: k for k, v in HERO_CATALOG_ID.items()}
POS_FREE = 0xFE
POS_PORT_SETTLER = 0xFF
RESERVED_POS_VALUES = {0x3d}  # p[114] 가 점유, 회피

def hero_idx_for_pos(pos: int) -> int | None:
    return HERO_CATALOG_TO_IDX.get(pos)
```

### 9.2 인물 탭 표시 강화

- **현재 소속 (read-only label)** — pos 값 decode:
  - `0x00..0x32` (hero catalog) → "{hero_name}의 동료"
  - `0xFE` → "(모집 가능)"
  - `0xFF` → "(항구 정착민 — {port_name})"
  - 기타 → "(NPC 카탈로그 0x??)"
- **소속 변경 Combobox** — Spinbox 보다 안전한 옵션:
  - 6 hero 별 등록 / 모집 가능 (free) / 항구 정착민 (port 별도)
  - raw byte Spinbox 는 advanced 모드 유지

### 9.3 검색 결과 Treeview 컬럼 추가

`(번호, 처음이름, 마지막이름, 항구)` → `(번호, 처음이름, 마지막이름, **소속**, 항구·위치)`

소속 컬럼에 hero 동료 표시.

### 9.4 안전 가드

- 인물 #0..#5 의 pos 변경 시 추가 경고 (게임 동작 불능 위험)
- catalog ID 충돌 가능한 값 (`0x01..0x44` 중 hero 제외) 입력 시 경고
- combobox 기본 옵션만 노출 — raw pos byte 는 v0.4.8 의 Spinbox 로 advanced 사용자만

## 10. 후속 분석 과제

1. **`none2[0]` 정확한 의미** (§8.2) — 0x02 / 0x03 / 0x06 의 game 내 차이
2. **0x3d catalog ID 의 정체** — p[114] 가 누구인지, 7번째 hero 슬롯 추정 검증
3. **Ship2.none[27]** 의 추가 의미 (cargo? formation?) — 선장 배속 UI (advanced) 의 ship 갱신 시 안전성 보장 위해
4. **Person 영역 0x1DE8..0x2243 미해석 영역** — 추가 동료 관련 데이터 없음을 다시 한번 확인
