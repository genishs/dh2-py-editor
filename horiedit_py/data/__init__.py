"""순수 데이터 액세스 레이어. GUI 가 호출하는 인터페이스.

print/input 절대 사용 금지. 에러는 예외로 전파.

서브 모듈:
  - hero    : 주인공 능력치/자금
  - person  : 인물 검색·편집
  - ship    : 함대(Ship1/2/3) + 함선 템플릿(Ship4/5) 슬롯 내 편집
  - game    : MAIN.EXE Ship4/5 ROM, 함선 record (analysis_G — kogyo/lhull)

이전에 있던 "등장공업치 표 (KOGYO_OFFSET_IN_SLOT / MAINEXE_KOGYO_TABLE_*)"
관련 export 는 analysis_G 의 record 구조 발견과 함께 제거되었다. 등장공업치
와 최대 내구도는 record 의 +0/+1 byte 이며, 헬퍼는 game.py 의
load/save_record_kogyo / load/save_record_lhull 를 통해 사용한다.
"""

from __future__ import annotations

from horiedit_py.common import (
    EditorState,
    PAGE,
    Init,
    Person,
    Ship1,
    Ship2,
    Ship3,
    Ship5,
    Port,
    decode_kr,
    person_addr,
    s_addr,
    c_addr,
    ship1_addr,
    ship2_addr,
    ship3_addr,
    port_addr,
    port_econ_addr,
    PORT_ECON_RECORD,
    INIT_HEADER_OFFSET,
)


def _refresh_hero_cache(state: EditorState) -> None:
    """6명 주인공 표시 이름 캐시 (init_hori 의 hero[6] 부분)."""
    base = person_addr + state.page
    for i in range(6):
        ps = Person.from_bytes(state.read(base + Person.SIZE * i, Person.SIZE))
        state.hero[i] = f"{decode_kr(ps.fname)} {decode_kr(ps.lname)}"


def _refresh_ship_name_cache(state: EditorState) -> None:
    """25개 선박 원본 이름 캐시 (init_hori 의 ship_name[25] 부분)."""
    base = s_addr + state.page
    for i in range(25):
        ship5 = Ship5.from_bytes(state.read(base + Ship5.SIZE * i, Ship5.SIZE))
        state.ship_name[i] = decode_kr(ship5.name)


def _refresh_port_name_cache(state: EditorState) -> None:
    """130개 항구 이름 캐시 (sel_save 슬롯 확정 후 동작)."""
    base = state.page + port_addr
    for i in range(130):
        port = Port.from_bytes(state.read(base + Port.SIZE * i, Port.SIZE))
        state.port_name[i] = decode_kr(port.name)


def _refresh_c_hero_and_ship_num(state: EditorState) -> None:
    """conferm_hero 로직: c_hero 와 ship_num 갱신."""
    raw = state.read(c_addr + state.page, 1)
    state.c_hero = raw[0] if raw else 0

    state.ship_num = 0
    while True:
        offset1 = ship1_addr[state.c_hero] + state.page + state.ship_num * Ship1.SIZE
        ship1 = Ship1.from_bytes(state.read(offset1, Ship1.SIZE))
        if ship1.select == 0xFF:
            break
        # ship2 는 형식상 읽고 버린다 (원본 conferm_hero 와 동일).
        offset2 = ship2_addr + state.page + state.ship_num * Ship2.SIZE
        _ = Ship2.from_bytes(state.read(offset2, Ship2.SIZE))
        offset3 = ship3_addr + state.page + ship1.select * Ship3.SIZE
        ship3 = Ship3.from_bytes(state.read(offset3, Ship3.SIZE))
        if ship3.ship_select == 0xFF:
            break
        state.ship_num += 1


def select_slot(state: EditorState, slot_index: int) -> None:
    """슬롯 변경. page 설정 + hero[6] / ship_name[25] / port_name[130] / c_hero / ship_num 캐시 갱신.

    slot_index: 0..9. 검증 (존재 여부) 은 GUI 책임.
    """
    if not (0 <= slot_index <= 9):
        raise ValueError(f"slot_index 는 0..9 범위여야 합니다: {slot_index}")
    state.page = PAGE * slot_index
    _refresh_hero_cache(state)
    _refresh_ship_name_cache(state)
    _refresh_port_name_cache(state)
    _refresh_c_hero_and_ship_num(state)


def slot_is_used(state: EditorState, slot_index: int) -> bool:
    """슬롯 헤더의 memo[0] != 0 이면 사용 중."""
    if not (0 <= slot_index <= 9):
        return False
    data = state.read(INIT_HEADER_OFFSET + Init.SIZE * slot_index, Init.SIZE)
    init = Init.from_bytes(data)
    return init.memo[0] != 0


def slot_init(state: EditorState, slot_index: int) -> Init:
    """슬롯 헤더 (Init) 로드."""
    data = state.read(INIT_HEADER_OFFSET + Init.SIZE * slot_index, Init.SIZE)
    return Init.from_bytes(data)
