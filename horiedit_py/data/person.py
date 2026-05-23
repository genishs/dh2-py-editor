"""인물 데이터 액세스."""

from __future__ import annotations

from typing import Iterator, Optional

from horiedit_py.common import (
    EditorState,
    Person,
    PERSON_AREA_END,
    person_addr,
    encode_kr_fixed,
)


# Person 영역에 들어갈 수 있는 최대 인원: PERSON_AREA_END(0x1DE7) 까지 50 byte 씩.
# 0x1DE7 / 50 = 152.78 → 152. 그러나 명세는 119 로 고정.
_PERSON_COUNT_MAX = 119


# ---------------------------------------------------------------------------
# 동료 메커니즘 — analysis_K 기반
# Person.pos 가 hero 의 catalog ID 와 같으면 그 hero 의 동료.
# ---------------------------------------------------------------------------

# c_hero idx → catalog ID (= Person.pos 값으로 동료를 표시할 때 쓰는 marker)
HERO_CATALOG_ID: dict[int, int] = {
    0: 0x00,  # JOAN  (조안)
    1: 0x0A,  # CAT   (카탈리나)
    2: 0x1E,  # OTTO  (오토)
    3: 0x32,  # ROPEZ (로페즈)
    4: 0x28,  # PIET  (피에트로)
    5: 0x14,  # AL    (알)
}
HERO_CATALOG_TO_IDX: dict[int, int] = {v: k for k, v in HERO_CATALOG_ID.items()}

POS_FREE = 0xFE          # 모집 가능 (재고용 풀)
POS_PORT_SETTLER = 0xFF  # 항구 정착민 — Person.port 가 위치
RESERVED_POS_VALUES = {0x3D}  # 잠재 reserved (idx 114 가 점유), 회피 권장

# Person.none2[0] = role marker (v0.4.10 발견, analysis_K §6 후속).
# v0.4.9 사용자 검증 결과: pos 만 바꿔서는 게임의 "인물 목록 (active party 순회)" 에
# 등록되지 않음. none2[0] 도 동반 변경 필요.
NONE2_ROLE_INACTIVE = 0x00   # free / 정착민 / 비활성 hero — party 표시 제외
NONE2_ROLE_CAPTAIN = 0x02    # 선장 배속됨 (Ship1/2/3 도 갱신 필요 — 본 모듈 범위 밖)
NONE2_ROLE_PARTY = 0x06      # party member (선장 없음)


def role_for_pos(pos: int) -> int:
    """pos 값에 어울리는 none2[0] role marker.

    hero catalog (party 등록) → PARTY, free/정착민 → INACTIVE, 그 외 → INACTIVE.
    선장 배속(0x02) 은 자동 적용하지 않음 — Ship 데이터 동반 수정이 필요한
    별도 기능 (v0.4.11+ 예정).
    """
    if pos in HERO_CATALOG_ID.values():
        return NONE2_ROLE_PARTY
    return NONE2_ROLE_INACTIVE


def hero_idx_for_pos(pos: int) -> Optional[int]:
    """pos 가 hero catalog ID 면 hero_idx (0..5) 반환, 아니면 None."""
    return HERO_CATALOG_TO_IDX.get(pos)


def is_safe_pos_value(pos: int) -> bool:
    """combobox 가 안전하게 노출할 수 있는 pos 값인지.

    안전 = {6 hero catalog, FREE, PORT_SETTLER}. 그 외 0x01..0x44 는 NPC catalog
    가 점유 (변경 시 충돌 가능) — raw Spinbox 로만 변경.
    """
    return (
        pos in HERO_CATALOG_ID.values()
        or pos == POS_FREE
        or pos == POS_PORT_SETTLER
    )


def describe_pos(
    person: Person,
    hero_names: list[str],
    port_names: list[str],
) -> str:
    """Person.pos 를 사람이 읽을 수 있는 문자열로.

    - hero catalog → "{hero_name} 의 동료"
    - 0xFE → "(모집 가능)"
    - 0xFF → "(항구 정착민 — {port_name}, 여관/술집)"  술집·여관은 가설 (none2[1] bit 7)
    - 기타 → "(NPC 카탈로그 #0x??)"
    """
    h = hero_idx_for_pos(person.pos)
    if h is not None:
        name = hero_names[h] if 0 <= h < len(hero_names) else f"hero #{h}"
        return f"{name} 의 동료"
    if person.pos == POS_FREE:
        return "(모집 가능)"
    if person.pos == POS_PORT_SETTLER:
        port = person.port
        pname = port_names[port] if 0 <= port < len(port_names) else f"항구 #{port}"
        loc = _guess_inn_or_tavern(person)
        return f"(정착 — {pname}{loc})"
    return f"(NPC 카탈로그 #0x{person.pos:02X})"


def _guess_inn_or_tavern(person: Person) -> str:
    """pos==0xFF 정착민의 none2[1] bit 7 로 여관/술집 추정 — 가설 단계.

    근거: 미구엘(idx85, 여관) none2[1]=0xC0, 필리(idx79, 여관) none2[1]=0xE0
    둘 다 bit 7 set. 확정용 술집 anchor 미확보 → "(가설)" 표시.
    """
    if len(person.none2) < 2:
        return ""
    if person.none2[1] & 0x80:
        return ", 여관(가설)"
    return ", 술집(가설)"


def _set_none2_role(person: Person, role: int) -> None:
    """Person.none2[0] 만 갱신 (none2[1] 보존)."""
    n2 = bytearray(person.none2)
    if len(n2) < 1:
        n2 = bytearray(b"\x00\x00")
    n2[0] = role & 0xFF
    person.none2 = bytes(n2)


def set_companion(state: EditorState, person_idx: int, hero_idx: int) -> None:
    """person_idx 를 hero_idx 의 party 동료로 등록.

    pos = hero catalog ID + none2[0] = PARTY (0x06) 둘 다 갱신.
    선장 배속은 추가 작업 (Ship1/2/3) 이 필요 — 본 함수는 party only.
    """
    if hero_idx not in HERO_CATALOG_ID:
        raise ValueError(f"hero_idx 는 0..5: {hero_idx}")
    person = load_person(state, person_idx)
    person.pos = HERO_CATALOG_ID[hero_idx]
    _set_none2_role(person, NONE2_ROLE_PARTY)
    save_person(state, person_idx, person)


def unset_companion(state: EditorState, person_idx: int) -> None:
    """동료 해제 — pos = 0xFE (모집 가능) + none2[0] = INACTIVE."""
    person = load_person(state, person_idx)
    person.pos = POS_FREE
    _set_none2_role(person, NONE2_ROLE_INACTIVE)
    save_person(state, person_idx, person)


def person_count_max() -> int:
    """Person 영역에 들어갈 수 있는 최대 인원 = 119."""
    return _PERSON_COUNT_MAX


def _person_offset(state: EditorState, idx: int) -> int:
    return person_addr + state.page + idx * Person.SIZE


def iter_persons(state: EditorState) -> Iterator[tuple[int, Person]]:
    """슬롯의 인물을 (idx, Person) 으로 순회. idx 는 0부터.
    person 영역 끝(person_addr + PERSON_AREA_END + page) 까지."""
    idx = 0
    # 원본 person_edit 의 종료 조건: offset(슬롯 내 상대) > PERSON_AREA_END.
    # offset 시작은 person_addr 자체 (절대 슬롯 내) 가 아니라 person_addr 만 사용.
    rel_offset = person_addr
    end = PERSON_AREA_END
    while rel_offset <= end and idx < _PERSON_COUNT_MAX:
        data = state.read(_person_offset(state, idx), Person.SIZE)
        if len(data) < Person.SIZE:
            return
        yield idx, Person.from_bytes(data)
        idx += 1
        rel_offset += Person.SIZE


def load_person(state: EditorState, person_idx: int) -> Person:
    if person_idx < 0:
        raise IndexError(f"person_idx 음수 불가: {person_idx}")
    return Person.from_bytes(state.read(_person_offset(state, person_idx), Person.SIZE))


def save_person(state: EditorState, person_idx: int, person: Person) -> None:
    if person_idx < 0:
        raise IndexError(f"person_idx 음수 불가: {person_idx}")
    state.write(_person_offset(state, person_idx), person.to_bytes())


def _trim_nul(buf: bytes) -> bytes:
    nul = buf.find(b"\x00")
    return buf[:nul] if nul >= 0 else buf


def find_persons(state: EditorState, fname: str = "", lname: str = "") -> list[int]:
    """fname, lname 으로 부분 일치하는 인물 idx 목록 반환.
    빈 문자열은 검색 조건에서 제외."""
    fname_exist = bool(fname)
    lname_exist = bool(lname)
    if not fname_exist and not lname_exist:
        return []

    # EUC-KR 13 byte 고정 버퍼로 인코딩 후 NUL 까지 트림 (원본 person_edit 과 동일 비교).
    fname_target = _trim_nul(encode_kr_fixed(fname, 13)) if fname_exist else b""
    lname_target = _trim_nul(encode_kr_fixed(lname, 13)) if lname_exist else b""

    result: list[int] = []
    for idx, person in iter_persons(state):
        ok = True
        if fname_exist:
            # 부분 일치: target 이 person.fname (NUL 트림) 안에 포함되면 매칭.
            if fname_target not in _trim_nul(person.fname):
                ok = False
        if ok and lname_exist:
            if lname_target not in _trim_nul(person.lname):
                ok = False
        if ok:
            result.append(idx)
    return result


# 비트필드 헬퍼 (Person.set_bit 가 이미 있지만 명시적으로 export)
def get_ability_bit(person: Person, name: str) -> int:
    bits = {"td": 0, "ac": 1, "gu": 2, "mp": 3, "me": 4}
    return (person.ability >> bits[name]) & 0x01


def set_ability_bit(person: Person, name: str, val: int) -> None:
    person.set_bit(name, val)
