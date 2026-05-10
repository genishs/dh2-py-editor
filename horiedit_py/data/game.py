"""MAIN.EXE 와 슬롯의 게임 기본 설정 데이터 액세스.

실패 시 OSError 발생 (파일 없음/짧음 등). 추정 위치는 상수명에 ESTIMATED 표기.
"""

from __future__ import annotations

import struct
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from horiedit_py.common import Ship4, Ship5

if TYPE_CHECKING:
    from horiedit_py.common import EditorState


# === 분석가 결과 (analysis_C 확정) ===
MAINEXE_SHIP4_ROM = 0x40871   # Ship4 ROM 25개 (12 byte × 25)
MAINEXE_SHIP5_ROM = 0x405FD   # Ship5 ROM 25개 (25 byte × 25)
# 추정 — 검증되지 않음, UI 가 경고 표시
MAINEXE_KOGYO_TABLE_ESTIMATED = 0x42722
MAINEXE_LHULL_TABLE_ESTIMATED = 0x424AE
MAINEXE_TABLE_LEN = 25


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


# === 추정 테이블 (uint16 LE × 25) ===

def load_u16_table(main_exe: Path, base_offset: int) -> list[int]:
    n = MAINEXE_TABLE_LEN
    with main_exe.open("rb") as fp:
        fp.seek(base_offset)
        raw = fp.read(2 * n)
    if len(raw) < 2 * n:
        raise OSError(f"MAIN.EXE 가 너무 짧습니다 (table @ 0x{base_offset:X}).")
    return list(struct.unpack(f"<{n}H", raw))


def save_u16_table_one(main_exe: Path, base_offset: int, idx: int, value: int) -> None:
    if not (0 <= idx < MAINEXE_TABLE_LEN):
        raise IndexError(f"idx 는 0..{MAINEXE_TABLE_LEN - 1} 범위여야 합니다: {idx}")
    with main_exe.open("r+b") as fp:
        fp.seek(base_offset + idx * 2)
        fp.write(struct.pack("<H", value & 0xFFFF))
        fp.flush()


def main_exe_path(state: "EditorState") -> Optional[Path]:
    """state.game_dir / 'MAIN.EXE' 가 존재하면 그 경로, 아니면 None."""
    if state.game_dir is None:
        return None
    p = Path(state.game_dir) / "MAIN.EXE"
    return p if p.is_file() else None


# === 슬롯 내 등장공업치 (analysis_D, 추정) ===

KOGYO_OFFSET_IN_SLOT = 0x06FEB    # uint16 LE × 25, 표시값 = 저장값 × 10


def load_kogyo_table(state: "EditorState") -> list[int]:
    """현재 슬롯의 등장공업치 25개 (저장값. 표시는 ×10 가정)."""
    raw = state.read(state.page + KOGYO_OFFSET_IN_SLOT, 2 * MAINEXE_TABLE_LEN)
    if len(raw) < 2 * MAINEXE_TABLE_LEN:
        raise OSError(
            f"세이브가 너무 짧습니다 (kogyo @ 0x{state.page + KOGYO_OFFSET_IN_SLOT:X})."
        )
    return list(struct.unpack(f"<{MAINEXE_TABLE_LEN}H", raw))


def save_kogyo_one(state: "EditorState", ship_type: int, stored: int) -> None:
    _check_ship_type(ship_type)
    offset = state.page + KOGYO_OFFSET_IN_SLOT + ship_type * 2
    state.write(offset, (stored & 0xFFFF).to_bytes(2, "little"))
