"""선박 편집 탭.

내부 sub-Notebook 으로 두 영역 분리:
1) 영웅 함대 편집  (HORIEDIT.C hero_ship_edit 대응)
2) 함선 종류(오리지널 템플릿) 편집  (HORIEDIT.C org_ship_edit 대응)
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Optional

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

        self._notebook = ttk.Notebook(self)
        self._notebook.pack(fill="both", expand=True)

        self._fleet = _FleetEditor(self._notebook, state)
        self._org = _OrgShipEditor(self._notebook, state)

        self._notebook.add(self._fleet, text="영웅 함대")
        self._notebook.add(self._org, text="함선 종류")

    # ---------------- 외부 인터페이스 ----------------

    def reload(self) -> None:
        self._slot_loaded = True
        self._fleet.reload()
        self._org.reload()

    def reset(self) -> None:
        self._slot_loaded = False
        self._fleet.reset()
        self._org.reset()


# ===========================================================================
# 1) 영웅 함대 편집
# ===========================================================================


class _FleetEditor(ttk.Frame):
    """현재 c_hero 가 보유한 함대(0..ship_num-1) 편집."""

    def __init__(self, master: tk.Misc, state: EditorState) -> None:
        super().__init__(master, padding=8)
        self._state = state
        self._slot_loaded = False
        self._sel: Optional[int] = None  # 현재 선택 fleet 인덱스 (0..ship_num-1)

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

        # 현재 로드된 구조체 (저장 시 미사용 필드 보존용)
        self._ship1: Optional[Ship1] = None
        self._ship2: Optional[Ship2] = None
        self._ship3: Optional[Ship3] = None
        self._ship4: Optional[Ship4] = None  # 현재 ship3.ship_select 의 템플릿

        self._build()
        self._set_form_state("disabled")

    # ---------------- 빌드 ----------------

    def _build(self) -> None:
        # 슬롯 미선택 안내
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
        self._sp_ccrew = self._add_spinbox(right, r, "현재 승무원", self._var_ccrew, 0, 65535); r += 1
        self._sp_chull = self._add_spinbox(right, r, "현재 선체", self._var_chull, 0, 255); r += 1
        self._sp_lhull = self._add_spinbox(right, r, "최대 선체", self._var_lhull, 0, 255); r += 1
        self._sp_crudder = self._add_spinbox(right, r, "현재 회전력", self._var_crudder, 0, 255); r += 1
        self._sp_csail = self._add_spinbox(right, r, "현재 돛", self._var_csail, 0, 255); r += 1
        self._sp_cnowea = self._add_spinbox(right, r, "현재 무기수", self._var_cnowea, 0, 255); r += 1
        self._sp_condition = self._add_spinbox(right, r, "현재 컨디션", self._var_condition, 0, 255); r += 1

        # 카르고 (읽기 전용)
        ttk.Label(right, text="카르고").grid(row=r, column=0, sticky="w", padx=4, pady=4)
        ttk.Label(right, textvariable=self._var_cargo).grid(row=r, column=1, sticky="w", padx=4, pady=4)
        r += 1

        self._sp_f_crew = self._add_spinbox(right, r, "최대 적재 승무원", self._var_f_crew, 0, 65535); r += 1
        self._sp_f_weap = self._add_spinbox(right, r, "최대 적재 무기수", self._var_f_weap, 0, 255); r += 1

        # 무기 콤보
        ttk.Label(right, text="현재 무기").grid(row=r, column=0, sticky="w", padx=4, pady=4)
        self._cb_cselwea = ttk.Combobox(
            right, textvariable=self._var_cselwea, values=list(weapon_name),
            state="readonly", width=14,
        )
        self._cb_cselwea.grid(row=r, column=1, sticky="w", padx=4, pady=4)
        r += 1

        # 진형 콤보
        ttk.Label(right, text="현재 진형").grid(row=r, column=0, sticky="w", padx=4, pady=4)
        self._cb_form = ttk.Combobox(
            right, textvariable=self._var_form, values=list(form_name),
            state="readonly", width=14,
        )
        self._cb_form.grid(row=r, column=1, sticky="w", padx=4, pady=4)
        r += 1

        # 함선 종류 콤보 (state.ship_name 25개)
        ttk.Label(right, text="현재 함선").grid(row=r, column=0, sticky="w", padx=4, pady=4)
        self._cb_ship_select = ttk.Combobox(
            right, textvariable=self._var_ship_select, values=[],
            state="readonly", width=22,
        )
        self._cb_ship_select.grid(row=r, column=1, sticky="w", padx=4, pady=4)
        r += 1

        # 함선 이름 (Entry)
        ttk.Label(right, text="함선 이름").grid(row=r, column=0, sticky="w", padx=4, pady=4)
        self._en_ship_name = ttk.Entry(right, textvariable=self._var_ship_name, width=22)
        self._en_ship_name.grid(row=r, column=1, sticky="w", padx=4, pady=4)
        r += 1

        # 버튼
        btns = ttk.Frame(self)
        btns.grid(row=2, column=0, columnspan=2, sticky="e", pady=(8, 0))
        self._btn_reload = ttk.Button(btns, text="다시 불러오기", command=self._on_reload_clicked)
        self._btn_reload.grid(row=0, column=0, padx=4)
        self._btn_save = ttk.Button(btns, text="저장", command=self._on_save_clicked)
        self._btn_save.grid(row=0, column=1, padx=4)

        self.columnconfigure(1, weight=1)

    def _add_spinbox(
        self, parent: tk.Misc, row: int, label: str, var: tk.IntVar, lo: int, hi: int,
    ) -> ttk.Spinbox:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=4, pady=4)
        sp = ttk.Spinbox(parent, from_=lo, to=hi, textvariable=var, width=10)
        sp.grid(row=row, column=1, sticky="w", padx=4, pady=4)
        return sp

    # ---------------- reload / reset ----------------

    def reload(self) -> None:
        """슬롯 변경 시 호출. 함대 목록 갱신."""
        self._slot_loaded = True
        self._hint.grid_remove()

        # 함선 종류 콤보 채우기 (슬롯별 ship_name 캐시 반영)
        self._cb_ship_select.configure(values=list(self._state.ship_name))

        self._refresh_listbox()

        if self._state.ship_num == 0:
            # 보유 함선 없음
            self._listbox.configure(state="disabled")
            self._set_form_state("disabled")
            self._show_no_fleet_label()
            self._sel = None
            self._ship1 = self._ship2 = self._ship3 = self._ship4 = None
            return

        self._hide_no_fleet_label()
        self._listbox.configure(state="normal")
        # 첫 항목 자동 선택
        self._listbox.selection_clear(0, "end")
        self._listbox.selection_set(0)
        self._listbox.activate(0)
        self._sel = 0
        self._load_fleet(0)

    def reset(self) -> None:
        self._slot_loaded = False
        self._sel = None
        self._ship1 = self._ship2 = self._ship3 = self._ship4 = None
        self._listbox.delete(0, "end")
        self._listbox.configure(state="normal")
        self._hide_no_fleet_label()
        self._set_form_state("disabled")
        self._hint.grid()

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
            # ship1 참조 회피용 (linter)
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

        # 무기 콤보: cselwea - 0x10 = weapon_name 인덱스
        wi = ship1.cselwea - 0x10
        if not (0 <= wi < len(weapon_name)):
            wi = 0
        self._var_cselwea.set(weapon_name[wi])

        # 진형
        fi = ship2.ship_form
        if not (0 <= fi < len(form_name)):
            fi = 0
        self._var_form.set(form_name[fi])

        # 함선 종류
        si = ship3.ship_select
        if 0 <= si < len(self._state.ship_name):
            self._var_ship_select.set(self._state.ship_name[si])
        else:
            self._var_ship_select.set("")

        # 함선 이름
        self._var_ship_name.set(decode_kr(ship3.ship_name))

        self._set_form_state("normal")

    # ---------------- 콜백 ----------------

    def _on_select(self, _event: object = None) -> None:
        if not self._slot_loaded:
            return
        sel = self._listbox.curselection()
        if not sel:
            return
        idx = int(sel[0])
        if idx == self._sel:
            return
        self._sel = idx
        self._load_fleet(idx)

    def _on_reload_clicked(self) -> None:
        if not self._slot_loaded:
            return
        # 목록도 새로 그린다 (외부 변경 가능성).
        cur = self._sel if self._sel is not None else 0
        self._refresh_listbox()
        if self._state.ship_num == 0:
            self._sel = None
            self._set_form_state("disabled")
            return
        if cur >= self._state.ship_num:
            cur = self._state.ship_num - 1
        self._listbox.selection_clear(0, "end")
        self._listbox.selection_set(cur)
        self._listbox.activate(cur)
        self._sel = cur
        self._load_fleet(cur)

    def _on_save_clicked(self) -> None:
        if not self._slot_loaded or self._sel is None:
            return
        if self._ship1 is None or self._ship2 is None or self._ship3 is None or self._ship4 is None:
            return
        ok = self._collect_and_save(self._sel)
        if not ok:
            return
        try:
            self._state.fp.flush()
        except Exception:
            pass
        # 목록 갱신 (이름/함종 반영)
        self._refresh_listbox()
        self._listbox.selection_clear(0, "end")
        self._listbox.selection_set(self._sel)
        self._listbox.activate(self._sel)
        messagebox.showinfo("저장 완료", "함대 데이터를 저장했습니다.")

    # ---------------- 저장 로직 ----------------

    def _collect_and_save(self, sel: int) -> bool:
        # 위젯 값 수집
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
            messagebox.showerror("입력 오류", "숫자 필드에 잘못된 값이 있습니다.")
            return False

        # 범위 검사 (저장 형식의 절대 한계만)
        bounds = [
            ("현재 승무원", ccrew, 0, 0xFFFF),
            ("현재 선체", chull, 0, 0xFF),
            ("최대 선체", lhull, 0, 0xFF),
            ("현재 회전력", crudder, 0, 0xFF),
            ("현재 돛", csail, 0, 0xFF),
            ("현재 무기수", cnowea, 0, 0xFF),
            ("현재 컨디션", condition, 0, 0xFF),
            ("최대 적재 승무원", f_crew, 0, 0xFFFF),
            ("최대 적재 무기수", f_weap, 0, 0xFF),
        ]
        for name, v, lo, hi in bounds:
            if not (lo <= v <= hi):
                messagebox.showerror(
                    "입력 오류", f"{name} 은 {lo}..{hi} 범위여야 합니다."
                )
                return False

        # 콤보 인덱스
        try:
            wi = list(weapon_name).index(self._var_cselwea.get())
        except ValueError:
            messagebox.showerror("입력 오류", "현재 무기를 선택하세요.")
            return False
        try:
            fi = list(form_name).index(self._var_form.get())
        except ValueError:
            messagebox.showerror("입력 오류", "현재 진형을 선택하세요.")
            return False
        try:
            si = list(self._state.ship_name).index(self._var_ship_select.get())
        except ValueError:
            messagebox.showerror("입력 오류", "현재 함선(종류)을 선택하세요.")
            return False
        if not (0 <= si < 25):
            messagebox.showerror("입력 오류", "함선 종류 인덱스가 범위를 벗어났습니다.")
            return False

        # 함선 이름 (14 byte 고정)
        ship_name_raw = encode_kr_fixed(self._var_ship_name.get(), 14)

        # 현재 메모리상의 ship1/2/3 을 복사해 수정 (none[] 필드 보존)
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

        # 함선 종류 변경 감지 → ship4 / ship5 다시 로드 + bform 합성
        ship_type_changed = (si != self._ship3.ship_select)
        try:
            ship4 = load_ship4(self._state, si)
        except Exception as e:
            messagebox.showerror("선박 템플릿 로드 실패", str(e))
            return False

        if ship_type_changed:
            try:
                ship5 = load_ship5(self._state, si)
            except Exception as e:
                messagebox.showerror("선박 템플릿(Ship5) 로드 실패", str(e))
                return False
            # bform 비트 합성: 상위 4비트=새 함선, 하위 4비트=기존
            ship3.bform = ((ship5.bform & 0xF0) | (ship3.bform & 0x0F)) & 0xFF

        # 클램프 체인 (case 1~12 의 모든 클램프 일괄 적용)
        # cnowea: cselwea==0x10 이면 0
        if ship1.cselwea == 0x10:
            ship1.cnowea = 0
        # f_crew ≤ ship4.lcrew*10
        max_crew = (ship4.lcrew & 0xFF) * 10
        if ship3.f_crew > max_crew:
            ship3.f_crew = max_crew
        # f_weap ≤ ship4.lnowea
        if ship3.f_weap > ship4.lnowea:
            ship3.f_weap = ship4.lnowea
        # ccrew ≤ f_crew
        if ship1.ccrew > ship3.f_crew:
            ship1.ccrew = ship3.f_crew
        # chull ≤ lhull
        if ship1.chull > ship1.lhull:
            ship1.chull = ship1.lhull
        # crudder ≤ ship4.lrudder
        if ship1.crudder > ship4.lrudder:
            ship1.crudder = ship4.lrudder
        # csail ≤ ship4.lsail
        if ship1.csail > ship4.lsail:
            ship1.csail = ship4.lsail
        # cnowea ≤ f_weap
        if ship1.cnowea > ship3.f_weap:
            ship1.cnowea = ship3.f_weap

        # cargo 재계산
        cargo_recalc(ship3, ship4.capacity, ship3.f_weap, ship3.f_crew)

        # 디스크 기록
        try:
            save_fleet_entry(self._state, sel, ship1, ship2, ship3)
        except Exception as e:
            messagebox.showerror("저장 실패", str(e))
            return False

        # 메모리 갱신
        self._ship1, self._ship2, self._ship3, self._ship4 = ship1, ship2, ship3, ship4
        # 폼 클램프 결과 다시 표시
        self._var_ccrew.set(ship1.ccrew)
        self._var_chull.set(ship1.chull)
        self._var_crudder.set(ship1.crudder)
        self._var_csail.set(ship1.csail)
        self._var_cnowea.set(ship1.cnowea)
        self._var_f_crew.set(ship3.f_crew)
        self._var_f_weap.set(ship3.f_weap)
        self._var_cargo.set(str(ship3.cargo))
        return True

    # ---------------- 위젯 활성화 ----------------

    def _set_form_state(self, st: str) -> None:
        combo_state = "readonly" if st == "normal" else "disabled"
        widgets = (
            self._sp_ccrew, self._sp_chull, self._sp_lhull, self._sp_crudder,
            self._sp_csail, self._sp_cnowea, self._sp_condition,
            self._sp_f_crew, self._sp_f_weap, self._en_ship_name,
            self._btn_reload, self._btn_save,
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
# 2) 함선 종류(오리지널 템플릿) 편집
# ===========================================================================


class _OrgShipEditor(ttk.Frame):
    """슬롯 내 25종 함선 템플릿(Ship4 + Ship5) 편집."""

    def __init__(self, master: tk.Misc, state: EditorState) -> None:
        super().__init__(master, padding=8)
        self._state = state
        self._slot_loaded = False
        self._sel: Optional[int] = None  # 현재 선택 함선 종류 (0..24)

        self._var_name = tk.StringVar()
        self._var_lsail = tk.IntVar(value=0)
        self._var_lrudder = tk.IntVar(value=0)
        self._var_capacity = tk.IntVar(value=0)
        self._var_lcrew = tk.IntVar(value=0)   # 표시는 *10 (실제 최대치)
        self._var_dcrew = tk.IntVar(value=0)
        self._var_lnowea = tk.IntVar(value=0)

        self._ship4: Optional[Ship4] = None
        self._ship5: Optional[Ship5] = None

        self._build()
        self._set_form_state("disabled")

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
        right = ttk.LabelFrame(self, text="템플릿 정보", padding=8)
        right.grid(row=1, column=1, sticky="nsew")

        r = 0
        ttk.Label(right, text="배이름").grid(row=r, column=0, sticky="w", padx=4, pady=4)
        self._en_name = ttk.Entry(right, textvariable=self._var_name, width=24)
        self._en_name.grid(row=r, column=1, sticky="w", padx=4, pady=4); r += 1

        self._sp_lsail = self._add_spinbox(right, r, "추진력 (최대 돛)", self._var_lsail, 0, 255); r += 1
        self._sp_lrudder = self._add_spinbox(right, r, "선회력 (최대 회전력)", self._var_lrudder, 0, 255); r += 1
        self._sp_capacity = self._add_spinbox(right, r, "최대 적재량", self._var_capacity, 0, 65535); r += 1
        self._sp_lcrew = self._add_spinbox(right, r, "최대 승무원", self._var_lcrew, 0, 2550); r += 1
        self._sp_dcrew = self._add_spinbox(right, r, "필요 승무원", self._var_dcrew, 0, 255); r += 1
        self._sp_lnowea = self._add_spinbox(right, r, "최대 무기수", self._var_lnowea, 0, 255); r += 1

        # 버튼
        btns = ttk.Frame(self)
        btns.grid(row=2, column=0, columnspan=2, sticky="e", pady=(8, 0))
        self._btn_reload = ttk.Button(btns, text="다시 불러오기", command=self._on_reload_clicked)
        self._btn_reload.grid(row=0, column=0, padx=4)
        self._btn_save = ttk.Button(btns, text="저장", command=self._on_save_clicked)
        self._btn_save.grid(row=0, column=1, padx=4)

        self.columnconfigure(1, weight=1)

    def _add_spinbox(
        self, parent: tk.Misc, row: int, label: str, var: tk.IntVar, lo: int, hi: int,
    ) -> ttk.Spinbox:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=4, pady=4)
        sp = ttk.Spinbox(parent, from_=lo, to=hi, textvariable=var, width=10)
        sp.grid(row=row, column=1, sticky="w", padx=4, pady=4)
        return sp

    # ---------------- reload / reset ----------------

    def reload(self) -> None:
        self._slot_loaded = True
        self._hint.grid_remove()
        self._refresh_listbox()
        # 첫 항목 선택
        self._listbox.selection_clear(0, "end")
        self._listbox.selection_set(0)
        self._listbox.activate(0)
        self._sel = 0
        self._load_template(0)

    def reset(self) -> None:
        self._slot_loaded = False
        self._sel = None
        self._ship4 = self._ship5 = None
        self._listbox.delete(0, "end")
        self._set_form_state("disabled")
        self._hint.grid()

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

        self._var_name.set(decode_kr(ship5.name))
        self._var_lsail.set(ship4.lsail)
        self._var_lrudder.set(ship4.lrudder)
        self._var_capacity.set(ship4.capacity)
        self._var_lcrew.set((ship4.lcrew & 0xFF) * 10)
        self._var_dcrew.set(ship4.dcrew)
        self._var_lnowea.set(ship4.lnowea)

        self._set_form_state("normal")

    # ---------------- 콜백 ----------------

    def _on_select(self, _event: object = None) -> None:
        if not self._slot_loaded:
            return
        sel = self._listbox.curselection()
        if not sel:
            return
        idx = int(sel[0])
        if idx == self._sel:
            return
        self._sel = idx
        self._load_template(idx)

    def _on_reload_clicked(self) -> None:
        if not self._slot_loaded or self._sel is None:
            return
        self._load_template(self._sel)

    def _on_save_clicked(self) -> None:
        if not self._slot_loaded or self._sel is None:
            return
        if self._ship4 is None or self._ship5 is None:
            return
        if self._collect_and_save(self._sel):
            try:
                self._state.fp.flush()
            except Exception:
                pass
            # 목록 라벨 갱신 (이름 변경 반영)
            self._refresh_listbox()
            self._listbox.selection_clear(0, "end")
            self._listbox.selection_set(self._sel)
            self._listbox.activate(self._sel)
            messagebox.showinfo("저장 완료", "함선 템플릿을 저장했습니다.")

    # ---------------- 저장 ----------------

    def _collect_and_save(self, sel: int) -> bool:
        try:
            lsail = int(self._var_lsail.get())
            lrudder = int(self._var_lrudder.get())
            capacity = int(self._var_capacity.get())
            lcrew_x10 = int(self._var_lcrew.get())
            dcrew = int(self._var_dcrew.get())
            lnowea = int(self._var_lnowea.get())
        except (tk.TclError, ValueError):
            messagebox.showerror("입력 오류", "숫자 필드에 잘못된 값이 있습니다.")
            return False

        bounds = [
            ("추진력", lsail, 0, 0xFF),
            ("선회력", lrudder, 0, 0xFF),
            ("최대 적재량", capacity, 0, 0xFFFF),
            ("최대 승무원", lcrew_x10, 0, 2550),
            ("필요 승무원", dcrew, 0, 0xFF),
            ("최대 무기수", lnowea, 0, 0xFF),
        ]
        for name, v, lo, hi in bounds:
            if not (lo <= v <= hi):
                messagebox.showerror(
                    "입력 오류", f"{name} 은 {lo}..{hi} 범위여야 합니다."
                )
                return False

        # 변경 감지 (한도 변경 시 영웅 함대 클램프 전파를 위해)
        old4 = self._ship4
        old5 = self._ship5
        assert old4 is not None and old5 is not None

        new_lcrew = lcrew_x10 // 10  # 저장값
        new_lcrew_max = (new_lcrew & 0xFF) * 10  # 비교/클램프용 실제 최대치

        new_ship4 = Ship4(
            lrudder=lrudder, lsail=lsail,
            lcrew=new_lcrew, dcrew=dcrew,
            capacity=capacity, lnowea=lnowea,
            none=old4.none,
        )

        # 배 이름 (Ship5.name 18 byte)
        name_raw = encode_kr_fixed(self._var_name.get(), 18)
        new_ship5 = Ship5(
            name=name_raw, sform=old5.sform, bform=old5.bform, none=old5.none,
        )

        # 변경 플래그
        changed_lrudder = (new_ship4.lrudder != old4.lrudder)
        changed_lsail = (new_ship4.lsail != old4.lsail)
        changed_lcrew = (new_ship4.lcrew != old4.lcrew)
        changed_capacity = (new_ship4.capacity != old4.capacity)
        changed_lnowea = (new_ship4.lnowea != old4.lnowea)

        # 디스크 기록 — Ship4, Ship5 먼저
        try:
            save_ship4(self._state, sel, new_ship4)
            save_ship5(self._state, sel, new_ship5)
        except Exception as e:
            messagebox.showerror("저장 실패", str(e))
            return False

        # ship_name 캐시 동기화 (org_ship_edit case 7 — 이름 변경 시 항상)
        new_name_str = decode_kr(new_ship5.name)
        if 0 <= sel < len(self._state.ship_name):
            self._state.ship_name[sel] = new_name_str

        # 영웅 함대 클램프 전파 (한도 또는 capacity 변경 시 그 종류를 사용 중인 모든 함대)
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
                # capacity 변경: 무조건 cargo 재계산
                # 또는 위 클램프로 f_weap/f_crew 가 변했으면 cargo 재계산
                if changed_capacity or touched:
                    cargo_recalc(s3, new_ship4.capacity, s3.f_weap, s3.f_crew)
                    touched = True
                if touched:
                    try:
                        save_fleet_entry(self._state, i, s1, s2, s3)
                    except Exception:
                        pass

        # 메모리 갱신
        self._ship4 = new_ship4
        self._ship5 = new_ship5
        return True

    # ---------------- 위젯 활성화 ----------------

    def _set_form_state(self, st: str) -> None:
        widgets = (
            self._en_name, self._sp_lsail, self._sp_lrudder,
            self._sp_capacity, self._sp_lcrew, self._sp_dcrew, self._sp_lnowea,
            self._btn_reload, self._btn_save,
        )
        for w in widgets:
            try:
                w.configure(state=st)
            except tk.TclError:
                pass
