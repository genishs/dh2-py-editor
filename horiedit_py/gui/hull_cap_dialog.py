"""최대 내구도 수정 다이얼로그 — MAIN.EXE 의 신조 cap (issue #5, analysis_N).

이 다이얼로그는 세이브 슬롯과 무관하게 MAIN.EXE 만 편집한다.
- 메뉴바: 도구 → 최대 내구도 수정... 으로 호출
- 모달 (grab_set) — 다이얼로그 닫기 전까지 메인 윈도우 비활성
- 입력 1 개 (최대 내구도 1..255) → 발견된 모든 cap 위치에 동일 값 일괄 적용

signature 검색으로 cap byte 위치 자동 탐색 (가이드 hardcoded offset 회피).
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Optional
from pathlib import Path

from horiedit_py.common import EditorState
from horiedit_py.data.game import (
    HULL_CAP_DEFAULT,
    ensure_hull_cap_backup,
    hull_cap_backup_path,
    load_hull_caps,
    main_exe_path,
    restore_hull_cap_backup,
    save_hull_caps,
)


def open_hull_cap_dialog(parent: tk.Misc, state: EditorState) -> None:
    """편의 함수 — 메뉴/버튼 핸들러에서 한 줄 호출용."""
    HullCapDialog(parent, state)


class HullCapDialog(tk.Toplevel):
    """최대 내구도 수정 모달 다이얼로그."""

    def __init__(self, parent: tk.Misc, state: EditorState) -> None:
        super().__init__(parent)
        self._state = state
        self._main_exe: Optional[Path] = None
        self._disk_caps: list[tuple[int, int]] = []
        self._var_cap = tk.IntVar(value=HULL_CAP_DEFAULT)
        self._editable_widgets: list[tk.Misc] = []

        self.title("최대 내구도 상한 바꾸기")
        self.transient(parent)
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build()
        self.reload()

        # 부모 윈도우 위에 띄우기
        self.update_idletasks()
        try:
            px = parent.winfo_rootx()
            py = parent.winfo_rooty()
            pw = parent.winfo_width()
            ph = parent.winfo_height()
            w = self.winfo_width()
            h = self.winfo_height()
            self.geometry(f"+{px + (pw - w) // 2}+{py + (ph - h) // 3}")
        except tk.TclError:
            pass

        # 모달
        self.grab_set()
        self.focus_set()

    # ---------------- 데이터 로드/UI ----------------

    def reload(self) -> None:
        self._main_exe = main_exe_path(self._state)
        if self._main_exe is None:
            self._disk_caps = []
            self._lbl_main_exe.configure(
                text="게임 본체 파일(MAIN.EXE)을 찾지 못했습니다.", foreground="#a00"
            )
            self._lbl_found.configure(
                text="저장 파일과 게임이 함께 있는 게임 폴더에서 실행해 주세요."
            )
            self._lbl_current.configure(text="", foreground="#246")
            self._lbl_backup.configure(text="")
            self._set_enabled(False)
            return

        self._lbl_main_exe.configure(
            text=f"게임 본체 파일: {self._main_exe.name}", foreground="#246"
        )
        caps = load_hull_caps(self._main_exe)
        self._disk_caps = caps

        if not caps:
            self._lbl_found.configure(
                text="이 버전의 게임에서는 해당 항목을 찾지 못했습니다 (다른 버전일 수 있습니다)."
            )
            self._lbl_current.configure(text="", foreground="#246")
            self._set_enabled(False)
        else:
            values = sorted(set(v for _, v in caps))
            self._lbl_found.configure(
                text=f"수정 가능한 위치 {len(caps)} 곳을 찾았습니다."
            )
            if len(values) == 1:
                self._lbl_current.configure(
                    text=f"현재 최대 내구도: {values[0]}", foreground="#246"
                )
                self._var_cap.set(values[0])
            else:
                self._lbl_current.configure(
                    text=(
                        f"⚠ 위치마다 값이 다릅니다 ({', '.join(str(v) for v in values)}) — "
                        "[적용] 시 입력한 값으로 통일됩니다."
                    ),
                    foreground="#a60",
                )
                self._var_cap.set(values[0])
            self._set_enabled(True)

        self._update_backup_label()

    def _build(self) -> None:
        outer = ttk.Frame(self, padding=14)
        outer.pack(fill="both", expand=True)

        header = ttk.Label(
            outer,
            text=(
                "조선소에서 새 배를 만들 때의 최대 내구도 상한(게임 기본 100)을 바꿉니다.\n"
                "이 설정은 게임 전체에 적용되며 세이브 칸과는 상관없습니다.\n"
                "처음 [적용]할 때 원본 백업(MAIN.EXE.beforeHullCap)이 자동으로 만들어집니다."
            ),
            foreground="#246",
            justify="left",
        )
        header.pack(side="top", fill="x", pady=(0, 12))

        status = ttk.LabelFrame(outer, text="현재 상태", padding=8)
        status.pack(side="top", fill="x", pady=4)
        self._lbl_main_exe = ttk.Label(status, text="", justify="left", anchor="w")
        self._lbl_main_exe.pack(side="top", fill="x")
        self._lbl_found = ttk.Label(status, text="", justify="left", anchor="w")
        self._lbl_found.pack(side="top", fill="x")
        self._lbl_current = ttk.Label(
            status, text="", justify="left", anchor="w", foreground="#246"
        )
        self._lbl_current.pack(side="top", fill="x")
        self._lbl_backup = ttk.Label(
            status, text="", justify="left", anchor="w", foreground="#666"
        )
        self._lbl_backup.pack(side="top", fill="x")

        input_frame = ttk.LabelFrame(outer, text="최대 내구도 (1~255)", padding=8)
        input_frame.pack(side="top", fill="x", pady=4)
        self._sp_cap = ttk.Spinbox(
            input_frame, from_=1, to=255, textvariable=self._var_cap, width=10
        )
        self._sp_cap.pack(side="left", padx=4)
        ttk.Label(
            input_frame,
            text="* 게임 기본값은 100입니다. 찾은 모든 위치에 같은 값을 한 번에 적용합니다.",
            foreground="#666",
        ).pack(side="left", padx=8)
        self._editable_widgets.append(self._sp_cap)

        btns = ttk.Frame(outer)
        btns.pack(side="top", fill="x", pady=(12, 0))
        self._btn_apply = ttk.Button(btns, text="적용", command=self._on_apply)
        self._btn_apply.pack(side="left", padx=4)
        self._btn_default = ttk.Button(
            btns, text="기본값 (100) 으로 입력", command=self._on_default
        )
        self._btn_default.pack(side="left", padx=4)
        self._btn_restore = ttk.Button(
            btns, text="백업에서 복원", command=self._on_restore
        )
        self._btn_restore.pack(side="left", padx=4)
        self._btn_reload = ttk.Button(btns, text="다시 불러오기", command=self.reload)
        self._btn_reload.pack(side="left", padx=4)
        self._btn_close = ttk.Button(btns, text="닫기", command=self._on_close)
        self._btn_close.pack(side="right", padx=4)
        self._editable_widgets.extend(
            (self._btn_apply, self._btn_default, self._btn_restore, self._btn_reload)
        )

    def _set_enabled(self, enabled: bool) -> None:
        st = "normal" if enabled else "disabled"
        for w in self._editable_widgets:
            try:
                w.configure(state=st)
            except tk.TclError:
                pass

    def _update_backup_label(self) -> None:
        if self._main_exe is None:
            return
        backup = hull_cap_backup_path(self._main_exe)
        if backup.exists():
            self._lbl_backup.configure(text=f"백업 있음: {backup.name}")
        else:
            self._lbl_backup.configure(
                text=f"백업 없음: {backup.name} (처음 적용할 때 자동 생성)"
            )

    # ---------------- 액션 ----------------

    def _on_apply(self) -> None:
        if self._main_exe is None or not self._disk_caps:
            return
        try:
            val = int(self._var_cap.get())
        except (tk.TclError, ValueError):
            messagebox.showerror("입력 오류", "최대 내구도 값을 숫자로 입력하세요.", parent=self)
            return
        if not (1 <= val <= 255):
            messagebox.showerror("입력 오류", "최대 내구도는 1~255 사이여야 합니다.", parent=self)
            return
        try:
            ensure_hull_cap_backup(self._main_exe)
            pairs = [(o, val) for o, _ in self._disk_caps]
            save_hull_caps(self._main_exe, pairs)
        except Exception as e:
            messagebox.showerror("적용 실패", str(e), parent=self)
            return
        messagebox.showinfo(
            "적용 완료",
            f"{len(self._disk_caps)} 곳에 최대 내구도 {val}을(를) 적용했습니다.\n"
            f"게임을 다시 실행해야 반영됩니다.",
            parent=self,
        )
        self.reload()

    def _on_default(self) -> None:
        self._var_cap.set(HULL_CAP_DEFAULT)

    def _on_restore(self) -> None:
        if self._main_exe is None:
            return
        backup = hull_cap_backup_path(self._main_exe)
        if not backup.exists():
            messagebox.showinfo(
                "백업 없음",
                f"{backup.name} 가 없습니다 — 아직 적용한 적이 없습니다.",
                parent=self,
            )
            return
        if not messagebox.askyesno(
            "백업에서 복원",
            f"백업({backup.name})으로 게임 본체 파일을 되돌립니다. 진행할까요?",
            parent=self,
        ):
            return
        if restore_hull_cap_backup(self._main_exe):
            messagebox.showinfo(
                "복원 완료",
                "게임 본체 파일을 백업 상태로 되돌렸습니다. 게임을 다시 실행해야 반영됩니다.",
                parent=self,
            )
            self.reload()
        else:
            messagebox.showerror("복원 실패", "백업 파일 복원 실패.", parent=self)

    def _on_close(self) -> None:
        try:
            self.grab_release()
        except tk.TclError:
            pass
        self.destroy()
