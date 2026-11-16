"""KOEI LS11 압축 컨테이너 — 해제/압축 (analysis_P 참조).

대항해시대 II 의 WORLDMAP.LZW 등 `*.LZW` 파일이 이 포맷이다.

파일 구조 (정수는 전부 빅엔디언):
  0x000  "LS11" + 12 바이트 0
  0x010  사전 256 바이트 — 심볼 번호(0~255) → 실제 바이트
  0x110  항목 표: 항목당 12 바이트 (압축크기, 해제크기, 시작주소), 압축크기==0 이면 끝
         (끝 표지 4바이트 0 포함)
  ...    각 항목의 비트 스트림 (시작주소부터 압축크기 바이트)

비트 스트림 (MSB 먼저):
  수 하나 = 「1 을 k 개 + 0 + (k+1) 비트 값」, 수 = (2^(k+1) - 2) + 값  (엘리아스 감마 변형)
  수 n < 256  : 리터럴, 출력 = 사전[n]
  수 n >= 256 : LZ 복사. 거리 = n - 256 (>=1), 이어지는 수 m 이 길이 = m + 3.
                현재 출력 위치에서 거리만큼 앞에서 바이트 단위로 복사 (겹침 허용).

출처 (LS11 Archiever 소스, Native/ls11_decode.cpp, ls11_encode.cpp):
  https://xn--rssu31gj1g.jp/?page=nobu_mod_the_ls11archiever

print/input 금지. 에러는 Ls11Error.
"""
from __future__ import annotations

import struct
from typing import List, Optional, Sequence, Tuple

MAGIC = b"LS11"
DICT_OFFSET = 0x10
TABLE_OFFSET = 0x110
ENTRY_SIZE = 12


class Ls11Error(ValueError):
    pass


# --------------------------------------------------------------------------
# 구조 파싱
# --------------------------------------------------------------------------
def parse_header(data: bytes) -> Tuple[bytes, List[Tuple[int, int, int]]]:
    """(사전 256B, [(압축크기, 해제크기, 시작주소), ...]) 반환."""
    if len(data) < TABLE_OFFSET + 4 or data[:4] != MAGIC:
        raise Ls11Error("LS11 헤더가 아님")
    dictionary = bytes(data[DICT_OFFSET:DICT_OFFSET + 256])
    entries: List[Tuple[int, int, int]] = []
    pos = TABLE_OFFSET
    while True:
        if pos + 4 > len(data):
            raise Ls11Error("항목 표 끝 표지 없음")
        if struct.unpack_from(">I", data, pos)[0] == 0:
            break
        if pos + ENTRY_SIZE > len(data):
            raise Ls11Error("항목 표 잘림")
        entries.append(struct.unpack_from(">III", data, pos))
        pos += ENTRY_SIZE
    for comp, _exp, start in entries:
        if start + comp > len(data):
            raise Ls11Error("항목 데이터가 파일 밖")
    return dictionary, entries


# --------------------------------------------------------------------------
# 해제
# --------------------------------------------------------------------------
def iter_tokens(stream: bytes, expanded_size: int):
    """비트 스트림을 토큰으로 푼다: ('L', 사전번호) / ('M', 거리, 길이).

    해제 크기가 expanded_size 에 도달하면 멈춘다(끝의 0 채움 비트는 읽지 않음).
    """
    total_bits = len(stream) * 8
    bitpos = 0
    produced = 0

    def read_bit() -> int:
        nonlocal bitpos
        if bitpos >= total_bits:
            raise Ls11Error("비트 스트림이 해제 크기 전에 끝남")
        b = (stream[bitpos >> 3] >> (7 - (bitpos & 7))) & 1
        bitpos += 1
        return b

    def read_number() -> int:
        k = 0
        while read_bit():
            k += 1
        value = 0
        for _ in range(k + 1):
            value = (value << 1) | read_bit()
        return (1 << (k + 1)) - 2 + value

    while produced < expanded_size:
        n = read_number()
        if n < 256:
            produced += 1
            yield ("L", n)
        else:
            length = read_number() + 3
            produced += length
            yield ("M", n - 256, length)


def decode_stream(stream: bytes, dictionary: bytes, expanded_size: int) -> bytes:
    """비트 스트림 하나를 해제한다."""
    out = bytearray()
    for t in iter_tokens(stream, expanded_size):
        if t[0] == "L":
            out.append(dictionary[t[1]])
        else:
            dist, length = t[1], t[2]
            if dist == 0 or dist > len(out):
                raise Ls11Error(f"잘못된 LZ 거리 {dist} (출력 {len(out)}B)")
            src = len(out) - dist
            for _ in range(length):
                out.append(out[src])
                src += 1
    if len(out) != expanded_size:
        raise Ls11Error(f"해제 크기 불일치: {len(out)} != {expanded_size}")
    return bytes(out)


def uses_lz(data: bytes) -> bool:
    """LS11 파일에 LZ 복사 토큰이 하나라도 있으면 True (False = 리터럴만 — 카페 패치본 방식)."""
    _d, entries = parse_header(data)
    for comp, exp, start in entries:
        for t in iter_tokens(data[start:start + comp], exp):
            if t[0] == "M":
                return True
    return False


def decode_pack(data: bytes) -> List[bytes]:
    """LS11 파일 전체 → 항목별 해제 데이터 리스트 (WORLDMAP 은 3개)."""
    dictionary, entries = parse_header(data)
    return [decode_stream(data[start:start + comp], dictionary, exp)
            for comp, exp, start in entries]


# --------------------------------------------------------------------------
# 압축
# --------------------------------------------------------------------------
#: LZ 최대 거리. 원본 WORLDMAP.LZW 3개 항목에서 관측한 최대 거리가 8190 이고
#: 8192 로 두면 원본 토큰열과 어긋난다 (analysis_P). 8190/8191 은 원본에서 구별 불가.
MAX_DISTANCE = 8190
MIN_MATCH = 3


def make_dictionary(parts: Sequence[bytes]) -> bytes:
    """전체 항목의 바이트 빈도 내림차순 사전. 동률은 바이트 값 오름차순.

    원본 사전은 같은 빈도 순이지만 동률 순서는 원본 도구의 정렬 구현에 따라 임의로
    갈린다(재현 불가) — 그래서 원본과 바이트 동일하게 다시 묶으려면 `dictionary=`
    인자로 원본 사전을 넘겨야 한다.
    """
    counts = [0] * 256
    for p in parts:
        for b in p:
            counts[b] += 1
    return bytes(sorted(range(256), key=lambda b: (-counts[b], b)))


class _BitWriter:
    def __init__(self) -> None:
        self.buf = bytearray()
        self.acc = 0
        self.nbits = 0

    def write(self, value: int, width: int) -> None:
        self.acc = (self.acc << width) | value
        self.nbits += width
        while self.nbits >= 8:
            self.nbits -= 8
            self.buf.append((self.acc >> self.nbits) & 0xFF)
        self.acc &= (1 << self.nbits) - 1

    def write_number(self, n: int) -> None:
        k = 0
        while n >= (2 << (k + 1)) - 2:
            k += 1
        # k 개의 1, 0, (k+1) 비트 값
        self.write(((1 << k) - 1) << 1, k + 1)
        self.write(n - ((2 << k) - 2), k + 1)

    def finish(self) -> bytes:
        if self.nbits:
            self.buf.append((self.acc << (8 - self.nbits)) & 0xFF)
            self.acc = 0
            self.nbits = 0
        return bytes(self.buf)


def _lz_tokens(data: bytes, window: int):
    """느긋한(lazy) 최장 일치 파싱 — 원본 토큰열과 일치한 규칙.

    각 위치에서 3바이트 이상 일치 중 가장 긴 것(동률은 가장 가까운 것)을 찾고,
    바로 다음 위치의 일치가 더 길면 지금은 리터럴로 내보낸다.
    반환: ('L', 바이트) / ('M', 거리, 길이) 리스트.
    """
    n = len(data)
    index: dict = {}
    for i in range(n - 2):
        index.setdefault(data[i:i + 3], []).append(i)
    cache: dict = {}

    def best(i: int) -> Tuple[int, int]:
        if i in cache:
            return cache[i]
        res = (0, 0)
        if i + 3 <= n:
            bl = 0
            bd = 0
            for q in reversed(index[data[i:i + 3]]):
                if q >= i:
                    continue
                dist = i - q
                if dist > window:
                    break
                length = 3
                while i + length < n and data[i + length] == data[q + length]:
                    length += 1
                if length > bl:
                    bl, bd = length, dist
            res = (bl, bd)
        cache[i] = res
        cache.pop(i - 2, None)
        return res

    toks = []
    i = 0
    while i < n:
        length, dist = best(i)
        if length >= MIN_MATCH:
            nxt = best(i + 1)[0] if i + 1 < n else 0
            if nxt > length:
                toks.append(("L", data[i]))
                i += 1
                continue
            toks.append(("M", dist, length))
            i += length
        else:
            toks.append(("L", data[i]))
            i += 1
    return toks


def encode_stream(data: bytes, dictionary: bytes, window: int = MAX_DISTANCE) -> bytes:
    """해제 데이터 하나 → 비트 스트림 (마지막 바이트는 0 비트로 채움)."""
    rev = {b: i for i, b in enumerate(dictionary)}
    w = _BitWriter()
    for t in _lz_tokens(data, window):
        if t[0] == "L":
            w.write_number(rev[t[1]])
        else:
            w.write_number(256 + t[1])
            w.write_number(t[2] - 3)
    return w.finish()


def encode_pack(parts: Sequence[bytes], dictionary: Optional[bytes] = None,
                window: int = MAX_DISTANCE) -> bytes:
    """해제 데이터 리스트 → LS11 파일.

    dictionary 를 주면 그 사전을 그대로 쓴다(원본과 바이트 동일 재현용).
    """
    if dictionary is None:
        dictionary = make_dictionary(parts)
    if len(dictionary) != 256 or len(set(dictionary)) != 256:
        raise Ls11Error("사전은 서로 다른 256 바이트여야 함")
    streams = [encode_stream(bytes(p), dictionary, window) for p in parts]
    start = TABLE_OFFSET + ENTRY_SIZE * len(parts) + 4
    out = bytearray(MAGIC + b"\x00" * 12 + dictionary)
    addr = start
    for p, s in zip(parts, streams):
        out += struct.pack(">III", len(s), len(p), addr)
        addr += len(s)
    out += b"\x00\x00\x00\x00"
    for s in streams:
        out += s
    return bytes(out)
