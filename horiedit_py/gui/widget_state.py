"""자식 위젯 트리 일괄 활성/비활성 공용 유틸."""

from __future__ import annotations

import tkinter as tk


def cascade_state(widget: tk.Misc, st: str) -> None:
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
        cascade_state(ch, st)
