"""게임 기본 설정 탭 (스텁).

lhull 단일 ROM 테이블은 존재 여부가 불확실하여 (analysis/analysis_E_lhull_table.md)
이 탭의 메뉴에서 lhull 편집 항목은 추가하지 않는다.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from horiedit_py.common import EditorState


class SettingsTab(ttk.Frame):
    """게임 기본 설정 탭. 다음 단계에서 구현 (lhull 항목은 제외)."""

    def __init__(self, master: tk.Misc, state: EditorState) -> None:
        super().__init__(master, padding=12)
        self._state = state
        ttk.Label(
            self,
            text="(개발 중) 다음 단계에서 구현 예정",
            anchor="center",
        ).pack(expand=True, fill="both")

    def reload(self) -> None:  # pragma: no cover - 스텁
        pass

    def reset(self) -> None:  # pragma: no cover - 스텁
        pass
