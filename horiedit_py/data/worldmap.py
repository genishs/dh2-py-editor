"""WORLDMAP 대륙 파일(worldmap.000/.001/.002 = LS11 항목 3개) 구조 — analysis_P 참조.

대륙 파일 하나(해제본):
  0x0000~0x0A8B  2바이트 LE × 1350 = 「4분할 맵」 시작 오프셋 표 (30 가로 × 45 세로)
                 오프셋은 0x0A8C(= DATA_BASE)를 0 으로 본다. 단조 증가.
  0x0A8C~        4분할 맵 데이터. 맵 하나 = 12×12 = 144 타일.
    첫 바이트 b0
      b0 & 0x80 != 0 : 맵 전체가 단일 타일(b0 & 0x7F) — 1바이트로 끝 (균일 맵)
      b0 & 0x80 == 0 : b0 = 기본 타일 코드, 이어서
                       18바이트 비트마스크(144비트, 타일 0 = 첫 바이트의 MSB, 행 우선)
                       + 마스크가 1 인 타일마다 코드 1바이트 (타일 번호 순)
                       마스크 0 인 타일 = 기본 타일 b0
  표 위치 = ((세로-1)*30 + (가로-1)) * 2   (세로·가로는 1 시작)

세 대륙 파일 × 1350 맵 전부에서 「길이 == 1」(균일) 또는 「길이 == 19 + 마스크의 1 개수」
임을 확인했다 (analysis_P §3).

print/input 금지.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

DATA_BASE = 0x0A8C
GRID_W = 30
GRID_H = 45
NUM_MAPS = GRID_W * GRID_H  # 1350
TILES_W = 12
TILES_PER_MAP = TILES_W * TILES_W  # 144
MASK_BYTES = 18
CANAL_WATER = 0xFF  # 카페 패치가 운하 타일에 쓰는 코드(원본 코드는 최대 0xB7)


class WorldmapError(ValueError):
    pass


def table_pos(row: int, col: int) -> int:
    """(세로, 가로) — 1 시작 — 의 표 위치(바이트)."""
    if not (1 <= row <= GRID_H and 1 <= col <= GRID_W):
        raise WorldmapError("세로/가로 범위 밖")
    return ((row - 1) * GRID_W + (col - 1)) * 2


def offsets(part: bytes) -> Tuple[int, ...]:
    if len(part) < DATA_BASE:
        raise WorldmapError("대륙 파일이 표보다 짧음")
    return struct.unpack_from("<%dH" % NUM_MAPS, part, 0)


def map_range(part: bytes, index: int) -> Tuple[int, int]:
    """맵 index(0~1349)의 [시작, 끝) 파일 내 절대 오프셋."""
    offs = offsets(part)
    start = DATA_BASE + offs[index]
    end = DATA_BASE + (offs[index + 1] if index + 1 < NUM_MAPS else len(part) - DATA_BASE)
    return start, end


def map_index_of(part: bytes, offset: int) -> int:
    """파일 내 절대 오프셋이 속한 맵 번호."""
    offs = offsets(part)
    rel = offset - DATA_BASE
    if rel < 0 or rel >= len(part) - DATA_BASE:
        raise WorldmapError("데이터 영역 밖")
    lo, hi = 0, NUM_MAPS - 1
    while lo < hi:  # offs[i] <= rel 인 마지막 i
        mid = (lo + hi + 1) // 2
        if offs[mid] <= rel:
            lo = mid
        else:
            hi = mid - 1
    return lo


@dataclass
class QuadMap:
    index: int
    start: int            # 파일 내 절대 오프셋
    end: int              # 끝(미포함)
    first: int            # 첫 바이트
    uniform: bool         # True 면 맵 전체가 단일 타일
    default: int          # 기본(또는 단일) 타일 코드
    mask: bytes           # 18바이트 (uniform 이면 빈 바이트열)
    tiles: Dict[int, Tuple[int, int]]  # 타일번호 -> (코드, 파일 내 절대 오프셋); 마스크 1 인 것만

    @property
    def row_col(self) -> Tuple[int, int]:
        """(세로, 가로) 1 시작."""
        return self.index // GRID_W + 1, self.index % GRID_W + 1


def parse_map(part: bytes, index: int) -> QuadMap:
    start, end = map_range(part, index)
    first = part[start]
    if first & 0x80:
        if end - start != 1:
            raise WorldmapError(f"균일 맵 {index} 길이 {end - start} != 1")
        return QuadMap(index, start, end, first, True, first & 0x7F, b"", {})
    mask = bytes(part[start + 1:start + 1 + MASK_BYTES])
    ones = sum(bin(b).count("1") for b in mask)
    if end - start != 1 + MASK_BYTES + ones:
        raise WorldmapError(
            f"맵 {index} 길이 {end - start} != 1+18+{ones} (마스크 불일치)")
    tiles: Dict[int, Tuple[int, int]] = {}
    pos = start + 1 + MASK_BYTES
    for t in range(TILES_PER_MAP):
        if mask[t >> 3] & (0x80 >> (t & 7)):
            tiles[t] = (part[pos], pos)
            pos += 1
    return QuadMap(index, start, end, first, False, first, mask, tiles)


def render_map(qm: QuadMap) -> str:
    """12×12 격자 두 장 — 16진 코드 격자와 기호 격자 — 을 문자열로.

    16진 격자: 코드 있는 타일 = 2자리 16진, 기본 타일 = `..`
    기호 격자: `.` 기본 타일(맵 바깥쪽 바다 계열로 보임), `#` 코드 타일, `=` 코드 0xFF(운하 물)
    """
    if qm.uniform:
        return f"(균일 맵, 단일 타일 0x{qm.default:02x})"
    lines = []
    hexrows = []
    symrows = []
    for r in range(TILES_W):
        hx = []
        sy = []
        for c in range(TILES_W):
            t = r * TILES_W + c
            if t in qm.tiles:
                code = qm.tiles[t][0]
                hx.append("%02x" % code)
                sy.append("=" if code == CANAL_WATER else "#")
            else:
                hx.append("..")
                sy.append(".")
        hexrows.append(" ".join(hx))
        symrows.append(" ".join(sy))
    lines.append("      " + " ".join("%2d" % c for c in range(TILES_W)) + "     |      " +
                 " ".join("%d" % (c % 10) for c in range(TILES_W)))
    for r in range(TILES_W):
        lines.append("  %2d  %s   |  %2d  %s" % (r, hexrows[r], r, symrows[r]))
    return "\n".join(lines)
