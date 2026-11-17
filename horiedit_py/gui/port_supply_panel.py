"""항구 공급 수치 패널 (물가, record +14..+23) — analysis_J.

세이브 칸(KOUKAI2.DAT)의 항구 데이터라서 [항구] 탭의 한 구역으로 들어간다.
dirty/commit 은 다른 탭과 같이 메인 [저장] / [초기화] 에 묶인다 (이 패널의 자체 [저장] 버튼도 그대로).
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable

from horiedit_py.common import EditorState
from horiedit_py.data.port import (
    NUM_PORTS,
    PORT_SUPPLY_SIZE,
    load_port_supply,
    port_supply_is_standard,
    save_port_supply,
)
from horiedit_py.gui.layout import SplitPane, track_wraplength
from horiedit_py.gui.widget_state import cascade_state as _cascade_state


def _decode_supply_byte_display(b: int) -> str:
    """공급 byte → 사람이 읽을 수 있는 표시."""
    if b == 0x2E:
        return "빈칸"
    if 0x2F <= b <= 0x39:
        level = b - 0x2F  # '/' = 0, '0' = 1, ..., '9' = 10
        return f"공급 {level}"
    return f"(값 {b})"


class PortSupplyPanel(SplitPane):
    """항구 공급 수치 편집 (record +14..+23, 10 byte/port).

    표준 항구 (0..99) 는 0x2E..0x39 (ASCII digit/dot) 인코딩.
    원거리 항구 (100..129) 는 raw byte (구조 미해석).
    """

    def __init__(self, master: tk.Misc, state: EditorState) -> None:
        super().__init__(master, grow="right", padding=8)
        self._state = state
        self._idx = 0
        self._enabled = False
        self._current_raw: bytes = b"\x00" * PORT_SUPPLY_SIZE

        self._loading = False
        self._dirty = False
        self._dirty_listeners: list[Callable[[], None]] = []

        self._vars: list[tk.IntVar] = [tk.IntVar(value=0) for _ in range(PORT_SUPPLY_SIZE)]
        self._decoded_labels: list[ttk.Label] = []

        self._build()
        for v in self._vars:
            v.trace_add("write", self._on_var_write)

    # -------- 외부 인터페이스 --------

    def is_dirty(self) -> bool:
        return self._dirty and self._enabled

    def add_dirty_listener(self, callback: Callable[[], None]) -> None:
        self._dirty_listeners.append(callback)

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
            # 슬롯이 활성화되었으므로 항구 이름이 캐시에 있을 것 — 목록 채움
            self._populate_listbox()
            if not self._listbox.curselection():
                self._listbox.selection_set(0)
                self._idx = 0
            self._loading = True
            try:
                self._load_current()
            finally:
                self._loading = False
            self._set_dirty(False)

    def commit(self) -> None:
        if not self.is_dirty():
            return
        try:
            new_bytes = bytes(int(v.get()) & 0xFF for v in self._vars)
        except (tk.TclError, ValueError):
            raise ValueError("항구 공급 수치: 숫자가 아닌 값이 있습니다.")
        try:
            save_port_supply(self._state, self._idx, new_bytes)
            self._state.fp.flush()
        except Exception as e:
            raise ValueError(f"항구 공급 수치 저장 실패: {e}") from e
        self._current_raw = new_bytes
        self._refresh_decoded_labels()
        self._set_dirty(False)

    # -------- 빌드 --------

    def _build(self) -> None:
        right = self.right   # 상세 열(자체 스크롤) — 안내·경고도 이 열 맨 위
        mode = ttk.Label(
            right,
            text=("💾 세이브 칸(KOUKAI2.DAT)의 항구 데이터입니다 — 위쪽 [저장]으로 반영되고(이 화면의 [저장]도 같은 동작), "
                  "[초기화]로 되돌립니다."),
            foreground="#246", justify="left",
        )
        mode.pack(side="top", fill="x", padx=4, pady=(0, 6))
        track_wraplength(mode)

        # 추가 경고 — 이 패널 특정 (사용자 검증 결과 가격 직접 영향 없음 확인됨)
        sub_warn = ttk.Label(
            right,
            text=(
                "⚠️ 확인 결과: 이 값을 바꿔도 시장 가격에 바로 영향이 나타나지 않았습니다.\n"
                "    게임이 값을 읽긴 하지만(한 달 뒤 자동 갱신 확인) 실제 효과는 분명치 않습니다.\n"
                "    평균물가는 매달 1일에만 바뀝니다.\n"
                "    일반 항구(0~99번)는 안전한 범위가 있고,\n"
                "    먼 바다 항구(100~129번)는 바꾸면 게임이 깨질 수 있습니다."
            ),
            foreground="#a00",
            justify="left",
        )
        sub_warn.pack(side="top", fill="x", padx=4, pady=(0, 6))
        track_wraplength(sub_warn)

        # 좌측 항구 목록 — 창 높이에 묶여 안에서 스크롤
        left = self.left
        ttk.Label(left, text="항구 (130곳):").pack(side="top", anchor="w")
        list_frame = ttk.Frame(left)
        list_frame.pack(side="top", fill="both", expand=True)
        self._listbox = tk.Listbox(
            list_frame, height=8, exportselection=False, width=22,
        )
        sb = ttk.Scrollbar(list_frame, orient="vertical", command=self._listbox.yview)
        self._listbox.configure(yscrollcommand=sb.set)
        self._listbox.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self._listbox.bind("<<ListboxSelect>>", self._on_port_selected)

        # 우측 폼
        self._lbl_current = ttk.Label(right, text="(항구 미선택)", foreground="#444")
        self._lbl_current.pack(side="top", anchor="w", pady=(0, 6))

        form = ttk.LabelFrame(right, text="공급 수치", padding=8)
        form.pack(side="top", fill="x")

        # 칸 10개를 5행 × 2열로 — 세로 길이를 절반으로 (스크롤 없이 한눈에)
        half = (PORT_SUPPLY_SIZE + 1) // 2
        for i in range(PORT_SUPPLY_SIZE):
            r, c = i % half, (i // half) * 3
            ttk.Label(form, text=f"칸 {i + 1}").grid(row=r, column=c, sticky="w", padx=4, pady=2)
            sp = ttk.Spinbox(
                form, from_=0, to=255, textvariable=self._vars[i], width=6,
            )
            sp.grid(row=r, column=c + 1, sticky="w", padx=4, pady=2)
            lbl = ttk.Label(form, text="", foreground="#666", width=8)
            lbl.grid(row=r, column=c + 2, sticky="w", padx=(8, 18), pady=2)
            self._decoded_labels.append(lbl)

        # 버튼 — 스크롤 밖 하단 고정 푸터
        btns = self.footer
        self._btn_reload = ttk.Button(btns, text="다시 불러오기", command=self._on_reload)
        self._btn_reload.pack(side="right", padx=4)
        self._btn_save = ttk.Button(btns, text="저장", command=self._on_save)
        self._btn_save.pack(side="right", padx=4)

        ttk.Label(
            right,
            text=(
                "입력 안내 (일반 항구 0~99번):\n"
                "  '.' = 빈칸, '/' = 공급 0 (가격 폭등),\n"
                "  '0'~'9' = 공급 1~10 (높을수록 가격 하락).\n"
                "먼 바다 항구(100~129번)는 위 규칙이 적용되지 않습니다."
            ),
            foreground="#666",
            justify="left",
        ).pack(side="top", anchor="w")

    def _populate_listbox(self) -> None:
        self._listbox.delete(0, "end")
        for i in range(NUM_PORTS):
            name = self._state.port_name[i] if 0 <= i < len(self._state.port_name) else ""
            mark = "" if i < 100 else " (먼 바다)"
            self._listbox.insert("end", f"{i:3d}. {name}{mark}")

    # -------- 콜백 --------

    def _on_port_selected(self, _e: object = None) -> None:
        if not self._enabled:
            return
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

    def _on_save(self) -> None:
        if not self._enabled:
            return
        try:
            self.commit()
        except ValueError as e:
            messagebox.showerror("저장 실패", str(e))
            return
        name = self._state.port_name[self._idx] if 0 <= self._idx < len(self._state.port_name) else ""
        messagebox.showinfo("저장 완료", f"{self._idx}번 항구 ({name}) 공급 수치를 저장했습니다.")

    def _on_var_write(self, *_a: object) -> None:
        if self._loading or not self._enabled:
            return
        # 실시간 디코딩 라벨 갱신
        self._refresh_decoded_labels()
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

    # -------- 로드/디코드 --------

    def _load_current(self) -> None:
        if not self._enabled:
            return
        try:
            raw = load_port_supply(self._state, self._idx)
        except Exception as e:
            messagebox.showerror("공급 수치 불러오기 실패", str(e))
            return
        self._current_raw = raw
        for i, b in enumerate(raw):
            self._vars[i].set(b)
        name = self._state.port_name[self._idx] if 0 <= self._idx < len(self._state.port_name) else ""
        category = "일반" if self._idx < 100 else "먼 바다 (분석 미완)"
        std = "✓" if port_supply_is_standard(raw) else "✗"
        self._lbl_current.configure(
            text=f"{self._idx}번 항구  {name}   [{category}, 표준 형식 {std}]"
        )
        self._refresh_decoded_labels()

    def _refresh_decoded_labels(self) -> None:
        for i, lbl in enumerate(self._decoded_labels):
            try:
                b = int(self._vars[i].get()) & 0xFF
            except (tk.TclError, ValueError):
                b = 0
            lbl.configure(text=_decode_supply_byte_display(b))
