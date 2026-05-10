"""주인공 데이터 액세스 (능력치 + 자금)."""

from __future__ import annotations

from dataclasses import dataclass

from horiedit_py.common import (
    EditorState,
    Abil,
    abil_addr,
    money_addr,
    c_addr,
)


@dataclass
class HeroData:
    """주인공 1명의 편집 가능한 데이터 (능력치 + 자금)."""
    abil: Abil          # 친밀도는 stored 값(0..200) 그대로 보관 — UI 가 ±100 변환
    money: int          # uint32


def _check_hero_idx(hero_idx: int) -> None:
    if not (0 <= hero_idx < 6):
        raise IndexError(f"hero_idx 는 0..5 범위여야 합니다: {hero_idx}")


def load_hero(state: EditorState, hero_idx: int) -> HeroData:
    _check_hero_idx(hero_idx)
    abil = Abil.from_bytes(state.read(abil_addr[hero_idx] + state.page, Abil.SIZE))
    money_raw = state.read(money_addr + state.page, 4)
    money = int.from_bytes(money_raw, "little")
    return HeroData(abil=abil, money=money)


def save_hero(state: EditorState, hero_idx: int, data: HeroData) -> None:
    _check_hero_idx(hero_idx)
    # 친밀도 wrap 은 호출 전 GUI 가 처리한다고 가정. Abil.to_bytes 가 & 0xFF 처리.
    state.write(abil_addr[hero_idx] + state.page, data.abil.to_bytes())
    state.write(money_addr + state.page, (data.money & 0xFFFFFFFF).to_bytes(4, "little"))


def hero_index_active(state: EditorState) -> int:
    """현재 슬롯의 활성 주인공 번호 c_hero (0..5)."""
    raw = state.read(c_addr + state.page, 1)
    return raw[0] if raw else 0


def hero_names(state: EditorState) -> list[str]:
    """6명 주인공 표시 이름 (init_hori 가 채우는 hero[6] 와 동일)."""
    return list(state.hero)
