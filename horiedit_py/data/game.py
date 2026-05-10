"""MAIN.EXE 와 슬롯의 게임 기본 설정 데이터 액세스.

실패 시 OSError 발생 (파일 없음/짧음 등).
"""

from __future__ import annotations

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


# === 슬롯 내 함선 record (analysis_G 확정) ===
#
# record 레이아웃 (12 byte):
#   +0 kogyo_stored   (u8, 표시값 = 저장값 × 10)
#   +1 lhull          (u8 직접)
#   +2 lrudder        (u8) ─┐
#   +3 lsail          (u8)  │
#   +4 lcrew_stored   (u8)  │ Ship4 (12 byte) 와 동일 영역
#   +5 dcrew          (u8)  │ ─ 단 마지막 2 byte 가 다음 함선의
#   +6 capacity       (u16) │   [kogyo, lhull] 로 겹침에 유의.
#   +8 lnowea         (u8)  │
#   +9 none[3]        (3B) ─┘


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
