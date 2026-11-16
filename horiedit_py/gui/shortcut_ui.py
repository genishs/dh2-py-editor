"""바탕화면 바로가기 관련 GUI 흐름 (이슈 #17).

로직은 horiedit_py.shortcut 에 있고, 여기서는 묻는 창 / 결과 안내만 맡는다.
어떤 실패도 프로그램 실행을 막지 않는다 — 안내창만 띄운다.
"""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Optional

from horiedit_py import shortcut

_SOURCE_RUN_MSG = (
    "지금은 소스(python)로 실행 중이라 바로가기를 만들 수 없습니다.\n"
    "바로가기는 koukai2_editor.exe 로 실행했을 때만 만들 수 있습니다."
)


def _ask_create_dialog(parent: tk.Misc, update: bool) -> tuple[bool, bool]:
    """「바로가기 만들까요?」 + 「다시 묻지 않기」 체크박스. (예 여부, 다시 묻지 않기 체크 여부)."""
    win = tk.Toplevel(parent)
    win.title("바탕화면 바로가기")
    win.transient(parent)
    win.resizable(False, False)

    answer = {"yes": False}
    never = tk.BooleanVar(value=False)

    outer = ttk.Frame(win, padding=14)
    outer.pack(fill="both", expand=True)
    if update:
        msg = ("바탕화면의 바로가기가 다른 세이브(또는 옛 위치의 프로그램)를\n"
               "가리키고 있습니다. 지금 세이브로 고칠까요?\n\n"
               "다음부터는 아이콘만 누르면 이 세이브로 바로 열립니다.")
    else:
        msg = ("바탕화면에 바로가기를 만들까요?\n\n"
               "다음부터는 아이콘만 누르면 이 세이브로 바로 열립니다.")
    ttk.Label(outer, text=msg, justify="left").pack(anchor="w")
    ttk.Checkbutton(outer, text="다시 묻지 않기", variable=never).pack(anchor="w", pady=(10, 0))

    btns = ttk.Frame(outer)
    btns.pack(fill="x", pady=(12, 0))

    def _yes() -> None:
        answer["yes"] = True
        win.destroy()

    ttk.Button(btns, text="아니오", command=win.destroy).pack(side="right", padx=(6, 0))
    yes_btn = ttk.Button(btns, text="예", command=_yes)
    yes_btn.pack(side="right")
    yes_btn.focus_set()
    win.bind("<Return>", lambda e: _yes())
    win.bind("<Escape>", lambda e: win.destroy())

    win.update_idletasks()
    try:
        px, py = parent.winfo_rootx(), parent.winfo_rooty()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        w, h = win.winfo_width(), win.winfo_height()
        win.geometry(f"+{px + (pw - w) // 2}+{py + max(0, (ph - h) // 3)}")
    except tk.TclError:
        pass
    win.grab_set()
    parent.wait_window(win)
    return answer["yes"], bool(never.get())


def _is_standard_save_name(save_path: Path) -> bool:
    """바로가기는 「시작 위치의 KOUKAI2.DAT」 를 여는 구조라, 다른 이름의 세이브엔 의미가 없다."""
    return save_path.name.lower() == "koukai2.dat"


def maybe_prompt_on_start(parent: tk.Misc, save_path: Path, found_by_dialog: bool) -> None:
    """프로그램 시작 때 바로가기를 만들지 묻는다 (조건이 안 되면 아무것도 하지 않음)."""
    try:
        exe = shortcut.current_exe()
        if exe is None:                      # 소스 실행 / 비 Windows → 묻지 않는다
            return
        if not _is_standard_save_name(save_path):
            return
        save_dir = save_path.resolve().parent
        if shortcut.prompt_disabled():       # 「다시 묻지 않기」
            return
        desktop = shortcut.resolve_desktop_dir()
        if desktop is None:
            return
        state, _ = shortcut.inspect_desktop(desktop, exe, save_dir)
        if state is None or not shortcut.should_ask_automatically(state, found_by_dialog):
            return
        yes, never = _ask_create_dialog(parent, update=state is not shortcut.State.MISSING)
        if never:
            shortcut.set_prompt_disabled(True)
        if not yes:
            return
        res = shortcut.create_or_update(desktop, exe, save_dir)
        if res.ok:
            messagebox.showinfo("바탕화면 바로가기", res.message, parent=parent)
        else:
            messagebox.showwarning(
                "바탕화면 바로가기",
                res.message + "\n\n프로그램은 정상적으로 계속 쓸 수 있습니다.\n"
                "[도움말] ▸ [바탕화면 바로가기 만들기] 로 나중에 다시 시도할 수 있어요.",
                parent=parent,
            )
    except Exception:
        # 바로가기 때문에 편집 화면이 죽는 일은 없어야 한다.
        pass


def create_manually(parent: tk.Misc, save_path: Optional[Path]) -> None:
    """[도움말] ▸ 바탕화면 바로가기 만들기 — 「다시 묻지 않기」 와 무관하게 항상 동작."""
    title = "바탕화면 바로가기 만들기"
    try:
        exe = shortcut.current_exe()
        if exe is None:
            messagebox.showinfo(title, _SOURCE_RUN_MSG, parent=parent)
            return
        if save_path is None:
            messagebox.showwarning(title, "세이브 폴더를 알 수 없습니다.", parent=parent)
            return
        if not _is_standard_save_name(save_path):
            messagebox.showinfo(
                title,
                "바로가기는 시작 위치의 KOUKAI2.DAT 를 여는 방식이라,\n"
                f"이름이 다른 세이브({save_path.name})에는 만들 수 없습니다.",
                parent=parent,
            )
            return
        save_dir = save_path.resolve().parent
        desktop = shortcut.resolve_desktop_dir()
        if desktop is None:
            messagebox.showwarning(title, "바탕화면 폴더를 찾지 못했습니다.", parent=parent)
            return
        res = shortcut.create_or_update(desktop, exe, save_dir)
        (messagebox.showinfo if res.ok else messagebox.showwarning)(
            title, res.message, parent=parent,
        )
    except Exception as e:
        messagebox.showwarning(title, f"바로가기를 만들지 못했습니다: {e}", parent=parent)


def remove_manually(parent: tk.Misc) -> None:
    """[도움말] ▸ 바로가기 제거 — 우리 exe 를 가리키는 바로가기를 찾아 목록을 보여주고 확인 뒤 삭제."""
    title = "바로가기 제거"
    try:
        found = shortcut.find_our_links(shortcut.scan_dirs())
        if found is None:
            messagebox.showwarning(title, "바로가기를 확인하지 못했습니다 (PowerShell 실행 실패).", parent=parent)
            return
        if not found:
            messagebox.showinfo(
                title, "지울 바로가기가 없습니다.\n(바탕화면·시작 메뉴에서 이 프로그램을 가리키는 바로가기를 찾지 못했습니다)",
                parent=parent,
            )
            return
        listing = "\n".join(f"  · {i.path}" for i in found)
        if not messagebox.askyesno(
            title,
            f"이 프로그램을 가리키는 바로가기 {len(found)}개를 찾았습니다.\n\n{listing}\n\n지울까요?\n"
            "(이름만 같고 다른 프로그램을 가리키는 바로가기는 건드리지 않습니다)",
            parent=parent,
        ):
            return
        items = shortcut.delete_links(found)  # 방금 보여 준 목록 그대로
        lines = [f"{'삭제됨' if it.removed else '실패'}: {it.path}" + (f" ({it.error})" if it.error else "")
                 for it in items]
        shortcut.clear_prompt_flag()
        messagebox.showinfo(title, "\n".join(lines) or "지울 바로가기가 없었습니다.", parent=parent)
    except Exception as e:
        messagebox.showwarning(title, f"바로가기를 지우지 못했습니다: {e}", parent=parent)
