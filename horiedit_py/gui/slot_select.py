"""상단 슬롯 선택 위젯 (Combobox) + 별도 정보 패널.

Combobox 선택은 즉시 select_slot 을 호출하지 않고 on_slot_request 콜백으로
app.py 에 위임한다. 따라서 app 가 dirty 검사 / 다이얼로그를 처리한 뒤
필요 시 set_active_slot() 으로 Combobox 를 이전 값으로 되돌릴 수 있다.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional

from horiedit_py.common import EditorState, decode_kr
from horiedit_py.data import slot_init, slot_is_used


SLOT_COUNT = 10


class SlotSelectFrame(ttk.Frame):
    """10개 세이브 슬롯 Combobox + 선택 슬롯 상세 정보 패널."""

    def __init__(
        self,
        master: tk.Misc,
        state: EditorState,
        on_slot_request: Callable[[int], None],
    ) -> None:
        super().__init__(master)
        self._state = state
        self._on_slot_request = on_slot_request
        # _suppress: set_active_slot 으로 직접 갱신할 때 Combobox 의 선택 변경
        # 콜백이 발동하지 않도록 가드.
        self._suppress = False
        # Combobox 표시용
        self._var_slot = tk.StringVar(value="")
        # 슬롯 사용 가능 여부 (라벨/disabled 계산용)
        self._slot_labels: list[str] = ["" for _ in range(SLOT_COUNT)]
        self._slot_used: list[bool] = [False for _ in range(SLOT_COUNT)]

        self._build()
        self.refresh_list()

    # ---------------- UI 구성 ----------------

    def _build(self) -> None:
        self.columnconfigure(0, weight=0)
        self.columnconfigure(1, weight=1)

        # 좌측: 세이브 칸 Combobox
        slots = ttk.LabelFrame(self, text="세이브 칸", padding=8)
        slots.grid(row=0, column=0, sticky="nsw", padx=(0, 4))

        ttk.Label(slots, text="세이브 칸:").grid(
            row=0, column=0, sticky="w", padx=(0, 4), pady=2
        )
        self._cb_slot = ttk.Combobox(
            slots,
            textvariable=self._var_slot,
            state="readonly",
            width=22,
            values=[],
        )
        self._cb_slot.grid(row=0, column=1, sticky="w", padx=2, pady=2)
        self._cb_slot.bind("<<ComboboxSelected>>", self._on_combobox_changed)

        # 우측: 선택한 세이브 칸 상세 (가로 충분히 확보)
        detail = ttk.LabelFrame(self, text="선택한 세이브 칸", padding=8)
        detail.grid(row=0, column=1, sticky="nsew", padx=(4, 0))
        detail.columnconfigure(1, weight=1)

        ttk.Label(detail, text="항해날짜:").grid(
            row=0, column=0, sticky="w", padx=4, pady=2
        )
        ttk.Label(detail, text="현재위치:").grid(
            row=1, column=0, sticky="w", padx=4, pady=2
        )
        ttk.Label(detail, text="주인공  :").grid(
            row=2, column=0, sticky="w", padx=4, pady=2
        )

        self._lbl_memo = ttk.Label(detail, text="(미선택)", width=60, anchor="w")
        self._lbl_memo.grid(row=0, column=1, sticky="ew", padx=4, pady=2)
        self._lbl_port = ttk.Label(detail, text="-", width=60, anchor="w")
        self._lbl_port.grid(row=1, column=1, sticky="ew", padx=4, pady=2)
        self._lbl_hero = ttk.Label(detail, text="-", width=60, anchor="w")
        self._lbl_hero.grid(row=2, column=1, sticky="ew", padx=4, pady=2)

    # ---------------- 라벨 갱신 ----------------

    def refresh_list(self) -> None:
        """모든 슬롯 라벨 재계산. Combobox values 를 갱신."""
        for i in range(SLOT_COUNT):
            self._slot_labels[i] = self._slot_label(i)
            self._slot_used[i] = slot_is_used(self._state, i)

        # 사용 불가 슬롯도 표시는 하되 라벨에 명시. 사용자가 빈 슬롯 선택 시
        # _on_combobox_changed 에서 가드 (사용 가능한 슬롯만 콜백).
        values: list[str] = []
        for i in range(SLOT_COUNT):
            label = self._slot_labels[i]
            if not self._slot_used[i]:
                values.append(label)  # 라벨에 "(없음)" 류로 이미 표시됨
            else:
                values.append(label)
        self._cb_slot.configure(values=values)

    def _slot_label(self, idx: int) -> str:
        try:
            init = slot_init(self._state, idx)
        except Exception:
            return f"{idx + 1}) (읽기 오류)"
        if init.memo[0] == 0:
            return f"{idx + 1}) 데이터 없음"
        memo = decode_kr(init.memo).strip()
        return f"{idx + 1}) {memo}"

    def refresh_detail(self, state: EditorState, idx: Optional[int]) -> None:
        """우측 상세 패널 갱신. idx=None 이면 미선택 표시."""
        if idx is None:
            self._lbl_memo.configure(text="(미선택)")
            self._lbl_port.configure(text="-")
            self._lbl_hero.configure(text="-")
            return
        try:
            init = slot_init(state, idx)
            memo = decode_kr(init.memo).strip() or "(빈 칸)"
            port_idx = init.port
            port_name = ""
            if 0 <= port_idx < len(state.port_name):
                port_name = state.port_name[port_idx]
            hero_name = ""
            c_hero = state.c_hero
            if 0 <= c_hero < len(state.hero):
                hero_name = state.hero[c_hero]
        except Exception as e:
            self._lbl_memo.configure(text=f"(읽기 오류: {e})")
            self._lbl_port.configure(text="-")
            self._lbl_hero.configure(text="-")
            return
        self._lbl_memo.configure(text=memo)
        self._lbl_port.configure(text=port_name or "-")
        self._lbl_hero.configure(text=hero_name or "-")

    # ---------------- Combobox 동작 ----------------

    def _on_combobox_changed(self, _event: object = None) -> None:
        if self._suppress:
            return
        idx = self._cb_slot.current()
        if idx < 0 or idx >= SLOT_COUNT:
            return
        # 빈 슬롯 (사용 불가) 인 경우, 콜백을 발동하지 않는다.
        # app 가 set_active_slot 으로 표시를 회복할 책임을 진다.
        if not self._slot_used[idx]:
            return
        self._on_slot_request(idx)

    def set_active_slot(self, idx: Optional[int]) -> None:
        """Combobox 표시를 강제 변경 (콜백을 발동시키지 않는다)."""
        self._suppress = True
        try:
            if idx is None or not (0 <= idx < SLOT_COUNT):
                self._cb_slot.set("")
            else:
                self._cb_slot.current(idx)
        finally:
            self._suppress = False

    def selected_index(self) -> Optional[int]:
        v = self._cb_slot.current()
        return v if v >= 0 else None
