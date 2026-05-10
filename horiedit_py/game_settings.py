# 게임 기본 설정 변경 — KOUKAI2.DAT 이외 파일 (MAIN.EXE 등) 편집.
#
# 함선 신조 관련 4개 메뉴:
#   1) 항구 공업 수치 요건 (추정 위치 0x42722, uint16 LE × 25)
#   2) 신조 시 최대 내구도 (추정 위치 0x424AE, uint16 LE × 25)
#   3) Ship4 ROM (확정 위치 0x40871, 12 byte × 25) — 정적 스펙
#   4) Ship5 ROM (확정 위치 0x405FD, 25 byte × 25) — 이름·외형
#
# 자세한 위치 분석은 analysis/analysis_C_mainexe_ship_build.md 참조.

from __future__ import annotations

import struct
from pathlib import Path
from typing import Optional

from .common import (
    EditorState,
    Ship4,
    Ship5,
    decode_kr,
    encode_kr_fixed,
)


# ---------------------------------------------------------------------------
# 상수
# ---------------------------------------------------------------------------

MAINEXE_SHIP4_ROM = 0x40871     # 확정: Ship4 25개 (12 byte × 25)
MAINEXE_SHIP5_ROM = 0x405FD     # 확정: Ship5 25개 (25 byte × 25)
MAINEXE_KOGYO_TABLE = 0x42722   # 추정: 신조 항구 공업 수치 (uint16 × 25)
MAINEXE_LHULL_TABLE = 0x424AE   # 추정: 신조 시 최대 내구도 (uint16 × 25)
MAINEXE_TABLE_LEN = 25


# 한국어 함선 이름 fallback (state.ship_name 이 비어있을 때 사용).
SHIP_NAMES_KR = [
    "발사선", "한선", "다우", "부스", "타르타네",
    "라틴 카라벨", "라티노 카라벨", "브리간틴", "나우", "카락",
    "갤리언", "제벡", "파네스", "슬루프", "프리게이트",
    "바그", "십", "정크", "대형 갤리언", "플로레스 갤리언",
    "바스크 갤리언", "라 아르마다", "철갑선", "안택선", "관선",
]


# ---------------------------------------------------------------------------
# 입력 헬퍼
# ---------------------------------------------------------------------------

def _ask_int(prompt: str, default: int = -1) -> int:
    """정수 입력. 공백/잘못된 입력 시 default."""
    try:
        s = input(prompt).strip()
        if not s:
            return default
        return int(s)
    except (ValueError, EOFError):
        return default


def _ask_str(prompt: str) -> str:
    try:
        return input(prompt)
    except EOFError:
        return ""


def _ask_yn(prompt: str) -> bool:
    try:
        s = input(prompt).strip().lower()
    except EOFError:
        return False
    return s in ("y", "yes")


def _ship_name(state: EditorState, idx: int) -> str:
    """state.ship_name 가 채워져 있으면 그 값, 아니면 한국어 fallback."""
    if 0 <= idx < len(state.ship_name):
        nm = state.ship_name[idx]
        if nm:
            return nm
    if 0 <= idx < len(SHIP_NAMES_KR):
        return SHIP_NAMES_KR[idx]
    return f"#{idx}"


# ---------------------------------------------------------------------------
# MAIN.EXE 경로 확인
# ---------------------------------------------------------------------------

def _resolve_mainexe(state: EditorState) -> Optional[Path]:
    if state.game_dir is None:
        return None
    p = Path(state.game_dir) / "MAIN.EXE"
    if not p.is_file():
        return None
    return p


# ---------------------------------------------------------------------------
# uint16 테이블 편집 (메뉴 1, 2 공용)
# ---------------------------------------------------------------------------

def _read_u16_table(path: Path, base_offset: int, count: int) -> list:
    with path.open("rb") as fp:
        fp.seek(base_offset)
        raw = fp.read(2 * count)
    if len(raw) < 2 * count:
        raise IOError(f"MAIN.EXE 가 너무 짧습니다 (offset 0x{base_offset:X}).")
    return list(struct.unpack(f"<{count}H", raw))


def _write_u16(path: Path, base_offset: int, idx: int, value: int) -> None:
    value &= 0xFFFF
    with path.open("r+b") as fp:
        fp.seek(base_offset + idx * 2)
        fp.write(struct.pack("<H", value))


def _edit_u16_table(
    state: EditorState,
    path: Path,
    base_offset: int,
    title: str,
) -> None:
    """uint16 LE × 25 테이블 편집 UI (메뉴 1, 2 공용)."""
    while True:
        try:
            values = _read_u16_table(path, base_offset, MAINEXE_TABLE_LEN)
        except IOError as e:
            print(f"읽기 실패: {e}")
            return

        print()
        print(f"=== {title} ===")
        print(f"[경고] 추정 위치 (0x{base_offset:X}). 게임 실험으로 검증되지 않았습니다.")
        print()

        # 2열 표시 (1..25)
        for j in range(13):
            left_idx = j * 2
            right_idx = j * 2 + 1
            left = (
                f"{left_idx + 1:2d}) {_ship_name(state, left_idx):<14s}: "
                f"{values[left_idx]:5d}"
            )
            if right_idx < MAINEXE_TABLE_LEN:
                right = (
                    f"{right_idx + 1:2d}) {_ship_name(state, right_idx):<14s}: "
                    f"{values[right_idx]:5d}"
                )
                print(f"  {left}    {right}")
            else:
                print(f"  {left}")
        print()
        print("  0) 돌아가기")
        print()

        sel = _ask_int("번호 선택 => ", default=-1)
        if sel == 0:
            return
        if not (1 <= sel <= MAINEXE_TABLE_LEN):
            continue

        idx = sel - 1
        cur = values[idx]
        print(f"  현재 값: {cur} (0x{cur:04X})")
        new_val = _ask_int(
            f"  새 값을 입력하세요 (0..65535, Enter 취소) => ",
            default=-1,
        )
        if new_val < 0 or new_val > 0xFFFF:
            print("  취소되었거나 범위 밖입니다.")
            continue

        try:
            _write_u16(path, base_offset, idx, new_val)
            print(f"  완료: {_ship_name(state, idx)} = {new_val} 로 저장했습니다.")
        except OSError as e:
            print(f"  쓰기 실패: {e}")


def _confirm_estimated(title: str) -> bool:
    """추정 테이블 메뉴 진입 시 한 번 더 확인."""
    print()
    print(f"=== {title} ===")
    print("⚠️ 이 위치는 분석가가 추정한 위치입니다.")
    print("   게임 실험으로 검증되지 않았으므로, 변경 시 게임이 정상 동작하지 않을 수 있습니다.")
    return _ask_yn("   계속하시겠습니까? (y/n) => ")


# ---------------------------------------------------------------------------
# 함선 선택 (메뉴 3, 4 공용)
# ---------------------------------------------------------------------------

def _select_ship(state: EditorState, prompt: str) -> int:
    """25개 함선을 2열로 표시하고 1..25 입력 받아 0..24 인덱스로 반환. 0 → -1."""
    while True:
        print()
        print(" 0) 돌아가기")
        for j in range(13):
            left_idx = j * 2
            right_idx = j * 2 + 1
            left = f"{left_idx + 1:2d}) {_ship_name(state, left_idx):<20s}"
            if right_idx < MAINEXE_TABLE_LEN:
                right = f"{right_idx + 1:2d}) {_ship_name(state, right_idx):<20s}"
                print(f"  {left}    {right}")
            else:
                print(f"  {left}")
        print()
        sel = _ask_int(prompt, default=-1)
        if sel == 0:
            return -1
        if 1 <= sel <= MAINEXE_TABLE_LEN:
            return sel - 1
        # 범위 밖이면 재표시.


# ---------------------------------------------------------------------------
# 메뉴 3: Ship4 ROM 편집 (확정)
# ---------------------------------------------------------------------------

def _edit_ship4_rom(state: EditorState, path: Path) -> None:
    while True:
        idx = _select_ship(state, "어느 배를 편집하시겠습니까? => ")
        if idx < 0:
            return

        offset = MAINEXE_SHIP4_ROM + idx * Ship4.SIZE
        try:
            with path.open("rb") as fp:
                fp.seek(offset)
                ship4 = Ship4.from_bytes(fp.read(Ship4.SIZE))
        except OSError as e:
            print(f"읽기 실패: {e}")
            return

        while True:
            print()
            print(f"--- Ship4 ROM 편집: [{idx + 1}] {_ship_name(state, idx)} ---")
            print(" 0) 저장하고 빠져나간다")
            print(f" 1) 최대 회전력 (lrudder) : {ship4.lrudder}")
            print(f" 2) 최대 돛     (lsail)   : {ship4.lsail}")
            print(f" 3) 최대 승무원 (lcrew*10): {ship4.lcrew * 10}")
            print(f" 4) 필요 승무원 (dcrew)   : {ship4.dcrew}")
            print(f" 5) 최대 적재량 (capacity): {ship4.capacity}")
            print(f" 6) 최대 무기수 (lnowea)  : {ship4.lnowea}")
            print()

            i = _ask_int("번호 선택 => ", default=-1)
            if i == 0:
                break
            if i == 1:
                v = _ask_int(f"  최대 회전력 (현재 {ship4.lrudder}) => ", default=-1)
                if 0 <= v <= 0xFF:
                    ship4.lrudder = v
            elif i == 2:
                v = _ask_int(f"  최대 돛 (현재 {ship4.lsail}) => ", default=-1)
                if 0 <= v <= 0xFF:
                    ship4.lsail = v
            elif i == 3:
                v = _ask_int(
                    f"  최대 승무원 (현재 {ship4.lcrew * 10}, 10단위) => ",
                    default=-1,
                )
                if 0 <= v:
                    ship4.lcrew = (v // 10) & 0xFF
            elif i == 4:
                v = _ask_int(f"  필요 승무원 (현재 {ship4.dcrew}) => ", default=-1)
                if 0 <= v <= 0xFF:
                    ship4.dcrew = v
            elif i == 5:
                v = _ask_int(f"  최대 적재량 (현재 {ship4.capacity}) => ", default=-1)
                if 0 <= v <= 0xFFFF:
                    ship4.capacity = v
            elif i == 6:
                v = _ask_int(f"  최대 무기수 (현재 {ship4.lnowea}) => ", default=-1)
                if 0 <= v <= 0xFF:
                    ship4.lnowea = v
            # 그 외는 무시.

        # 저장.
        try:
            with path.open("r+b") as fp:
                fp.seek(offset)
                fp.write(ship4.to_bytes())
            print(f"저장 완료 (offset 0x{offset:X}, 12 byte).")
        except OSError as e:
            print(f"쓰기 실패: {e}")


# ---------------------------------------------------------------------------
# 메뉴 4: Ship5 ROM 편집 (확정)
# ---------------------------------------------------------------------------

def _edit_ship5_rom(state: EditorState, path: Path) -> None:
    while True:
        idx = _select_ship(state, "어느 배를 편집하시겠습니까? => ")
        if idx < 0:
            return

        offset = MAINEXE_SHIP5_ROM + idx * Ship5.SIZE
        try:
            with path.open("rb") as fp:
                fp.seek(offset)
                ship5 = Ship5.from_bytes(fp.read(Ship5.SIZE))
        except OSError as e:
            print(f"읽기 실패: {e}")
            return

        while True:
            cur_name = decode_kr(ship5.name)
            bform_hi = (ship5.bform >> 4) & 0x0F
            print()
            print(f"--- Ship5 ROM 편집: [{idx + 1}] {_ship_name(state, idx)} ---")
            print(" 0) 저장하고 빠져나간다")
            print(f" 1) 함선 이름 (name)              : {cur_name}")
            print(f" 2) 평상시 외형 (sform)           : {ship5.sform}")
            print(f" 3) 부울때 외형 (bform 상위 4비트): {bform_hi}")
            print()

            i = _ask_int("번호 선택 => ", default=-1)
            if i == 0:
                break
            if i == 1:
                new_name = _ask_str(f"  새 이름 (현재 {cur_name}) => ")
                # 빈 입력이면 변경하지 않음.
                if new_name != "":
                    ship5.name = encode_kr_fixed(new_name, 18)
            elif i == 2:
                v = _ask_int(f"  평상시 외형 (현재 {ship5.sform}) => ", default=-1)
                if 0 <= v <= 0xFF:
                    ship5.sform = v
            elif i == 3:
                v = _ask_int(
                    f"  부울때 외형 0..15 (현재 {bform_hi}) => ",
                    default=-1,
                )
                if 0 <= v <= 0x0F:
                    # 상위 4비트만 교체.
                    ship5.bform = ((v & 0x0F) << 4) | (ship5.bform & 0x0F)
            # 그 외는 무시.

        # 저장.
        try:
            with path.open("r+b") as fp:
                fp.seek(offset)
                fp.write(ship5.to_bytes())
            # ship_name 캐시 갱신 (다른 메뉴 표시에도 반영).
            if 0 <= idx < len(state.ship_name):
                state.ship_name[idx] = decode_kr(ship5.name)
            print(f"저장 완료 (offset 0x{offset:X}, 25 byte).")
        except OSError as e:
            print(f"쓰기 실패: {e}")


# ---------------------------------------------------------------------------
# 메인 메뉴
# ---------------------------------------------------------------------------

def game_settings_menu(state: EditorState) -> None:
    while True:
        print()
        print("=== 게임 기본 설정 변경 ===")
        print("세이브 데이터(KOUKAI2.DAT)가 아닌 게임 실행 데이터(MAIN.EXE)를 직접 수정합니다.")
        print("편집은 즉시 디스크에 반영되며 되돌릴 수 없습니다.")
        print("경고: MAIN.EXE 를 백업해 두세요. 같은 폴더의 MAIN.EXE.bak 가 원본입니다.")
        print()
        print(" 0) 돌아가기")
        print(" 1) 함선 신조 - 항구 공업 수치 요건 편집  [추정 위치 — 검증 필요]")
        print(" 2) 함선 신조 - 신조 시 최대 내구도 편집  [추정 위치 — 검증 필요]")
        print(" 3) 함선 정적 스펙(Ship4 ROM) 편집        [확정 위치]")
        print(" 4) 함선 이름·외형(Ship5 ROM) 편집        [확정 위치]")
        print()

        sel = _ask_int("선택 => ", default=-1)
        if sel == 0:
            return
        if sel < 1 or sel > 4:
            continue

        path = _resolve_mainexe(state)
        if path is None:
            print("MAIN.EXE 를 찾지 못했습니다.")
            continue

        if sel == 1:
            if not _confirm_estimated("함선 신조: 항구 공업 수치 요건 편집"):
                continue
            _edit_u16_table(
                state, path, MAINEXE_KOGYO_TABLE,
                "함선 신조: 항구 공업 수치 요건 편집",
            )
        elif sel == 2:
            if not _confirm_estimated("함선 신조: 최대 내구도 편집"):
                continue
            _edit_u16_table(
                state, path, MAINEXE_LHULL_TABLE,
                "함선 신조: 최대 내구도 편집",
            )
        elif sel == 3:
            _edit_ship4_rom(state, path)
        elif sel == 4:
            _edit_ship5_rom(state, path)
