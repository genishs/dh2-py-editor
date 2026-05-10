"""선박 편집 탭 (스텁)."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from horiedit_py.common import EditorState


class ShipTab(ttk.Frame):
    """선박 편집 탭. 다음 단계에서 구현."""

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
