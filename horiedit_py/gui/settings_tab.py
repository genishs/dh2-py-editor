"""게임 기본 설정 탭.

MAIN.EXE 의 함선 ROM (Ship4 / Ship5) 과 슬롯 내 등장공업치를 편집한다.

lhull 단일 ROM 테이블은 위치가 미확인이라 (analysis/analysis_E_lhull_table.md)
어떤 sub-tab 에서도 lhull 편집 메뉴를 추가하지 않는다.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Optional

from horiedit_py.common import (
    EditorState,
    Ship4,
    Ship5,
    decode_kr,
    encode_kr_fixed,
)
from horiedit_py.data.game import (
    KOGYO_OFFSET_IN_SLOT,
    MAINEXE_KOGYO_TABLE_ESTIMATED,
    MAINEXE_TABLE_LEN,
    load_kogyo_table,
    load_ship4_rom,
    load_ship5_rom,
    load_u16_table,
    main_exe_path,
    save_kogyo_one,
    save_ship4_rom,
    save_ship5_rom,
    save_u16_table_one,
)


_HEADER_HINT = (
    "[참고] 이 탭은 MAIN.EXE 또는 슬롯 내 ROM 데이터를 직접 편집합니다.\n"
    "       편집 전 MAIN.EXE / KOUKAI2.DAT 백업을 권장합니다."
)

_NO_MAINEXE_MSG = (
    "MAIN.EXE 를 찾지 못했습니다.\n"
    "이 프로그램을 KOUKAI2.DAT 와 MAIN.EXE 가 같이 있는 게임 폴더에서 실행해 주세요."
)

_KOGYO_HINT = (
    "[추정 위치 — 검증 필요] 분석 결과 슬롯 내 0x06FEB (uint16 LE × 25, ×10 스케일).\n"
    "실제 게임 표시값 = 저장값 × 10 으로 보입니다 (analysis_D_industry_table.md).\n"
    "검증되지 않았으므로 변경 시 게임 동작이 이상할 수 있습니다."
)


def _ship_display_names(state: EditorState) -> list[str]:
    """25종 함선 표시 이름. 캐시가 비어 있으면 fallback."""
    out: list[str] = []
    for i in range(MAINEXE_TABLE_LEN):
        name = ""
        if 0 <= i < len(state.ship_name):
            name = (state.ship_name[i] or "").strip()
        if not name:
            name = f"함선 #{i:02d}"
        out.append(name)
    return out


def _in_range(v: int, lo: int, hi: int) -> bool:
    return lo <= v <= hi


class SettingsTab(ttk.Frame):
    """게임 기본 설정 탭. Ship4 / Ship5 / 등장공업치 sub-tab 보유."""

    def __init__(self, master: tk.Misc, state: EditorState) -> None:
        super().__init__(master, padding=8)
        self._state = state
        self._slot_loaded = False

        # 동적 컨테이너 (MAIN.EXE 유무에 따라 내용이 달라진다)
        self._inner: Optional[ttk.Frame] = None
        self._ship4_panel: Optional[_Ship4Panel] = None
        self._ship5_panel: Optional[_Ship5Panel] = None
        self._kogyo_panel: Optional[_KogyoPanel] = None
        self._missing_label: Optional[ttk.Label] = None

        self._build_initial()

    # ---------------- 외부 API ----------------

    def reload(self) -> None:
        """슬롯 변경 또는 외부 갱신. MAIN.EXE 재확인 + 모든 sub-tab 데이터 새로고침."""
        self._slot_loaded = True
        self._rebuild_for_current_environment()

    def reset(self) -> None:
        """슬롯 미선택 상태로 되돌림."""
        self._slot_loaded = False
        if self._ship4_panel is not None:
            self._ship4_panel.set_enabled(False)
        if self._ship5_panel is not None:
            self._ship5_panel.set_enabled(False)
        if self._kogyo_panel is not None:
            self._kogyo_panel.set_enabled(False)

    # ---------------- 내부 구성 ----------------

    def _build_initial(self) -> None:
        # 위쪽 안내 라벨 (항상 표시)
        self._hint_label = ttk.Label(
            self, text=_HEADER_HINT, foreground="#555", justify="left"
        )
        self._hint_label.pack(side="top", fill="x", padx=4, pady=(0, 6))

        self._content = ttk.Frame(self)
        self._content.pack(side="top", fill="both", expand=True)

        self._rebuild_for_current_environment()

    def _clear_content(self) -> None:
        for child in list(self._content.winfo_children()):
            child.destroy()
        self._inner = None
        self._ship4_panel = None
        self._ship5_panel = None
        self._kogyo_panel = None
        self._missing_label = None

    def _rebuild_for_current_environment(self) -> None:
        main_exe = main_exe_path(self._state)
        self._clear_content()

        if main_exe is None:
            self._missing_label = ttk.Label(
                self._content,
                text=_NO_MAINEXE_MSG,
                anchor="center",
                justify="center",
                foreground="#a00",
            )
            self._missing_label.pack(expand=True, fill="both", padx=12, pady=12)
            return

        # 정상: sub-Notebook
        self._inner = ttk.Frame(self._content)
        self._inner.pack(fill="both", expand=True)

        nb = ttk.Notebook(self._inner)
        nb.pack(fill="both", expand=True)

        names = _ship_display_names(self._state)

        self._ship4_panel = _Ship4Panel(nb, self._state, main_exe, names)
        nb.add(self._ship4_panel, text="함선 정적 스펙 (Ship4 ROM)")

        self._ship5_panel = _Ship5Panel(nb, self._state, main_exe, names)
        nb.add(self._ship5_panel, text="함선 이름·외형 (Ship5 ROM)")

        self._kogyo_panel = _KogyoPanel(nb, self._state, main_exe, names)
        nb.add(self._kogyo_panel, text="등장공업치 (추정)")

        # 슬롯 로드 상태에 따라 활성화. 등장공업치는 슬롯이 필요.
        slot_ok = self._slot_loaded
        # Ship4/Ship5 는 MAIN.EXE 만 필요하므로 항상 사용 가능.
        self._ship4_panel.set_enabled(True)
        self._ship5_panel.set_enabled(True)
        self._kogyo_panel.set_enabled(slot_ok)


# ---------------------------------------------------------------------------
# Sub-panel: Ship4 ROM
# ---------------------------------------------------------------------------


class _Ship4Panel(ttk.Frame):
    """Ship4 ROM 편집 (확정 위치 0x40871). 25종 함선 lrudder/lsail/lcrew/dcrew/capacity/lnowea."""

    def __init__(
        self,
        master: tk.Misc,
        state: EditorState,
        main_exe,
        ship_names: list[str],
    ) -> None:
        super().__init__(master, padding=8)
        self._state = state
        self._main_exe = main_exe
        self._ship_names = ship_names
        self._idx = 0
        self._enabled = False
        self._current: Optional[Ship4] = None  # none[5] 보존용

        self._var_lrudder = tk.IntVar(value=0)
        self._var_lsail = tk.IntVar(value=0)
        self._var_lcrew_max = tk.IntVar(value=0)  # 표시값 = lcrew * 10
        self._var_dcrew = tk.IntVar(value=0)
        self._var_capacity = tk.IntVar(value=0)
        self._var_lnowea = tk.IntVar(value=0)

        self._build()

    def _build(self) -> None:
        # 좌측 함선 목록
        left = ttk.Frame(self)
        left.pack(side="left", fill="y", padx=(0, 8))
        ttk.Label(left, text="함선 종류 (25종):").pack(side="top", anchor="w")
        list_frame = ttk.Frame(left)
        list_frame.pack(side="top", fill="y", expand=True)
        self._listbox = tk.Listbox(list_frame, height=18, exportselection=False, width=22)
        sb = ttk.Scrollbar(list_frame, orient="vertical", command=self._listbox.yview)
        self._listbox.configure(yscrollcommand=sb.set)
        self._listbox.pack(side="left", fill="y", expand=True)
        sb.pack(side="right", fill="y")
        for i, name in enumerate(self._ship_names):
            self._listbox.insert("end", f"{i:02d}. {name}")
        self._listbox.bind("<<ListboxSelect>>", self._on_ship_selected)

        # 우측 폼
        right = ttk.Frame(self)
        right.pack(side="left", fill="both", expand=True)

        form = ttk.LabelFrame(right, text="Ship4 ROM 필드", padding=8)
        form.pack(side="top", fill="x")

        self._add_spin(form, 0, "최대 회전력 (lrudder)", self._var_lrudder, 0, 255)
        self._add_spin(form, 1, "최대 돛 (lsail)", self._var_lsail, 0, 255)
        self._add_spin(
            form,
            2,
            "최대 승무원 (lcrew × 10)",
            self._var_lcrew_max,
            0,
            2550,
        )
        ttk.Label(
            form,
            text="* 저장 시 //10. 0..2550 범위. lcrew 자체는 0..255.",
            foreground="#888",
        ).grid(row=3, column=0, columnspan=2, sticky="w", padx=4)
        self._add_spin(form, 4, "필요 승무원 (dcrew)", self._var_dcrew, 0, 255)
        self._add_spin(form, 5, "최대 적재량 (capacity)", self._var_capacity, 0, 65535)
        self._add_spin(form, 6, "최대 무기수 (lnowea)", self._var_lnowea, 0, 255)

        # 버튼
        btns = ttk.Frame(right)
        btns.pack(side="top", fill="x", pady=8)
        self._btn_reload = ttk.Button(btns, text="다시 불러오기", command=self._on_reload)
        self._btn_reload.pack(side="right", padx=4)
        self._btn_save = ttk.Button(btns, text="저장", command=self._on_save)
        self._btn_save.pack(side="right", padx=4)

        # 안내
        note = ttk.Label(
            right,
            text=(
                "이 편집은 MAIN.EXE 의 ROM 만 변경합니다.\n"
                "주인공 함대의 슬롯 내 데이터는 영향받지 않습니다."
            ),
            foreground="#666",
            justify="left",
        )
        note.pack(side="top", anchor="w")

        # 기본 선택
        if self._ship_names:
            self._listbox.selection_set(0)
            self._listbox.see(0)
            self._load_current()

    def _add_spin(
        self,
        parent: tk.Misc,
        row: int,
        label: str,
        var: tk.IntVar,
        lo: int,
        hi: int,
    ) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=4, pady=3)
        sp = ttk.Spinbox(parent, from_=lo, to=hi, textvariable=var, width=10)
        sp.grid(row=row, column=1, sticky="w", padx=4, pady=3)

    # -------- 로드/저장 --------

    def _on_ship_selected(self, _e: object = None) -> None:
        sel = self._listbox.curselection()
        if not sel:
            return
        self._idx = int(sel[0])
        self._load_current()

    def _on_reload(self) -> None:
        if not self._enabled:
            return
        self._load_current()

    def _load_current(self) -> None:
        if not self._enabled:
            return
        try:
            ship4 = load_ship4_rom(self._main_exe, self._idx)
        except Exception as e:
            messagebox.showerror("Ship4 ROM 로드 실패", str(e))
            return
        self._current = ship4
        self._var_lrudder.set(ship4.lrudder)
        self._var_lsail.set(ship4.lsail)
        self._var_lcrew_max.set(ship4.lcrew * 10)
        self._var_dcrew.set(ship4.dcrew)
        self._var_capacity.set(ship4.capacity)
        self._var_lnowea.set(ship4.lnowea)

    def _on_save(self) -> None:
        if not self._enabled:
            return
        try:
            lrudder = int(self._var_lrudder.get())
            lsail = int(self._var_lsail.get())
            lcrew_max = int(self._var_lcrew_max.get())
            dcrew = int(self._var_dcrew.get())
            capacity = int(self._var_capacity.get())
            lnowea = int(self._var_lnowea.get())
        except (tk.TclError, ValueError):
            messagebox.showerror("입력 오류", "숫자 필드에 잘못된 값이 있습니다.")
            return

        if not _in_range(lrudder, 0, 255):
            messagebox.showerror("입력 오류", "최대 회전력은 0..255 입니다.")
            return
        if not _in_range(lsail, 0, 255):
            messagebox.showerror("입력 오류", "최대 돛은 0..255 입니다.")
            return
        if not _in_range(lcrew_max, 0, 2550):
            messagebox.showerror("입력 오류", "최대 승무원(×10)은 0..2550 입니다.")
            return
        if not _in_range(dcrew, 0, 255):
            messagebox.showerror("입력 오류", "필요 승무원은 0..255 입니다.")
            return
        if not _in_range(capacity, 0, 65535):
            messagebox.showerror("입력 오류", "최대 적재량은 0..65535 입니다.")
            return
        if not _in_range(lnowea, 0, 255):
            messagebox.showerror("입력 오류", "최대 무기수는 0..255 입니다.")
            return

        # none[5] 보존: 직전 로드 값을 사용
        try:
            base = self._current if self._current is not None else load_ship4_rom(
                self._main_exe, self._idx
            )
        except Exception as e:
            messagebox.showerror("Ship4 ROM 재읽기 실패", str(e))
            return

        ship4 = Ship4(
            lrudder=lrudder,
            lsail=lsail,
            lcrew=lcrew_max // 10,
            dcrew=dcrew,
            capacity=capacity,
            lnowea=lnowea,
            none=base.none,
        )

        try:
            save_ship4_rom(self._main_exe, self._idx, ship4)
        except Exception as e:
            messagebox.showerror("Ship4 ROM 저장 실패", str(e))
            return

        self._current = ship4
        # 표시값 갱신 (//10 절삭 결과를 사용자에게 보여주기 위해)
        self._var_lcrew_max.set(ship4.lcrew * 10)
        messagebox.showinfo("저장 완료", f"Ship4 ROM (함선 {self._idx:02d}) 저장 완료.")

    # -------- 활성/비활성 --------

    def set_enabled(self, on: bool) -> None:
        self._enabled = on
        st = "normal" if on else "disabled"
        try:
            self._listbox.configure(state="normal" if on else "disabled")
        except tk.TclError:
            pass
        for child in self.winfo_children():
            _cascade_state(child, st)
        if on:
            # 활성화 직후, 선택된 함선이 있으면 다시 로드
            if not self._listbox.curselection() and self._ship_names:
                self._listbox.selection_set(0)
            self._load_current()


# ---------------------------------------------------------------------------
# Sub-panel: Ship5 ROM
# ---------------------------------------------------------------------------


class _Ship5Panel(ttk.Frame):
    """Ship5 ROM 편집 (확정 위치 0x405FD). name(18B), sform, bform 상위 4비트."""

    def __init__(
        self,
        master: tk.Misc,
        state: EditorState,
        main_exe,
        ship_names: list[str],
    ) -> None:
        super().__init__(master, padding=8)
        self._state = state
        self._main_exe = main_exe
        self._ship_names = ship_names
        self._idx = 0
        self._enabled = False
        self._current: Optional[Ship5] = None  # bform 하위 4비트 / none[5] 보존

        self._var_name = tk.StringVar()
        self._var_sform = tk.IntVar(value=0)
        self._var_bform_hi = tk.IntVar(value=0)  # 상위 4비트만

        self._build()

    def _build(self) -> None:
        # 좌측 함선 목록
        left = ttk.Frame(self)
        left.pack(side="left", fill="y", padx=(0, 8))
        ttk.Label(left, text="함선 종류 (25종):").pack(side="top", anchor="w")
        list_frame = ttk.Frame(left)
        list_frame.pack(side="top", fill="y", expand=True)
        self._listbox = tk.Listbox(list_frame, height=18, exportselection=False, width=22)
        sb = ttk.Scrollbar(list_frame, orient="vertical", command=self._listbox.yview)
        self._listbox.configure(yscrollcommand=sb.set)
        self._listbox.pack(side="left", fill="y", expand=True)
        sb.pack(side="right", fill="y")
        for i, name in enumerate(self._ship_names):
            self._listbox.insert("end", f"{i:02d}. {name}")
        self._listbox.bind("<<ListboxSelect>>", self._on_ship_selected)

        # 우측 폼
        right = ttk.Frame(self)
        right.pack(side="left", fill="both", expand=True)

        form = ttk.LabelFrame(right, text="Ship5 ROM 필드", padding=8)
        form.pack(side="top", fill="x")

        ttk.Label(form, text="배이름 (18 byte 한글)").grid(
            row=0, column=0, sticky="w", padx=4, pady=3
        )
        self._entry_name = ttk.Entry(form, textvariable=self._var_name, width=18)
        self._entry_name.grid(row=0, column=1, sticky="w", padx=4, pady=3)

        ttk.Label(form, text="평상시 외형 (sform)").grid(
            row=1, column=0, sticky="w", padx=4, pady=3
        )
        ttk.Spinbox(
            form, from_=0, to=255, textvariable=self._var_sform, width=10
        ).grid(row=1, column=1, sticky="w", padx=4, pady=3)

        ttk.Label(form, text="부울때 외형 (bform 상위 4비트)").grid(
            row=2, column=0, sticky="w", padx=4, pady=3
        )
        ttk.Spinbox(
            form, from_=0, to=15, textvariable=self._var_bform_hi, width=10
        ).grid(row=2, column=1, sticky="w", padx=4, pady=3)

        ttk.Label(
            form,
            text="* 저장: (new & 0x0F) << 4 | (기존 bform & 0x0F). 하위 4비트는 보존.",
            foreground="#888",
        ).grid(row=3, column=0, columnspan=2, sticky="w", padx=4)

        # 버튼
        btns = ttk.Frame(right)
        btns.pack(side="top", fill="x", pady=8)
        self._btn_reload = ttk.Button(btns, text="다시 불러오기", command=self._on_reload)
        self._btn_reload.pack(side="right", padx=4)
        self._btn_save = ttk.Button(btns, text="저장", command=self._on_save)
        self._btn_save.pack(side="right", padx=4)

        if self._ship_names:
            self._listbox.selection_set(0)
            self._listbox.see(0)
            self._load_current()

    # -------- 로드/저장 --------

    def _on_ship_selected(self, _e: object = None) -> None:
        sel = self._listbox.curselection()
        if not sel:
            return
        self._idx = int(sel[0])
        self._load_current()

    def _on_reload(self) -> None:
        if not self._enabled:
            return
        self._load_current()

    def _load_current(self) -> None:
        if not self._enabled:
            return
        try:
            ship5 = load_ship5_rom(self._main_exe, self._idx)
        except Exception as e:
            messagebox.showerror("Ship5 ROM 로드 실패", str(e))
            return
        self._current = ship5
        self._var_name.set(decode_kr(ship5.name))
        self._var_sform.set(ship5.sform)
        self._var_bform_hi.set((ship5.bform >> 4) & 0x0F)

    def _on_save(self) -> None:
        if not self._enabled:
            return
        try:
            sform = int(self._var_sform.get())
            bform_hi = int(self._var_bform_hi.get())
        except (tk.TclError, ValueError):
            messagebox.showerror("입력 오류", "숫자 필드에 잘못된 값이 있습니다.")
            return
        name = self._var_name.get()

        if not _in_range(sform, 0, 255):
            messagebox.showerror("입력 오류", "평상시 외형은 0..255 입니다.")
            return
        if not _in_range(bform_hi, 0, 15):
            messagebox.showerror("입력 오류", "부울때 외형(상위 4비트)은 0..15 입니다.")
            return

        # none[5] / bform 하위 4비트 보존
        try:
            base = self._current if self._current is not None else load_ship5_rom(
                self._main_exe, self._idx
            )
        except Exception as e:
            messagebox.showerror("Ship5 ROM 재읽기 실패", str(e))
            return

        new_bform = ((bform_hi & 0x0F) << 4) | (base.bform & 0x0F)
        try:
            name_bytes = encode_kr_fixed(name, 18)
        except Exception as e:
            messagebox.showerror("입력 오류", f"배이름 인코딩 실패: {e}")
            return

        ship5 = Ship5(
            name=name_bytes,
            sform=sform,
            bform=new_bform,
            none=base.none,
        )

        try:
            save_ship5_rom(self._main_exe, self._idx, ship5)
        except Exception as e:
            messagebox.showerror("Ship5 ROM 저장 실패", str(e))
            return

        self._current = ship5
        # 인코딩/잘림 결과 다시 표시
        self._var_name.set(decode_kr(ship5.name))
        messagebox.showinfo("저장 완료", f"Ship5 ROM (함선 {self._idx:02d}) 저장 완료.")

    # -------- 활성/비활성 --------

    def set_enabled(self, on: bool) -> None:
        self._enabled = on
        st = "normal" if on else "disabled"
        try:
            self._listbox.configure(state="normal" if on else "disabled")
        except tk.TclError:
            pass
        for child in self.winfo_children():
            _cascade_state(child, st)
        if on:
            if not self._listbox.curselection() and self._ship_names:
                self._listbox.selection_set(0)
            self._load_current()


# ---------------------------------------------------------------------------
# Sub-panel: 등장공업치 (추정)
# ---------------------------------------------------------------------------


class _KogyoPanel(ttk.Frame):
    """등장공업치 편집 (추정). 슬롯 내 0x06FEB + 선택적 MAIN.EXE 0x42722 동기화."""

    def __init__(
        self,
        master: tk.Misc,
        state: EditorState,
        main_exe,
        ship_names: list[str],
    ) -> None:
        super().__init__(master, padding=8)
        self._state = state
        self._main_exe = main_exe
        self._ship_names = ship_names
        self._idx = 0
        self._enabled = False
        self._sync_in_progress = False  # spinbox 양방향 동기화 가드

        self._var_stored = tk.IntVar(value=0)
        self._var_display = tk.IntVar(value=0)
        self._var_sync_mainexe = tk.BooleanVar(value=False)

        self._build()

    def _build(self) -> None:
        # 안내
        ttk.Label(
            self, text=_KOGYO_HINT, foreground="#a00", justify="left"
        ).pack(side="top", fill="x", pady=(0, 6))

        body = ttk.Frame(self)
        body.pack(side="top", fill="both", expand=True)

        # Treeview
        tree_frame = ttk.Frame(body)
        tree_frame.pack(side="left", fill="both", expand=True, padx=(0, 8))
        cols = ("idx", "name", "stored", "display")
        self._tree = ttk.Treeview(
            tree_frame, columns=cols, show="headings", height=18, selectmode="browse"
        )
        self._tree.heading("idx", text="#")
        self._tree.heading("name", text="함선 이름")
        self._tree.heading("stored", text="저장값")
        self._tree.heading("display", text="표시값 (×10)")
        self._tree.column("idx", width=40, anchor="e")
        self._tree.column("name", width=180, anchor="w")
        self._tree.column("stored", width=80, anchor="e")
        self._tree.column("display", width=100, anchor="e")
        sb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=sb.set)
        self._tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self._tree.bind("<<TreeviewSelect>>", self._on_tree_selected)

        # 우측 폼
        right = ttk.Frame(body)
        right.pack(side="left", fill="y")

        form = ttk.LabelFrame(right, text="선택 함선 편집", padding=8)
        form.pack(side="top", fill="x")

        ttk.Label(form, text="저장값").grid(row=0, column=0, sticky="w", padx=4, pady=3)
        self._sp_stored = ttk.Spinbox(
            form,
            from_=0,
            to=65535,
            textvariable=self._var_stored,
            width=10,
            command=self._on_stored_changed,
        )
        self._sp_stored.grid(row=0, column=1, sticky="w", padx=4, pady=3)
        # 키보드 입력 시에도 동기화
        self._var_stored.trace_add("write", self._on_stored_var_write)

        ttk.Label(form, text="표시값 (×10)").grid(
            row=1, column=0, sticky="w", padx=4, pady=3
        )
        self._sp_display = ttk.Spinbox(
            form,
            from_=0,
            to=655350,
            increment=10,
            textvariable=self._var_display,
            width=10,
            command=self._on_display_changed,
        )
        self._sp_display.grid(row=1, column=1, sticky="w", padx=4, pady=3)
        self._var_display.trace_add("write", self._on_display_var_write)

        ttk.Label(
            form,
            text="* 저장값 ↔ 표시값 자동 동기화 (× 또는 ÷ 10)",
            foreground="#888",
        ).grid(row=2, column=0, columnspan=2, sticky="w", padx=4)

        self._cb_sync_mainexe = ttk.Checkbutton(
            form,
            text="MAIN.EXE 의 ROM (0x42722) 도 동기화",
            variable=self._var_sync_mainexe,
        )
        self._cb_sync_mainexe.grid(
            row=3, column=0, columnspan=2, sticky="w", padx=4, pady=(8, 4)
        )

        # 버튼
        btns = ttk.Frame(right)
        btns.pack(side="top", fill="x", pady=8)
        self._btn_reload = ttk.Button(btns, text="다시 불러오기", command=self._on_reload)
        self._btn_reload.pack(side="right", padx=4)
        self._btn_save = ttk.Button(btns, text="저장", command=self._on_save)
        self._btn_save.pack(side="right", padx=4)

        # 초기 행 채우기 (이름만; 값은 reload 호출 시 채워진다)
        for i, name in enumerate(self._ship_names):
            self._tree.insert(
                "", "end", iid=str(i), values=(f"{i:02d}", name, "-", "-")
            )

    # -------- 양방향 동기화 --------

    def _on_stored_changed(self) -> None:
        self._sync_from_stored()

    def _on_stored_var_write(self, *_a: object) -> None:
        # 자동 동기화 도중에는 무시
        if self._sync_in_progress:
            return
        self._sync_from_stored()

    def _on_display_changed(self) -> None:
        self._sync_from_display()

    def _on_display_var_write(self, *_a: object) -> None:
        if self._sync_in_progress:
            return
        self._sync_from_display()

    def _sync_from_stored(self) -> None:
        try:
            v = int(self._var_stored.get())
        except (tk.TclError, ValueError):
            return
        self._sync_in_progress = True
        try:
            self._var_display.set(v * 10)
        finally:
            self._sync_in_progress = False

    def _sync_from_display(self) -> None:
        try:
            v = int(self._var_display.get())
        except (tk.TclError, ValueError):
            return
        self._sync_in_progress = True
        try:
            self._var_stored.set(v // 10)
        finally:
            self._sync_in_progress = False

    # -------- 로드/저장 --------

    def _on_tree_selected(self, _e: object = None) -> None:
        sel = self._tree.selection()
        if not sel:
            return
        try:
            self._idx = int(sel[0])
        except ValueError:
            return
        # 선택 행의 저장값을 폼에 반영
        item = self._tree.item(sel[0])
        vals = item.get("values", [])
        if len(vals) >= 3:
            try:
                stored = int(vals[2])
            except (TypeError, ValueError):
                stored = 0
            self._sync_in_progress = True
            try:
                self._var_stored.set(stored)
                self._var_display.set(stored * 10)
            finally:
                self._sync_in_progress = False

    def _on_reload(self) -> None:
        if not self._enabled:
            return
        self._reload_table()

    def _reload_table(self) -> None:
        """슬롯에서 25개 값을 다시 읽어 Treeview 갱신."""
        try:
            slot_vals = load_kogyo_table(self._state)
        except Exception as e:
            messagebox.showerror("등장공업치 로드 실패", str(e))
            return

        # MAIN.EXE 측 값을 같이 보여주지는 않지만, 일관성 확인용으로 읽기 시도(실패 무시)
        for i in range(MAINEXE_TABLE_LEN):
            stored = slot_vals[i] if i < len(slot_vals) else 0
            self._tree.item(
                str(i),
                values=(
                    f"{i:02d}",
                    self._ship_names[i],
                    int(stored),
                    int(stored) * 10,
                ),
            )

        # 현재 선택 항목 폼 갱신
        if self._tree.selection():
            self._on_tree_selected()
        else:
            # 첫 행 선택
            if self._ship_names:
                self._tree.selection_set("0")
                self._tree.see("0")

    def _on_save(self) -> None:
        if not self._enabled:
            return
        try:
            stored = int(self._var_stored.get())
        except (tk.TclError, ValueError):
            messagebox.showerror("입력 오류", "저장값이 숫자가 아닙니다.")
            return
        if not _in_range(stored, 0, 65535):
            messagebox.showerror("입력 오류", "저장값은 0..65535 (uint16) 범위여야 합니다.")
            return

        idx = self._idx
        if not (0 <= idx < MAINEXE_TABLE_LEN):
            messagebox.showerror("입력 오류", "함선이 선택되지 않았습니다.")
            return

        # 슬롯에 저장
        try:
            save_kogyo_one(self._state, idx, stored)
            self._state.fp.flush()
        except Exception as e:
            messagebox.showerror("슬롯 저장 실패", str(e))
            return

        # MAIN.EXE 동기화 (옵션)
        if self._var_sync_mainexe.get():
            try:
                save_u16_table_one(
                    self._main_exe, MAINEXE_KOGYO_TABLE_ESTIMATED, idx, stored
                )
            except Exception as e:
                messagebox.showerror(
                    "MAIN.EXE 동기화 실패",
                    f"슬롯 저장은 완료되었으나 MAIN.EXE 쓰기 실패: {e}",
                )
                # 슬롯은 이미 저장됨 — Treeview 만 갱신하고 이탈
                self._update_row(idx, stored)
                return

        self._update_row(idx, stored)
        target = "슬롯 + MAIN.EXE" if self._var_sync_mainexe.get() else "슬롯"
        messagebox.showinfo(
            "저장 완료",
            f"등장공업치 (함선 {idx:02d}) 저장 완료 [{target}].",
        )

    def _update_row(self, idx: int, stored: int) -> None:
        if 0 <= idx < MAINEXE_TABLE_LEN:
            self._tree.item(
                str(idx),
                values=(
                    f"{idx:02d}",
                    self._ship_names[idx],
                    int(stored),
                    int(stored) * 10,
                ),
            )

    # -------- 활성/비활성 --------

    def set_enabled(self, on: bool) -> None:
        self._enabled = on
        st = "normal" if on else "disabled"
        for child in self.winfo_children():
            _cascade_state(child, st)
        # Treeview 는 cascade 로 처리되지 않을 수 있음
        try:
            self._tree.configure(selectmode="browse" if on else "none")
        except tk.TclError:
            pass
        if on:
            self._reload_table()
        else:
            # 비활성 시 표시값 초기화
            for i in range(MAINEXE_TABLE_LEN):
                try:
                    self._tree.item(
                        str(i),
                        values=(f"{i:02d}", self._ship_names[i], "-", "-"),
                    )
                except tk.TclError:
                    pass


# ---------------------------------------------------------------------------
# 공통 유틸: 자식 위젯 트리 일괄 활성/비활성
# ---------------------------------------------------------------------------


def _cascade_state(widget: tk.Misc, st: str) -> None:
    cls = widget.winfo_class()
    try:
        if cls in ("TSpinbox", "TEntry", "TButton", "TCheckbutton"):
            widget.configure(state=st)
        elif cls == "TCombobox":
            widget.configure(state="readonly" if st == "normal" else "disabled")
        elif cls == "Listbox":
            widget.configure(state="normal" if st == "normal" else "disabled")
    except tk.TclError:
        pass
    for ch in widget.winfo_children():
        _cascade_state(ch, st)
