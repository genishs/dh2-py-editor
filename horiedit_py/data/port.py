"""항구 경제 (상업치/공업치) 편집 — analysis_I 기반.

테이블 위치 (slot 안):
  base   = port_econ_addr (0x5DE3)
  stride = PORT_ECON_RECORD (37 byte)
  size   = 130 × 37 = 4810 byte

record layout (확정 필드만):
  +0  u16 LE  commerce (상업치)
  +4  u16 LE  industry (공업치)

다른 필드 (+8.. 등) 은 분석 진행 중 — 본 모듈은 commerce/industry 만 다룬다.

API:
  load_port_econ(state, idx)          → (commerce, industry)
  save_port_econ(state, idx, c, i)    디스크에 c,i 만 in-place 갱신
  iter_port_econ(state)               130개 (idx, name, c, i) yield
"""
from __future__ import annotations

import struct
from typing import Iterator

from horiedit_py.common import EditorState, port_econ_addr, PORT_ECON_RECORD


NUM_PORTS = 130


def _check_idx(idx: int) -> None:
    if not (0 <= idx < NUM_PORTS):
        raise ValueError(f"port idx {idx} 가 0..{NUM_PORTS - 1} 범위를 벗어남")


def load_port_econ(state: EditorState, idx: int) -> tuple[int, int]:
    """반환: (commerce, industry)."""
    _check_idx(idx)
    base = state.page + port_econ_addr + idx * PORT_ECON_RECORD
    raw = state.read(base, 6)
    commerce, _pad, industry = struct.unpack("<HHH", raw)
    return commerce, industry


def save_port_econ(state: EditorState, idx: int, commerce: int, industry: int) -> None:
    """디스크에 commerce(@+0), industry(@+4) 만 갱신. +2/+3 padding 보존."""
    _check_idx(idx)
    if not (0 <= commerce <= 0xFFFF):
        raise ValueError(f"commerce {commerce} 가 0..65535 범위를 벗어남")
    if not (0 <= industry <= 0xFFFF):
        raise ValueError(f"industry {industry} 가 0..65535 범위를 벗어남")
    base = state.page + port_econ_addr + idx * PORT_ECON_RECORD
    state.write(base + 0, struct.pack("<H", commerce & 0xFFFF))
    state.write(base + 4, struct.pack("<H", industry & 0xFFFF))


def iter_port_econ(state: EditorState) -> Iterator[tuple[int, str, int, int]]:
    """모든 항구의 (idx, name, commerce, industry) yield."""
    for i in range(NUM_PORTS):
        c, ind = load_port_econ(state, i)
        name = state.port_name[i] if 0 <= i < len(state.port_name) else ""
        yield i, name, c, ind
