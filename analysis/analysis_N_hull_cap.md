# 신조 내구도 cap — MAIN.EXE 의 `MOV DX, 100` 패치

(issue #5, v0.4.13. 2026-05-24 사용자 검증으로 확정.)

## 1. 결론 (한 줄)

조선소 신조 시 청구 내구력은 `MAIN.EXE` 안의 **`MOV DX, 100`** instruction 2 곳으로 cap 된다. 이 즉시값을 100 → 255 등으로 바꾸면 cap 도 변경됨. 게임 진행에 부작용 없음 확인.

## 2. 출처 (사용자 보고)

> ▲조선소에서 선박 신조시
>   첫 화면에서 주인이 제시하는 수치는 표준내구력 x 0.9 이며
>   재질에 따라 x0.8 x0.9 x1.0 x1.1 x1.2 x1.3(철갑)의 청구내구력이 표시됨.
>   단, 청구내구력이 100을 초과하는 경우 100을 상한으로 함.
>   -> 이 상한은 세이브파일이 아닌
>      main.exe offset 30893: 64 및 30a20: 64 두군데에 설정되어 있음.

## 3. 검증 (Test β, 2026-05-24)

dh2_cust/MAIN.EXE (한국어 빌드, 288,823 byte):
- 두 offset `0x30893` / `0x30A20` 의 `0x64` (100) → `0xFF` (255) 패치
- 함부르크 공업가치 3000 으로 올려 좋은 재질 신조 시도 → 청구 내구력 **198** 확인 (>100)
- 패치 되돌림 (0xFF → 0x64) → 같은 조건에서 다시 100 으로 cap 확인 ✓

→ **두 byte 가 신조 cap 임이 완전 확정.**

## 4. instruction 구조

두 위치 모두 동일한 8086 패턴:
```
... F7 F9       IDIV CX           ; 결과 / 분모
    BA 64 00   MOV DX, 100        ; cap 을 DX 에 적재
    9A 40 4D 00 00   CALL FAR 0000:4D40   ; cap 적용 함수 호출
```

함수 `0000:4D40` 은 cap 적용 (MIN) 루틴으로 추정.

## 5. signature 기반 자동 탐색 (v0.4.13)

빌드별로 offset 이 다를 수 있어 하드코딩 회피. signature:
```
F7 F9 BA ?? 00 9A 40 4D 00 00
         ^^ = cap byte (1..255)
```
패턴이 발견된 모든 `??` 위치 = cap 후보. dh2_cust/MAIN.EXE 에서는 3 곳:
- `0x17525` value=50 (의미 불명 — 동일 signature, 다른 시스템)
- `0x30893` value=100 (신조 cap #1)
- `0x30A20` value=100 (신조 cap #2)

`value=100` 만 표시값 "신조 cap (확정)" 으로 라벨링, 그 외는 "변경 주의" 경고.

## 6. dh2_init/MAIN.EXE 의 경우

다른 빌드 (297,783 byte, 한일 어느 버전인지 미정) 에서는 signature 미발견.
이 경우 패널이 "이 빌드는 자동 검출 불가" 메시지 표시 + 편집 비활성.

## 7. v0.4.13 구현

`horiedit_py/data/game.py`:
- `HULL_CAP_SIG_BEFORE` / `HULL_CAP_SIG_AFTER` 상수
- `find_hull_cap_offsets(main_exe)` 패턴 검색
- `load_hull_caps(main_exe)` `(offset, value)` 리스트
- `save_hull_caps(main_exe, pairs)` 일괄 쓰기
- `ensure_hull_cap_backup(main_exe)` / `restore_hull_cap_backup(main_exe)` — `.beforeHullCap` 백업

`horiedit_py/gui/settings_tab.py`:
- `_HullCapPanel` 신규 sub-tab "신조 내구도 cap (issue #5)"
- Spinbox 1..255, [패치 적용] / [기본값(100) 복원] / [백업에서 복원] / [다시 불러오기]

## 8. 후속 과제

1. **0x17525 (value=50) 의 정체** — 어떤 시스템의 cap 인지 확인 (모험 보상? 전투 데미지?)
2. **CALL FAR 0000:4D40** 함수의 정확한 동작 (MIN 인지 다른 clamp 인지)
3. **다른 빌드** 지원 — dh2_init 같은 빌드의 signature 검출 또는 수동 offset 입력
