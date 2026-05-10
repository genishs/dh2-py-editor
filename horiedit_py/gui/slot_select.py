"""상단 슬롯 선택 위젯 (라디오) + 별도 정보 패널.

라디오 클릭은 즉시 select_slot 을 호출하지 않고 on_slot_request 콜백으로
app.py 에 위임한다. 따라서 app 가 dirty 검사 / 다이얼로그를 처리한 뒤
필요 시 set_active_slot() 으로 라디오를 이전 값으로 되돌릴 수 있다.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional

from horiedit_py.common import EditorState, decode_kr
from horiedit_py.data import slot_init, slot_is_used


SLOT_COUNT = 10


class SlotSelectFrame(ttk.Frame):
    """10개 세이브 슬롯 라디오 + 선택 슬롯 상세 정보 패널."""

    def __init__(
        self,
        master: tk.Misc,
        state: EditorState,
        on_slot_request: Callable[[int], None],
    ) -> None:
        super().__init__(master)
        self._state = state
        self._on_slot_request = on_slot_request
        # _var: 현재 라디오에 표시되는 값. set_active_slot 으로 직접 갱신할 때
        # _on_radio_clicked 가 호출되지 않도록 _suppress 플래그 사용.
        self._var = tk.IntVar(value=-1)
        self._suppress = False
        self._radios: list[ttk.Radiobutton] = []

        self._build()
        self.refresh_list()

    # ---------------- UI 구성 ----------------

    def _build(self) -> None:
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)

        # 좌측: 슬롯 라디오 박스
        slots = ttk.LabelFrame(self, text="세이브 슬롯", padding=8)
        slots.grid(row=0, column=0, sticky="nsew", padx=(0, 4))

        # 2 x 5 배치
        for i in range(SLOT_COUNT):
            r, c = divmod(i, 5)
            rb = ttk.Radiobutton(
                slots,
                text=f"{i + 1}) (없음)",
                value=i,
                variable=self._var,
                command=self._on_radio_clicked,
            )
            rb.grid(row=r, column=c, sticky="w", padx=4, pady=2)
            self._radios.append(rb)

        # 우측: 선택한 슬롯 상세
        detail = ttk.LabelFrame(self, text="선택한 슬롯", padding=8)
        detail.grid(row=0, column=1, sticky="nsew", padx=(4, 0))

        ttk.Label(detail, text="메모:").grid(row=0, column=0, sticky="w", padx=4, pady=2)
        ttk.Label(detail, text="항구:").grid(row=1, column=0, sticky="w", padx=4, pady=2)
        ttk.Label(detail, text="주인공:").grid(row=2, column=0, sticky="w", padx=4, pady=2)

        self._lbl_memo = ttk.Label(detail, text="(미선택)")
        self._lbl_memo.grid(row=0, column=1, sticky="w", padx=4, pady=2)
        self._lbl_port = ttk.Label(detail, text="-")
        self._lbl_port.grid(row=1, column=1, sticky="w", padx=4, pady=2)
        self._lbl_hero = ttk.Label(detail, text="-")
        self._lbl_hero.grid(row=2, column=1, sticky="w", padx=4, pady=2)

        detail.columnconfigure(1, weight=1)

    # ---------------- 라벨 갱신 ----------------

    def refresh_list(self) -> None:
        """모든 라디오 라벨 재계산. 데이터 없는 슬롯은 비활성."""
        for i in range(SLOT_COUNT):
            label = self._slot_label(i)
            used = slot_is_used(self._state, i)
            self._radios[i].configure(
                text=label,
                state=("normal" if used else "disabled"),
            )

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
            memo = decode_kr(init.memo).strip() or "(빈 슬롯)"
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

    # ---------------- 라디오 동작 ----------------

    def _on_radio_clicked(self) -> None:
        if self._suppress:
            return
        idx = self._var.get()
        if idx < 0:
            return
        self._on_slot_request(idx)

    def set_active_slot(self, idx: Optional[int]) -> None:
        """라디오 표시를 강제 변경 (콜백을 발동시키지 않는다)."""
        self._suppress = True
        try:
            self._var.set(idx if idx is not None else -1)
        finally:
            self._suppress = False

    def selected_index(self) -> Optional[int]:
        v = self._var.get()
        return v if v >= 0 else None
