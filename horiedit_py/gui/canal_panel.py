"""게임 전체 탭의 「운하」 구역 — 수에즈·파나마 운하 개통/원상복원.

표시·버튼 결정은 `canal_logic` (위젯 없는 순수 함수), 파일 변경은 `horiedit_py.data.canal`.
이 구역은 세이브 칸(slot)이 필요 없다 — 게임 폴더의 지도 파일(WORLDMAP.LZW)만 본다.
"""
from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Dict, Optional

from horiedit_py.common import EditorState
from horiedit_py.data import canal as _canal
from horiedit_py.gui import canal_logic as logic
from horiedit_py.gui.layout import Page, track_wraplength

_INTRO = (
    "수에즈·파나마 운하를 열거나 닫습니다. 게임 폴더의 지도 파일(WORLDMAP.LZW)을 바꿉니다.\n"
    "· ⚡ [개통] / [원상복원] 버튼을 누르면 바로 게임 파일(WORLDMAP.LZW)에 반영됩니다 — 위쪽 [저장] 버튼은 필요 없습니다. 되돌리기: [원상복원].\n"
    "· 바꾸기 전에 게임(DOSBox)을 완전히 종료하세요.\n"
    "· 첫 변경 때 원본 백업(WORLDMAP.LZW.canal-orig)이 자동으로 만들어집니다.\n"
    "· 항구 [자동 이동] 은 운하를 쓰지 않습니다. 운하 근처까지 가서 직접 조종해 지나가야 합니다.\n"
    "· " + logic.SCOPE_NOTE
)


class CanalPanel(Page):
    """운하 한 줄씩(수에즈·파나마): 현재 상태 + [개통]/[원상복원] 버튼."""

    def __init__(self, master: tk.Misc, state: EditorState) -> None:
        super().__init__(master, footer=True, max_body_width=980, padding=8)
        self._state = state
        self._path: Optional[Path] = None
        self._states: Optional[Dict[str, str]] = None
        self._rows: Dict[str, logic.RowView] = {}
        self._status_labels: Dict[str, ttk.Label] = {}
        self._buttons: Dict[str, ttk.Button] = {}

        self._box = ttk.LabelFrame(self.body, text="운하", padding=8)
        self._box.pack(side="top", fill="x")
        self._box.columnconfigure(1, weight=1)
        for r, key in enumerate(logic.CANAL_ORDER):
            ttk.Label(self._box, text=_canal.CANALS[key].name).grid(
                row=r, column=0, sticky="w", padx=4, pady=4
            )
            lab = ttk.Label(self._box, text="", justify="left")
            lab.grid(row=r, column=1, sticky="ew", padx=8, pady=4)
            track_wraplength(lab, min_wrap=200)
            btn = ttk.Button(
                self._box, text=logic.BTN_OPEN, width=10,
                command=lambda k=key: self._on_toggle(k),
            )
            btn.grid(row=r, column=2, sticky="e", padx=4, pady=4)
            self._status_labels[key] = lab
            self._buttons[key] = btn

        self._msg_label = ttk.Label(self.body, text="", foreground="#a00", justify="left")
        self._msg_label.pack(side="top", fill="x", pady=(8, 0))
        track_wraplength(self._msg_label)

        # 설명·지도 파일 경로는 조작 줄(개통/원상복원) 아래 — 낮은 창에서도 버튼이 먼저 보이게
        self._path_label = ttk.Label(self.body, text="", foreground="#555", justify="left")
        self._path_label.pack(side="top", fill="x", pady=(10, 6))
        track_wraplength(self._path_label)
        intro = ttk.Label(self.body, text=_INTRO, foreground="#666", justify="left")
        intro.pack(side="top", fill="x", pady=(0, 6))
        track_wraplength(intro)

        bar = self.footer   # 스크롤 밖 하단 고정 푸터
        self._btn_refresh = ttk.Button(bar, text="상태 다시 읽기", command=self.refresh)
        self._btn_refresh.pack(side="left")

        self.refresh()

    # ---------------- 상태 읽기·표시 ----------------

    def refresh(self) -> None:
        """게임 폴더에서 지도 파일을 다시 찾고 상태를 다시 읽어 화면을 갱신한다."""
        gd = getattr(self._state, "game_dir", None)
        self._path = logic.find_worldmap(gd)
        self._states = None
        msg = ""
        if gd is None:
            msg = logic.MSG_NO_GAME_DIR
        elif self._path is None:
            msg = logic.MSG_NO_WORLDMAP
        else:
            self._states, err = logic.read_states(self._path)
            if err:
                msg = err
        self._path_label.configure(
            text=(f"지도 파일: {self._path}" if self._path is not None else "지도 파일: (없음)")
        )
        self._msg_label.configure(text=msg)
        self._render()

    def _render(self) -> None:
        self._rows = {r.key: r for r in logic.describe_rows(self._states)}
        for key, row in self._rows.items():
            self._status_labels[key].configure(text=row.status_text)
            self._buttons[key].configure(
                text=row.button_label,
                state=("normal" if (row.button_enabled and self._path is not None) else "disabled"),
            )

    # ---------------- 버튼 ----------------

    def _on_toggle(self, key: str) -> None:
        row = self._rows.get(key)
        if row is None or not row.button_enabled or row.target_mode is None or self._path is None:
            return
        path = self._path
        ok = messagebox.askyesno(
            logic.confirm_title(key, row.target_mode),
            logic.confirm_message(key, row.target_mode, path),
            icon="warning",
            default="no",
            parent=self.winfo_toplevel(),
        )
        if not ok:
            return
        expected = (self._states or {}).get(key)
        result = logic.apply_toggle(path, key, expected or "")
        if result.states is not None:
            self._states = result.states
        self._msg_label.configure(text="" if result.ok else result.message)
        self._render()
        top = self.winfo_toplevel()
        if result.ok:
            messagebox.showinfo("완료", result.message, parent=top)
        else:
            messagebox.showwarning("운하를 바꾸지 못했습니다", result.message, parent=top)
