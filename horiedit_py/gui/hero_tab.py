"""주인공 능력치 편집 탭."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Optional

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
    """주인공 능력치 / 자금 / 작위 / 친밀도 편집 탭 (full functional)."""

    def __init__(self, master: tk.Misc, state: EditorState) -> None:
        super().__init__(master, padding=12)
        self._state = state
        self._hero_idx = 0
        self._loaded = False
        self._slot_loaded = False

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
        self._add_spinbox(fame, 0, "무역 명성", self._var_trade, 0, 65535)
        self._add_spinbox(fame, 1, "해적 명성", self._var_robber, 0, 65535)
        self._add_spinbox(fame, 2, "모험 명성", self._var_adven, 0, 65535)

        # 자금 + 작위
        misc = ttk.LabelFrame(self, text="자금 / 작위", padding=8)
        misc.grid(row=1, column=2, columnspan=2, sticky="nsew", padx=(6, 0), pady=4)
        self._add_spinbox(misc, 0, "자금", self._var_money, 0, 0xFFFFFFFF, width=14)
        ttk.Label(misc, text="작위").grid(row=1, column=0, sticky="w", padx=4, pady=4)
        self._cb_peer = ttk.Combobox(
            misc, textvariable=self._var_peer, state="readonly", width=14
        )
        self._cb_peer.grid(row=1, column=1, sticky="w", padx=4, pady=4)

        # 친밀도
        favor = ttk.LabelFrame(self, text="친밀도 (-100 ~ +100)", padding=8)
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

        # 버튼
        buttons = ttk.Frame(self)
        buttons.grid(row=3, column=0, columnspan=4, sticky="e", pady=(8, 0))
        self._btn_reload = ttk.Button(
            buttons, text="다시 불러오기", command=self._on_reload_clicked
        )
        self._btn_reload.grid(row=0, column=0, padx=4)
        self._btn_save = ttk.Button(buttons, text="저장", command=self._on_save_clicked)
        self._btn_save.grid(row=0, column=1, padx=4)

        # 안내 라벨 (슬롯 미선택 시)
        self._hint = ttk.Label(
            self, text="(슬롯을 먼저 선택하세요)", foreground="#888"
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

    # ---------------- 로드 / 저장 ----------------

    def reload(self) -> None:
        """슬롯 변경 또는 외부 갱신 시 호출. 콤보박스/값을 다시 채운다."""
        names = hero_names(self._state)
        self._cb_hero.configure(values=names)

        # 활성 영웅 기본 선택
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

    def reset(self) -> None:
        """슬롯 미선택 상태로 되돌림."""
        self._slot_loaded = False
        self._loaded = False
        self._set_inputs_state("disabled")
        self._hint.grid()

    def _load_current_hero(self) -> None:
        try:
            data = load_hero(self._state, self._hero_idx)
        except Exception as e:
            messagebox.showerror("주인공 로드 실패", str(e))
            return

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

        # 작위 콤보 채우기 (ipeer if c_hero==5(AAL) else epeer)
        peer_list = Ipeer if self._state.c_hero == AAL else Epeer
        self._cb_peer.configure(values=list(peer_list))
        peer_idx = abil.peer if 0 <= abil.peer < len(peer_list) else 0
        self._var_peer.set(peer_list[peer_idx])

        self._loaded = True

    def _on_hero_changed(self, _event: object = None) -> None:
        if not self._slot_loaded:
            return
        try:
            idx = list(self._cb_hero["values"]).index(self._var_hero.get())
        except ValueError:
            return
        self._hero_idx = idx
        self._load_current_hero()

    def _on_reload_clicked(self) -> None:
        if not self._slot_loaded:
            return
        self._load_current_hero()

    def _on_save_clicked(self) -> None:
        if not self._slot_loaded:
            return
        data = self._collect_data()
        if data is None:
            return
        try:
            save_hero(self._state, self._hero_idx, data)
            self._state.fp.flush()
        except Exception as e:
            messagebox.showerror("저장 실패", str(e))
            return
        messagebox.showinfo("저장 완료", "주인공 데이터를 저장했습니다.")

    def _collect_data(self) -> Optional[HeroData]:
        try:
            trade = int(self._var_trade.get())
            robber = int(self._var_robber.get())
            adven = int(self._var_adven.get())
            money = int(self._var_money.get())
        except (tk.TclError, ValueError):
            messagebox.showerror("입력 오류", "숫자 필드에 잘못된 값이 있습니다.")
            return None

        if not _in_range(trade, 0, 65535):
            messagebox.showerror("입력 오류", "무역 명성은 0..65535 범위여야 합니다.")
            return None
        if not _in_range(robber, 0, 65535):
            messagebox.showerror("입력 오류", "해적 명성은 0..65535 범위여야 합니다.")
            return None
        if not _in_range(adven, 0, 65535):
            messagebox.showerror("입력 오류", "모험 명성은 0..65535 범위여야 합니다.")
            return None
        if not _in_range(money, 0, 0xFFFFFFFF):
            messagebox.showerror("입력 오류", "자금은 0..4294967295 범위여야 합니다.")
            return None

        favor_stored: dict[str, int] = {}
        for label, key in _FAVOR_LABELS:
            try:
                v = int(self._var_favor[key].get())
            except (tk.TclError, ValueError):
                messagebox.showerror("입력 오류", f"친밀도({label}) 값이 숫자가 아닙니다.")
                return None
            if not _in_range(v, -100, 100):
                messagebox.showerror(
                    "입력 오류",
                    f"친밀도({label}) 는 -100..+100 범위여야 합니다.",
                )
                return None
            favor_stored[key] = v + 100  # 저장 형식 0..200

        peer_list = Ipeer if self._state.c_hero == AAL else Epeer
        peer_text = self._var_peer.get()
        try:
            peer_idx = list(peer_list).index(peer_text)
        except ValueError:
            messagebox.showerror("입력 오류", "작위를 선택하세요.")
            return None

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

    def _set_inputs_state(self, st: str) -> None:
        """입력 위젯 일괄 활성/비활성. ttk 에서는 'normal'/'disabled'."""
        # readonly 콤보는 'readonly' 로 되돌려야 한다.
        combo_state = "readonly" if st == "normal" else "disabled"
        try:
            self._cb_hero.configure(state=combo_state)
            self._cb_peer.configure(state=combo_state)
        except tk.TclError:
            pass
        # 나머지 위젯은 자식 트리 순회해서 'normal'/'disabled' 로
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
