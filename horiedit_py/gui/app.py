"""메인 GUI 애플리케이션.

진입점: run(save_path) — fp 를 열고 EditorState 를 초기화한 뒤 mainloop 실행.

[저장] / [초기화] / [프로그램 종료] 3버튼 + dirty 통합 관리.
슬롯 변경 시 dirty 라면 저장 확인 다이얼로그 → 결과에 따라 commit/revert/취소.
"""

from __future__ import annotations

import sys
import tkinter as tk
from pathlib import Path
from tkinter import font as tkfont
from tkinter import messagebox, ttk
from typing import Optional

from horiedit_py.common import state
from horiedit_py.data import select_slot, slot_is_used
from horiedit_py.gui.hero_tab import HeroTab
from horiedit_py.gui.person_tab import PersonTab
from horiedit_py.gui.port_tab import PortTab
from horiedit_py.gui.settings_tab import SettingsTab
from horiedit_py.gui.ship_tab import ShipTab
from horiedit_py.gui.slot_select import SlotSelectFrame


_TITLE = "대항해시대 II 세이브 에디터  Ver 0.1"
_WIDTH = 980
_HEIGHT = 700


def _resource_path(*parts: str) -> Path:
    """PyInstaller --onefile 빌드 / 개발 모드 양쪽에서 리소스 경로를 해석."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
    return base.joinpath(*parts)


class EditorApp:
    """메인 윈도우 + 탭 컨테이너."""

    def __init__(self, root: tk.Tk, save_path: Path) -> None:
        self._root = root
        self._save_path = save_path
        self._current_slot: Optional[int] = None

        root.title(_TITLE)
        root.geometry(f"{_WIDTH}x{_HEIGHT}")
        root.minsize(820, 580)

        icon_path = _resource_path("assets", "icon.ico")
        if icon_path.is_file():
            try:
                root.iconbitmap(default=str(icon_path))
            except tk.TclError:
                pass

        self._configure_style()
        self._build()

        root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---------------- 스타일 ----------------

    def _configure_style(self) -> None:
        """한글 폰트 + 기본 스타일."""
        families = set(tkfont.families())
        candidates = ("Malgun Gothic", "맑은 고딕", "NanumGothic", "Noto Sans CJK KR")
        chosen = next((f for f in candidates if f in families), None)
        style = ttk.Style()
        if chosen is not None:
            style.configure(".", font=(chosen, 10))
        else:
            style.configure(".", font=("TkDefaultFont", 10))

    # ---------------- UI 구성 ----------------

    def _build(self) -> None:
        # 상단 영역: 좌(슬롯) + 우(액션 + 슬롯 상세)
        top = ttk.Frame(self._root)
        top.pack(side="top", fill="x", padx=8, pady=(8, 4))
        top.columnconfigure(0, weight=2)
        top.columnconfigure(1, weight=1)

        # 좌측: 슬롯 선택 + 상세
        self._slot_frame = SlotSelectFrame(
            top, state, on_slot_request=self._on_slot_request,
        )
        self._slot_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 6))

        # 우측: 액션 버튼들
        actions = ttk.LabelFrame(top, text="액션", padding=8)
        actions.grid(row=0, column=1, sticky="nsew")

        self._btn_save = ttk.Button(
            actions, text="저장", command=self._on_save_all, state="disabled",
        )
        self._btn_save.grid(row=0, column=0, padx=4, pady=2, sticky="ew")
        self._btn_reset = ttk.Button(
            actions, text="초기화", command=self._on_reset_all, state="disabled",
        )
        self._btn_reset.grid(row=0, column=1, padx=4, pady=2, sticky="ew")
        self._btn_quit = ttk.Button(
            actions, text="프로그램 종료", command=self._on_close,
        )
        self._btn_quit.grid(row=0, column=2, padx=4, pady=2, sticky="ew")

        actions.columnconfigure(0, weight=1)
        actions.columnconfigure(1, weight=1)
        actions.columnconfigure(2, weight=1)

        # 노트북
        self._notebook = ttk.Notebook(self._root)
        self._notebook.pack(side="top", fill="both", expand=True, padx=8, pady=4)

        self._hero_tab = HeroTab(self._notebook, state)
        self._person_tab = PersonTab(self._notebook, state)
        self._ship_tab = ShipTab(self._notebook, state)
        self._port_tab = PortTab(self._notebook, state)
        self._settings_tab = SettingsTab(self._notebook, state)

        self._notebook.add(self._hero_tab, text="주인공")
        self._notebook.add(self._person_tab, text="인물")
        self._notebook.add(self._ship_tab, text="선박")
        self._notebook.add(self._port_tab, text="항구")
        self._notebook.add(self._settings_tab, text="게임 설정")

        self._tabs = (
            self._hero_tab, self._person_tab, self._ship_tab,
            self._port_tab, self._settings_tab,
        )
        for tab in self._tabs:
            tab.add_dirty_listener(self._update_action_buttons)

        # 하단 상태바
        self._status_var = tk.StringVar(
            value=f"파일: {self._save_path}  |  슬롯: (선택 안 됨)"
        )
        self._dirty_var = tk.StringVar(value="")
        bottom = ttk.Frame(self._root, relief="sunken")
        bottom.pack(side="bottom", fill="x")
        ttk.Label(
            bottom, textvariable=self._status_var, anchor="w", padding=4,
        ).pack(side="left", fill="x", expand=True)
        self._dirty_label = ttk.Label(
            bottom, textvariable=self._dirty_var, anchor="e",
            padding=4, foreground="#a00",
        )
        self._dirty_label.pack(side="right")

    # ---------------- dirty 통합 ----------------

    def _any_tab_dirty(self) -> bool:
        return any(tab.is_dirty() for tab in self._tabs)

    def _update_action_buttons(self) -> None:
        dirty = self._any_tab_dirty()
        st = "normal" if dirty else "disabled"
        try:
            self._btn_save.configure(state=st)
            self._btn_reset.configure(state=st)
        except tk.TclError:
            pass
        self._dirty_var.set("● 변경됨" if dirty else "")

    def _commit_all(self) -> None:
        """모든 탭 commit. 첫 ValueError 에서 중단."""
        for tab in self._tabs:
            tab.commit()

    def _reload_all_tabs(self) -> None:
        for tab in self._tabs:
            try:
                tab.reload()
            except Exception as e:
                messagebox.showerror("탭 갱신 오류", f"{type(tab).__name__}: {e}")

    # ---------------- 슬롯 변경 ----------------

    def _on_slot_request(self, idx: int) -> None:
        """슬롯 라디오 클릭 콜백. dirty 면 다이얼로그, 아니면 즉시 변경."""
        if not slot_is_used(state, idx):
            # 데이터 없는 슬롯 — 라디오를 이전 값으로 되돌림
            self._slot_frame.set_active_slot(self._current_slot)
            return

        if self._any_tab_dirty():
            ans = messagebox.askyesnocancel(
                "변경 사항 저장",
                "현재 슬롯의 변경 사항을 저장하시겠습니까?\n\n"
                "[예] 저장 후 다른 슬롯으로\n"
                "[아니오] 변경 폐기 후 다른 슬롯으로\n"
                "[취소] 슬롯 변경 취소",
            )
            if ans is None:
                # 취소: 라디오를 이전 값으로 되돌리고 종료
                self._slot_frame.set_active_slot(self._current_slot)
                return
            if ans:
                # 예: 저장 시도
                try:
                    self._commit_all()
                    state.fp.flush()
                except ValueError as e:
                    messagebox.showerror("저장 실패", str(e))
                    self._slot_frame.set_active_slot(self._current_slot)
                    return
                except Exception as e:
                    messagebox.showerror("저장 실패", str(e))
                    self._slot_frame.set_active_slot(self._current_slot)
                    return
            # 아니오: 변경 폐기 후 진행

        # 슬롯 변경 수행
        try:
            select_slot(state, idx)
        except Exception as e:
            messagebox.showerror("슬롯 로드 실패", str(e))
            self._slot_frame.set_active_slot(self._current_slot)
            return

        self._current_slot = idx
        self._slot_frame.set_active_slot(idx)
        self._slot_frame.refresh_list()
        self._slot_frame.refresh_detail(state, idx)
        self._reload_all_tabs()
        self._update_status_bar()
        self._update_action_buttons()

    def _update_status_bar(self) -> None:
        if self._current_slot is None:
            self._status_var.set(
                f"파일: {self._save_path}  |  슬롯: (선택 안 됨)"
            )
            return
        hero_name = ""
        c_hero = state.c_hero
        if 0 <= c_hero < len(state.hero):
            hero_name = state.hero[c_hero]
        self._status_var.set(
            f"파일: {self._save_path}  |  슬롯: {self._current_slot + 1}  "
            f"|  주인공: {hero_name}"
        )

    # ---------------- 액션 버튼 ----------------

    def _on_save_all(self) -> None:
        try:
            self._commit_all()
        except ValueError as e:
            messagebox.showerror("저장 실패", str(e))
            return
        except Exception as e:
            messagebox.showerror("저장 실패", str(e))
            return
        try:
            state.fp.flush()
        except Exception:
            pass
        # 슬롯 상세도 갱신 (메모/항구 변경 시 반영)
        if self._current_slot is not None:
            self._slot_frame.refresh_list()
            self._slot_frame.refresh_detail(state, self._current_slot)
        self._update_status_bar()
        self._update_action_buttons()
        messagebox.showinfo("저장 완료", "모든 변경 사항을 저장했습니다.")

    def _on_reset_all(self) -> None:
        if not messagebox.askyesno(
            "초기화",
            "모든 변경 사항을 폐기하고 디스크에서 다시 읽어옵니다. 진행하시겠습니까?",
        ):
            return
        # 슬롯이 로드된 상태라면 다시 select_slot (캐시도 다시 채움)
        if self._current_slot is not None:
            try:
                select_slot(state, self._current_slot)
            except Exception as e:
                messagebox.showerror("슬롯 재로드 실패", str(e))
                return
        self._reload_all_tabs()
        if self._current_slot is not None:
            self._slot_frame.refresh_list()
            self._slot_frame.refresh_detail(state, self._current_slot)
        self._update_action_buttons()

    def _on_close(self) -> None:
        if self._any_tab_dirty():
            ans = messagebox.askyesnocancel(
                "변경 사항 저장",
                "변경 사항을 저장하시겠습니까?\n\n"
                "[예] 저장 후 종료\n"
                "[아니오] 변경 폐기 후 종료\n"
                "[취소] 종료 취소",
            )
            if ans is None:
                return
            if ans:
                try:
                    self._commit_all()
                    state.fp.flush()
                except ValueError as e:
                    messagebox.showerror("저장 실패", str(e))
                    return
                except Exception as e:
                    messagebox.showerror("저장 실패", str(e))
                    return
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
        try:
            if state.fp is not None and not state.fp.closed:
                state.fp.close()
        except Exception:
            pass
    return 0
