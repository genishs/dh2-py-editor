"""상단 슬롯 선택 위젯."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional

from horiedit_py.common import EditorState, decode_kr
from horiedit_py.data import select_slot, slot_init, slot_is_used


SLOT_COUNT = 10


class SlotSelectFrame(ttk.LabelFrame):
    """10개 세이브 슬롯을 라디오버튼으로 선택하는 상단 위젯."""

    def __init__(
        self,
        master: tk.Misc,
        state: EditorState,
        on_slot_changed: Callable[[int], None],
        on_quit: Callable[[], None],
    ) -> None:
        super().__init__(master, text="세이브 슬롯", padding=8)
        self._state = state
        self._on_slot_changed = on_slot_changed
        self._on_quit = on_quit
        self._var = tk.IntVar(value=-1)
        self._radios: list[ttk.Radiobutton] = []
        self._build()
        self.refresh()

    def _build(self) -> None:
        # 라디오버튼은 2줄 x 5칸으로 배치.
        grid = ttk.Frame(self)
        grid.grid(row=0, column=0, sticky="nsew")
        for i in range(SLOT_COUNT):
            r, c = divmod(i, 5)
            rb = ttk.Radiobutton(
                grid,
                text=f"{i + 1}) (없음)",
                value=i,
                variable=self._var,
                command=self._on_radio_clicked,
            )
            rb.grid(row=r, column=c, sticky="w", padx=4, pady=2)
            self._radios.append(rb)

        # 우측 종료 버튼
        side = ttk.Frame(self)
        side.grid(row=0, column=1, sticky="ne", padx=8)
        ttk.Button(side, text="프로그램 종료", command=self._on_quit).grid(
            row=0, column=0, sticky="ne"
        )

        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=0)

    def refresh(self) -> None:
        """파일에서 다시 슬롯 메타를 읽어 라벨 갱신."""
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
        # 항구 이름은 슬롯이 로드되어야 캐시되므로 여기서는 메모만.
        return f"{idx + 1}) {memo}"

    def _on_radio_clicked(self) -> None:
        idx = self._var.get()
        if idx < 0:
            return
        if not slot_is_used(self._state, idx):
            return
        try:
            select_slot(self._state, idx)
        except Exception as e:
            from tkinter import messagebox
            messagebox.showerror("슬롯 로드 실패", str(e))
            return
        # 슬롯이 로드되면 port_name 캐시가 갱신되므로 라벨 다시 한 번 보강 가능.
        self._update_active_label(idx)
        self._on_slot_changed(idx)

    def _update_active_label(self, idx: int) -> None:
        """슬롯 로드 후, 활성 슬롯에 항구·주인공 이름을 덧붙인다."""
        try:
            init = slot_init(self._state, idx)
            memo = decode_kr(init.memo).strip()
            port_idx = init.port
            port_name = ""
            if 0 <= port_idx < len(self._state.port_name):
                port_name = self._state.port_name[port_idx]
            hero_name = ""
            c_hero = self._state.c_hero
            if 0 <= c_hero < len(self._state.hero):
                hero_name = self._state.hero[c_hero]
            text = f"{idx + 1}) {memo}  *{port_name}  {hero_name}"
            self._radios[idx].configure(text=text)
        except Exception:
            pass

    def selected_index(self) -> Optional[int]:
        v = self._var.get()
        return v if v >= 0 else None
