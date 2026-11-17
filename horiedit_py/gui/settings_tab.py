"""게임 전체 탭 — 이 게임 폴더의 모든 세이브에 공통으로 적용되는 설정.

sub-tab (순서):
- 함선 기본 성능 (MAIN.EXE, Ship4 ROM)   — 메인 [저장] 으로 반영 (dirty/commit)
- 함선 이름·모양 (MAIN.EXE, Ship5 ROM)   — 메인 [저장] 으로 반영 (dirty/commit)
- 신조 내구도 상한 (MAIN.EXE)            — 버튼을 누르면 바로 파일에 반영
- 운하 (WORLDMAP.LZW)                    — 버튼을 누르면 바로 파일에 반영

이전 버전의 "등장공업치" sub-tab 은 제거되었다. analysis_G 에서 함선 record
구조가 발견되면서 등장공업치(요구공업치) 와 최대 내구도(lhull) 는 record 의
+0/+1 byte 임이 확정되었다. 두 항목은 "선박 탭 → 원래 함선 정보" 에서
편집한다. (항구 공급 수치는 세이브 칸 데이터라 [항구] 탭으로 옮겼다.)
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
from horiedit_py.gui.canal_panel import CanalPanel
from horiedit_py.gui.hull_cap_panel import HullCapPanel
from horiedit_py.gui.layout import add_scroll_page, track_wraplength
from horiedit_py.gui.widget_state import cascade_state as _cascade_state


_HEADER_HINT = (
    "이 탭의 설정은 이 게임 폴더의 모든 세이브(와 새 게임)에 공통으로 적용됩니다 — 세이브 칸과 무관합니다.\n"
    "· 함선 기본 성능 · 함선 이름·모양 · 신조 내구도 상한 → 게임 본체 파일(MAIN.EXE)   · 운하 → 지도 파일(WORLDMAP.LZW)\n"
    "· 반영 방식: 함선 두 곳은 [저장]을 눌러야 반영 / 신조 내구도 상한·운하는 버튼을 누르면 바로 반영 (각 sub-tab 위에도 표시)\n"
    "· 되돌리기: 신조 내구도 상한은 [백업에서 복원], 운하는 [원상복원]. 편집 전 게임 본체 파일 복사를 권장합니다."
)

_NO_MAINEXE_MSG = (
    "게임 본체 파일(MAIN.EXE)을 찾지 못했습니다.\n"
    "저장 파일과 게임이 함께 있는 게임 폴더에서 실행해 주세요."
)

# 설명·폼 위주 화면(내구도 상한·운하)의 최대 폭 — 창이 아무리 커도 이 폭을 넘어 늘어나지 않는다
_FORM_MAX_W = 980

_EXPERIMENTAL_TEXT = (
    "⚠️ 시험 기능 — 이 화면의 항목 편집은 게임 실행에 오류를 일으킬 수 있습니다.\n"
    "   분석이 완전치 않거나 덜 밝혀진 영역을 직접 편집합니다.\n"
    "   편집 전 게임 본체 파일(MAIN.EXE)을 반드시 복사해 두세요."
)

_SAVE_MODE_TEXT = (
    "💾 [저장]을 눌러야 반영됩니다 (이 화면의 [저장] 또는 위쪽 [저장]). "
    "반영되는 파일: 게임 본체 파일(MAIN.EXE)."
)


def _experimental_banner(parent: tk.Misc) -> None:
    """ROM 직접 편집(아직 시험 단계인) 화면 맨 위의 경고 + 반영 방식 안내."""
    box = ttk.Frame(parent)
    box.pack(side="top", fill="x", pady=(0, 6))
    warn = ttk.Label(
        box, text=_EXPERIMENTAL_TEXT, foreground="#a00", background="#fff8dc",
        padding=8, justify="left", font=("TkDefaultFont", 10, "bold"),
    )
    warn.pack(side="top", fill="x")
    track_wraplength(warn, pad=18)
    mode = ttk.Label(box, text=_SAVE_MODE_TEXT, foreground="#246", justify="left")
    mode.pack(side="top", fill="x", pady=(4, 0))
    track_wraplength(mode)


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
    """게임 전체 탭. Ship4 / Ship5 / 신조 내구도 상한 / 운하 sub-tab 보유."""

    def __init__(self, master: tk.Misc, state: EditorState) -> None:
        super().__init__(master, padding=8)
        self._state = state
        self._slot_loaded = False
        self._dirty_listeners: list[Callable[[], None]] = []

        # 동적 컨테이너 (MAIN.EXE 유무에 따라 내용이 달라진다)
        self._inner: Optional[ttk.Frame] = None
        self._ship4_panel: Optional[_Ship4Panel] = None
        self._ship5_panel: Optional[_Ship5Panel] = None
        self._hull_cap_panel: Optional[HullCapPanel] = None
        self._canal_panel: Optional[CanalPanel] = None
        self._notebook: Optional[ttk.Notebook] = None
        self._sub_pages: dict[str, tk.Misc] = {}
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

    #: sub-tab 키 → 표시 이름 (도구 메뉴 등에서 키로 이동)
    SUBTAB_TITLES = {
        "ship4": "함선 기본 성능",
        "ship5": "함선 이름·모양",
        "hullcap": "신조 내구도 상한",
        "canal": "운하",
    }

    def select_subtab(self, key: str) -> None:
        """sub-tab 을 키(``ship4``/``ship5``/``hullcap``/``canal``)로 선택."""
        page = self._sub_pages.get(key)
        if self._notebook is None or page is None:
            return
        try:
            self._notebook.select(page)
        except tk.TclError:
            pass

    def _build_initial(self) -> None:
        # 이 탭이 무엇을 바꾸는지 (모든 세이브 공통 · 파일별 · 반영 방식) — 탭 맨 위 안내
        hint = ttk.Label(self, text=_HEADER_HINT, foreground="#246", justify="left")
        hint.pack(side="top", fill="x", padx=4, pady=(0, 6))
        track_wraplength(hint)
        self._hint_label = hint

        self._content = ttk.Frame(self)
        self._content.pack(side="top", fill="both", expand=True)

        self._rebuild_for_current_environment()

    def _clear_content(self) -> None:
        for child in list(self._content.winfo_children()):
            child.destroy()
        self._inner = None
        self._ship4_panel = None
        self._ship5_panel = None
        self._hull_cap_panel = None
        self._canal_panel = None
        self._missing_label = None
        self._notebook = None
        self._sub_pages = {}

    def _missing_mainexe_page(self, parent: tk.Misc) -> tk.Misc:
        """MAIN.EXE 가 없을 때 MAIN.EXE 가 필요한 sub-tab 에 놓는 안내 페이지."""
        f = ttk.Frame(parent, padding=12)
        lbl = ttk.Label(
            f, text=_NO_MAINEXE_MSG + "\n(게임 본체 파일이 필요한 항목은 사용할 수 없습니다.)",
            anchor="w", justify="left", foreground="#a00",
        )
        lbl.pack(side="top", fill="x")
        track_wraplength(lbl)
        return f

    def _rebuild_for_current_environment(self) -> None:
        main_exe = main_exe_path(self._state)
        prev_sel = None
        if self._notebook is not None:
            for k, pg in self._sub_pages.items():
                try:
                    if self._notebook.select() == str(pg):
                        prev_sel = k
                except tk.TclError:
                    pass
        self._clear_content()

        self._inner = ttk.Frame(self._content)
        self._inner.pack(fill="both", expand=True)

        nb = ttk.Notebook(self._inner)
        nb.pack(fill="both", expand=True)
        self._notebook = nb
        T = self.SUBTAB_TITLES

        # 1) 함선 기본 성능 — MAIN.EXE, 메인 [저장]
        if main_exe is not None:
            names = _ship_display_names(self._state)
            self._ship4_panel, sf = add_scroll_page(
                nb, lambda p: _Ship4Panel(p, self._state, main_exe, names), T["ship4"],
            )
            self._ship4_panel.add_dirty_listener(self._on_panel_dirty)
            self._ship4_panel.set_enabled(True)
        else:
            _pg, sf = add_scroll_page(nb, self._missing_mainexe_page, T["ship4"])
        self._sub_pages["ship4"] = sf

        # 2) 함선 이름·모양 — MAIN.EXE, 메인 [저장]
        if main_exe is not None:
            self._ship5_panel, sf = add_scroll_page(
                nb, lambda p: _Ship5Panel(p, self._state, main_exe, names), T["ship5"],
            )
            self._ship5_panel.add_dirty_listener(self._on_panel_dirty)
            self._ship5_panel.set_enabled(True)
        else:
            _pg, sf = add_scroll_page(nb, self._missing_mainexe_page, T["ship5"])
        self._sub_pages["ship5"] = sf

        # 3) 신조 내구도 상한 — MAIN.EXE, 버튼으로 즉시 반영 (자체적으로 MAIN.EXE 없음 처리)
        self._hull_cap_panel, sf = add_scroll_page(
            nb, lambda p: HullCapPanel(p, self._state), T["hullcap"],
            max_body_width=_FORM_MAX_W,
        )
        self._sub_pages["hullcap"] = sf

        # 4) 운하 — WORLDMAP.LZW 만 필요 (MAIN.EXE·세이브 칸과 무관), 버튼으로 즉시 반영
        self._canal_panel, sf = add_scroll_page(
            nb, lambda p: CanalPanel(p, self._state), T["canal"],
            max_body_width=_FORM_MAX_W,
        )
        self._sub_pages["canal"] = sf

        if prev_sel in self._sub_pages:
            self.select_subtab(prev_sel)

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
        _experimental_banner(self)
        # 좌측 함선 목록
        left = ttk.Frame(self)
        left.pack(side="left", fill="y", padx=(0, 8))
        ttk.Label(left, text="함선 종류 (25종):").pack(side="top", anchor="w")
        list_frame = ttk.Frame(left)
        list_frame.pack(side="top", fill="y", expand=True)
        self._listbox = tk.Listbox(list_frame, height=8, exportselection=False, width=22)
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
        _experimental_banner(self)
        # 좌측 함선 목록
        left = ttk.Frame(self)
        left.pack(side="left", fill="y", padx=(0, 8))
        ttk.Label(left, text="함선 종류 (25종):").pack(side="top", anchor="w")
        list_frame = ttk.Frame(left)
        list_frame.pack(side="top", fill="y", expand=True)
        self._listbox = tk.Listbox(list_frame, height=8, exportselection=False, width=22)
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
