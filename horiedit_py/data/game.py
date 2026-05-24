"""MAIN.EXE 와 슬롯의 게임 기본 설정 데이터 액세스.

실패 시 OSError 발생 (파일 없음/짧음 등).
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from horiedit_py.common import Ship4, Ship5

if TYPE_CHECKING:
    from horiedit_py.common import EditorState


# === Ship4/Ship5 ROM 위치 (analysis_F 정정 — 확정) ===
# Ship4 ROM 은 record (analysis_G) 의 +2 (lrudder 시작) 와 동일 주소.
MAINEXE_SHIP4_ROM = 0x0407DA   # Ship4 ROM 25개 (12 byte × 25). record + 2.
MAINEXE_SHIP5_ROM = 0x040566   # Ship5 ROM 25개 (25 byte × 25)

MAINEXE_TABLE_LEN = 25


# === 함선 record (analysis_G 확정) ===
# 함선당 12 byte × 25 record. horiedit.h 의 ship4_addr (0x5291) 은 record 의
# +2 (lrudder) 부터 시작 — off-by-2 였음을 analysis_G 에서 발견.
# 첫 두 byte 는 [kogyo_stored, lhull] 로 horiedit 가 다루지 않던 영역.
MAINEXE_SHIP_RECORD_ROM = 0x0407D8        # MAIN.EXE record ROM (12 × 25 = 300 byte)
SHIP_RECORD_OFFSET_IN_SLOT = 0x528F       # KOUKAI2.DAT 슬롯 N 내 record 시작
SHIP_RECORD_SIZE = 12

# === 선박 가격 + 선박 분류 (analysis_H 확정) ===
# record +9 (1 byte) = ship_class (선박 분류 0..5)
# record +10..+11 (2 byte u16 LE, ×10 표시) = price_stored
# (analysis_G 의 none[3] 영역은 사실 [ship_class, price_stored_lo, price_stored_hi].)
SHIP_CLASS_OFFSET_IN_RECORD = 9
PRICE_OFFSET_IN_RECORD = 10
PRICE_SCALE = 10  # 표시값 = stored × 10
PRICE_MAX_DISPLAY = 0xFFFF * PRICE_SCALE  # 655,350


# 폐기된 추정 (analysis_G 에서 record 구조 발견 → 추정 위치는 잘못된 것으로 확정):
# - MAINEXE_KOGYO_TABLE_ESTIMATED = 0x42722  (analysis_C, 항구 카탈로그였음)
# - KOGYO_OFFSET_IN_SLOT = 0x06FEB           (analysis_D, ×10 ≠ 검증값)
# - MAINEXE_LHULL_TABLE_ESTIMATED = 0x424AE  (analysis_C)
# - MAINEXE_LHULL_CANDIDATE = 0x4252A        (analysis_E)
# 위 위치 기반의 load_kogyo_table / save_kogyo_one / load_u16_table /
# save_u16_table_one / load/save_lhull_candidate 함수들도 함께 제거됨.
# 등장공업치/최대 내구도는 위 record 의 +0 / +1 byte 로 편집한다.


def _check_ship_type(ship_type: int) -> None:
    if not (0 <= ship_type < MAINEXE_TABLE_LEN):
        raise IndexError(f"ship_type 은 0..{MAINEXE_TABLE_LEN - 1} 범위여야 합니다: {ship_type}")


# === Ship4/Ship5 ROM (확정) ===

def load_ship4_rom(main_exe: Path, ship_type: int) -> Ship4:
    _check_ship_type(ship_type)
    offset = MAINEXE_SHIP4_ROM + ship_type * Ship4.SIZE
    with main_exe.open("rb") as fp:
        fp.seek(offset)
        data = fp.read(Ship4.SIZE)
    if len(data) < Ship4.SIZE:
        raise OSError(f"MAIN.EXE 가 너무 짧습니다 (Ship4 @ 0x{offset:X}).")
    return Ship4.from_bytes(data)


def save_ship4_rom(main_exe: Path, ship_type: int, ship4: Ship4) -> None:
    _check_ship_type(ship_type)
    offset = MAINEXE_SHIP4_ROM + ship_type * Ship4.SIZE
    with main_exe.open("r+b") as fp:
        fp.seek(offset)
        fp.write(ship4.to_bytes())
        fp.flush()


def load_ship5_rom(main_exe: Path, ship_type: int) -> Ship5:
    _check_ship_type(ship_type)
    offset = MAINEXE_SHIP5_ROM + ship_type * Ship5.SIZE
    with main_exe.open("rb") as fp:
        fp.seek(offset)
        data = fp.read(Ship5.SIZE)
    if len(data) < Ship5.SIZE:
        raise OSError(f"MAIN.EXE 가 너무 짧습니다 (Ship5 @ 0x{offset:X}).")
    return Ship5.from_bytes(data)


def save_ship5_rom(main_exe: Path, ship_type: int, ship5: Ship5) -> None:
    _check_ship_type(ship_type)
    offset = MAINEXE_SHIP5_ROM + ship_type * Ship5.SIZE
    with main_exe.open("r+b") as fp:
        fp.seek(offset)
        fp.write(ship5.to_bytes())
        fp.flush()


def main_exe_path(state: "EditorState") -> Optional[Path]:
    """state.game_dir / 'MAIN.EXE' 가 존재하면 그 경로, 아니면 None."""
    if state.game_dir is None:
        return None
    p = Path(state.game_dir) / "MAIN.EXE"
    return p if p.is_file() else None


# === 슬롯 내 함선 record (analysis_G + analysis_H 확정) ===
#
# record 레이아웃 (12 byte, 모든 byte 가 의미 있음):
#   +0  kogyo_stored   (u8, 표시값 = 저장값 × 10)
#   +1  lhull          (u8 직접)
#   +2  lrudder        (u8) ─┐
#   +3  lsail          (u8)  │
#   +4  lcrew_stored   (u8)  │ Ship4 (12 byte) 와 동일 영역
#   +5  dcrew          (u8)  │ ─ 단 마지막 2 byte 가 다음 함선의
#   +6  capacity       (u16) │   [kogyo, lhull] 로 겹침에 유의.
#   +8  lnowea         (u8)  │
#   +9  ship_class     (u8) ─┘ 선박 분류 0..5 (analysis_H)
#   +10 price_stored   (u16 LE) 표시 가격 = stored × 10 (analysis_H)


def load_record_kogyo(state: "EditorState", ship_type: int) -> int:
    """슬롯의 record +0 byte (kogyo_stored). 표시값 = 저장값 × 10."""
    _check_ship_type(ship_type)
    offset = state.page + SHIP_RECORD_OFFSET_IN_SLOT + ship_type * SHIP_RECORD_SIZE
    raw = state.read(offset, 1)
    if len(raw) < 1:
        raise OSError(f"세이브가 너무 짧습니다 (record kogyo @ 0x{offset:X}).")
    return raw[0]


def save_record_kogyo(state: "EditorState", ship_type: int, stored: int) -> None:
    """record +0 byte 갱신 (u8). 입력은 stored = 표시값 // 10."""
    _check_ship_type(ship_type)
    offset = state.page + SHIP_RECORD_OFFSET_IN_SLOT + ship_type * SHIP_RECORD_SIZE
    state.write(offset, bytes([stored & 0xFF]))


def load_record_lhull(state: "EditorState", ship_type: int) -> int:
    """슬롯의 record +1 byte (lhull, u8 직접)."""
    _check_ship_type(ship_type)
    offset = state.page + SHIP_RECORD_OFFSET_IN_SLOT + ship_type * SHIP_RECORD_SIZE + 1
    raw = state.read(offset, 1)
    if len(raw) < 1:
        raise OSError(f"세이브가 너무 짧습니다 (record lhull @ 0x{offset:X}).")
    return raw[0]


def save_record_lhull(state: "EditorState", ship_type: int, lhull: int) -> None:
    """record +1 byte 갱신 (u8)."""
    _check_ship_type(ship_type)
    offset = state.page + SHIP_RECORD_OFFSET_IN_SLOT + ship_type * SHIP_RECORD_SIZE + 1
    state.write(offset, bytes([lhull & 0xFF]))


# === MAIN.EXE record ROM (analysis_G 확정) ===

def load_rom_record_kogyo(main_exe: Path, ship_type: int) -> int:
    """MAIN.EXE record ROM 의 +0 byte (kogyo_stored)."""
    _check_ship_type(ship_type)
    offset = MAINEXE_SHIP_RECORD_ROM + ship_type * SHIP_RECORD_SIZE
    with main_exe.open("rb") as fp:
        fp.seek(offset)
        data = fp.read(1)
    if len(data) < 1:
        raise OSError(f"MAIN.EXE 가 너무 짧습니다 (record kogyo @ 0x{offset:X}).")
    return data[0]


def save_rom_record_kogyo(main_exe: Path, ship_type: int, stored: int) -> None:
    """MAIN.EXE record ROM 의 +0 byte 갱신 (u8). 입력은 stored = 표시값 // 10."""
    _check_ship_type(ship_type)
    offset = MAINEXE_SHIP_RECORD_ROM + ship_type * SHIP_RECORD_SIZE
    with main_exe.open("r+b") as fp:
        fp.seek(offset)
        fp.write(bytes([stored & 0xFF]))
        fp.flush()


def load_rom_record_lhull(main_exe: Path, ship_type: int) -> int:
    """MAIN.EXE record ROM 의 +1 byte (lhull, u8)."""
    _check_ship_type(ship_type)
    offset = MAINEXE_SHIP_RECORD_ROM + ship_type * SHIP_RECORD_SIZE + 1
    with main_exe.open("rb") as fp:
        fp.seek(offset)
        data = fp.read(1)
    if len(data) < 1:
        raise OSError(f"MAIN.EXE 가 너무 짧습니다 (record lhull @ 0x{offset:X}).")
    return data[0]


def save_rom_record_lhull(main_exe: Path, ship_type: int, lhull: int) -> None:
    """MAIN.EXE record ROM 의 +1 byte 갱신 (u8)."""
    _check_ship_type(ship_type)
    offset = MAINEXE_SHIP_RECORD_ROM + ship_type * SHIP_RECORD_SIZE + 1
    with main_exe.open("r+b") as fp:
        fp.seek(offset)
        fp.write(bytes([lhull & 0xFF]))
        fp.flush()


# === 선박 가격 / 선박 분류 (analysis_H 확정) ===
#
# 슬롯 record:
#   +9      ship_class    u8       (0..5 의 6 가지)
#   +10..11 price_stored  u16 LE   (표시 가격 = stored × 10, 0..655,350)
#
# MAIN.EXE record ROM 도 동일한 record 레이아웃 (record ROM = 0x0407D8) 을 가진다.


def load_record_ship_class(state: "EditorState", ship_type: int) -> int:
    """슬롯 record +9 byte (선박 분류 0..5)."""
    _check_ship_type(ship_type)
    offset = (
        state.page + SHIP_RECORD_OFFSET_IN_SLOT
        + ship_type * SHIP_RECORD_SIZE + SHIP_CLASS_OFFSET_IN_RECORD
    )
    raw = state.read(offset, 1)
    if len(raw) < 1:
        raise OSError(f"세이브가 너무 짧습니다 (record ship_class @ 0x{offset:X}).")
    return raw[0]


def save_record_ship_class(state: "EditorState", ship_type: int, ship_class: int) -> None:
    """슬롯 record +9 byte 갱신 (u8). 입력은 0..255 (보통 0..5)."""
    _check_ship_type(ship_type)
    if not (0 <= ship_class <= 0xFF):
        raise ValueError("선박 분류는 0..255 범위여야 합니다.")
    offset = (
        state.page + SHIP_RECORD_OFFSET_IN_SLOT
        + ship_type * SHIP_RECORD_SIZE + SHIP_CLASS_OFFSET_IN_RECORD
    )
    state.write(offset, bytes([ship_class & 0xFF]))


def load_record_price(state: "EditorState", ship_type: int) -> int:
    """슬롯 record +10..+11 의 u16 LE × 10 = 표시 가격 (0..655,350)."""
    _check_ship_type(ship_type)
    offset = (
        state.page + SHIP_RECORD_OFFSET_IN_SLOT
        + ship_type * SHIP_RECORD_SIZE + PRICE_OFFSET_IN_RECORD
    )
    raw = state.read(offset, 2)
    if len(raw) < 2:
        raise OSError(f"세이브가 너무 짧습니다 (record price @ 0x{offset:X}).")
    return int.from_bytes(raw, "little") * PRICE_SCALE


def save_record_price(state: "EditorState", ship_type: int, price_display: int) -> None:
    """슬롯 record +10..+11 갱신. 입력은 표시값 (10 의 배수, 0..655,350)."""
    _check_ship_type(ship_type)
    if price_display < 0 or price_display > PRICE_MAX_DISPLAY:
        raise ValueError(f"선박 가격 범위 초과 (0..{PRICE_MAX_DISPLAY}).")
    if price_display % PRICE_SCALE != 0:
        raise ValueError(f"선박 가격은 {PRICE_SCALE} 의 배수여야 합니다.")
    stored = price_display // PRICE_SCALE
    if not (0 <= stored <= 0xFFFF):
        raise ValueError("선박 가격 stored 가 u16 범위를 벗어났습니다.")
    offset = (
        state.page + SHIP_RECORD_OFFSET_IN_SLOT
        + ship_type * SHIP_RECORD_SIZE + PRICE_OFFSET_IN_RECORD
    )
    state.write(offset, stored.to_bytes(2, "little"))


def load_rom_record_ship_class(main_exe: Path, ship_type: int) -> int:
    """MAIN.EXE record ROM 의 +9 byte (선박 분류 0..5)."""
    _check_ship_type(ship_type)
    offset = MAINEXE_SHIP_RECORD_ROM + ship_type * SHIP_RECORD_SIZE + SHIP_CLASS_OFFSET_IN_RECORD
    with main_exe.open("rb") as fp:
        fp.seek(offset)
        data = fp.read(1)
    if len(data) < 1:
        raise OSError(f"MAIN.EXE 가 너무 짧습니다 (record ship_class @ 0x{offset:X}).")
    return data[0]


def save_rom_record_ship_class(main_exe: Path, ship_type: int, ship_class: int) -> None:
    """MAIN.EXE record ROM 의 +9 byte 갱신 (u8)."""
    _check_ship_type(ship_type)
    if not (0 <= ship_class <= 0xFF):
        raise ValueError("선박 분류는 0..255 범위여야 합니다.")
    offset = MAINEXE_SHIP_RECORD_ROM + ship_type * SHIP_RECORD_SIZE + SHIP_CLASS_OFFSET_IN_RECORD
    with main_exe.open("r+b") as fp:
        fp.seek(offset)
        fp.write(bytes([ship_class & 0xFF]))
        fp.flush()


def load_rom_record_price(main_exe: Path, ship_type: int) -> int:
    """MAIN.EXE record ROM 의 +10..+11 (u16 LE × 10 = 표시 가격)."""
    _check_ship_type(ship_type)
    offset = MAINEXE_SHIP_RECORD_ROM + ship_type * SHIP_RECORD_SIZE + PRICE_OFFSET_IN_RECORD
    with main_exe.open("rb") as fp:
        fp.seek(offset)
        data = fp.read(2)
    if len(data) < 2:
        raise OSError(f"MAIN.EXE 가 너무 짧습니다 (record price @ 0x{offset:X}).")
    return int.from_bytes(data, "little") * PRICE_SCALE


def save_rom_record_price(main_exe: Path, ship_type: int, price_display: int) -> None:
    """MAIN.EXE record ROM 의 +10..+11 갱신. 입력은 표시값 (10 의 배수, 0..655,350)."""
    _check_ship_type(ship_type)
    if price_display < 0 or price_display > PRICE_MAX_DISPLAY:
        raise ValueError(f"선박 가격 범위 초과 (0..{PRICE_MAX_DISPLAY}).")
    if price_display % PRICE_SCALE != 0:
        raise ValueError(f"선박 가격은 {PRICE_SCALE} 의 배수여야 합니다.")
    stored = price_display // PRICE_SCALE
    if not (0 <= stored <= 0xFFFF):
        raise ValueError("선박 가격 stored 가 u16 범위를 벗어났습니다.")
    offset = MAINEXE_SHIP_RECORD_ROM + ship_type * SHIP_RECORD_SIZE + PRICE_OFFSET_IN_RECORD
    with main_exe.open("r+b") as fp:
        fp.seek(offset)
        fp.write(stored.to_bytes(2, "little"))
        fp.flush()


# ===========================================================================
# 신조 내구도 cap (issue #5, analysis_N) — v0.4.13
# ===========================================================================
#
# 조선소 신조 메뉴에서 청구 내구력은 표준 내구력 × 재질 계수 (0.8..1.3) 로
# 계산된다. 그러나 그 결과가 100 을 넘으면 100 으로 절단된다.
# MAIN.EXE 의 신조 코드는 다음 패턴:
#
#   B9 0A 00 99 F7 F9 BA 64 00 9A 40 4D 00 00
#   ^MOV CX,10   ^IDIV CX      ^CALL FAR 0000:4D40
#               ^CWD     ^MOV DX, 100 (cap byte)
#
# 즉 "(어떤 값) / 10" 후 "MOV DX, 100" 으로 cap 적재 + CALL.
# 한국어 빌드에서 2 곳 (offset 0x30893, 0x30A20).
#
# 비슷한 signature 가 다른 곳 (예: MOV CX,100 으로 IDIV) 에도 있지만 그건
# 다른 시스템의 cap (의미 불명) 이므로 'MOV CX,10' 으로 시작하는 패턴만 매칭.

HULL_CAP_SIG_BEFORE = bytes.fromhex("B90A0099F7F9BA")      # MOV CX,10 + CWD + IDIV CX + MOV DX
HULL_CAP_SIG_AFTER = bytes.fromhex("009A404D0000")         # MOV DX 의 imm 상위 + CALL FAR
HULL_CAP_DEFAULT = 100


def find_hull_cap_offsets(main_exe: Path) -> list[int]:
    """MAIN.EXE 안에서 신조 cap byte 의 offset 리스트.

    패턴: 'B9 0A 00 99 F7 F9 BA ?? 00 9A 40 4D 00 00' — '?' 가 cap byte.
    한국어 빌드 기준 보통 2 곳.
    """
    data = main_exe.read_bytes()
    out: list[int] = []
    pos = 0
    sig_len = len(HULL_CAP_SIG_BEFORE)
    after_len = len(HULL_CAP_SIG_AFTER)
    while True:
        idx = data.find(HULL_CAP_SIG_BEFORE, pos)
        if idx < 0:
            break
        imm_off = idx + sig_len
        after_off = imm_off + 1
        if data[after_off:after_off + after_len] == HULL_CAP_SIG_AFTER:
            out.append(imm_off)
        pos = idx + 1
    return out


def load_hull_caps(main_exe: Path) -> list[tuple[int, int]]:
    """[(offset, value)] 리스트. 자동 탐색."""
    offsets = find_hull_cap_offsets(main_exe)
    if not offsets:
        return []
    data = main_exe.read_bytes()
    return [(o, data[o]) for o in offsets]


def save_hull_caps(main_exe: Path, offset_value_pairs: list[tuple[int, int]]) -> None:
    """주어진 (offset, value) 들을 MAIN.EXE 에 일괄 쓴다.

    각 value 는 0..255 범위. offset 은 find_hull_cap_offsets 가 반환한 값이어야
    안전 (signature 검증된 위치).
    """
    for off, val in offset_value_pairs:
        if not (0 <= val <= 0xFF):
            raise ValueError(f"cap 은 0..255 범위여야 합니다: {val}")
    with main_exe.open("r+b") as fp:
        for off, val in offset_value_pairs:
            fp.seek(off)
            fp.write(bytes([val & 0xFF]))
        fp.flush()


HULL_CAP_BACKUP_SUFFIX = ".EXE.beforeHullCap"


def hull_cap_backup_path(main_exe: Path) -> Path:
    """백업 파일 경로 — MAIN.EXE 옆에 .EXE.beforeHullCap."""
    return main_exe.with_suffix(HULL_CAP_BACKUP_SUFFIX)


def ensure_hull_cap_backup(main_exe: Path) -> Path:
    """백업이 없으면 생성. 있으면 그대로. 백업 경로 반환."""
    backup = hull_cap_backup_path(main_exe)
    if not backup.exists():
        shutil.copy2(main_exe, backup)
    return backup


def restore_hull_cap_backup(main_exe: Path) -> bool:
    """백업 파일에서 MAIN.EXE 복원. 백업이 없으면 False."""
    backup = hull_cap_backup_path(main_exe)
    if not backup.exists():
        return False
    shutil.copy2(backup, main_exe)
    return True
