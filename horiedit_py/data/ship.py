"""선박/함대 데이터 액세스."""

from __future__ import annotations

from horiedit_py.common import (
    EditorState,
    Ship1,
    Ship2,
    Ship3,
    Ship4,
    Ship5,
    ship1_addr,
    ship2_addr,
    ship3_addr,
    ship4_addr,
    s_addr,
)


# === 영웅 함대 ===

def _fleet_offsets(state: EditorState, sel: int, ship_select: int) -> tuple[int, int, int]:
    """fleet entry sel 의 ship1/ship2/ship3 절대 오프셋 계산.

    ship3 은 ship1.select (= ship_select 인자) 인덱스를 사용한다.
    """
    o1 = ship1_addr[state.c_hero] + state.page + sel * Ship1.SIZE
    o2 = ship2_addr + state.page + sel * Ship2.SIZE
    o3 = ship3_addr + state.page + ship_select * Ship3.SIZE
    return o1, o2, o3


def load_fleet_entry(state: EditorState, sel: int) -> tuple[Ship1, Ship2, Ship3]:
    """함대 sel 번째 함선의 ship1/ship2/ship3 동시 로드."""
    o1 = ship1_addr[state.c_hero] + state.page + sel * Ship1.SIZE
    o2 = ship2_addr + state.page + sel * Ship2.SIZE
    ship1 = Ship1.from_bytes(state.read(o1, Ship1.SIZE))
    ship2 = Ship2.from_bytes(state.read(o2, Ship2.SIZE))
    o3 = ship3_addr + state.page + ship1.select * Ship3.SIZE
    ship3 = Ship3.from_bytes(state.read(o3, Ship3.SIZE))
    return ship1, ship2, ship3


def save_fleet_entry(state: EditorState, sel: int,
                     ship1: Ship1, ship2: Ship2, ship3: Ship3) -> None:
    """fleet entry 저장 (offset 은 sel 로 다시 계산, 클램프 없음 — UI 가 책임)."""
    o1, o2, o3 = _fleet_offsets(state, sel, ship1.select)
    state.write(o1, ship1.to_bytes())
    state.write(o2, ship2.to_bytes())
    state.write(o3, ship3.to_bytes())


def cargo_recalc(ship3: Ship3, ship4_capacity: int, ship3_f_weap: int,
                 ship3_f_crew: int) -> int:
    """ship3.cargo = (capacity - f_weap - f_crew) & 0xFFFF."""
    cargo = (ship4_capacity - ship3_f_weap - ship3_f_crew) & 0xFFFF
    ship3.cargo = cargo
    return cargo


# === 25종 함선 템플릿 (KOUKAI2.DAT 슬롯 내) ===

def _check_ship_type(ship_type: int) -> None:
    if not (0 <= ship_type < 25):
        raise IndexError(f"ship_type 은 0..24 범위여야 합니다: {ship_type}")


def load_ship4(state: EditorState, ship_type: int) -> Ship4:
    _check_ship_type(ship_type)
    offset = state.page + ship4_addr + Ship4.SIZE * ship_type
    return Ship4.from_bytes(state.read(offset, Ship4.SIZE))


def save_ship4(state: EditorState, ship_type: int, ship4: Ship4) -> None:
    _check_ship_type(ship_type)
    offset = state.page + ship4_addr + Ship4.SIZE * ship_type
    state.write(offset, ship4.to_bytes())


def load_ship5(state: EditorState, ship_type: int) -> Ship5:
    _check_ship_type(ship_type)
    offset = s_addr + state.page + Ship5.SIZE * ship_type
    return Ship5.from_bytes(state.read(offset, Ship5.SIZE))


def save_ship5(state: EditorState, ship_type: int, ship5: Ship5) -> None:
    _check_ship_type(ship_type)
    offset = s_addr + state.page + Ship5.SIZE * ship_type
    state.write(offset, ship5.to_bytes())


# === 함대 길이 ===

def ship_num_for_hero(state: EditorState, hero_idx: int) -> int:
    """hero_idx 가 보유한 함대 척수 (conferm_hero 의 카운트 로직과 동일)."""
    if not (0 <= hero_idx < 6):
        raise IndexError(f"hero_idx 는 0..5 범위여야 합니다: {hero_idx}")
    n = 0
    while True:
        o1 = ship1_addr[hero_idx] + state.page + n * Ship1.SIZE
        ship1 = Ship1.from_bytes(state.read(o1, Ship1.SIZE))
        if ship1.select == 0xFF:
            break
        # ship2 형식상 읽음 (원본 동일).
        o2 = ship2_addr + state.page + n * Ship2.SIZE
        _ = Ship2.from_bytes(state.read(o2, Ship2.SIZE))
        o3 = ship3_addr + state.page + ship1.select * Ship3.SIZE
        ship3 = Ship3.from_bytes(state.read(o3, Ship3.SIZE))
        if ship3.ship_select == 0xFF:
            break
        n += 1
    return n
