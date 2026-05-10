"""인물 데이터 액세스."""

from __future__ import annotations

from typing import Iterator

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
