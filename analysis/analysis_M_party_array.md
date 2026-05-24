# party 배열 (외부 동료 list) — slot+0x21BE

(analysis_K §7 "별도 companion list 부정" 폐기 ★★★★★. 2026-05-24 dh2_cust vs dh2_init 비교로 확정.)

## 1. 결론 (한 줄)

게임의 "인물 목록" UI 는 **slot+0x21BE 부터의 30 byte party 배열** 로부터 그려진다. Person record 의 `pos` / `none1` / `none2[0]` 는 NPC 자신의 상태일 뿐, 이 배열에 등록되지 않으면 게임 메뉴에 동료로 표시되지 않는다.

## 2. 결정적 증거

dh2_init / dh2_cust 두 KOUKAI2.DAT 의 슬롯 0,1 비교:

| 슬롯 | c_hero | 동료 (Person.pos 기준) | slot+0x21BE.. (실제 배열) |
|---|---|---|---|
| init 0 | AL | 자한 (idx 78) | `4E FF FF ...` = (자한) |
| cust 0 | AL | 자한·**필리·라울**·개빈 4명 | `4E 74 FF ...` = (자한, 개빈) — **필리·라울 누락** |
| cust 1 | JOAN | 로코(69)·엔리코(70)·도밍고(71) | `45 46 47 FF ...` = 정확히 일치 |

→ **에디터로 person.pos 만 변경한 필리·라울은 배열에 안 들어가서 게임 메뉴에 안 보임.**
→ 사용자가 게임 내에서 채용한 개빈은 게임이 배열을 갱신해줘서 보임.

## 3. 배열 구조

```
slot + 0x21BB : remaining_slots (byte)   ← party 추가 시 1 감소
slot + 0x21BC : 0x64 (상수)
slot + 0x21BD : 0x64 (상수)
slot + 0x21BE : party[0]   ← person_idx 또는 0xFF (빈 슬롯)
slot + 0x21BF : party[1]
...
slot + 0x21DB : party[29]
slot + 0x21DC : aux[0]     ← 동반 attribute 배열 (loyalty / condition 추정)
slot + 0x21DD : aux[1]
... (이하 미해석)
```

- 배열 길이: 30 슬롯 (0x21BE..0x21DB)
- `remaining_slots` 와 party 추가 수의 관계:
  - init AL (자한 1명): remaining=`0x06` → 게임 시작 capacity = 7 (1 + 6)
  - cust AL (자한+개빈 2명): remaining=`0x05` → 5 + 2 = 7 ✓
  - cust JOAN (3명): remaining=`0x07` → 7 + 3 = 10
  - JOAN max capacity = 10, AL max capacity = 7 (?) — hero 별 다를 수 있음, 추가 검증 필요

## 4. v0.4.12 fix 설계

`set_companion()` 가 추가로 해야 할 작업:
1. `slot + 0x21BE..0x21DB` 에서 첫 0xFF 슬롯 찾기
2. 거기에 person_idx 기록
3. `slot + 0x21BB` 의 `remaining_slots` 1 감소

`unset_companion()` 의 역작업:
1. 배열에서 person_idx 찾아 0xFF 로 지움 (compact 필요? 추정: 안 해도 됨, 게임이 빈 슬롯 무시)
2. `remaining_slots` 1 증가

⚠ 검증 필요:
- 배열에 추가만 하면 충분한가, `aux[]` 도 동시 갱신 필요한가? (init 에선 자한의 aux=`0x02`, 빈 슬롯 aux=`0xFF` 인 듯)
- `remaining_slots` 갱신 누락 시 게임 동작?
- 한 슬롯 안에서 max 도달 시 (`remaining_slots = 0`) 게임 동작?

## 5. 사용자 검증 — **Test α 성공 ★★★★★ (2026-05-24)**

dh2_cust slot 0 (AL game) 의 party 배열에 필리·라울 person_idx 를 직접 hex 패치:
- 0x21BB: 0x05 → 0x03 (remaining_slots)
- 0x21C0: 0xFF → 0x4F (필리, idx 79)
- 0x21C1: 0xFF → 0x63 (라울, idx 99)
- (0x21DE/0x21DF 의 aux byte 는 이미 0x02 로 초기화되어 있어 추가 패치 불필요)

→ 게임 인물 목록에 필리·라울 정상 표시 확인. **가설 확정.**

### 5.1 부수 발견 — aux 배열 초기값

aux 배열 (0x21DC..0x21F5, 26 byte) 은 **빈 슬롯도 기본 0x02** 로 초기화되어 있음
(0xFF 가 아님). 따라서 party 추가 시 aux 갱신은 일반적으로 불필요.

예외 — 개빈 핏셔 (current AL 선장) 의 aux 가 0x01 인 패턴 관찰. 가설:
- 0x01 = 선장 (Ship2.captin 에 등록된 자)
- 0x02 = 일반 party / 빈 슬롯

party 만 등록하는 본 기능에서는 aux 변경 없이 0x02 유지가 안전.

## 6. v0.4.12 구현 (확정)

`horiedit_py/data/person.py` 의 신규 함수:
- `add_to_party_array(state, person_idx) -> bool`
- `remove_from_party_array(state, person_idx) -> bool`
- `is_in_party_array(state, person_idx) -> bool`

`set_companion` / `unset_companion` 가 위 함수를 동반 호출.

`horiedit_py/gui/person_tab.py` 의 `commit()` 가 pos 변경 시:
- `old_pos != this_catalog` and `new_pos == this_catalog` → add
- `old_pos == this_catalog` and `new_pos != this_catalog` → remove
- `this_catalog = HERO_CATALOG_ID[state.c_hero]`

## 7. 후속 과제

1. **aux 0x01 의 정확한 의미** — 선장 marker 인지, 다른 sub-role 인지 검증
2. **party 배열 max 크기 hero 별 다른가** — AL=7, JOAN=10 으로 보이지만 추가 검증 필요
3. **counter (0x21BB) 안 맞추면 어떻게 되는가** — 표시는 되는데 다른 로직 영향?
4. **0x21F6..0x21FB 6 byte** 의 정체 (init AL=FF FF FF FF FF FF, cust JOAN=2A 03 01 0A 18 14)
