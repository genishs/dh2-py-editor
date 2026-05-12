"""horiedit 공통 모듈: 상수, 구조체 직렬화, EditorState, IO 헬퍼.

원본: HORIEDIT.C / HORIEDIT.H (Koukai 2 / 대항해시대 II 세이브 에디터).
모든 다바이트 정수는 little-endian (DOS x86 Borland Turbo C).
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import BinaryIO, List, Optional


# ---------------------------------------------------------------------------
# 1. 상수
# ---------------------------------------------------------------------------

PAGE = 33340  # 한 슬롯의 바이트 크기 (HORIEDIT.H:195)

# 6명 주인공 인덱스 (HORIEDIT.H:4-9)
JOAN = 0   # 조안
CAT = 1    # 카탈리나
OTTO = 2   # 오토
ROPEZ = 3  # 로페즈
PIET = 4   # 피에트로
AAL = 5    # 알 (이탈리아계 → Ipeer 사용)

# 슬롯 베이스 오프셋 (HORIEDIT.H)
abil_addr = (0x064D, 0x065B, 0x0669, 0x0677, 0x0685, 0x0693)  # 6명 능력치
money_addr = 0x06A1
c_addr = 0x06A8
person_addr = 0x06A9
ship1_addr = (0x2244, 0x2776, 0x31DA, 0x3C3E, 0x370C, 0x2CA8)  # 주인공별
ship2_addr = 0x4692
ship3_addr = 0x4C35
ship4_addr = 0x5291
s_addr = 0x501D
port_addr = 0x53BF

# 항구 경제 (상업치/공업치/물가 후보) 테이블 — analysis_I
# slot + port_econ_addr 시작, 130 × PORT_ECON_RECORD 구조.
port_econ_addr = 0x5DE3
PORT_ECON_RECORD = 37  # byte per port (확정: anchor 4개 일치)

# Person 영역 종료 매직 넘버 (HORIEDIT.C:211)
PERSON_AREA_END = 0x1DE7

# 슬롯 헤더(Init) 위치: 파일 맨 앞 1바이트 건너뛰고 sizeof(Init)*i
INIT_HEADER_OFFSET = 1
INIT_SIZE = 15

# ---------------------------------------------------------------------------
# 2. 정적 문자열 테이블 (HORIEDIT.H 의 깨진 한글을 분석 문서 기반으로 복원)
# ---------------------------------------------------------------------------

# Epeer[10]: 일반 주인공용 작위 (포르투갈/스페인/잉글랜드/네덜란드 등)
Epeer: List[str] = [
    "남작",
    "준남작",
    "자작",
    "백작",
    "후작",
    "공작",
    "대공작",
    "왕자",
    "국왕",
    "황제",
]

# Ipeer[10]: 알(c_hero==5) 전용 이탈리아 작위
Ipeer: List[str] = [
    "기사",
    "남작",
    "준남작",
    "자작",
    "백작",
    "후작",
    "대영주",
    "공작",
    "대공",
    "도제장",
]

# weapon_name[8]: 인덱스 0=없음(0x10), 1..7=CANO..KND (HORIEDIT.H:92-100)
weapon_name: List[str] = [
    "없음",
    "캐넌",
    "더블캐넌",
    "캐넌포얼",
    "쿨베린",
    "더블쿨베린",
    "세이커",
    "카로네이드",
]

# form_name[11]: 진형(선수상). 0=없음, 1..10=JAGU..GOD (HORIEDIT.H:113-124)
form_name: List[str] = [
    "없음",
    "바다표범",
    "제독",
    "유니콘",
    "사자",
    "독수리",
    "왕자",
    "포세이돈",
    "용",
    "천사",
    "여신",
]


# ---------------------------------------------------------------------------
# 3. IO 헬퍼
# ---------------------------------------------------------------------------

def read_at(fp: BinaryIO, offset: int, size: int) -> bytes:
    fp.seek(offset)
    return fp.read(size)


def write_at(fp: BinaryIO, offset: int, data: bytes) -> None:
    fp.seek(offset)
    fp.write(data)


def decode_kr(buf: bytes) -> str:
    """EUC-KR 디코드. NUL 종료 처리."""
    nul = buf.find(b"\x00")
    if nul >= 0:
        buf = buf[:nul]
    try:
        return buf.decode("euc-kr", errors="replace")
    except Exception:
        return buf.decode("latin-1", errors="replace")


def encode_kr_fixed(s: str, size: int) -> bytes:
    """문자열을 EUC-KR 로 인코딩하여 size 바이트 고정 버퍼에 채움. 남는 부분은 NUL."""
    raw = s.encode("euc-kr", errors="replace")
    if len(raw) >= size:
        # NUL 종료 보장: 마지막 1바이트는 0
        raw = raw[: size - 1] + b"\x00"
    else:
        raw = raw + b"\x00" * (size - len(raw))
    return raw


# ---------------------------------------------------------------------------
# 4. 구조체 직렬화 (struct.pack/unpack 기반)
# ---------------------------------------------------------------------------

@dataclass
class Abil:
    """주인공 능력치. sizeof = 14 bytes. 포맷 <3H 8B."""
    trade: int = 0    # 무역 명성 (uint16)
    robber: int = 0   # 해적 명성
    adven: int = 0    # 모험 명성
    pro: int = 100    # 포르투갈 친밀도 (저장: 0..200, 표시: -100..+100)
    spa: int = 100
    osm: int = 100
    eng: int = 100
    ita: int = 100
    ned: int = 100
    none: int = 0     # 패딩
    peer: int = 0     # 작위 (0..9)

    _FMT = "<3H8B"
    SIZE = struct.calcsize(_FMT)  # 14

    @classmethod
    def from_bytes(cls, data: bytes) -> "Abil":
        t, r, a, pro, spa, osm, eng, ita, ned, none, peer = struct.unpack(cls._FMT, data[: cls.SIZE])
        return cls(t, r, a, pro, spa, osm, eng, ita, ned, none, peer)

    def to_bytes(self) -> bytes:
        return struct.pack(
            self._FMT,
            self.trade & 0xFFFF, self.robber & 0xFFFF, self.adven & 0xFFFF,
            self.pro & 0xFF, self.spa & 0xFF, self.osm & 0xFF,
            self.eng & 0xFF, self.ita & 0xFF, self.ned & 0xFF,
            self.none & 0xFF, self.peer & 0xFF,
        )


@dataclass
class Person:
    """일반 인물. sizeof = 50 bytes."""
    fname: bytes = b"\x00" * 13
    lname: bytes = b"\x00" * 13
    none: bytes = b"\x00" * 2
    command: int = 0
    sail: int = 0
    know: int = 0
    hunch: int = 0
    tool: int = 0
    sword: int = 0
    charm: int = 0
    death: int = 0
    l_sail: int = 0
    l_battle: int = 0
    exp_sail: int = 0
    exp_battle: int = 0
    age: int = 0
    none1: int = 0
    pos: int = 0
    port: int = 0
    none2: bytes = b"\x00" * 2
    ability: int = 0   # 비트필드 1바이트 (td|ac<<1|gu<<2|mp<<3|me<<4)
    none3: int = 0

    _FMT = "<13s13s2s8B2B2H4B2sBB"
    SIZE = struct.calcsize(_FMT)  # 50

    @classmethod
    def from_bytes(cls, data: bytes) -> "Person":
        unpacked = struct.unpack(cls._FMT, data[: cls.SIZE])
        return cls(*unpacked)

    def to_bytes(self) -> bytes:
        return struct.pack(
            self._FMT,
            self.fname, self.lname, self.none,
            self.command & 0xFF, self.sail & 0xFF, self.know & 0xFF, self.hunch & 0xFF,
            self.tool & 0xFF, self.sword & 0xFF, self.charm & 0xFF, self.death & 0xFF,
            self.l_sail & 0xFF, self.l_battle & 0xFF,
            self.exp_sail & 0xFFFF, self.exp_battle & 0xFFFF,
            self.age & 0xFF, self.none1 & 0xFF, self.pos & 0xFF, self.port & 0xFF,
            self.none2, self.ability & 0xFF, self.none3 & 0xFF,
        )

    # 비트필드 접근자
    @property
    def td(self) -> int: return self.ability & 0x01
    @property
    def ac(self) -> int: return (self.ability >> 1) & 0x01
    @property
    def gu(self) -> int: return (self.ability >> 2) & 0x01
    @property
    def mp(self) -> int: return (self.ability >> 3) & 0x01
    @property
    def me(self) -> int: return (self.ability >> 4) & 0x01

    def set_bit(self, name: str, val: int) -> None:
        bits = {"td": 0, "ac": 1, "gu": 2, "mp": 3, "me": 4}
        b = bits[name]
        if val & 1:
            self.ability |= (1 << b)
        else:
            self.ability &= ~(1 << b) & 0xFF


@dataclass
class Init:
    """슬롯 메타데이터. sizeof = 15 bytes. 포맷 <12sBBB."""
    memo: bytes = b"\x00" * 12
    port: int = 0
    ending: int = 0
    none: int = 0

    _FMT = "<12sBBB"
    SIZE = struct.calcsize(_FMT)  # 15

    @classmethod
    def from_bytes(cls, data: bytes) -> "Init":
        memo, port, ending, none = struct.unpack(cls._FMT, data[: cls.SIZE])
        return cls(memo, port, ending, none)

    def to_bytes(self) -> bytes:
        return struct.pack(self._FMT, self.memo, self.port & 0xFF, self.ending & 0xFF, self.none & 0xFF)


@dataclass
class Ship1:
    """함대 1척 현재 상태. sizeof = 9 bytes. 포맷 <HBBBBBBB."""
    ccrew: int = 0
    chull: int = 0
    lhull: int = 0
    crudder: int = 0
    csail: int = 0
    cnowea: int = 0
    select: int = 0xFF
    cselwea: int = 0x10

    _FMT = "<HBBBBBBB"
    SIZE = struct.calcsize(_FMT)  # 9

    @classmethod
    def from_bytes(cls, data: bytes) -> "Ship1":
        return cls(*struct.unpack(cls._FMT, data[: cls.SIZE]))

    def to_bytes(self) -> bytes:
        return struct.pack(
            self._FMT,
            self.ccrew & 0xFFFF,
            self.chull & 0xFF, self.lhull & 0xFF,
            self.crudder & 0xFF, self.csail & 0xFF,
            self.cnowea & 0xFF, self.select & 0xFF, self.cselwea & 0xFF,
        )


@dataclass
class Ship2:
    """함대 1척 운용 상태. sizeof = 30 bytes. 포맷 <BBB27s."""
    captin: int = 0
    condition: int = 0
    ship_form: int = 0
    none: bytes = b"\x00" * 27

    _FMT = "<BBB27s"
    SIZE = struct.calcsize(_FMT)  # 30

    @classmethod
    def from_bytes(cls, data: bytes) -> "Ship2":
        return cls(*struct.unpack(cls._FMT, data[: cls.SIZE]))

    def to_bytes(self) -> bytes:
        return struct.pack(
            self._FMT,
            self.captin & 0xFF, self.condition & 0xFF, self.ship_form & 0xFF,
            self.none,
        )


@dataclass
class Ship3:
    """함대 1척 가변 정보. sizeof = 25 bytes. 포맷 <14s4sBBBHH."""
    ship_name: bytes = b"\x00" * 14
    none: bytes = b"\x00" * 4
    ship_select: int = 0xFF
    bform: int = 0
    f_weap: int = 0
    f_crew: int = 0
    cargo: int = 0

    _FMT = "<14s4sBBBHH"
    SIZE = struct.calcsize(_FMT)  # 25

    @classmethod
    def from_bytes(cls, data: bytes) -> "Ship3":
        return cls(*struct.unpack(cls._FMT, data[: cls.SIZE]))

    def to_bytes(self) -> bytes:
        return struct.pack(
            self._FMT,
            self.ship_name, self.none,
            self.ship_select & 0xFF, self.bform & 0xFF, self.f_weap & 0xFF,
            self.f_crew & 0xFFFF, self.cargo & 0xFFFF,
        )


@dataclass
class Ship4:
    """선박 종류 25종 정적 스펙. sizeof = 12 bytes. 포맷 <BBBBHB5s."""
    lrudder: int = 0
    lsail: int = 0
    lcrew: int = 0     # 실제 최대치는 lcrew*10
    dcrew: int = 0
    capacity: int = 0
    lnowea: int = 0
    none: bytes = b"\x00" * 5

    _FMT = "<BBBBHB5s"
    SIZE = struct.calcsize(_FMT)  # 12

    @classmethod
    def from_bytes(cls, data: bytes) -> "Ship4":
        return cls(*struct.unpack(cls._FMT, data[: cls.SIZE]))

    def to_bytes(self) -> bytes:
        return struct.pack(
            self._FMT,
            self.lrudder & 0xFF, self.lsail & 0xFF,
            self.lcrew & 0xFF, self.dcrew & 0xFF,
            self.capacity & 0xFFFF, self.lnowea & 0xFF, self.none,
        )


@dataclass
class Ship5:
    """선박 종류 25종 이름·외형. sizeof = 25 bytes. 포맷 <18sBB5s."""
    name: bytes = b"\x00" * 18
    sform: int = 0
    bform: int = 0
    none: bytes = b"\x00" * 5

    _FMT = "<18sBB5s"
    SIZE = struct.calcsize(_FMT)  # 25

    @classmethod
    def from_bytes(cls, data: bytes) -> "Ship5":
        return cls(*struct.unpack(cls._FMT, data[: cls.SIZE]))

    def to_bytes(self) -> bytes:
        return struct.pack(
            self._FMT,
            self.name, self.sform & 0xFF, self.bform & 0xFF, self.none,
        )


@dataclass
class Port:
    """항구. sizeof = 20 bytes. 포맷 <15s5s."""
    name: bytes = b"\x00" * 15
    none: bytes = b"\x00" * 5

    _FMT = "<15s5s"
    SIZE = struct.calcsize(_FMT)  # 20

    @classmethod
    def from_bytes(cls, data: bytes) -> "Port":
        return cls(*struct.unpack(cls._FMT, data[: cls.SIZE]))

    def to_bytes(self) -> bytes:
        return struct.pack(self._FMT, self.name, self.none)


# ---------------------------------------------------------------------------
# 5. EditorState — 전역 상태 (원본의 전역 변수들을 한 곳에 모음)
# ---------------------------------------------------------------------------

@dataclass
class EditorState:
    """에디터 전역 상태. main 에서 1개만 만든다."""
    fp: BinaryIO = None  # type: ignore
    page: int = 0
    c_hero: int = 0
    ship_num: int = 0
    eXit: int = 0

    # KOUKAI2.DAT 가 있는 디렉토리 (game_settings 가 같은 폴더의
    # MAIN.EXE 등을 편집할 때 사용). koukai2_editor.py 에서 설정.
    game_dir: Optional[Path] = None

    # 캐시
    hero: List[str] = field(default_factory=lambda: ["" for _ in range(6)])
    ship_name: List[str] = field(default_factory=lambda: ["" for _ in range(25)])
    port_name: List[str] = field(default_factory=lambda: ["" for _ in range(130)])
    save_flg: List[int] = field(default_factory=lambda: [0] * 10)

    # 마지막 load() 의 offset & 구조체 (B 가 호출하는 store() 가 사용)
    offset1: int = 0
    offset2: int = 0
    offset3: int = 0
    offset: int = 0  # load4/원본에서의 offset (org_ship_edit 마지막 fwrite 용)

    ship1: Ship1 = field(default_factory=Ship1)
    ship2: Ship2 = field(default_factory=Ship2)
    ship3: Ship3 = field(default_factory=Ship3)
    ship4: Ship4 = field(default_factory=Ship4)
    ship5: Ship5 = field(default_factory=Ship5)

    # ---- IO 헬퍼 메서드 ----
    def read(self, offset: int, size: int) -> bytes:
        self.fp.seek(offset)
        return self.fp.read(size)

    def write(self, offset: int, data: bytes) -> None:
        self.fp.seek(offset)
        self.fp.write(data)

    # ---- 분석 A §9 의 load / store / load4 / load5 (B 도 동일하게 호출) ----
    def load(self, sel: int) -> None:
        """함대 슬롯 sel 의 ship1/ship2/ship3 동시 로드."""
        self.offset1 = ship1_addr[self.c_hero] + self.page + sel * Ship1.SIZE
        self.offset2 = ship2_addr + self.page + sel * Ship2.SIZE
        self.ship1 = Ship1.from_bytes(self.read(self.offset1, Ship1.SIZE))
        self.ship2 = Ship2.from_bytes(self.read(self.offset2, Ship2.SIZE))
        # ship3 의 인덱스는 ship_num 이 아니라 ship1.select
        self.offset3 = ship3_addr + self.page + self.ship1.select * Ship3.SIZE
        self.ship3 = Ship3.from_bytes(self.read(self.offset3, Ship3.SIZE))

    def store(self) -> None:
        """직전 load() 가 기록한 offset1/2/3 위치에 ship1/ship2/ship3 다시 쓴다."""
        self.write(self.offset1, self.ship1.to_bytes())
        self.write(self.offset2, self.ship2.to_bytes())
        self.write(self.offset3, self.ship3.to_bytes())

    def load4(self, sel: int) -> None:
        """선박 종류 25종 중 sel 의 Ship4 로드."""
        self.offset = self.page + ship4_addr + Ship4.SIZE * sel
        self.ship4 = Ship4.from_bytes(self.read(self.offset, Ship4.SIZE))

    def load5(self, sel: int) -> None:
        """선박 종류 25종 중 sel 의 Ship5 로드. (offset 갱신하지 않음)"""
        addr = s_addr + self.page + Ship5.SIZE * sel
        self.ship5 = Ship5.from_bytes(self.read(addr, Ship5.SIZE))


# 모듈 전역 EditorState 인스턴스 (원본의 전역 변수에 해당)
state = EditorState()
