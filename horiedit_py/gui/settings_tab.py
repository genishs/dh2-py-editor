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


_HEADER_HINT = (
    "[참고] 이 탭은 MAIN.EXE 의 ROM 데이터를 직접 편집합니다.\n"
    "       편집 전 MAIN.EXE 백업을 권장합니다.\n"
    "       등장공업치 / 최대 내구도는 [선박] 탭의 [원래 함선 정보] 에서 편집할 수 있습니다."
)

_NO_MAINEXE_MSG = (
    "MAIN.EXE 를 찾지 못했습니다.\n"
    "이 프로그램을 KOUKAI2.DAT 와 MAIN.EXE 가 같이 있는 게임 폴더에서 실행해 주세요."
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

    def revert(self) -> None:
        """디스크에서 다시 읽음. reload 와 동일."""
        self.reload()

    def is_dirty(self) -> bool:
        for panel in (self._ship4_panel, self._ship5_panel):
            if panel is not None and panel.is_dirty():
                return True
        return False

    def commit(self) -> None:
        """모든 sub-panel commit."""
        for panel in (self._ship4_panel, self._ship5_panel):
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

        # 각 sub-panel 의 dirty 를 SettingsTab 으로 전파
        self._ship4_panel.add_dirty_listener(self._on_panel_dirty)
        self._ship5_panel.add_dirty_listener(self._on_panel_dirty)

        # Ship4/Ship5 는 MAIN.EXE 만 필요하므로 항상 사용 가능.
        self._ship4_panel.set_enabled(True)
        self._ship5_panel.set_enabled(True)
        # rebuild 직후에는 깨끗한 상태이므로 외부에 알린다.
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
            messagebox.showerror("Ship4 ROM 로드 실패", str(e))
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
            raise ValueError("Ship4 ROM: 숫자 필드에 잘못된 값이 있습니다.")
        if not _in_range(lrudder, 0, 255):
            raise ValueError("Ship4 ROM: 최대 회전력은 0..255 입니다.")
        if not _in_range(lsail, 0, 255):
            raise ValueError("Ship4 ROM: 최대 돛은 0..255 입니다.")
        if not _in_range(lcrew_max, 0, 2550):
            raise ValueError("Ship4 ROM: 최대 승무원(×10)은 0..2550 입니다.")
        if not _in_range(dcrew, 0, 255):
            raise ValueError("Ship4 ROM: 필요 승무원은 0..255 입니다.")
        if not _in_range(capacity, 0, 65535):
            raise ValueError("Ship4 ROM: 최대 적재량은 0..65535 입니다.")
        if not _in_range(lnowea, 0, 255):
            raise ValueError("Ship4 ROM: 최대 무기수는 0..255 입니다.")

        try:
            base = self._current if self._current is not None else load_ship4_rom(
                self._main_exe, self._idx
            )
        except Exception as e:
            raise ValueError(f"Ship4 ROM 재읽기 실패: {e}")

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
            raise ValueError(f"Ship4 ROM 저장 실패: {e}")
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
            messagebox.showerror("Ship5 ROM 로드 실패", str(e))
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
            raise ValueError("Ship5 ROM: 숫자 필드에 잘못된 값이 있습니다.")
        if not _in_range(sform, 0, 255):
            raise ValueError("Ship5 ROM: 평상시 외형은 0..255 입니다.")
        if not _in_range(bform_hi, 0, 15):
            raise ValueError("Ship5 ROM: 부울때 외형(상위 4비트)은 0..15 입니다.")
        try:
            base = self._current if self._current is not None else load_ship5_rom(
                self._main_exe, self._idx
            )
        except Exception as e:
            raise ValueError(f"Ship5 ROM 재읽기 실패: {e}")
        new_bform = ((bform_hi & 0x0F) << 4) | (base.bform & 0x0F)
        try:
            name_bytes = encode_kr_fixed(self._var_name.get(), 18)
        except Exception as e:
            raise ValueError(f"Ship5 ROM: 배이름 인코딩 실패: {e}")
        ship5 = Ship5(
            name=name_bytes, sform=sform, bform=new_bform, none=base.none,
        )
        try:
            save_ship5_rom(self._main_exe, self._idx, ship5)
        except Exception as e:
            raise ValueError(f"Ship5 ROM 저장 실패: {e}")
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
