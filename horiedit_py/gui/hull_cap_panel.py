"""신조 내구도 상한 패널 — MAIN.EXE 의 신조 cap (issue #5, analysis_N).

[게임 전체] 탭의 한 구역으로 들어간다 (예전에는 [도구] 메뉴의 모달 다이얼로그였다).
세이브 슬롯과 무관하게 MAIN.EXE 만 편집하고, [저장] 이 아니라 버튼을 누르면 바로 파일에 반영한다.
- 입력 1 개 (최대 내구도 1..255) → 발견된 모든 cap 위치에 동일 값 일괄 적용
- 처음 [적용] 때 원본 백업(MAIN.EXE.beforeHullCap) 자동 생성, [백업에서 복원] 으로 되돌림

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
from horiedit_py.gui.layout import Page, track_wraplength


class HullCapPanel(Page):
    """신조 내구도 상한 패널 (게임 전체 탭의 sub-tab)."""

    def __init__(self, master: tk.Misc, state: EditorState) -> None:
        super().__init__(master, footer=True, max_body_width=980, padding=14)
        self._state = state
        self._main_exe: Optional[Path] = None
        self._disk_caps: list[tuple[int, int]] = []
        self._var_cap = tk.IntVar(value=HULL_CAP_DEFAULT)
        self._editable_widgets: list[tk.Misc] = []

        self._build()
        self.reload()

    def _dlg(self) -> tk.Misc:
        """메시지 상자의 부모 — 이 패널이 놓인 최상위 창."""
        return self.winfo_toplevel()

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
        outer = self.body

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
        header.pack(side="top", fill="x", pady=(0, 6))
        track_wraplength(header)

        apply_note = ttk.Label(
            outer,
            text="⚡ [적용] / [백업에서 복원] 버튼을 누르면 바로 게임 파일(MAIN.EXE)에 반영됩니다 "
                 "— 위쪽 [저장] 버튼은 필요 없습니다. 되돌리기: [백업에서 복원].",
            foreground="#a40", justify="left",
        )
        apply_note.pack(side="top", fill="x", pady=(0, 10))
        track_wraplength(apply_note)

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

        # 실행 버튼 줄 — 스크롤 밖 하단 고정 푸터
        btns = self.footer
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
            messagebox.showerror("입력 오류", "최대 내구도 값을 숫자로 입력하세요.", parent=self._dlg())
            return
        if not (1 <= val <= 255):
            messagebox.showerror("입력 오류", "최대 내구도는 1~255 사이여야 합니다.", parent=self._dlg())
            return
        try:
            ensure_hull_cap_backup(self._main_exe)
            pairs = [(o, val) for o, _ in self._disk_caps]
            save_hull_caps(self._main_exe, pairs)
        except Exception as e:
            messagebox.showerror("적용 실패", str(e), parent=self._dlg())
            return
        messagebox.showinfo(
            "적용 완료",
            f"{len(self._disk_caps)} 곳에 최대 내구도 {val}을(를) 적용했습니다.\n"
            f"게임을 다시 실행해야 반영됩니다.",
            parent=self._dlg(),
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
                parent=self._dlg(),
            )
            return
        if not messagebox.askyesno(
            "백업에서 복원",
            f"백업({backup.name})으로 게임 본체 파일을 되돌립니다. 진행할까요?",
            parent=self._dlg(),
        ):
            return
        if restore_hull_cap_backup(self._main_exe):
            messagebox.showinfo(
                "복원 완료",
                "게임 본체 파일을 백업 상태로 되돌렸습니다. 게임을 다시 실행해야 반영됩니다.",
                parent=self._dlg(),
            )
            self.reload()
        else:
            messagebox.showerror("복원 실패", "백업 파일 복원 실패.", parent=self._dlg())
