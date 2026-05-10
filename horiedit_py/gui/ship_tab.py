"""선박 편집 탭.

내부 sub-Notebook 으로 두 영역 분리:
1) 나의 함대 — 현재 c_hero 가 보유한 함대 편집
2) 원래 함선 정보 — 슬롯 내 25종 함선 템플릿 + (추정) MAIN.EXE lhull

dirty/commit/revert 인터페이스 통합:
- ShipTab 자체가 EditorTab 역할을 하며, 내부 sub-editor 두 개의 dirty 를
  OR 로 합치고 add_dirty_listener 로 외부에 전파한다.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable, Optional

from horiedit_py.common import (
    EditorState,
    Ship1,
    Ship2,
    Ship3,
    Ship4,
    Ship5,
    decode_kr,
    encode_kr_fixed,
    form_name,
    weapon_name,
)
# 함선 record (analysis_G 확정): record +0 = kogyo, record +1 = lhull.
# horiedit.h 의 ship4_addr (0x5291) 은 record 의 +2 (lrudder) 부터 시작
# (off-by-2). 실제 record 시작은 슬롯 +0x528F / MAIN.EXE 0x0407D8.
from horiedit_py.data.game import (
    PRICE_MAX_DISPLAY,
    PRICE_SCALE,
    load_record_kogyo,
    load_record_lhull,
    load_record_price,
    load_record_ship_class,
    save_record_kogyo,
    save_record_lhull,
    save_record_price,
)
from horiedit_py.data.ship import (
    cargo_recalc,
    load_fleet_entry,
    load_ship4,
    load_ship5,
    save_fleet_entry,
    save_ship4,
    save_ship5,
)


class ShipTab(ttk.Frame):
    """선박 편집 탭."""

    def __init__(self, master: tk.Misc, state: EditorState) -> None:
        super().__init__(master, padding=8)
        self._state = state
        self._slot_loaded = False
        self._dirty_listeners: list[Callable[[], None]] = []

        self._notebook = ttk.Notebook(self)
        self._notebook.pack(fill="both", expand=True)

        self._fleet = _FleetEditor(self._notebook, state)
        self._org = _OrgShipEditor(self._notebook, state)

        self._notebook.add(self._fleet, text="나의 함대")
        self._notebook.add(self._org, text="원래 함선 정보")

        # 하위 sub-editor 의 dirty 를 외부로 전파
        self._fleet.add_dirty_listener(self._on_sub_dirty)
        self._org.add_dirty_listener(self._on_sub_dirty)

    # ---------------- EditorTab 인터페이스 ----------------

    def reload(self) -> None:
        self._slot_loaded = True
        self._fleet.reload()
        self._org.reload()

    def reset(self) -> None:
        self._slot_loaded = False
        self._fleet.reset()
        self._org.reset()

    def revert(self) -> None:
        self.reload()

    def is_dirty(self) -> bool:
        return self._fleet.is_dirty() or self._org.is_dirty()

    def commit(self) -> None:
        # sub-editor 두 개 순차 commit
        self._fleet.commit()
        self._org.commit()

    def add_dirty_listener(self, callback: Callable[[], None]) -> None:
        self._dirty_listeners.append(callback)

    def _on_sub_dirty(self) -> None:
        for cb in list(self._dirty_listeners):
            try:
                cb()
            except Exception:
                pass


# ===========================================================================
# 1) 나의 함대 편집
# ===========================================================================


class _FleetEditor(ttk.Frame):
    """현재 c_hero 가 보유한 함대(0..ship_num-1) 편집."""

    def __init__(self, master: tk.Misc, state: EditorState) -> None:
        super().__init__(master, padding=8)
        self._state = state
        self._slot_loaded = False
        self._sel: Optional[int] = None
        self._loading = False
        self._dirty = False
        self._dirty_listeners: list[Callable[[], None]] = []

        # 위젯 변수
        self._var_ccrew = tk.IntVar(value=0)
        self._var_chull = tk.IntVar(value=0)
        self._var_lhull = tk.IntVar(value=0)
        self._var_crudder = tk.IntVar(value=0)
        self._var_csail = tk.IntVar(value=0)
        self._var_cnowea = tk.IntVar(value=0)
        self._var_condition = tk.IntVar(value=0)
        self._var_cargo = tk.StringVar(value="-")
        self._var_f_crew = tk.IntVar(value=0)
        self._var_f_weap = tk.IntVar(value=0)
        self._var_cselwea = tk.StringVar()
        self._var_form = tk.StringVar()
        self._var_ship_select = tk.StringVar()
        self._var_ship_name = tk.StringVar()

        # 현재 로드된 구조체
        self._ship1: Optional[Ship1] = None
        self._ship2: Optional[Ship2] = None
        self._ship3: Optional[Ship3] = None
        self._ship4: Optional[Ship4] = None

        self._build()
        self._set_form_state("disabled")
        self._install_dirty_traces()

    # ---------------- 빌드 ----------------

    def _build(self) -> None:
        self._hint = ttk.Label(self, text="(슬롯을 먼저 선택하세요)", foreground="#888")
        self._hint.grid(row=0, column=0, columnspan=2, pady=8)

        # 좌: 함대 목록
        left = ttk.LabelFrame(self, text="함대", padding=6)
        left.grid(row=1, column=0, sticky="nsw", padx=(0, 6))
        self._listbox = tk.Listbox(left, height=18, exportselection=False, width=34)
        self._listbox.grid(row=0, column=0, sticky="nsew")
        sb = ttk.Scrollbar(left, orient="vertical", command=self._listbox.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self._listbox.configure(yscrollcommand=sb.set)
        self._listbox.bind("<<ListboxSelect>>", self._on_select)

        # 우: 편집 폼
        right = ttk.LabelFrame(self, text="함선 정보", padding=8)
        right.grid(row=1, column=1, sticky="nsew")

        r = 0
        self._sp_ccrew = self._add_spinbox(right, r, "현재 선원수", self._var_ccrew, 0, 65535); r += 1
        self._sp_chull = self._add_spinbox(right, r, "현재 내구력", self._var_chull, 0, 255); r += 1
        self._sp_lhull = self._add_spinbox(right, r, "최대 내구력", self._var_lhull, 0, 255); r += 1
        self._sp_crudder = self._add_spinbox(right, r, "현재 선회력", self._var_crudder, 0, 255); r += 1
        self._sp_csail = self._add_spinbox(right, r, "현재 추진력", self._var_csail, 0, 255); r += 1
        self._sp_cnowea = self._add_spinbox(right, r, "현재 포문수", self._var_cnowea, 0, 255); r += 1
        self._sp_condition = self._add_spinbox(right, r, "현재 컨디션", self._var_condition, 0, 255); r += 1

        ttk.Label(right, text="최대 적재량").grid(row=r, column=0, sticky="w", padx=4, pady=4)
        ttk.Label(right, textvariable=self._var_cargo).grid(row=r, column=1, sticky="w", padx=4, pady=4)
        r += 1

        self._sp_f_crew = self._add_spinbox(right, r, "최대 선원수", self._var_f_crew, 0, 65535); r += 1
        self._sp_f_weap = self._add_spinbox(right, r, "최대 포문수", self._var_f_weap, 0, 255); r += 1

        ttk.Label(right, text="현재 무기").grid(row=r, column=0, sticky="w", padx=4, pady=4)
        self._cb_cselwea = ttk.Combobox(
            right, textvariable=self._var_cselwea, values=list(weapon_name),
            state="readonly", width=14,
        )
        self._cb_cselwea.grid(row=r, column=1, sticky="w", padx=4, pady=4)
        self._cb_cselwea.bind("<<ComboboxSelected>>", self._on_dirty_event)
        r += 1

        ttk.Label(right, text="선수상").grid(row=r, column=0, sticky="w", padx=4, pady=4)
        self._cb_form = ttk.Combobox(
            right, textvariable=self._var_form, values=list(form_name),
            state="readonly", width=14,
        )
        self._cb_form.grid(row=r, column=1, sticky="w", padx=4, pady=4)
        self._cb_form.bind("<<ComboboxSelected>>", self._on_dirty_event)
        r += 1

        ttk.Label(right, text="함선종류").grid(row=r, column=0, sticky="w", padx=4, pady=4)
        self._cb_ship_select = ttk.Combobox(
            right, textvariable=self._var_ship_select, values=[],
            state="readonly", width=22,
        )
        self._cb_ship_select.grid(row=r, column=1, sticky="w", padx=4, pady=4)
        self._cb_ship_select.bind("<<ComboboxSelected>>", self._on_dirty_event)
        r += 1

        ttk.Label(right, text="함선 이름").grid(row=r, column=0, sticky="w", padx=4, pady=4)
        self._en_ship_name = ttk.Entry(right, textvariable=self._var_ship_name, width=22)
        self._en_ship_name.grid(row=r, column=1, sticky="w", padx=4, pady=4)
        r += 1

        self.columnconfigure(1, weight=1)

    def _add_spinbox(
        self, parent: tk.Misc, row: int, label: str, var: tk.IntVar, lo: int, hi: int,
    ) -> ttk.Spinbox:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=4, pady=4)
        sp = ttk.Spinbox(parent, from_=lo, to=hi, textvariable=var, width=10)
        sp.grid(row=row, column=1, sticky="w", padx=4, pady=4)
        return sp

    # ---------------- dirty ----------------

    def _install_dirty_traces(self) -> None:
        for v in (
            self._var_ccrew, self._var_chull, self._var_lhull, self._var_crudder,
            self._var_csail, self._var_cnowea, self._var_condition,
            self._var_f_crew, self._var_f_weap,
        ):
            v.trace_add("write", self._on_var_write)
        self._var_ship_name.trace_add("write", self._on_var_write)

    def _on_var_write(self, *_a: object) -> None:
        if self._loading:
            return
        if not self._slot_loaded or self._sel is None:
            return
        self._set_dirty(True)

    def _on_dirty_event(self, _event: object = None) -> None:
        if self._loading:
            return
        if not self._slot_loaded or self._sel is None:
            return
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

    def is_dirty(self) -> bool:
        return self._dirty and self._slot_loaded and self._sel is not None

    def add_dirty_listener(self, callback: Callable[[], None]) -> None:
        self._dirty_listeners.append(callback)

    # ---------------- reload / reset ----------------

    def reload(self) -> None:
        self._loading = True
        try:
            self._slot_loaded = True
            self._hint.grid_remove()

            self._cb_ship_select.configure(values=list(self._state.ship_name))
            self._refresh_listbox()

            if self._state.ship_num == 0:
                self._listbox.configure(state="disabled")
                self._set_form_state("disabled")
                self._show_no_fleet_label()
                self._sel = None
                self._ship1 = self._ship2 = self._ship3 = self._ship4 = None
            else:
                self._hide_no_fleet_label()
                self._listbox.configure(state="normal")
                self._listbox.selection_clear(0, "end")
                self._listbox.selection_set(0)
                self._listbox.activate(0)
                self._sel = 0
                self._load_fleet(0)
        finally:
            self._loading = False
        self._set_dirty(False)

    def reset(self) -> None:
        self._loading = True
        try:
            self._slot_loaded = False
            self._sel = None
            self._ship1 = self._ship2 = self._ship3 = self._ship4 = None
            self._listbox.delete(0, "end")
            self._listbox.configure(state="normal")
            self._hide_no_fleet_label()
            self._set_form_state("disabled")
            self._hint.grid()
        finally:
            self._loading = False
        self._set_dirty(False)

    def revert(self) -> None:
        self.reload()

    def commit(self) -> None:
        if not self._slot_loaded or self._sel is None:
            return
        if not self._dirty:
            return
        if self._ship1 is None or self._ship2 is None or self._ship3 is None or self._ship4 is None:
            return
        self._collect_and_save(self._sel)
        # 목록 라벨 갱신 (이름/함종 반영)
        self._loading = True
        try:
            self._refresh_listbox()
            self._listbox.selection_clear(0, "end")
            self._listbox.selection_set(self._sel)
            self._listbox.activate(self._sel)
        finally:
            self._loading = False
        self._set_dirty(False)

    def _show_no_fleet_label(self) -> None:
        if not hasattr(self, "_no_fleet_lbl"):
            self._no_fleet_lbl = ttk.Label(
                self, text="(보유 함선 없음)", foreground="#888"
            )
        self._no_fleet_lbl.grid(row=3, column=0, columnspan=2, pady=(8, 0))

    def _hide_no_fleet_label(self) -> None:
        if hasattr(self, "_no_fleet_lbl"):
            self._no_fleet_lbl.grid_remove()

    def _refresh_listbox(self) -> None:
        self._listbox.delete(0, "end")
        for i in range(self._state.ship_num):
            try:
                ship1, _ship2, ship3 = load_fleet_entry(self._state, i)
            except Exception:
                self._listbox.insert("end", f"함선 {i + 1}: (읽기 실패)")
                continue
            sel_idx = ship3.ship_select
            if 0 <= sel_idx < len(self._state.ship_name):
                stype = self._state.ship_name[sel_idx]
            else:
                stype = f"?({sel_idx})"
            sname = decode_kr(ship3.ship_name)
            label = f'함선 {i + 1}: <{stype}> "{sname}"'
            self._listbox.insert("end", label)
            _ = ship1

    # ---------------- 폼 채우기 ----------------

    def _load_fleet(self, sel: int) -> None:
        try:
            ship1, ship2, ship3 = load_fleet_entry(self._state, sel)
            ship4 = load_ship4(self._state, ship3.ship_select)
        except Exception as e:
            messagebox.showerror("함대 로드 실패", str(e))
            return

        self._ship1 = ship1
        self._ship2 = ship2
        self._ship3 = ship3
        self._ship4 = ship4

        self._var_ccrew.set(ship1.ccrew)
        self._var_chull.set(ship1.chull)
        self._var_lhull.set(ship1.lhull)
        self._var_crudder.set(ship1.crudder)
        self._var_csail.set(ship1.csail)
        self._var_cnowea.set(ship1.cnowea)
        self._var_condition.set(ship2.condition)
        self._var_f_crew.set(ship3.f_crew)
        self._var_f_weap.set(ship3.f_weap)
        self._var_cargo.set(str(ship3.cargo))

        wi = ship1.cselwea - 0x10
        if not (0 <= wi < len(weapon_name)):
            wi = 0
        self._var_cselwea.set(weapon_name[wi])

        fi = ship2.ship_form
        if not (0 <= fi < len(form_name)):
            fi = 0
        self._var_form.set(form_name[fi])

        si = ship3.ship_select
        if 0 <= si < len(self._state.ship_name):
            self._var_ship_select.set(self._state.ship_name[si])
        else:
            self._var_ship_select.set("")

        self._var_ship_name.set(decode_kr(ship3.ship_name))

        self._set_form_state("normal")

    # ---------------- 콜백 ----------------

    def _on_select(self, _event: object = None) -> None:
        if self._loading or not self._slot_loaded:
            return
        sel = self._listbox.curselection()
        if not sel:
            return
        idx = int(sel[0])
        if idx == self._sel:
            return
        # 다른 함선 선택: 폼 dirty 면 변경분 폐기 (탭 내부 전환은 일상적).
        self._sel = idx
        self._loading = True
        try:
            self._load_fleet(idx)
        finally:
            self._loading = False
        self._set_dirty(False)

    # ---------------- 저장 로직 ----------------

    def _collect_and_save(self, sel: int) -> None:
        try:
            ccrew = int(self._var_ccrew.get())
            chull = int(self._var_chull.get())
            lhull = int(self._var_lhull.get())
            crudder = int(self._var_crudder.get())
            csail = int(self._var_csail.get())
            cnowea = int(self._var_cnowea.get())
            condition = int(self._var_condition.get())
            f_crew = int(self._var_f_crew.get())
            f_weap = int(self._var_f_weap.get())
        except (tk.TclError, ValueError):
            raise ValueError("나의 함대: 숫자 필드에 잘못된 값이 있습니다.")

        bounds = [
            ("현재 선원수", ccrew, 0, 0xFFFF),
            ("현재 내구력", chull, 0, 0xFF),
            ("최대 내구력", lhull, 0, 0xFF),
            ("현재 선회력", crudder, 0, 0xFF),
            ("현재 추진력", csail, 0, 0xFF),
            ("현재 포문수", cnowea, 0, 0xFF),
            ("현재 컨디션", condition, 0, 0xFF),
            ("최대 선원수", f_crew, 0, 0xFFFF),
            ("최대 포문수", f_weap, 0, 0xFF),
        ]
        for name, v, lo, hi in bounds:
            if not (lo <= v <= hi):
                raise ValueError(f"나의 함대: {name} 은 {lo}..{hi} 범위여야 합니다.")

        try:
            wi = list(weapon_name).index(self._var_cselwea.get())
        except ValueError:
            raise ValueError("나의 함대: 현재 무기를 선택하세요.")
        try:
            fi = list(form_name).index(self._var_form.get())
        except ValueError:
            raise ValueError("나의 함대: 선수상을 선택하세요.")
        try:
            si = list(self._state.ship_name).index(self._var_ship_select.get())
        except ValueError:
            raise ValueError("나의 함대: 함선종류를 선택하세요.")
        if not (0 <= si < 25):
            raise ValueError("나의 함대: 함선종류 인덱스가 범위를 벗어났습니다.")

        ship_name_raw = encode_kr_fixed(self._var_ship_name.get(), 14)

        assert self._ship1 is not None and self._ship2 is not None and self._ship3 is not None
        ship1 = Ship1(
            ccrew=ccrew, chull=chull, lhull=lhull,
            crudder=crudder, csail=csail, cnowea=cnowea,
            select=self._ship1.select, cselwea=(0x10 + wi) & 0xFF,
        )
        ship2 = Ship2(
            captin=self._ship2.captin, condition=condition, ship_form=fi,
            none=self._ship2.none,
        )
        ship3 = Ship3(
            ship_name=ship_name_raw, none=self._ship3.none,
            ship_select=si, bform=self._ship3.bform,
            f_weap=f_weap, f_crew=f_crew, cargo=self._ship3.cargo,
        )

        ship_type_changed = (si != self._ship3.ship_select)
        try:
            ship4 = load_ship4(self._state, si)
        except Exception as e:
            raise ValueError(f"나의 함대: 선박 템플릿 로드 실패: {e}")

        if ship_type_changed:
            try:
                ship5 = load_ship5(self._state, si)
            except Exception as e:
                raise ValueError(f"나의 함대: 선박 템플릿(Ship5) 로드 실패: {e}")
            ship3.bform = ((ship5.bform & 0xF0) | (ship3.bform & 0x0F)) & 0xFF

        # 클램프 체인
        if ship1.cselwea == 0x10:
            ship1.cnowea = 0
        max_crew = (ship4.lcrew & 0xFF) * 10
        if ship3.f_crew > max_crew:
            ship3.f_crew = max_crew
        if ship3.f_weap > ship4.lnowea:
            ship3.f_weap = ship4.lnowea
        if ship1.ccrew > ship3.f_crew:
            ship1.ccrew = ship3.f_crew
        if ship1.chull > ship1.lhull:
            ship1.chull = ship1.lhull
        if ship1.crudder > ship4.lrudder:
            ship1.crudder = ship4.lrudder
        if ship1.csail > ship4.lsail:
            ship1.csail = ship4.lsail
        if ship1.cnowea > ship3.f_weap:
            ship1.cnowea = ship3.f_weap

        cargo_recalc(ship3, ship4.capacity, ship3.f_weap, ship3.f_crew)

        try:
            save_fleet_entry(self._state, sel, ship1, ship2, ship3)
        except Exception as e:
            raise ValueError(f"나의 함대: 저장 실패: {e}")

        self._ship1, self._ship2, self._ship3, self._ship4 = ship1, ship2, ship3, ship4
        # 클램프 결과 다시 표시 (loading 가드 내부에서)
        prev_loading = self._loading
        self._loading = True
        try:
            self._var_ccrew.set(ship1.ccrew)
            self._var_chull.set(ship1.chull)
            self._var_crudder.set(ship1.crudder)
            self._var_csail.set(ship1.csail)
            self._var_cnowea.set(ship1.cnowea)
            self._var_f_crew.set(ship3.f_crew)
            self._var_f_weap.set(ship3.f_weap)
            self._var_cargo.set(str(ship3.cargo))
        finally:
            self._loading = prev_loading

    # ---------------- 위젯 활성화 ----------------

    def _set_form_state(self, st: str) -> None:
        combo_state = "readonly" if st == "normal" else "disabled"
        widgets = (
            self._sp_ccrew, self._sp_chull, self._sp_lhull, self._sp_crudder,
            self._sp_csail, self._sp_cnowea, self._sp_condition,
            self._sp_f_crew, self._sp_f_weap, self._en_ship_name,
        )
        for w in widgets:
            try:
                w.configure(state=st)
            except tk.TclError:
                pass
        for cb in (self._cb_cselwea, self._cb_form, self._cb_ship_select):
            try:
                cb.configure(state=combo_state)
            except tk.TclError:
                pass


# ===========================================================================
# 2) 원래 함선 정보 (오리지널 템플릿) 편집 — Ship4 + Ship5 + record kogyo/lhull
# ===========================================================================


class _OrgShipEditor(ttk.Frame):
    """슬롯 내 25종 함선 템플릿 편집.

    편집 대상:
      - Ship5 (슬롯 내) : 배이름
      - Ship4 (슬롯 내) : lsail / lrudder / capacity / lcrew / dcrew / lnowea
      - record (슬롯 내, analysis_G + analysis_H):
          +0  kogyo (×10 표시),  +1  lhull (u8 직접),
          +9  ship_class (분류 0..5, 보기 전용),
          +10 price_stored (u16 LE × 10 표시).

    record 는 Ship4 와 동일 영역 (record +2 ~ +9 일부) 을 공유하면서
    [kogyo, lhull, ship_class, price] 를 추가로 노출한다.
    """

    def __init__(self, master: tk.Misc, state: EditorState) -> None:
        super().__init__(master, padding=8)
        self._state = state
        self._slot_loaded = False
        self._sel: Optional[int] = None
        self._loading = False
        self._dirty = False
        self._dirty_listeners: list[Callable[[], None]] = []

        # 위젯 변수 (Ship4 / Ship5 in slot + record kogyo/lhull/price/class)
        self._var_name = tk.StringVar()
        self._var_lsail = tk.IntVar(value=0)
        self._var_lrudder = tk.IntVar(value=0)
        self._var_kogyo = tk.IntVar(value=0)   # 표시값 (저장값 × 10)
        self._var_lhull = tk.IntVar(value=0)   # u8 직접
        self._var_capacity = tk.IntVar(value=0)
        self._var_lcrew = tk.IntVar(value=0)
        self._var_dcrew = tk.IntVar(value=0)
        self._var_lnowea = tk.IntVar(value=0)
        # 선박 분류 (record +9, read-only) — 표시 전용
        self._var_ship_class = tk.IntVar(value=0)
        # 선박 가격 (record +10..+11, ×10 표시값)
        self._var_price = tk.IntVar(value=0)

        # 디스크에서 마지막으로 읽은 record 값 (commit 시 변경 비교용)
        self._loaded_kogyo: int = 0
        self._loaded_lhull: int = 0
        self._loaded_ship_class: int = 0
        self._loaded_price: int = 0  # 표시값 (×10 적용된)

        self._ship4: Optional[Ship4] = None
        self._ship5: Optional[Ship5] = None

        self._build()
        self._set_form_state("disabled")
        self._install_dirty_traces()

    # ---------------- 빌드 ----------------

    def _build(self) -> None:
        self._hint = ttk.Label(self, text="(슬롯을 먼저 선택하세요)", foreground="#888")
        self._hint.grid(row=0, column=0, columnspan=2, pady=8)

        # 좌: 25종 목록
        left = ttk.LabelFrame(self, text="함선 종류 (25)", padding=6)
        left.grid(row=1, column=0, sticky="nsw", padx=(0, 6))
        self._listbox = tk.Listbox(left, height=18, exportselection=False, width=22)
        self._listbox.grid(row=0, column=0, sticky="nsew")
        sb = ttk.Scrollbar(left, orient="vertical", command=self._listbox.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self._listbox.configure(yscrollcommand=sb.set)
        self._listbox.bind("<<ListboxSelect>>", self._on_select)

        # 우: 폼
        right = ttk.LabelFrame(self, text="원래 함선 정보", padding=8)
        right.grid(row=1, column=1, sticky="nsew")

        r = 0
        # 1) 배이름
        ttk.Label(right, text="배이름").grid(row=r, column=0, sticky="w", padx=4, pady=4)
        self._en_name = ttk.Entry(right, textvariable=self._var_name, width=24)
        self._en_name.grid(row=r, column=1, sticky="w", padx=4, pady=4); r += 1

        # 2) 추진력 / 3) 선회력
        self._sp_lsail = self._add_spinbox(right, r, "추진력 (lsail)", self._var_lsail, 0, 255); r += 1
        self._sp_lrudder = self._add_spinbox(right, r, "선회력 (lrudder)", self._var_lrudder, 0, 255); r += 1

        # 4) 등장공업치 (kogyo) — record +0. 표시값 = 저장값 × 10.
        self._sp_kogyo = self._add_spinbox(right, r, "등장공업치", self._var_kogyo, 0, 2550); r += 1
        # 5) 최대 내구도 (lhull) — record +1. u8 직접.
        self._sp_lhull = self._add_spinbox(right, r, "최대 내구도", self._var_lhull, 0, 255); r += 1

        # 6) 최대 적재량
        self._sp_capacity = self._add_spinbox(right, r, "최대 적재량", self._var_capacity, 0, 65535); r += 1
        # 7) 최대 선원수 (lcrew × 10)
        self._sp_lcrew = self._add_spinbox(right, r, "최대 선원수", self._var_lcrew, 0, 2550); r += 1
        # 8) 필요 선원수 (dcrew)
        self._sp_dcrew = self._add_spinbox(right, r, "필요 선원수", self._var_dcrew, 0, 255); r += 1
        # 9) 최대 포문수 (lnowea)
        self._sp_lnowea = self._add_spinbox(right, r, "최대 포문수", self._var_lnowea, 0, 255); r += 1

        # 10) 선박 분류 (record +9) — 보기 전용. 다음 버전에서 편집 가능.
        ttk.Label(right, text="선박 분류 (0..5, 보기 전용)").grid(
            row=r, column=0, sticky="w", padx=4, pady=4
        )
        self._sp_ship_class = ttk.Spinbox(
            right, from_=0, to=255,
            textvariable=self._var_ship_class, width=10, state="disabled",
        )
        self._sp_ship_class.grid(row=r, column=1, sticky="w", padx=4, pady=4); r += 1

        # 11) 선박 가격 (record +10..+11, u16 LE × 10). 0..655,350, 10 단위 step.
        self._sp_price = self._add_price_spinbox(
            right, r, "선박 가격", self._var_price, 0, PRICE_MAX_DISPLAY, PRICE_SCALE,
        ); r += 1

        self.columnconfigure(1, weight=1)

    def _add_price_spinbox(
        self,
        parent: tk.Misc,
        row: int,
        label: str,
        var: tk.IntVar,
        lo: int,
        hi: int,
        increment: int,
    ) -> ttk.Spinbox:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=4, pady=4)
        sp = ttk.Spinbox(
            parent, from_=lo, to=hi, increment=increment,
            textvariable=var, width=12,
        )
        sp.grid(row=row, column=1, sticky="w", padx=4, pady=4)
        return sp

    def _add_spinbox(
        self, parent: tk.Misc, row: int, label: str, var: tk.IntVar, lo: int, hi: int,
    ) -> ttk.Spinbox:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=4, pady=4)
        sp = ttk.Spinbox(parent, from_=lo, to=hi, textvariable=var, width=10)
        sp.grid(row=row, column=1, sticky="w", padx=4, pady=4)
        return sp

    # ---------------- dirty ----------------

    def _install_dirty_traces(self) -> None:
        for v in (
            self._var_lsail, self._var_lrudder,
            self._var_kogyo, self._var_lhull,
            self._var_capacity,
            self._var_lcrew, self._var_dcrew, self._var_lnowea,
            self._var_price,  # 분류는 보기 전용이므로 dirty 추적 안 함
        ):
            v.trace_add("write", self._on_var_write)
        self._var_name.trace_add("write", self._on_var_write)

    def _on_var_write(self, *_a: object) -> None:
        if self._loading:
            return
        if not self._slot_loaded or self._sel is None:
            return
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

    def is_dirty(self) -> bool:
        return self._dirty and self._slot_loaded and self._sel is not None

    def add_dirty_listener(self, callback: Callable[[], None]) -> None:
        self._dirty_listeners.append(callback)

    # ---------------- reload / reset ----------------

    def reload(self) -> None:
        self._loading = True
        try:
            self._slot_loaded = True
            self._hint.grid_remove()
            self._refresh_listbox()
            self._listbox.selection_clear(0, "end")
            self._listbox.selection_set(0)
            self._listbox.activate(0)
            self._sel = 0
            self._load_template(0)
        finally:
            self._loading = False
        self._set_dirty(False)

    def reset(self) -> None:
        self._loading = True
        try:
            self._slot_loaded = False
            self._sel = None
            self._ship4 = self._ship5 = None
            self._listbox.delete(0, "end")
            self._set_form_state("disabled")
            self._hint.grid()
        finally:
            self._loading = False
        self._set_dirty(False)

    def revert(self) -> None:
        self.reload()

    def commit(self) -> None:
        if not self._slot_loaded or self._sel is None:
            return
        if not self._dirty:
            return
        if self._ship4 is None or self._ship5 is None:
            return
        self._collect_and_save(self._sel)
        self._loading = True
        try:
            self._refresh_listbox()
            self._listbox.selection_clear(0, "end")
            self._listbox.selection_set(self._sel)
            self._listbox.activate(self._sel)
        finally:
            self._loading = False
        self._set_dirty(False)

    def _refresh_listbox(self) -> None:
        self._listbox.delete(0, "end")
        for i, name in enumerate(self._state.ship_name):
            self._listbox.insert("end", f"{i + 1:2d}. {name}")

    # ---------------- 폼 채우기 ----------------

    def _load_template(self, sel: int) -> None:
        try:
            ship4 = load_ship4(self._state, sel)
            ship5 = load_ship5(self._state, sel)
        except Exception as e:
            messagebox.showerror("템플릿 로드 실패", str(e))
            return

        self._ship4 = ship4
        self._ship5 = ship5

        # record (analysis_G + analysis_H):
        #   +0 kogyo (×10 표시), +1 lhull (u8),
        #   +9 ship_class (u8 분류 0..5),  +10..11 price_stored (u16 LE × 10).
        try:
            kogyo_stored = load_record_kogyo(self._state, sel)
            lhull_val = load_record_lhull(self._state, sel)
            ship_class = load_record_ship_class(self._state, sel)
            price_disp = load_record_price(self._state, sel)
        except Exception as e:
            messagebox.showerror("템플릿 로드 실패", f"record 읽기 실패: {e}")
            return
        self._loaded_kogyo = kogyo_stored
        self._loaded_lhull = lhull_val
        self._loaded_ship_class = ship_class
        self._loaded_price = price_disp

        self._var_name.set(decode_kr(ship5.name))
        self._var_lsail.set(ship4.lsail)
        self._var_lrudder.set(ship4.lrudder)
        self._var_kogyo.set(kogyo_stored * 10)
        self._var_lhull.set(lhull_val)
        self._var_capacity.set(ship4.capacity)
        self._var_lcrew.set((ship4.lcrew & 0xFF) * 10)
        self._var_dcrew.set(ship4.dcrew)
        self._var_lnowea.set(ship4.lnowea)
        self._var_ship_class.set(ship_class)
        self._var_price.set(price_disp)

        self._set_form_state("normal")

    # ---------------- 콜백 ----------------

    def _on_select(self, _event: object = None) -> None:
        if self._loading or not self._slot_loaded:
            return
        sel = self._listbox.curselection()
        if not sel:
            return
        idx = int(sel[0])
        if idx == self._sel:
            return
        self._sel = idx
        self._loading = True
        try:
            self._load_template(idx)
        finally:
            self._loading = False
        self._set_dirty(False)

    # ---------------- 저장 ----------------

    def _collect_and_save(self, sel: int) -> None:
        try:
            lsail = int(self._var_lsail.get())
            lrudder = int(self._var_lrudder.get())
            kogyo_disp = int(self._var_kogyo.get())
            lhull_val = int(self._var_lhull.get())
            capacity = int(self._var_capacity.get())
            lcrew_x10 = int(self._var_lcrew.get())
            dcrew = int(self._var_dcrew.get())
            lnowea = int(self._var_lnowea.get())
            price_disp = int(self._var_price.get())
        except (tk.TclError, ValueError):
            raise ValueError("원래 함선 정보: 숫자 필드에 잘못된 값이 있습니다.")

        bounds = [
            ("추진력", lsail, 0, 0xFF),
            ("선회력", lrudder, 0, 0xFF),
            ("등장공업치", kogyo_disp, 0, 2550),
            ("최대 내구도", lhull_val, 0, 0xFF),
            ("최대 적재량", capacity, 0, 0xFFFF),
            ("최대 선원수", lcrew_x10, 0, 2550),
            ("필요 선원수", dcrew, 0, 0xFF),
            ("최대 포문수", lnowea, 0, 0xFF),
            ("선박 가격", price_disp, 0, PRICE_MAX_DISPLAY),
        ]
        for name, v, lo, hi in bounds:
            if not (lo <= v <= hi):
                raise ValueError(f"원래 함선 정보: {name} 은 {lo}..{hi} 범위여야 합니다.")
        if price_disp % PRICE_SCALE != 0:
            raise ValueError(
                f"원래 함선 정보: 선박 가격은 {PRICE_SCALE} 의 배수여야 합니다."
            )

        old4 = self._ship4
        old5 = self._ship5
        assert old4 is not None and old5 is not None

        new_lcrew = lcrew_x10 // 10

        new_ship4 = Ship4(
            lrudder=lrudder, lsail=lsail,
            lcrew=new_lcrew, dcrew=dcrew,
            capacity=capacity, lnowea=lnowea,
            none=old4.none,
        )

        name_raw = encode_kr_fixed(self._var_name.get(), 18)
        new_ship5 = Ship5(
            name=name_raw, sform=old5.sform, bform=old5.bform, none=old5.none,
        )

        # 변경 플래그 + 클램프 전파에 사용할 값
        new_lcrew_max = (new_lcrew & 0xFF) * 10
        changed_lrudder = (new_ship4.lrudder != old4.lrudder)
        changed_lsail = (new_ship4.lsail != old4.lsail)
        changed_lcrew = (new_ship4.lcrew != old4.lcrew)
        changed_capacity = (new_ship4.capacity != old4.capacity)
        changed_lnowea = (new_ship4.lnowea != old4.lnowea)

        try:
            save_ship4(self._state, sel, new_ship4)
            save_ship5(self._state, sel, new_ship5)
        except Exception as e:
            raise ValueError(f"원래 함선 정보: 저장 실패: {e}")

        # record (analysis_G): +0 kogyo (×10 표시→//10 저장), +1 lhull.
        # 변경된 byte 만 부분 갱신 (Ship4 와는 별개 영역인 +0/+1 만 건드림).
        new_kogyo_stored = (kogyo_disp // 10) & 0xFF
        if new_kogyo_stored != self._loaded_kogyo:
            try:
                save_record_kogyo(self._state, sel, new_kogyo_stored)
            except Exception as e:
                raise ValueError(f"원래 함선 정보: 등장공업치 저장 실패: {e}")
            self._loaded_kogyo = new_kogyo_stored
        if (lhull_val & 0xFF) != self._loaded_lhull:
            try:
                save_record_lhull(self._state, sel, lhull_val)
            except Exception as e:
                raise ValueError(f"원래 함선 정보: 최대 내구도 저장 실패: {e}")
            self._loaded_lhull = lhull_val & 0xFF

        # 선박 가격 (record +10..+11). 분류 (+9) 는 보기 전용 — 저장하지 않음.
        if price_disp != self._loaded_price:
            try:
                save_record_price(self._state, sel, price_disp)
            except Exception as e:
                raise ValueError(f"원래 함선 정보: 선박 가격 저장 실패: {e}")
            self._loaded_price = price_disp

        new_name_str = decode_kr(new_ship5.name)
        if 0 <= sel < len(self._state.ship_name):
            self._state.ship_name[sel] = new_name_str

        # 영웅 함대 클램프 전파
        any_lim_changed = (
            changed_lrudder or changed_lsail or changed_lcrew
            or changed_capacity or changed_lnowea
        )
        if any_lim_changed and self._state.ship_num > 0:
            for i in range(self._state.ship_num):
                try:
                    s1, s2, s3 = load_fleet_entry(self._state, i)
                except Exception:
                    continue
                if s3.ship_select != sel:
                    continue
                touched = False
                if changed_lrudder and s1.crudder > new_ship4.lrudder:
                    s1.crudder = new_ship4.lrudder
                    touched = True
                if changed_lsail and s1.csail > new_ship4.lsail:
                    s1.csail = new_ship4.lsail
                    touched = True
                if changed_lcrew and s3.f_crew > new_lcrew_max:
                    s3.f_crew = new_lcrew_max
                    if s1.ccrew > s3.f_crew:
                        s1.ccrew = s3.f_crew
                    touched = True
                if changed_lnowea and s3.f_weap > new_ship4.lnowea:
                    s3.f_weap = new_ship4.lnowea
                    if s1.cnowea > s3.f_weap:
                        s1.cnowea = s3.f_weap
                    touched = True
                if changed_capacity or touched:
                    cargo_recalc(s3, new_ship4.capacity, s3.f_weap, s3.f_crew)
                    touched = True
                if touched:
                    try:
                        save_fleet_entry(self._state, i, s1, s2, s3)
                    except Exception:
                        pass

        self._ship4 = new_ship4
        self._ship5 = new_ship5

        # 사용자가 //10 클램프 (예: 105 → 100) 후 표시값 (1000) 으로 다시 보이도록
        # 폼을 갱신. loading 가드 내에서 수행해 dirty 재발화 방지.
        prev_loading = self._loading
        self._loading = True
        try:
            self._var_kogyo.set(self._loaded_kogyo * 10)
            self._var_lhull.set(self._loaded_lhull)
            self._var_price.set(self._loaded_price)
        finally:
            self._loading = prev_loading

    # ---------------- 위젯 활성화 ----------------

    def _set_form_state(self, st: str) -> None:
        widgets = (
            self._en_name, self._sp_lsail, self._sp_lrudder,
            self._sp_kogyo, self._sp_lhull,
            self._sp_capacity, self._sp_lcrew, self._sp_dcrew, self._sp_lnowea,
            self._sp_price,
        )
        for w in widgets:
            try:
                w.configure(state=st)
            except tk.TclError:
                pass
        # 선박 분류 (read-only) — 항상 disabled 유지.
        try:
            self._sp_ship_class.configure(state="disabled")
        except tk.TclError:
            pass
