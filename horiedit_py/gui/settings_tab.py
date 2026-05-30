"""게임 기본 설정 탭.

MAIN.EXE 의 함선 ROM (Ship4 / Ship5) 을 편집한다.

이전 버전의 "등장공업치" sub-tab 은 제거되었다. analysis_G 에서 함선 record
구조가 발견되면서 등장공업치(요구공업치) 와 최대 내구도(lhull) 는 record 의
+0/+1 byte 임이 확정되었다. 두 항목은 "선박 탭 → 원래 함선 정보" 에서
편집한다.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable, Optional

from horiedit_py.common import (
    EditorState,
    Ship4,
    Ship5,
    decode_kr,
    encode_kr_fixed,
)
from horiedit_py.data.game import (
    MAINEXE_TABLE_LEN,
    load_ship4_rom,
    load_ship5_rom,
    main_exe_path,
    save_ship4_rom,
    save_ship5_rom,
)
from horiedit_py.data.port import (
    NUM_PORTS,
    PORT_SUPPLY_SIZE,
    load_port_supply,
    port_supply_is_standard,
    save_port_supply,
)


_HEADER_HINT = (
    "[참고] 이 탭은 게임 본체 파일(MAIN.EXE)을 직접 바꿉니다.\n"
    "       편집 전 게임 본체 파일 복사를 권장합니다.\n"
    "       등장공업치 / 최대 내구도는 [선박] 탭의 [원래 함선 정보] 에서 바꿀 수 있습니다."
)

_NO_MAINEXE_MSG = (
    "게임 본체 파일(MAIN.EXE)을 찾지 못했습니다.\n"
    "저장 파일과 게임이 함께 있는 게임 폴더에서 실행해 주세요."
)


def _ship_display_names(state: EditorState) -> list[str]:
    """25종 함선 표시 이름. 캐시가 비어 있으면 fallback."""
    out: list[str] = []
    for i in range(MAINEXE_TABLE_LEN):
        name = ""
        if 0 <= i < len(state.ship_name):
            name = (state.ship_name[i] or "").strip()
        if not name:
            name = f"함선 {i + 1}번"
        out.append(name)
    return out


def _in_range(v: int, lo: int, hi: int) -> bool:
    return lo <= v <= hi


class SettingsTab(ttk.Frame):
    """게임 기본 설정 탭. Ship4 / Ship5 sub-tab 보유."""

    def __init__(self, master: tk.Misc, state: EditorState) -> None:
        super().__init__(master, padding=8)
        self._state = state
        self._slot_loaded = False
        self._dirty_listeners: list[Callable[[], None]] = []

        # 동적 컨테이너 (MAIN.EXE 유무에 따라 내용이 달라진다)
        self._inner: Optional[ttk.Frame] = None
        self._ship4_panel: Optional[_Ship4Panel] = None
        self._ship5_panel: Optional[_Ship5Panel] = None
        self._supply_panel: Optional[_PortSupplyPanel] = None
        self._missing_label: Optional[ttk.Label] = None

        self._build_initial()

    # ---------------- 외부 API (EditorTab 인터페이스) ----------------

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
        if self._supply_panel is not None:
            self._supply_panel.set_enabled(False)

    def revert(self) -> None:
        """디스크에서 다시 읽음. reload 와 동일."""
        self.reload()

    def is_dirty(self) -> bool:
        for panel in (self._ship4_panel, self._ship5_panel, self._supply_panel):
            if panel is not None and panel.is_dirty():
                return True
        return False

    def commit(self) -> None:
        """모든 sub-panel commit."""
        for panel in (self._ship4_panel, self._ship5_panel, self._supply_panel):
            if panel is None:
                continue
            try:
                panel.commit()
            except ValueError:
                raise

    def add_dirty_listener(self, callback: Callable[[], None]) -> None:
        self._dirty_listeners.append(callback)

    def _on_panel_dirty(self) -> None:
        for cb in list(self._dirty_listeners):
            try:
                cb()
            except Exception:
                pass

    # ---------------- 내부 구성 ----------------

    def _build_initial(self) -> None:
        # 시험 기능 경고 (탭 최상단, 강조)
        warning = ttk.Label(
            self,
            text=(
                "⚠️ 시험 기능 — 이 탭의 항목 편집은 게임 실행에 오류를 일으킬 수 있습니다.\n"
                "   분석이 완전치 않거나 덜 밝혀진 영역을 직접 편집합니다.\n"
                "   편집 전 저장 파일(KOUKAI2.DAT)과 게임 본체 파일(MAIN.EXE)을 반드시 복사해 두세요."
            ),
            foreground="#a00",
            background="#fff8dc",
            padding=8,
            justify="left",
            font=("TkDefaultFont", 10, "bold"),
        )
        warning.pack(side="top", fill="x", padx=8, pady=(8, 4))

        # 기존 안내 라벨 (항상 표시)
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
        self._supply_panel = None
        self._missing_label = None

    def _rebuild_for_current_environment(self) -> None:
        main_exe = main_exe_path(self._state)
        self._clear_content()

        # supply 패널은 slot 만 필요하므로 항상 표시. ship4/5 는 MAIN.EXE 필요.
        self._inner = ttk.Frame(self._content)
        self._inner.pack(fill="both", expand=True)

        if main_exe is None:
            note = ttk.Label(
                self._inner,
                text=_NO_MAINEXE_MSG + "\n(게임 본체 파일이 필요한 항목은 사용할 수 없습니다.)",
                anchor="center",
                justify="center",
                foreground="#a00",
            )
            note.pack(side="top", fill="x", padx=12, pady=(8, 4))

        nb = ttk.Notebook(self._inner)
        nb.pack(fill="both", expand=True)

        if main_exe is not None:
            names = _ship_display_names(self._state)

            self._ship4_panel = _Ship4Panel(nb, self._state, main_exe, names)
            nb.add(self._ship4_panel, text="함선 기본 성능")

            self._ship5_panel = _Ship5Panel(nb, self._state, main_exe, names)
            nb.add(self._ship5_panel, text="함선 이름·모양")

            self._ship4_panel.add_dirty_listener(self._on_panel_dirty)
            self._ship5_panel.add_dirty_listener(self._on_panel_dirty)
            self._ship4_panel.set_enabled(True)
            self._ship5_panel.set_enabled(True)

        # 항구 공급 수치 (효과 불확실) — analysis_J §7
        self._supply_panel = _PortSupplyPanel(nb, self._state)
        nb.add(self._supply_panel, text="항구 공급 수치 (효과 불확실)")
        self._supply_panel.add_dirty_listener(self._on_panel_dirty)
        self._supply_panel.set_enabled(self._slot_loaded)

        self._on_panel_dirty()


# ---------------------------------------------------------------------------
# Sub-panel: Ship4 ROM
# ---------------------------------------------------------------------------


class _Ship4Panel(ttk.Frame):
    """Ship4 ROM 편집 (확정 위치 0x0407DA = record + 2). lrudder/lsail/lcrew/dcrew/capacity/lnowea."""

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

        self._loading = False
        self._dirty = False
        self._dirty_listeners: list[Callable[[], None]] = []

        self._var_lrudder = tk.IntVar(value=0)
        self._var_lsail = tk.IntVar(value=0)
        self._var_lcrew_max = tk.IntVar(value=0)  # 표시값 = lcrew * 10
        self._var_dcrew = tk.IntVar(value=0)
        self._var_capacity = tk.IntVar(value=0)
        self._var_lnowea = tk.IntVar(value=0)

        self._build()
        for v in (
            self._var_lrudder, self._var_lsail, self._var_lcrew_max,
            self._var_dcrew, self._var_capacity, self._var_lnowea,
        ):
            v.trace_add("write", self._on_var_write)

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
            self._listbox.insert("end", f"{i + 1}. {name}")
        self._listbox.bind("<<ListboxSelect>>", self._on_ship_selected)

        # 우측 폼
        right = ttk.Frame(self)
        right.pack(side="left", fill="both", expand=True)

        form = ttk.LabelFrame(right, text="함선 기본 성능", padding=8)
        form.pack(side="top", fill="x")

        self._add_spin(form, 0, "최대 회전력", self._var_lrudder, 0, 255)
        self._add_spin(form, 1, "최대 돛", self._var_lsail, 0, 255)
        self._add_spin(
            form,
            2,
            "최대 승무원",
            self._var_lcrew_max,
            0,
            2550,
        )
        ttk.Label(
            form,
            text="* 0~2550 범위로 입력합니다 (10 단위로 저장됩니다).",
            foreground="#888",
        ).grid(row=3, column=0, columnspan=2, sticky="w", padx=4)
        self._add_spin(form, 4, "필요 승무원", self._var_dcrew, 0, 255)
        self._add_spin(form, 5, "최대 적재량", self._var_capacity, 0, 65535)
        self._add_spin(form, 6, "최대 무기수", self._var_lnowea, 0, 255)

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
                "이 편집은 게임 본체 파일만 바꿉니다.\n"
                "현재 세이브 칸의 함대 정보에는 영향을 주지 않습니다."
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
        self._loading = True
        try:
            self._load_current()
        finally:
            self._loading = False
        self._set_dirty(False)

    def _on_reload(self) -> None:
        if not self._enabled:
            return
        self._loading = True
        try:
            self._load_current()
        finally:
            self._loading = False
        self._set_dirty(False)

    def _load_current(self) -> None:
        if not self._enabled:
            return
        try:
            ship4 = load_ship4_rom(self._main_exe, self._idx)
        except Exception as e:
            messagebox.showerror("함선 기본 성능 불러오기 실패", str(e))
            return
        self._current = ship4
        self._var_lrudder.set(ship4.lrudder)
        self._var_lsail.set(ship4.lsail)
        self._var_lcrew_max.set(ship4.lcrew * 10)
        self._var_dcrew.set(ship4.dcrew)
        self._var_capacity.set(ship4.capacity)
        self._var_lnowea.set(ship4.lnowea)

    # -------- dirty / commit / revert --------

    def _on_var_write(self, *_a: object) -> None:
        if self._loading or not self._enabled:
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

    def is_dirty(self) -> bool:
        return self._dirty and self._enabled

    def add_dirty_listener(self, callback: Callable[[], None]) -> None:
        self._dirty_listeners.append(callback)

    def commit(self) -> None:
        if not self.is_dirty():
            return
        try:
            lrudder = int(self._var_lrudder.get())
            lsail = int(self._var_lsail.get())
            lcrew_max = int(self._var_lcrew_max.get())
            dcrew = int(self._var_dcrew.get())
            capacity = int(self._var_capacity.get())
            lnowea = int(self._var_lnowea.get())
        except (tk.TclError, ValueError):
            raise ValueError("함선 기본 성능: 숫자 칸에 잘못된 값이 있습니다.")
        if not _in_range(lrudder, 0, 255):
            raise ValueError("함선 기본 성능: 최대 회전력은 0~255 사이여야 합니다.")
        if not _in_range(lsail, 0, 255):
            raise ValueError("함선 기본 성능: 최대 돛은 0~255 사이여야 합니다.")
        if not _in_range(lcrew_max, 0, 2550):
            raise ValueError("함선 기본 성능: 최대 승무원은 0~2550 사이여야 합니다.")
        if not _in_range(dcrew, 0, 255):
            raise ValueError("함선 기본 성능: 필요 승무원은 0~255 사이여야 합니다.")
        if not _in_range(capacity, 0, 65535):
            raise ValueError("함선 기본 성능: 최대 적재량은 0~65535 사이여야 합니다.")
        if not _in_range(lnowea, 0, 255):
            raise ValueError("함선 기본 성능: 최대 무기수는 0~255 사이여야 합니다.")

        try:
            base = self._current if self._current is not None else load_ship4_rom(
                self._main_exe, self._idx
            )
        except Exception as e:
            raise ValueError(f"함선 기본 성능 다시 읽기 실패: {e}")

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
            raise ValueError(f"함선 기본 성능 저장 실패: {e}")
        self._current = ship4
        self._loading = True
        try:
            self._var_lcrew_max.set(ship4.lcrew * 10)
        finally:
            self._loading = False
        self._set_dirty(False)

    def _on_save(self) -> None:
        """sub-panel 의 [저장] 버튼 — 이 패널만 commit. (전역 [저장] 과는 별개)"""
        if not self._enabled:
            return
        try:
            self.commit()
        except ValueError as e:
            messagebox.showerror("저장 실패", str(e))
            return
        messagebox.showinfo("저장 완료", f"함선 기본 성능을 저장했습니다 (함선 {self._idx + 1}번).")

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
            self._loading = True
            try:
                self._load_current()
            finally:
                self._loading = False
            self._set_dirty(False)


# ---------------------------------------------------------------------------
# Sub-panel: Ship5 ROM
# ---------------------------------------------------------------------------


class _Ship5Panel(ttk.Frame):
    """Ship5 ROM 편집 (확정 위치 0x040566). name(18B), sform, bform 상위 4비트."""

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

        self._loading = False
        self._dirty = False
        self._dirty_listeners: list[Callable[[], None]] = []

        self._var_name = tk.StringVar()
        self._var_sform = tk.IntVar(value=0)
        self._var_bform_hi = tk.IntVar(value=0)  # 상위 4비트만

        self._build()
        for v in (self._var_name, self._var_sform, self._var_bform_hi):
            v.trace_add("write", self._on_var_write)

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
            self._listbox.insert("end", f"{i + 1}. {name}")
        self._listbox.bind("<<ListboxSelect>>", self._on_ship_selected)

        # 우측 폼
        right = ttk.Frame(self)
        right.pack(side="left", fill="both", expand=True)

        form = ttk.LabelFrame(right, text="함선 이름·모양", padding=8)
        form.pack(side="top", fill="x")

        ttk.Label(form, text="배 이름").grid(
            row=0, column=0, sticky="w", padx=4, pady=3
        )
        self._entry_name = ttk.Entry(form, textvariable=self._var_name, width=18)
        self._entry_name.grid(row=0, column=1, sticky="w", padx=4, pady=3)

        ttk.Label(form, text="평상시 모양").grid(
            row=1, column=0, sticky="w", padx=4, pady=3
        )
        ttk.Spinbox(
            form, from_=0, to=255, textvariable=self._var_sform, width=10
        ).grid(row=1, column=1, sticky="w", padx=4, pady=3)

        ttk.Label(form, text="전투 시 모양").grid(
            row=2, column=0, sticky="w", padx=4, pady=3
        )
        ttk.Spinbox(
            form, from_=0, to=15, textvariable=self._var_bform_hi, width=10
        ).grid(row=2, column=1, sticky="w", padx=4, pady=3)

        ttk.Label(
            form,
            text="* 0~15 사이로 입력하세요.",
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
        self._loading = True
        try:
            self._load_current()
        finally:
            self._loading = False
        self._set_dirty(False)

    def _on_reload(self) -> None:
        if not self._enabled:
            return
        self._loading = True
        try:
            self._load_current()
        finally:
            self._loading = False
        self._set_dirty(False)

    def _load_current(self) -> None:
        if not self._enabled:
            return
        try:
            ship5 = load_ship5_rom(self._main_exe, self._idx)
        except Exception as e:
            messagebox.showerror("함선 이름·모양 불러오기 실패", str(e))
            return
        self._current = ship5
        self._var_name.set(decode_kr(ship5.name))
        self._var_sform.set(ship5.sform)
        self._var_bform_hi.set((ship5.bform >> 4) & 0x0F)

    # -------- dirty / commit --------

    def _on_var_write(self, *_a: object) -> None:
        if self._loading or not self._enabled:
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

    def is_dirty(self) -> bool:
        return self._dirty and self._enabled

    def add_dirty_listener(self, callback: Callable[[], None]) -> None:
        self._dirty_listeners.append(callback)

    def commit(self) -> None:
        if not self.is_dirty():
            return
        try:
            sform = int(self._var_sform.get())
            bform_hi = int(self._var_bform_hi.get())
        except (tk.TclError, ValueError):
            raise ValueError("함선 이름·모양: 숫자 칸에 잘못된 값이 있습니다.")
        if not _in_range(sform, 0, 255):
            raise ValueError("함선 이름·모양: 평상시 모양은 0~255 사이여야 합니다.")
        if not _in_range(bform_hi, 0, 15):
            raise ValueError("함선 이름·모양: 전투 시 모양은 0~15 사이여야 합니다.")
        try:
            base = self._current if self._current is not None else load_ship5_rom(
                self._main_exe, self._idx
            )
        except Exception as e:
            raise ValueError(f"함선 이름·모양 다시 읽기 실패: {e}")
        new_bform = ((bform_hi & 0x0F) << 4) | (base.bform & 0x0F)
        try:
            name_bytes = encode_kr_fixed(self._var_name.get(), 18)
        except Exception as e:
            raise ValueError(f"함선 이름·모양: 배 이름을 저장할 수 없습니다: {e}")
        ship5 = Ship5(
            name=name_bytes, sform=sform, bform=new_bform, none=base.none,
        )
        try:
            save_ship5_rom(self._main_exe, self._idx, ship5)
        except Exception as e:
            raise ValueError(f"함선 이름·모양 저장 실패: {e}")
        self._current = ship5
        self._loading = True
        try:
            self._var_name.set(decode_kr(ship5.name))
        finally:
            self._loading = False
        self._set_dirty(False)

    def _on_save(self) -> None:
        """sub-panel 의 [저장] 버튼 — 이 패널만 commit."""
        if not self._enabled:
            return
        try:
            self.commit()
        except ValueError as e:
            messagebox.showerror("저장 실패", str(e))
            return
        messagebox.showinfo("저장 완료", f"함선 이름·모양을 저장했습니다 (함선 {self._idx + 1}번).")

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
            self._loading = True
            try:
                self._load_current()
            finally:
                self._loading = False
            self._set_dirty(False)


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


# ---------------------------------------------------------------------------
# Sub-panel: 항구 공급 수치 (물가) — analysis_J
# ---------------------------------------------------------------------------


def _decode_supply_byte_display(b: int) -> str:
    """공급 byte → 사람이 읽을 수 있는 표시."""
    if b == 0x2E:
        return "빈칸"
    if 0x2F <= b <= 0x39:
        level = b - 0x2F  # '/' = 0, '0' = 1, ..., '9' = 10
        return f"공급 {level}"
    return f"(값 {b})"


class _PortSupplyPanel(ttk.Frame):
    """항구 공급 수치 편집 (record +14..+23, 10 byte/port).

    표준 항구 (0..99) 는 0x2E..0x39 (ASCII digit/dot) 인코딩.
    원거리 항구 (100..129) 는 raw byte (구조 미해석).
    """

    def __init__(self, master: tk.Misc, state: EditorState) -> None:
        super().__init__(master, padding=8)
        self._state = state
        self._idx = 0
        self._enabled = False
        self._current_raw: bytes = b"\x00" * PORT_SUPPLY_SIZE

        self._loading = False
        self._dirty = False
        self._dirty_listeners: list[Callable[[], None]] = []

        self._vars: list[tk.IntVar] = [tk.IntVar(value=0) for _ in range(PORT_SUPPLY_SIZE)]
        self._decoded_labels: list[ttk.Label] = []

        self._build()
        for v in self._vars:
            v.trace_add("write", self._on_var_write)

    # -------- 외부 인터페이스 --------

    def is_dirty(self) -> bool:
        return self._dirty and self._enabled

    def add_dirty_listener(self, callback: Callable[[], None]) -> None:
        self._dirty_listeners.append(callback)

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
            # 슬롯이 활성화되었으므로 항구 이름이 캐시에 있을 것 — 목록 채움
            self._populate_listbox()
            if not self._listbox.curselection():
                self._listbox.selection_set(0)
                self._idx = 0
            self._loading = True
            try:
                self._load_current()
            finally:
                self._loading = False
            self._set_dirty(False)

    def commit(self) -> None:
        if not self.is_dirty():
            return
        try:
            new_bytes = bytes(int(v.get()) & 0xFF for v in self._vars)
        except (tk.TclError, ValueError):
            raise ValueError("항구 공급 수치: 숫자가 아닌 값이 있습니다.")
        try:
            save_port_supply(self._state, self._idx, new_bytes)
            self._state.fp.flush()
        except Exception as e:
            raise ValueError(f"항구 공급 수치 저장 실패: {e}") from e
        self._current_raw = new_bytes
        self._refresh_decoded_labels()
        self._set_dirty(False)

    # -------- 빌드 --------

    def _build(self) -> None:
        # 추가 경고 — 이 패널 특정 (사용자 검증 결과 가격 직접 영향 없음 확인됨)
        sub_warn = ttk.Label(
            self,
            text=(
                "⚠️ 확인 결과: 이 값을 바꿔도 시장 가격에 바로 영향이 나타나지 않았습니다.\n"
                "    게임이 값을 읽긴 하지만(한 달 뒤 자동 갱신 확인) 실제 효과는 분명치 않습니다.\n"
                "    평균물가는 매달 1일에만 바뀝니다.\n"
                "    일반 항구(0~99번)는 안전한 범위가 있고,\n"
                "    먼 바다 항구(100~129번)는 바꾸면 게임이 깨질 수 있습니다."
            ),
            foreground="#a00",
            justify="left",
        )
        sub_warn.pack(side="top", fill="x", padx=4, pady=(0, 6))

        # 좌측 항구 목록
        left = ttk.Frame(self)
        left.pack(side="left", fill="y", padx=(0, 8))
        ttk.Label(left, text="항구 (130곳):").pack(side="top", anchor="w")
        list_frame = ttk.Frame(left)
        list_frame.pack(side="top", fill="y", expand=True)
        self._listbox = tk.Listbox(
            list_frame, height=22, exportselection=False, width=22,
        )
        sb = ttk.Scrollbar(list_frame, orient="vertical", command=self._listbox.yview)
        self._listbox.configure(yscrollcommand=sb.set)
        self._listbox.pack(side="left", fill="y", expand=True)
        sb.pack(side="right", fill="y")
        self._listbox.bind("<<ListboxSelect>>", self._on_port_selected)

        # 우측 폼
        right = ttk.Frame(self)
        right.pack(side="left", fill="both", expand=True)

        self._lbl_current = ttk.Label(right, text="(항구 미선택)", foreground="#444")
        self._lbl_current.pack(side="top", anchor="w", pady=(0, 6))

        form = ttk.LabelFrame(right, text="공급 수치", padding=8)
        form.pack(side="top", fill="x")

        for i in range(PORT_SUPPLY_SIZE):
            ttk.Label(form, text=f"칸 {i + 1}").grid(row=i, column=0, sticky="w", padx=4, pady=2)
            sp = ttk.Spinbox(
                form, from_=0, to=255, textvariable=self._vars[i], width=6,
            )
            sp.grid(row=i, column=1, sticky="w", padx=4, pady=2)
            lbl = ttk.Label(form, text="", foreground="#666")
            lbl.grid(row=i, column=2, sticky="w", padx=8, pady=2)
            self._decoded_labels.append(lbl)

        # 버튼
        btns = ttk.Frame(right)
        btns.pack(side="top", fill="x", pady=8)
        self._btn_reload = ttk.Button(btns, text="다시 불러오기", command=self._on_reload)
        self._btn_reload.pack(side="right", padx=4)
        self._btn_save = ttk.Button(btns, text="저장", command=self._on_save)
        self._btn_save.pack(side="right", padx=4)

        ttk.Label(
            right,
            text=(
                "입력 안내 (일반 항구 0~99번):\n"
                "  '.' = 빈칸, '/' = 공급 0 (가격 폭등),\n"
                "  '0'~'9' = 공급 1~10 (높을수록 가격 하락).\n"
                "먼 바다 항구(100~129번)는 위 규칙이 적용되지 않습니다."
            ),
            foreground="#666",
            justify="left",
        ).pack(side="top", anchor="w")

    def _populate_listbox(self) -> None:
        self._listbox.delete(0, "end")
        for i in range(NUM_PORTS):
            name = self._state.port_name[i] if 0 <= i < len(self._state.port_name) else ""
            mark = "" if i < 100 else " (먼 바다)"
            self._listbox.insert("end", f"{i:3d}. {name}{mark}")

    # -------- 콜백 --------

    def _on_port_selected(self, _e: object = None) -> None:
        if not self._enabled:
            return
        sel = self._listbox.curselection()
        if not sel:
            return
        self._idx = int(sel[0])
        self._loading = True
        try:
            self._load_current()
        finally:
            self._loading = False
        self._set_dirty(False)

    def _on_reload(self) -> None:
        if not self._enabled:
            return
        self._loading = True
        try:
            self._load_current()
        finally:
            self._loading = False
        self._set_dirty(False)

    def _on_save(self) -> None:
        if not self._enabled:
            return
        try:
            self.commit()
        except ValueError as e:
            messagebox.showerror("저장 실패", str(e))
            return
        name = self._state.port_name[self._idx] if 0 <= self._idx < len(self._state.port_name) else ""
        messagebox.showinfo("저장 완료", f"{self._idx}번 항구 ({name}) 공급 수치를 저장했습니다.")

    def _on_var_write(self, *_a: object) -> None:
        if self._loading or not self._enabled:
            return
        # 실시간 디코딩 라벨 갱신
        self._refresh_decoded_labels()
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

    # -------- 로드/디코드 --------

    def _load_current(self) -> None:
        if not self._enabled:
            return
        try:
            raw = load_port_supply(self._state, self._idx)
        except Exception as e:
            messagebox.showerror("공급 수치 불러오기 실패", str(e))
            return
        self._current_raw = raw
        for i, b in enumerate(raw):
            self._vars[i].set(b)
        name = self._state.port_name[self._idx] if 0 <= self._idx < len(self._state.port_name) else ""
        category = "일반" if self._idx < 100 else "먼 바다 (분석 미완)"
        std = "✓" if port_supply_is_standard(raw) else "✗"
        self._lbl_current.configure(
            text=f"{self._idx}번 항구  {name}   [{category}, 표준 형식 {std}]"
        )
        self._refresh_decoded_labels()

    def _refresh_decoded_labels(self) -> None:
        for i, lbl in enumerate(self._decoded_labels):
            try:
                b = int(self._vars[i].get()) & 0xFF
            except (tk.TclError, ValueError):
                b = 0
            lbl.configure(text=_decode_supply_byte_display(b))
