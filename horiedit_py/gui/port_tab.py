"""항구 편집 탭 — 상업치 / 공업치 (analysis_I).

좌측: 130개 항구 Treeview (idx · 이름 · 상업치 · 공업치).
우측: 선택된 항구의 폼 (commerce, industry Spinbox).

dirty/commit/revert/reload 인터페이스는 PersonTab 과 동일 패턴.
물가(가설 +14..+23) 는 별도 확정 단계에서 추가 예정.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable, Optional

from horiedit_py.common import EditorState
from horiedit_py.data.port import (
    NUM_PORTS,
    iter_port_econ,
    load_port_econ,
    save_port_econ,
)


def _in_range(v: int, lo: int, hi: int) -> bool:
    return lo <= v <= hi


class PortTab(ttk.Frame):
    """항구 상업치/공업치 편집 탭."""

    def __init__(self, master: tk.Misc, state: EditorState) -> None:
        super().__init__(master, padding=8)
        self._state = state
        self._slot_loaded = False
        self._port_idx: Optional[int] = None

        self._loading = False
        self._dirty = False
        self._dirty_listeners: list[Callable[[], None]] = []

        self._var_commerce = tk.IntVar(value=0)
        self._var_industry = tk.IntVar(value=0)

        self._build()
        self._set_inputs_state("disabled")
        self._install_dirty_traces()

    # ---------------- UI ----------------

    def _build(self) -> None:
        self.columnconfigure(0, weight=2)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        self._build_left()
        self._build_right()

        self._hint = ttk.Label(
            self, text="(세이브 칸을 먼저 선택하세요)", foreground="#888",
        )
        self._hint.grid(row=1, column=0, columnspan=2, pady=(8, 0))

    def _build_left(self) -> None:
        left = ttk.Frame(self)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        left.rowconfigure(1, weight=1)
        left.columnconfigure(0, weight=1)

        ttk.Label(left, text="130개 항구 — 행을 클릭하면 우측 폼에 로드됩니다.")\
            .grid(row=0, column=0, sticky="w", pady=(0, 4))

        tv_frame = ttk.Frame(left)
        tv_frame.grid(row=1, column=0, sticky="nsew")
        tv_frame.rowconfigure(0, weight=1)
        tv_frame.columnconfigure(0, weight=1)

        cols = ("idx", "name", "commerce", "industry")
        self._tv = ttk.Treeview(
            tv_frame, columns=cols, show="headings", height=22, selectmode="browse",
        )
        self._tv.heading("idx", text="번호")
        self._tv.heading("name", text="항구")
        self._tv.heading("commerce", text="상업치")
        self._tv.heading("industry", text="공업치")
        self._tv.column("idx", width=50, anchor="center", stretch=False)
        self._tv.column("name", width=160, anchor="w")
        self._tv.column("commerce", width=80, anchor="e")
        self._tv.column("industry", width=80, anchor="e")
        self._tv.grid(row=0, column=0, sticky="nsew")

        sb = ttk.Scrollbar(tv_frame, orient="vertical", command=self._tv.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self._tv.configure(yscrollcommand=sb.set)

        self._tv.bind("<<TreeviewSelect>>", self._on_tv_select)

    def _build_right(self) -> None:
        right = ttk.Frame(self)
        right.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        right.columnconfigure(0, weight=1)

        self._lbl_current = ttk.Label(
            right, text="(선택된 항구 없음)", foreground="#444",
        )
        self._lbl_current.grid(row=0, column=0, sticky="w", pady=(0, 6))

        econ = ttk.LabelFrame(right, text="경제", padding=8)
        econ.grid(row=1, column=0, sticky="ew", pady=4)
        econ.columnconfigure(1, weight=1)

        ttk.Label(econ, text="상업치").grid(row=0, column=0, sticky="w", padx=2, pady=3)
        self._sp_commerce = ttk.Spinbox(
            econ, from_=0, to=65535, textvariable=self._var_commerce, width=10,
        )
        self._sp_commerce.grid(row=0, column=1, sticky="w", padx=2, pady=3)

        ttk.Label(econ, text="공업치").grid(row=1, column=0, sticky="w", padx=2, pady=3)
        self._sp_industry = ttk.Spinbox(
            econ, from_=0, to=65535, textvariable=self._var_industry, width=10,
        )
        self._sp_industry.grid(row=1, column=1, sticky="w", padx=2, pady=3)

        ttk.Label(
            econ,
            text="입력 범위: 0~65535 (게임에서 자연스러운 값은 약 0~1000).",
            foreground="#666",
        ).grid(row=2, column=0, columnspan=2, sticky="w", padx=2, pady=(4, 0))

        # caveat — analysis_I §4 참조
        warn = ttk.LabelFrame(right, text="주의 (시험 기능)", padding=8)
        warn.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        warn.columnconfigure(0, weight=1)
        ttk.Label(
            warn,
            text=(
                "• 항구 경제 항목은 비교적 최근에 분석된 영역입니다.\n"
                "• 일부 항구 값은 지도 좌표 정보와 저장 영역이 겹칠 수 있어,\n"
                "  너무 큰 값으로 바꾸면 지도가 깨질 수 있습니다.\n"
                "• 편집 전 저장 파일(KOUKAI2.DAT)을 복사해 두는 것을 권합니다."
            ),
            foreground="#a00",
            justify="left",
        ).grid(row=0, column=0, sticky="w")

    # ---------------- dirty ----------------

    def _install_dirty_traces(self) -> None:
        for v in (self._var_commerce, self._var_industry):
            v.trace_add("write", self._on_var_write)

    def _on_var_write(self, *_a: object) -> None:
        if self._loading or not self._slot_loaded or self._port_idx is None:
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
        return self._dirty and self._slot_loaded and self._port_idx is not None

    def add_dirty_listener(self, callback: Callable[[], None]) -> None:
        self._dirty_listeners.append(callback)

    def reload(self) -> None:
        self._loading = True
        try:
            self._slot_loaded = True
            self._port_idx = None
            self._populate_tree()
            self._clear_form()
            self._hint.grid_remove()
            self._set_inputs_state("normal")
            self._lbl_current.configure(text="(선택된 항구 없음)")
        finally:
            self._loading = False
        self._set_dirty(False)

    def reset(self) -> None:
        self._loading = True
        try:
            self._slot_loaded = False
            self._port_idx = None
            self._clear_tree()
            self._clear_form()
            self._set_inputs_state("disabled")
            self._hint.grid()
            self._lbl_current.configure(text="(선택된 항구 없음)")
        finally:
            self._loading = False
        self._set_dirty(False)

    def revert(self) -> None:
        if not self._slot_loaded or self._port_idx is None:
            self._set_dirty(False)
            return
        self._loading = True
        try:
            self._load_port_into_form(self._port_idx)
        finally:
            self._loading = False
        self._set_dirty(False)

    def commit(self) -> None:
        if not self._slot_loaded or self._port_idx is None or not self._dirty:
            return
        try:
            c = int(self._var_commerce.get())
            ind = int(self._var_industry.get())
        except (tk.TclError, ValueError):
            raise ValueError("항구: 상업치/공업치 값이 숫자가 아닙니다.")
        if not _in_range(c, 0, 65535):
            raise ValueError("항구: 상업치는 0..65535 범위여야 합니다.")
        if not _in_range(ind, 0, 65535):
            raise ValueError("항구: 공업치는 0..65535 범위여야 합니다.")
        try:
            save_port_econ(self._state, self._port_idx, c, ind)
        except Exception as e:
            raise ValueError(f"항구 저장 실패: {e}") from e

        self._refresh_tree_row(self._port_idx, c, ind)
        name = self._state.port_name[self._port_idx] if 0 <= self._port_idx < len(self._state.port_name) else ""
        self._lbl_current.configure(
            text=f"{self._port_idx}번 항구  {name}  (저장됨)"
        )
        self._set_dirty(False)

    # ---------------- 목록 ----------------

    def _populate_tree(self) -> None:
        self._clear_tree()
        try:
            for idx, name, c, ind in iter_port_econ(self._state):
                self._tv.insert(
                    "", "end", iid=str(idx), values=(idx, name, c, ind),
                )
        except Exception as e:
            messagebox.showerror("항구 목록 로드 실패", str(e))

    def _refresh_tree_row(self, idx: int, c: int, ind: int) -> None:
        iid = str(idx)
        if not self._tv.exists(iid):
            return
        name = self._state.port_name[idx] if 0 <= idx < len(self._state.port_name) else ""
        self._tv.item(iid, values=(idx, name, c, ind))

    def _clear_tree(self) -> None:
        for iid in self._tv.get_children():
            self._tv.delete(iid)

    def _on_tv_select(self, _event: object = None) -> None:
        if not self._slot_loaded:
            return
        sel = self._tv.selection()
        if not sel:
            return
        try:
            idx = int(sel[0])
        except ValueError:
            return
        if idx == self._port_idx:
            return
        # 다른 항구 로드: 폼 dirty 면 변경분이 폐기된다 (app 가 슬롯 변경에서만 다이얼로그)
        self._loading = True
        try:
            self._load_port_into_form(idx)
        finally:
            self._loading = False
        self._set_dirty(False)

    # ---------------- 폼 ----------------

    def _load_port_into_form(self, idx: int) -> None:
        if not (0 <= idx < NUM_PORTS):
            return
        try:
            c, ind = load_port_econ(self._state, idx)
        except Exception as e:
            messagebox.showerror("항구 로드 실패", str(e))
            return
        self._port_idx = idx
        self._var_commerce.set(c)
        self._var_industry.set(ind)
        name = self._state.port_name[idx] if 0 <= idx < len(self._state.port_name) else ""
        self._lbl_current.configure(text=f"{idx}번 항구  {name}")

    def _clear_form(self) -> None:
        self._var_commerce.set(0)
        self._var_industry.set(0)

    def _set_inputs_state(self, st: str) -> None:
        for w in (self._sp_commerce, self._sp_industry):
            try:
                w.configure(state=st)
            except tk.TclError:
                pass
