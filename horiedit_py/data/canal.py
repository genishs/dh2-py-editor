"""수에즈·파나마 운하 개통/원상복원 — WORLDMAP.LZW 바이트 패치 (analysis_P).

출처: 네이버 카페 「대항해시대 2 / 외전」 「수에즈 운하 패치 … 맵 HEX」
      https://cafe.naver.com/daehangs/49651  (그림 출처 언급: https://cafe.naver.com/daehangs/40602 수정가루 님)
      우리 판 원본·카페 패치본 대조로 전·후 값을 모두 확인함 (analysis_P §5~6).

운하 하나 = (대륙 파일 번호, 해제본 오프셋, 전 값, 후 값) 목록.
  전 = 원본(닫힘), 후 = 개통.
같은 길이의 바이트 치환뿐이라 맵 크기·오프셋 표는 변하지 않는다.

안전 규칙
  - 상태 판정: 모든 바이트가 「후」 → OPEN, 모두 「전」 → CLOSED, 그 밖(섞임·다른 값·
    위치 이상) → UNKNOWN. UNKNOWN 이면 어느 쪽으로도 바꾸지 않고 CanalError.
  - 운하별로 독립. 다른 운하·다른 바이트(예: 카페 패치의 제주·울릉·독도)는 건드리지 않는다.
  - 파일 쓰기는 백업(최초 1회, 덮어쓰지 않음) → 임시 파일 → 재해제 검증 → 교체.

print/input 금지. 에러는 CanalError / Ls11Error.
"""
from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple

from horiedit_py.data import ls11, worldmap

OPEN = "open"        # 개통
CLOSED = "closed"    # 원상(닫힘)
UNKNOWN = "unknown"  # 알 수 없음

BACKUP_SUFFIX = ".canal-orig"


class CanalError(ValueError):
    pass


@dataclass(frozen=True)
class Edit:
    file: int      # 0/1/2 = worldmap.000/.001/.002
    offset: int    # 해제본 안의 절대 오프셋
    before: int    # 닫힘(원본) 값
    after: int     # 개통 값


@dataclass(frozen=True)
class Canal:
    key: str
    name: str
    edits: Tuple[Edit, ...]
    map_checks: Tuple[Tuple[int, int, int], ...]  # (파일, 오프셋, 기대 4분할 맵 번호)


SUEZ = Canal(
    "suez", "수에즈 운하",
    (
        Edit(0, 0x3E5F, 0xAF, 0x6F),   # 마스크 바이트
        Edit(0, 0x3E60, 0xB3, 0xA7),   # 마스크 바이트
        Edit(0, 0x3E7B, 0x08, 0x0F),
        Edit(0, 0x3E7C, 0x0F, 0xFF),
        Edit(0, 0x3E86, 0x05, 0xFF),
        Edit(0, 0x3E8E, 0x01, 0xFF),
        Edit(0, 0x3E95, 0x0D, 0xFF),
        Edit(0, 0x3E98, 0x05, 0xFF),
        Edit(0, 0x3E9E, 0x04, 0xFF),
    ),
    ((0, 0x3E5F, 525), (0, 0x3E9E, 525)),
)

PANAMA = Canal(
    "panama", "파나마 운하",
    (
        Edit(2, 0x3F7A, 0x0F, 0xFF),   # 북쪽 (맵 736)
        Edit(2, 0x3F82, 0x0F, 0xFF),   # 북쪽 (맵 736)
        Edit(2, 0x40E5, 0x0C, 0xFF),   # 남쪽 (맵 766)
    ),
    ((2, 0x3F7A, 736), (2, 0x40E5, 766)),
)

CANALS: Dict[str, Canal] = {SUEZ.key: SUEZ, PANAMA.key: PANAMA}

#: 카페 패치에 함께 들어 있는 제주·울릉·독도 변경(worldmap.001, 해제본 오프셋, 전, 후).
#: 어떤 함수도 적용하지 않는다 — 「운하만 되돌릴 때 이 바이트가 그대로인지」 시험용 기록.
#: 글의 표기 2151/2152/2ca2 는 실측 2E51/2E52/2CA1 과 다르다 (analysis_P §6).
CAFE_EXTRA_EDITS: Tuple[Edit, ...] = (
    Edit(1, 0x2E2A, 0x0A, 0x00),
    Edit(1, 0x2E2B, 0x00, 0xC0),
    Edit(1, 0x2E51, 0x04, 0x07),
    Edit(1, 0x2E52, 0x04, 0x08),
    Edit(1, 0x2C9D, 0x00, 0x20),
    Edit(1, 0x2C9F, 0x01, 0x80),
    Edit(1, 0x2CA1, 0x20, 0x00),
)


def _canal(canal) -> Canal:
    if isinstance(canal, Canal):
        return canal
    try:
        return CANALS[canal]
    except KeyError:
        raise CanalError(f"알 수 없는 운하: {canal!r}") from None


# --------------------------------------------------------------------------
# 상태 판정 / 전환 (해제본 리스트 대상)
# --------------------------------------------------------------------------
def canal_state(parts: Sequence[bytes], canal) -> str:
    """OPEN / CLOSED / UNKNOWN. 모든 바이트가 후 → OPEN, 모두 전 → CLOSED."""
    c = _canal(canal)
    try:
        for f, off, idx in c.map_checks:
            if worldmap.map_index_of(parts[f], off) != idx:
                return UNKNOWN
        vals = [(parts[e.file][e.offset], e) for e in c.edits]
    except (IndexError, worldmap.WorldmapError):
        return UNKNOWN
    if all(v == e.after for v, e in vals):
        return OPEN
    if all(v == e.before for v, e in vals):
        return CLOSED
    return UNKNOWN


def canal_states(parts: Sequence[bytes]) -> Dict[str, str]:
    return {k: canal_state(parts, k) for k in CANALS}


def set_canal(parts: Sequence[bytes], canal, mode: str) -> List[bytes]:
    """운하 하나를 개통(mode=OPEN) 또는 원상복원(mode=CLOSED) 한 새 해제본 리스트.

    입력은 바꾸지 않는다. 현재 상태가 UNKNOWN 이면 CanalError (아무것도 바꾸지 않음).
    이미 목표 상태면 그대로 복사본을 돌려준다.
    """
    if mode not in (OPEN, CLOSED):
        raise CanalError(f"mode 는 {OPEN!r} 또는 {CLOSED!r}: {mode!r}")
    c = _canal(canal)
    state = canal_state(parts, c)
    if state == UNKNOWN:
        raise CanalError(
            f"{c.name}: 현재 바이트가 전/후 어느 쪽도 아님(섞임·다른 판) — 바꾸지 않음")
    new = [bytearray(p) for p in parts]
    if state != mode:
        for e in c.edits:
            new[e.file][e.offset] = e.after if mode == OPEN else e.before
    return [bytes(p) for p in new]


# --------------------------------------------------------------------------
# 파일 수준 (LS11 해제 → 패치 → 재압축)
# --------------------------------------------------------------------------
def read_worldmap(path: str) -> Tuple[bytes, List[bytes]]:
    """(사전, 해제본 3개). 항목 수가 3 이 아니면 CanalError."""
    with open(path, "rb") as f:
        raw = f.read()
    dictionary, _entries = ls11.parse_header(raw)
    parts = ls11.decode_pack(raw)
    if len(parts) != 3:
        raise CanalError(f"WORLDMAP 항목이 3개가 아님: {len(parts)}")
    return dictionary, parts


def file_canal_states(path: str) -> Dict[str, str]:
    _d, parts = read_worldmap(path)
    return canal_states(parts)


def apply_canal_to_file(path: str, canal, mode: str, backup: bool = True) -> str:
    """파일을 읽어 운하 하나를 전환해 같은 경로에 쓴다. 새 상태를 돌려준다.

    1) UNKNOWN 이면 거부(파일 그대로).
    2) backup=True 면 `<path>.canal-orig` 가 없을 때만 원본을 복사해 둔다(덮어쓰지 않음).
    3) 원본 사전·압축 방식(LZ 사용 여부)을 그대로 써서 재압축 → 다시 해제해 기대값과 대조
       → 임시 파일 → 교체.
       이미 목표 상태면 파일을 건드리지 않는다.
    """
    c = _canal(canal)
    with open(path, "rb") as f:
        raw = f.read()
    dictionary, _entries = ls11.parse_header(raw)
    parts = ls11.decode_pack(raw)
    if len(parts) != 3:
        raise CanalError(f"WORLDMAP 항목이 3개가 아님: {len(parts)}")
    if canal_state(parts, c) == mode:
        return mode
    new_parts = set_canal(parts, c, mode)
    # 원본 파일의 압축 방식을 따른다: LZ 를 쓴 파일(게임 원본)은 LZ, 리터럴만 쓴 파일(카페 패치본)은 리터럴만.
    window = ls11.MAX_DISTANCE if ls11.uses_lz(raw) else 0
    blob = ls11.encode_pack(new_parts, dictionary=dictionary, window=window)
    if ls11.decode_pack(blob) != new_parts:  # 방어: 압축기 오류가 게임 파일을 망치지 않게
        raise CanalError("재압축 검증 실패 — 파일을 바꾸지 않음")
    if backup:
        bak = path + BACKUP_SUFFIX
        if not os.path.exists(bak):
            shutil.copy2(path, bak)
    tmp = path + ".canal-tmp"
    with open(tmp, "wb") as f:
        f.write(blob)
    os.replace(tmp, path)
    return canal_state(new_parts, c)
