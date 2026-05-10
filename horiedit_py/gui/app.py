"""메인 GUI 애플리케이션.

진입점: run(save_path) — fp 를 열고 EditorState 를 초기화한 뒤 mainloop 실행.
"""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import font as tkfont
from tkinter import messagebox, ttk

from horiedit_py.common import state
from horiedit_py.gui.hero_tab import HeroTab
from horiedit_py.gui.person_tab import PersonTab
from horiedit_py.gui.settings_tab import SettingsTab
from horiedit_py.gui.ship_tab import ShipTab
from horiedit_py.gui.slot_select import SlotSelectFrame


_TITLE = "대항해시대 II 세이브 에디터  Ver 0.1"
_WIDTH = 900
_HEIGHT = 650


class EditorApp:
    """메인 윈도우 + 탭 컨테이너."""

    def __init__(self, root: tk.Tk, save_path: Path) -> None:
        self._root = root
        self._save_path = save_path
        self._slot_idx: int | None = None

        root.title(_TITLE)
        root.geometry(f"{_WIDTH}x{_HEIGHT}")
        root.minsize(720, 520)

        self._configure_style()
        self._build()

        root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---------------- UI 구성 ----------------

    def _configure_style(self) -> None:
        """한글 폰트 + 기본 스타일. Windows 외 환경에서는 자동 fallback."""
        families = set(tkfont.families())
        candidates = ("Malgun Gothic", "맑은 고딕", "NanumGothic", "Noto Sans CJK KR")
        chosen = next((f for f in candidates if f in families), None)
        style = ttk.Style()
        if chosen is not None:
            style.configure(".", font=(chosen, 10))
        else:
            style.configure(".", font=("TkDefaultFont", 10))

    def _build(self) -> None:
        # 상단 슬롯 선택
        self._slot_frame = SlotSelectFrame(
            self._root,
            state,
            on_slot_changed=self._on_slot_changed,
            on_quit=self._on_close,
        )
        self._slot_frame.pack(side="top", fill="x", padx=8, pady=(8, 4))

        # 노트북
        self._notebook = ttk.Notebook(self._root)
        self._notebook.pack(side="top", fill="both", expand=True, padx=8, pady=4)

        self._hero_tab = HeroTab(self._notebook, state)
        self._person_tab = PersonTab(self._notebook, state)
        self._ship_tab = ShipTab(self._notebook, state)
        self._settings_tab = SettingsTab(self._notebook, state)

        self._notebook.add(self._hero_tab, text="주인공")
        self._notebook.add(self._person_tab, text="인물")
        self._notebook.add(self._ship_tab, text="선박")
        self._notebook.add(self._settings_tab, text="게임 설정")

        # 하단 상태바
        self._status_var = tk.StringVar(
            value=f"파일: {self._save_path}  |  슬롯: (선택 안 됨)"
        )
        status = ttk.Label(
            self._root,
            textvariable=self._status_var,
            anchor="w",
            relief="sunken",
            padding=4,
        )
        status.pack(side="bottom", fill="x")

    # ---------------- 콜백 ----------------

    def _on_slot_changed(self, idx: int) -> None:
        self._slot_idx = idx
        # 모든 탭 reload
        for tab in (self._hero_tab, self._person_tab, self._ship_tab, self._settings_tab):
            try:
                tab.reload()
            except Exception as e:  # pragma: no cover - 방어
                messagebox.showerror("탭 갱신 오류", f"{type(tab).__name__}: {e}")

        hero_name = ""
        c_hero = state.c_hero
        if 0 <= c_hero < len(state.hero):
            hero_name = state.hero[c_hero]
        self._status_var.set(
            f"파일: {self._save_path}  |  슬롯: {idx + 1}  |  주인공: {hero_name}"
        )

    def _on_close(self) -> None:
        try:
            fp = state.fp
            if fp is not None:
                try:
                    fp.flush()
                except Exception:
                    pass
                try:
                    fp.close()
                except Exception:
                    pass
        finally:
            try:
                self._root.destroy()
            except tk.TclError:
                pass


def run(save_path: Path) -> int:
    """KOUKAI2.DAT 를 열고 GUI mainloop 진입.

    반환값: 종료 코드 (성공 0, 열기 실패 -1).
    """
    try:
        fp = open(save_path, "r+b")
    except OSError as e:
        try:
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("파일 열기 실패", f"{save_path}\n{e}")
            root.destroy()
        except Exception:
            pass
        return -1

    state.fp = fp
    state.page = 0
    state.eXit = 0
    state.game_dir = save_path.resolve().parent

    root = tk.Tk()
    try:
        EditorApp(root, save_path)
        root.mainloop()
    finally:
        # mainloop 종료 후 fp 가 아직 열려 있으면 닫는다.
        try:
            if state.fp is not None and not state.fp.closed:
                state.fp.close()
        except Exception:
            pass
    return 0
