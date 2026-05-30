"""주인공 능력치 편집 탭.

dirty/commit/revert 인터페이스 제공:
- reload(): 디스크 → 폼, dirty=False
- reset(): 폼 비우기/비활성, dirty=False
- is_dirty(): 변경 여부
- commit(): 폼 → 디스크 (실패 시 ValueError), dirty=False
- revert(): reload 의 alias
- add_dirty_listener(cb): dirty 변경 시 호출되는 콜백 등록
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional

from horiedit_py.common import (
    AAL,
    Abil,
    EditorState,
    Epeer,
    Ipeer,
)
from horiedit_py.data.hero import (
    HeroData,
    hero_index_active,
    hero_names,
    load_hero,
    save_hero,
)


_FAVOR_LABELS = [
    ("포르투갈", "pro"),
    ("스페인", "spa"),
    ("오스만", "osm"),
    ("잉글랜드", "eng"),
    ("이탈리아", "ita"),
    ("네덜란드", "ned"),
]


class HeroTab(ttk.Frame):
    """주인공 능력치 / 자금 / 작위 / 친밀도 편집 탭."""

    def __init__(self, master: tk.Misc, state: EditorState) -> None:
        super().__init__(master, padding=12)
        self._state = state
        self._hero_idx = 0
        self._loaded = False
        self._slot_loaded = False
        self._loading = False  # reload 중 trace 콜백 무시 가드
        self._dirty = False
        self._dirty_listeners: list[Callable[[], None]] = []

        # 위젯 변수
        self._var_hero = tk.StringVar()
        self._var_trade = tk.IntVar(value=0)
        self._var_robber = tk.IntVar(value=0)
        self._var_adven = tk.IntVar(value=0)
        self._var_money = tk.IntVar(value=0)
        self._var_favor: dict[str, tk.IntVar] = {
            key: tk.IntVar(value=0) for _, key in _FAVOR_LABELS
        }
        self._var_peer = tk.StringVar()

        self._build()
        self._set_inputs_state("disabled")
        self._install_dirty_traces()

    # ---------------- 구성 ----------------

    def _build(self) -> None:
        # 영웅 선택
        top = ttk.Frame(self)
        top.grid(row=0, column=0, columnspan=4, sticky="ew", pady=(0, 8))
        ttk.Label(top, text="주인공:").grid(row=0, column=0, padx=(0, 6))
        self._cb_hero = ttk.Combobox(
            top, textvariable=self._var_hero, state="readonly", width=24
        )
        self._cb_hero.grid(row=0, column=1, sticky="w")
        self._cb_hero.bind("<<ComboboxSelected>>", self._on_hero_changed)

        # 명성
        fame = ttk.LabelFrame(self, text="명성", padding=8)
        fame.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=(0, 6), pady=4)
        self._add_spinbox(fame, 0, "교역 명성", self._var_trade, 0, 50000)
        self._add_spinbox(fame, 1, "해적 명성", self._var_robber, 0, 50000)
        self._add_spinbox(fame, 2, "모험 명성", self._var_adven, 0, 50000)

        # 자금 + 작위
        misc = ttk.LabelFrame(self, text="자금 / 작위", padding=8)
        misc.grid(row=1, column=2, columnspan=2, sticky="nsew", padx=(6, 0), pady=4)
        self._add_spinbox(misc, 0, "자금", self._var_money, 0, 0xFFFFFFFF, width=14)
        ttk.Label(misc, text="작위").grid(row=1, column=0, sticky="w", padx=4, pady=4)
        self._cb_peer = ttk.Combobox(
            misc, textvariable=self._var_peer, state="readonly", width=14
        )
        self._cb_peer.grid(row=1, column=1, sticky="w", padx=4, pady=4)
        self._cb_peer.bind("<<ComboboxSelected>>", self._on_dirty_event)

        # 친밀도 (각 나라와의 관계)
        favor = ttk.LabelFrame(self, text="각 나라와의 관계", padding=8)
        favor.grid(row=2, column=0, columnspan=4, sticky="nsew", pady=8)
        for i, (label, key) in enumerate(_FAVOR_LABELS):
            r, c = divmod(i, 3)
            cell = ttk.Frame(favor)
            cell.grid(row=r, column=c, sticky="w", padx=8, pady=4)
            ttk.Label(cell, text=label, width=8).grid(row=0, column=0, sticky="w")
            sp = ttk.Spinbox(
                cell,
                from_=-100,
                to=100,
                textvariable=self._var_favor[key],
                width=6,
            )
            sp.grid(row=0, column=1, padx=(4, 0))

        # 안내 라벨 (슬롯 미선택 시)
        self._hint = ttk.Label(
            self, text="(세이브 칸을 먼저 선택하세요)", foreground="#888"
        )
        self._hint.grid(row=4, column=0, columnspan=4, pady=(8, 0))

        for c in range(4):
            self.columnconfigure(c, weight=1)

    def _add_spinbox(
        self,
        parent: tk.Misc,
        row: int,
        label: str,
        var: tk.IntVar,
        lo: int,
        hi: int,
        width: int = 10,
    ) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=4, pady=4)
        sp = ttk.Spinbox(parent, from_=lo, to=hi, textvariable=var, width=width)
        sp.grid(row=row, column=1, sticky="w", padx=4, pady=4)

    # ---------------- dirty 처리 ----------------

    def _install_dirty_traces(self) -> None:
        for v in (
            self._var_trade, self._var_robber, self._var_adven, self._var_money,
        ):
            v.trace_add("write", self._on_var_write)
        for v in self._var_favor.values():
            v.trace_add("write", self._on_var_write)

    def _on_var_write(self, *_a: object) -> None:
        if self._loading:
            return
        if not self._slot_loaded:
            return
        self._set_dirty(True)

    def _on_dirty_event(self, _event: object = None) -> None:
        if self._loading:
            return
        if not self._slot_loaded:
            return
        self._set_dirty(True)

    def _set_dirty(self, value: bool) -> None:
        if self._dirty == value:
            return
        self._dirty = value
        for cb in list(self._dirty_listeners):
            try:
                cb()
            except Exception:
                pass

    # ---------------- 외부 인터페이스 ----------------

    def is_dirty(self) -> bool:
        return self._dirty and self._slot_loaded

    def add_dirty_listener(self, callback: Callable[[], None]) -> None:
        self._dirty_listeners.append(callback)

    def reload(self) -> None:
        """디스크 → 폼. dirty=False 로 리셋."""
        self._loading = True
        try:
            names = hero_names(self._state)
            self._cb_hero.configure(values=names)

            active = hero_index_active(self._state)
            if not (0 <= active < len(names)):
                active = 0
            self._hero_idx = active
            if names:
                self._var_hero.set(names[active])

            self._slot_loaded = True
            self._hint.grid_remove()
            self._set_inputs_state("normal")
            self._load_current_hero()
        finally:
            self._loading = False
        self._set_dirty(False)

    def reset(self) -> None:
        """폼 비우기/비활성. dirty=False."""
        self._loading = True
        try:
            self._slot_loaded = False
            self._loaded = False
            self._set_inputs_state("disabled")
            self._hint.grid()
        finally:
            self._loading = False
        self._set_dirty(False)

    def revert(self) -> None:
        """reload 와 동일."""
        self.reload()

    def commit(self) -> None:
        """현재 폼 → 디스크. 실패 시 ValueError."""
        if not self._slot_loaded:
            return
        if not self._dirty:
            return
        data = self._collect_data()
        try:
            save_hero(self._state, self._hero_idx, data)
        except Exception as e:
            raise ValueError(f"주인공 저장 실패: {e}") from e
        self._set_dirty(False)

    # ---------------- 로드 ----------------

    def _load_current_hero(self) -> None:
        """_loading=True 컨텍스트 안에서만 호출. textvariable 변경이 dirty 로 잡히지 않도록."""
        try:
            data = load_hero(self._state, self._hero_idx)
        except Exception as e:
            raise ValueError(f"주인공 로드 실패: {e}") from e

        abil = data.abil
        self._var_trade.set(abil.trade)
        self._var_robber.set(abil.robber)
        self._var_adven.set(abil.adven)
        self._var_money.set(data.money)

        # 친밀도: stored(0..200) → 표시(-100..+100)
        favor_keys = ("pro", "spa", "osm", "eng", "ita", "ned")
        for key in favor_keys:
            stored = getattr(abil, key)
            self._var_favor[key].set(int(stored) - 100)

        # 작위 콤보 채우기
        peer_list = Ipeer if self._state.c_hero == AAL else Epeer
        self._cb_peer.configure(values=list(peer_list))
        peer_idx = abil.peer if 0 <= abil.peer < len(peer_list) else 0
        self._var_peer.set(peer_list[peer_idx])

        self._loaded = True

    def _on_hero_changed(self, _event: object = None) -> None:
        if self._loading or not self._slot_loaded:
            return
        try:
            idx = list(self._cb_hero["values"]).index(self._var_hero.get())
        except ValueError:
            return
        if idx == self._hero_idx:
            return
        # 다른 hero 로 변경: 자동 dirty 처리 — 기존 변경분은 폐기 (commit 은 app 가 책임).
        # 새 hero 의 값으로 폼을 다시 채운다.
        self._hero_idx = idx
        self._loading = True
        try:
            self._load_current_hero()
        finally:
            self._loading = False
        # hero 변경 자체는 dirty 가 아님 (단순 표시 전환).
        self._set_dirty(False)

    # ---------------- 입력 수집/검증 ----------------

    def _collect_data(self) -> HeroData:
        try:
            trade = int(self._var_trade.get())
            robber = int(self._var_robber.get())
            adven = int(self._var_adven.get())
            money = int(self._var_money.get())
        except (tk.TclError, ValueError):
            raise ValueError("주인공: 숫자 필드에 잘못된 값이 있습니다.")

        if not _in_range(trade, 0, 50000):
            raise ValueError("주인공: 교역 명성은 0..50000 범위여야 합니다.")
        if not _in_range(robber, 0, 50000):
            raise ValueError("주인공: 해적 명성은 0..50000 범위여야 합니다.")
        if not _in_range(adven, 0, 50000):
            raise ValueError("주인공: 모험 명성은 0..50000 범위여야 합니다.")
        if not _in_range(money, 0, 0xFFFFFFFF):
            raise ValueError("주인공: 자금은 0..4294967295 범위여야 합니다.")

        favor_stored: dict[str, int] = {}
        for label, key in _FAVOR_LABELS:
            try:
                v = int(self._var_favor[key].get())
            except (tk.TclError, ValueError):
                raise ValueError(f"주인공: 친밀도({label}) 값이 숫자가 아닙니다.")
            if not _in_range(v, -100, 100):
                raise ValueError(
                    f"주인공: 친밀도({label}) 는 -100..+100 범위여야 합니다."
                )
            favor_stored[key] = v + 100  # 저장 형식 0..200

        peer_list = Ipeer if self._state.c_hero == AAL else Epeer
        peer_text = self._var_peer.get()
        try:
            peer_idx = list(peer_list).index(peer_text)
        except ValueError:
            raise ValueError("주인공: 작위를 선택하세요.")

        abil = Abil(
            trade=trade,
            robber=robber,
            adven=adven,
            pro=favor_stored["pro"],
            spa=favor_stored["spa"],
            osm=favor_stored["osm"],
            eng=favor_stored["eng"],
            ita=favor_stored["ita"],
            ned=favor_stored["ned"],
            none=0,
            peer=peer_idx,
        )
        return HeroData(abil=abil, money=money)

    # ---------------- 위젯 활성화 ----------------

    def _set_inputs_state(self, st: str) -> None:
        combo_state = "readonly" if st == "normal" else "disabled"
        try:
            self._cb_hero.configure(state=combo_state)
            self._cb_peer.configure(state=combo_state)
        except tk.TclError:
            pass
        for child in self.winfo_children():
            self._cascade_state(child, st, combo_state)

    def _cascade_state(self, widget: tk.Misc, st: str, combo_state: str) -> None:
        cls = widget.winfo_class()
        try:
            if cls in ("TSpinbox", "TEntry", "TButton"):
                widget.configure(state=st)
            elif cls == "TCombobox":
                widget.configure(state=combo_state)
        except tk.TclError:
            pass
        for ch in widget.winfo_children():
            self._cascade_state(ch, st, combo_state)


def _in_range(v: int, lo: int, hi: int) -> bool:
    return lo <= v <= hi
