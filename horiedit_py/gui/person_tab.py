"""인물(NPC + 동료) 편집 탭.

좌측: 검색 폼 + 결과 Treeview.
우측: 선택된 인물의 편집 폼.
hero_tab.py 와 동일하게 reload() / reset() 인터페이스를 제공한다.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Optional

from horiedit_py.common import EditorState, Person, decode_kr, encode_kr_fixed
from horiedit_py.data.person import (
    find_persons,
    get_ability_bit,
    iter_persons,
    load_person,
    person_count_max,
    save_person,
    set_ability_bit,
)


# (라벨, Person 속성, 최소, 최대) 8개 능력치 + 2개 레벨
_STAT_FIELDS: list[tuple[str, str, int, int]] = [
    ("통솔", "command", 0, 255),
    ("항해", "sail", 0, 255),
    ("지식", "know", 0, 255),
    ("직감", "hunch", 0, 255),
    ("공구", "tool", 0, 255),
    ("검술", "sword", 0, 255),
    ("매력", "charm", 0, 255),
    ("행운", "death", 0, 255),
]

_LEVEL_FIELDS: list[tuple[str, str, int, int]] = [
    ("항해 레벨", "l_sail", 0, 255),
    ("전투 레벨", "l_battle", 0, 255),
]

_EXP_FIELDS: list[tuple[str, str, int, int]] = [
    ("항해 경험", "exp_sail", 0, 65535),
    ("전투 경험", "exp_battle", 0, 65535),
]

# (라벨, 비트키) 5개
_ABILITY_FIELDS: list[tuple[str, str]] = [
    ("점술", "td"),
    ("회계", "ac"),
    ("구급", "gu"),
    ("지도작성", "mp"),
    ("검술메뉴", "me"),
]


def _in_range(v: int, lo: int, hi: int) -> bool:
    return lo <= v <= hi


def _person_is_empty(p: Person) -> bool:
    """이름이 모두 0 인 빈 슬롯인지."""
    return p.fname[:1] == b"\x00" and p.lname[:1] == b"\x00"


class PersonTab(ttk.Frame):
    """일반 인물 편집 탭."""

    def __init__(self, master: tk.Misc, state: EditorState) -> None:
        super().__init__(master, padding=8)
        self._state = state
        self._slot_loaded = False
        self._person_idx: Optional[int] = None
        self._current_pos: int = 0  # 마지막 로드한 인물의 pos (0xFF 여부 판정)

        # ---- 검색 입력 ----
        self._var_search_fname = tk.StringVar()
        self._var_search_lname = tk.StringVar()

        # ---- 편집 폼 입력 ----
        self._var_fname = tk.StringVar()
        self._var_lname = tk.StringVar()
        self._var_stats: dict[str, tk.IntVar] = {
            key: tk.IntVar(value=0) for _, key, _, _ in _STAT_FIELDS
        }
        self._var_levels: dict[str, tk.IntVar] = {
            key: tk.IntVar(value=0) for _, key, _, _ in _LEVEL_FIELDS
        }
        self._var_exps: dict[str, tk.IntVar] = {
            key: tk.IntVar(value=0) for _, key, _, _ in _EXP_FIELDS
        }
        self._var_abilities: dict[str, tk.IntVar] = {
            key: tk.IntVar(value=0) for _, key in _ABILITY_FIELDS
        }
        self._var_port = tk.StringVar()

        self._build()
        self._set_inputs_state("disabled")

    # ---------------- UI 구성 ----------------

    def _build(self) -> None:
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=2)
        self.rowconfigure(0, weight=1)

        self._build_left()
        self._build_right()

        self._hint = ttk.Label(
            self,
            text="(슬롯을 먼저 선택하세요)",
            foreground="#888",
        )
        self._hint.grid(row=1, column=0, columnspan=2, pady=(8, 0))

    def _build_left(self) -> None:
        left = ttk.Frame(self)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        left.rowconfigure(2, weight=1)
        left.columnconfigure(0, weight=1)

        # 검색 입력 영역
        search = ttk.LabelFrame(left, text="검색", padding=8)
        search.grid(row=0, column=0, sticky="ew")
        search.columnconfigure(1, weight=1)

        ttk.Label(search, text="처음 이름").grid(row=0, column=0, sticky="w", padx=2, pady=2)
        self._ent_search_fname = ttk.Entry(
            search, textvariable=self._var_search_fname
        )
        self._ent_search_fname.grid(row=0, column=1, sticky="ew", padx=2, pady=2)

        ttk.Label(search, text="마지막 이름").grid(row=1, column=0, sticky="w", padx=2, pady=2)
        self._ent_search_lname = ttk.Entry(
            search, textvariable=self._var_search_lname
        )
        self._ent_search_lname.grid(row=1, column=1, sticky="ew", padx=2, pady=2)

        btns = ttk.Frame(search)
        btns.grid(row=2, column=0, columnspan=2, sticky="e", pady=(4, 0))
        self._btn_search = ttk.Button(btns, text="검색", command=self._on_search_clicked)
        self._btn_search.grid(row=0, column=0, padx=2)
        self._btn_all = ttk.Button(btns, text="전체", command=self._on_all_clicked)
        self._btn_all.grid(row=0, column=1, padx=2)

        # 결과 안내 라벨
        self._lbl_count = ttk.Label(left, text="결과: -")
        self._lbl_count.grid(row=1, column=0, sticky="w", padx=2, pady=(8, 2))

        # 결과 Treeview
        tv_frame = ttk.Frame(left)
        tv_frame.grid(row=2, column=0, sticky="nsew")
        tv_frame.rowconfigure(0, weight=1)
        tv_frame.columnconfigure(0, weight=1)

        cols = ("idx", "fname", "lname", "port")
        self._tv = ttk.Treeview(
            tv_frame, columns=cols, show="headings", height=14, selectmode="browse"
        )
        self._tv.heading("idx", text="번호")
        self._tv.heading("fname", text="처음이름")
        self._tv.heading("lname", text="마지막이름")
        self._tv.heading("port", text="항구")
        self._tv.column("idx", width=50, anchor="center", stretch=False)
        self._tv.column("fname", width=100, anchor="w")
        self._tv.column("lname", width=100, anchor="w")
        self._tv.column("port", width=100, anchor="w")
        self._tv.grid(row=0, column=0, sticky="nsew")

        sb = ttk.Scrollbar(tv_frame, orient="vertical", command=self._tv.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self._tv.configure(yscrollcommand=sb.set)

        self._tv.bind("<Double-1>", self._on_tv_double)

        sel_btn_frame = ttk.Frame(left)
        sel_btn_frame.grid(row=3, column=0, sticky="e", pady=(4, 0))
        self._btn_select = ttk.Button(
            sel_btn_frame, text="선택 → 우측에 로드", command=self._on_select_clicked
        )
        self._btn_select.grid(row=0, column=0, padx=2)

    def _build_right(self) -> None:
        right = ttk.Frame(self)
        right.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        right.columnconfigure(0, weight=1)

        # 현재 선택된 인물 안내
        self._lbl_current = ttk.Label(
            right, text="(선택된 인물 없음)", foreground="#444"
        )
        self._lbl_current.grid(row=0, column=0, sticky="w", pady=(0, 6))

        # 이름
        name_frame = ttk.LabelFrame(right, text="이름", padding=8)
        name_frame.grid(row=1, column=0, sticky="ew", pady=4)
        name_frame.columnconfigure(1, weight=1)
        name_frame.columnconfigure(3, weight=1)

        ttk.Label(name_frame, text="처음").grid(row=0, column=0, sticky="w", padx=2, pady=2)
        self._ent_fname = ttk.Entry(name_frame, textvariable=self._var_fname, width=14)
        self._ent_fname.grid(row=0, column=1, sticky="ew", padx=2, pady=2)
        ttk.Label(name_frame, text="마지막").grid(row=0, column=2, sticky="w", padx=2, pady=2)
        self._ent_lname = ttk.Entry(name_frame, textvariable=self._var_lname, width=14)
        self._ent_lname.grid(row=0, column=3, sticky="ew", padx=2, pady=2)

        # 능력치 (8개)
        stats_frame = ttk.LabelFrame(right, text="능력치", padding=8)
        stats_frame.grid(row=2, column=0, sticky="ew", pady=4)
        for i, (label, key, lo, hi) in enumerate(_STAT_FIELDS):
            r, c = divmod(i, 4)
            cell = ttk.Frame(stats_frame)
            cell.grid(row=r, column=c, sticky="w", padx=4, pady=3)
            ttk.Label(cell, text=label, width=4).grid(row=0, column=0, sticky="w")
            sp = ttk.Spinbox(
                cell,
                from_=lo,
                to=hi,
                textvariable=self._var_stats[key],
                width=6,
            )
            sp.grid(row=0, column=1, padx=(2, 0))

        # 레벨/경험치
        lvl_frame = ttk.LabelFrame(right, text="레벨 / 경험", padding=8)
        lvl_frame.grid(row=3, column=0, sticky="ew", pady=4)
        for i, (label, key, lo, hi) in enumerate(_LEVEL_FIELDS):
            cell = ttk.Frame(lvl_frame)
            cell.grid(row=0, column=i, sticky="w", padx=6, pady=3)
            ttk.Label(cell, text=label).grid(row=0, column=0, sticky="w")
            sp = ttk.Spinbox(
                cell,
                from_=lo,
                to=hi,
                textvariable=self._var_levels[key],
                width=6,
            )
            sp.grid(row=0, column=1, padx=(4, 0))
        for i, (label, key, lo, hi) in enumerate(_EXP_FIELDS):
            cell = ttk.Frame(lvl_frame)
            cell.grid(row=1, column=i, sticky="w", padx=6, pady=3)
            ttk.Label(cell, text=label).grid(row=0, column=0, sticky="w")
            sp = ttk.Spinbox(
                cell,
                from_=lo,
                to=hi,
                textvariable=self._var_exps[key],
                width=8,
            )
            sp.grid(row=0, column=1, padx=(4, 0))

        # 비트필드 능력
        ab_frame = ttk.LabelFrame(right, text="능력 (비트)", padding=8)
        ab_frame.grid(row=4, column=0, sticky="ew", pady=4)
        for i, (label, key) in enumerate(_ABILITY_FIELDS):
            cb = ttk.Checkbutton(
                ab_frame,
                text=label,
                variable=self._var_abilities[key],
                onvalue=1,
                offvalue=0,
            )
            cb.grid(row=0, column=i, sticky="w", padx=4, pady=2)

        # 정착 항구 (pos==0xFF 일 때만)
        port_frame = ttk.LabelFrame(right, text="정착 항구", padding=8)
        port_frame.grid(row=5, column=0, sticky="ew", pady=4)
        port_frame.columnconfigure(1, weight=1)

        ttk.Label(port_frame, text="항구").grid(row=0, column=0, sticky="w", padx=2, pady=2)
        self._cb_port = ttk.Combobox(
            port_frame,
            textvariable=self._var_port,
            state="disabled",
            width=22,
            values=[],
        )
        self._cb_port.grid(row=0, column=1, sticky="ew", padx=2, pady=2)
        self._lbl_port_hint = ttk.Label(
            port_frame,
            text="(pos != 0xFF 이므로 항구 편집 불가)",
            foreground="#888",
        )
        self._lbl_port_hint.grid(row=1, column=0, columnspan=2, sticky="w", padx=2)

        # 버튼
        buttons = ttk.Frame(right)
        buttons.grid(row=6, column=0, sticky="e", pady=(8, 0))
        self._btn_reload_form = ttk.Button(
            buttons, text="다시 불러오기", command=self._on_reload_form_clicked
        )
        self._btn_reload_form.grid(row=0, column=0, padx=2)
        self._btn_save = ttk.Button(buttons, text="저장", command=self._on_save_clicked)
        self._btn_save.grid(row=0, column=1, padx=2)

    # ---------------- reload / reset ----------------

    def reload(self) -> None:
        """슬롯이 변경되었을 때 호출. 검색결과/폼 초기화 + 위젯 활성화."""
        self._slot_loaded = True
        self._person_idx = None
        self._current_pos = 0

        # 항구 콤보 채우기
        self._refresh_port_values()

        # 검색 입력 비우고 결과 비우기
        self._var_search_fname.set("")
        self._var_search_lname.set("")
        self._clear_results()

        # 폼 비우기
        self._clear_form()

        self._hint.grid_remove()
        self._set_inputs_state("normal")
        # 항구 콤보는 별도 정책 (현재 로드된 인물 없음 → 비활성)
        self._update_port_state()

        self._lbl_current.configure(text="(선택된 인물 없음)")

    def reset(self) -> None:
        """폼/검색 초기화 + 모든 위젯 비활성."""
        self._slot_loaded = False
        self._person_idx = None
        self._current_pos = 0
        self._var_search_fname.set("")
        self._var_search_lname.set("")
        self._clear_results()
        self._clear_form()
        self._set_inputs_state("disabled")
        self._hint.grid()
        self._lbl_current.configure(text="(선택된 인물 없음)")

    # ---------------- 검색 ----------------

    def _on_search_clicked(self) -> None:
        if not self._slot_loaded:
            return
        fname = self._var_search_fname.get().strip()
        lname = self._var_search_lname.get().strip()
        if not fname and not lname:
            messagebox.showinfo(
                "검색", "처음 이름 또는 마지막 이름 중 하나는 입력해야 합니다."
            )
            return
        try:
            indices = find_persons(self._state, fname, lname)
        except Exception as e:
            messagebox.showerror("검색 실패", str(e))
            return
        self._populate_results(indices)

    def _on_all_clicked(self) -> None:
        """모든 인물 표시 (이름이 빈 인물은 제외)."""
        if not self._slot_loaded:
            return
        try:
            indices = [
                idx for idx, p in iter_persons(self._state) if not _person_is_empty(p)
            ]
        except Exception as e:
            messagebox.showerror("전체 조회 실패", str(e))
            return
        self._populate_results(indices)

    def _populate_results(self, indices: list[int]) -> None:
        """주어진 idx 리스트로 Treeview 채우기."""
        self._clear_results()
        if not indices:
            self._lbl_count.configure(text="결과: 0 (결과 없음)")
            return
        for idx in indices:
            try:
                p = load_person(self._state, idx)
            except Exception:
                continue
            fname_s = decode_kr(p.fname)
            lname_s = decode_kr(p.lname)
            port_s = ""
            if p.pos == 0xFF:
                if 0 <= p.port < len(self._state.port_name):
                    port_s = self._state.port_name[p.port]
            self._tv.insert(
                "", "end", iid=str(idx), values=(idx, fname_s, lname_s, port_s)
            )
        self._lbl_count.configure(text=f"결과: {len(indices)}")

    def _clear_results(self) -> None:
        for iid in self._tv.get_children():
            self._tv.delete(iid)
        self._lbl_count.configure(text="결과: -")

    def _on_tv_double(self, _event: object = None) -> None:
        self._on_select_clicked()

    def _on_select_clicked(self) -> None:
        if not self._slot_loaded:
            return
        sel = self._tv.selection()
        if not sel:
            messagebox.showinfo("선택", "결과 목록에서 인물을 먼저 선택하세요.")
            return
        try:
            idx = int(sel[0])
        except ValueError:
            return
        self._load_person_into_form(idx)

    # ---------------- 폼 로드 / 저장 ----------------

    def _load_person_into_form(self, idx: int) -> None:
        if not (0 <= idx < person_count_max()):
            messagebox.showerror("로드 실패", f"잘못된 인물 번호: {idx}")
            return
        try:
            p = load_person(self._state, idx)
        except Exception as e:
            messagebox.showerror("로드 실패", str(e))
            return

        self._person_idx = idx
        self._current_pos = p.pos

        self._var_fname.set(decode_kr(p.fname))
        self._var_lname.set(decode_kr(p.lname))
        for _, key, _, _ in _STAT_FIELDS:
            self._var_stats[key].set(int(getattr(p, key)))
        for _, key, _, _ in _LEVEL_FIELDS:
            self._var_levels[key].set(int(getattr(p, key)))
        for _, key, _, _ in _EXP_FIELDS:
            self._var_exps[key].set(int(getattr(p, key)))
        for _, key in _ABILITY_FIELDS:
            self._var_abilities[key].set(get_ability_bit(p, key))

        # 항구
        port_idx = p.port if 0 <= p.port < len(self._state.port_name) else 0
        port_name = ""
        if 0 <= port_idx < len(self._state.port_name):
            port_name = f"{port_idx}: {self._state.port_name[port_idx]}"
        self._var_port.set(port_name)
        self._update_port_state()

        # 안내 갱신
        fname_s = decode_kr(p.fname)
        lname_s = decode_kr(p.lname)
        self._lbl_current.configure(
            text=f"인물 #{idx}  {fname_s} {lname_s}  pos=0x{p.pos:02X}"
        )

    def _on_reload_form_clicked(self) -> None:
        if not self._slot_loaded or self._person_idx is None:
            return
        self._load_person_into_form(self._person_idx)

    def _on_save_clicked(self) -> None:
        if not self._slot_loaded:
            return
        if self._person_idx is None:
            messagebox.showinfo("저장", "먼저 결과 목록에서 인물을 선택하세요.")
            return
        person = self._collect_form()
        if person is None:
            return
        try:
            save_person(self._state, self._person_idx, person)
            self._state.fp.flush()
        except Exception as e:
            messagebox.showerror("저장 실패", str(e))
            return

        # 결과 목록의 해당 행도 갱신 (이름/항구가 바뀌었을 수 있음)
        self._refresh_result_row(self._person_idx, person)

        # 안내 라벨 갱신
        fname_s = decode_kr(person.fname)
        lname_s = decode_kr(person.lname)
        self._lbl_current.configure(
            text=f"인물 #{self._person_idx}  {fname_s} {lname_s}  pos=0x{person.pos:02X}"
        )
        messagebox.showinfo("저장 완료", f"인물 #{self._person_idx} 데이터를 저장했습니다.")

    def _collect_form(self) -> Optional[Person]:
        """폼 → 새 Person 객체. 검증 실패 시 None."""
        if self._person_idx is None:
            return None

        # 원본 인물을 다시 읽어 패딩/none/pos 등 손대지 않는 필드를 보존
        try:
            p = load_person(self._state, self._person_idx)
        except Exception as e:
            messagebox.showerror("저장 준비 실패", str(e))
            return None

        # 이름
        fname_str = self._var_fname.get()
        lname_str = self._var_lname.get()
        try:
            p.fname = encode_kr_fixed(fname_str, 13)
            p.lname = encode_kr_fixed(lname_str, 13)
        except Exception as e:
            messagebox.showerror("입력 오류", f"이름 인코딩 실패: {e}")
            return None

        # 능력치 / 레벨 / 경험치
        for spec, src in (
            (_STAT_FIELDS, self._var_stats),
            (_LEVEL_FIELDS, self._var_levels),
            (_EXP_FIELDS, self._var_exps),
        ):
            for label, key, lo, hi in spec:
                v = self._read_int_var(src[key], label)
                if v is None:
                    return None
                if not _in_range(v, lo, hi):
                    messagebox.showerror(
                        "입력 오류", f"{label} 는 {lo}..{hi} 범위여야 합니다."
                    )
                    return None
                setattr(p, key, v)

        # 비트필드
        for label, key in _ABILITY_FIELDS:
            try:
                bv = int(self._var_abilities[key].get())
            except (tk.TclError, ValueError):
                messagebox.showerror("입력 오류", f"능력({label}) 값이 잘못되었습니다.")
                return None
            set_ability_bit(p, key, 1 if bv else 0)

        # 항구 (pos==0xFF 일 때만 적용)
        if p.pos == 0xFF:
            port_idx = self._parse_port_selection(self._var_port.get())
            if port_idx is None:
                messagebox.showerror(
                    "입력 오류",
                    "정착 항구를 선택하세요 (pos == 0xFF 인 인물).",
                )
                return None
            if not _in_range(port_idx, 0, 129):
                messagebox.showerror("입력 오류", "항구 인덱스는 0..129 범위여야 합니다.")
                return None
            p.port = port_idx
        # pos != 0xFF 이면 port 는 원본 그대로 유지 (다시 읽어왔으므로 OK).

        return p

    def _read_int_var(self, var: tk.IntVar, label: str) -> Optional[int]:
        try:
            return int(var.get())
        except (tk.TclError, ValueError):
            messagebox.showerror("입력 오류", f"{label} 값이 숫자가 아닙니다.")
            return None

    def _parse_port_selection(self, text: str) -> Optional[int]:
        """콤보 항목 'NN: 항구이름' 또는 'NN' 또는 '항구이름' 형태에서 idx 추출."""
        text = text.strip()
        if not text:
            return None
        # "NN: name" 형태
        if ":" in text:
            head = text.split(":", 1)[0].strip()
            try:
                return int(head)
            except ValueError:
                pass
        # 순수 숫자
        try:
            return int(text)
        except ValueError:
            pass
        # 이름만 들어 있으면 port_name 에서 매칭
        names = self._state.port_name
        for i, n in enumerate(names):
            if n == text:
                return i
        return None

    def _refresh_result_row(self, idx: int, p: Person) -> None:
        """결과 Treeview 의 해당 행을 갱신. 없으면 그냥 둔다."""
        iid = str(idx)
        if not self._tv.exists(iid):
            return
        fname_s = decode_kr(p.fname)
        lname_s = decode_kr(p.lname)
        port_s = ""
        if p.pos == 0xFF and 0 <= p.port < len(self._state.port_name):
            port_s = self._state.port_name[p.port]
        self._tv.item(iid, values=(idx, fname_s, lname_s, port_s))

    # ---------------- 항구 콤보 ----------------

    def _refresh_port_values(self) -> None:
        names = self._state.port_name
        values = [f"{i}: {n}" for i, n in enumerate(names) if n]
        self._cb_port.configure(values=values)

    def _update_port_state(self) -> None:
        """현재 인물의 pos 에 따라 항구 콤보 활성/비활성 + 안내 라벨 갱신."""
        if not self._slot_loaded or self._person_idx is None:
            self._cb_port.configure(state="disabled")
            self._lbl_port_hint.configure(
                text="(인물을 먼저 선택하세요)",
            )
            return
        if self._current_pos == 0xFF:
            self._cb_port.configure(state="readonly")
            self._lbl_port_hint.configure(text="(정착 항구를 선택하세요)")
        else:
            self._cb_port.configure(state="disabled")
            self._lbl_port_hint.configure(
                text=f"(pos = 0x{self._current_pos:02X} 이므로 항구 편집 불가)"
            )

    # ---------------- 폼 비우기 / 위젯 상태 ----------------

    def _clear_form(self) -> None:
        self._var_fname.set("")
        self._var_lname.set("")
        for var in self._var_stats.values():
            var.set(0)
        for var in self._var_levels.values():
            var.set(0)
        for var in self._var_exps.values():
            var.set(0)
        for var in self._var_abilities.values():
            var.set(0)
        self._var_port.set("")

    def _set_inputs_state(self, st: str) -> None:
        """모든 입력 위젯 일괄 활성/비활성. ttk 'normal' / 'disabled'."""
        combo_state = "readonly" if st == "normal" else "disabled"
        for child in self.winfo_children():
            self._cascade_state(child, st, combo_state)
        # 항구 콤보는 _update_port_state 에서 별도 관리하므로 여기서 강제하지 않음.
        if st != "normal":
            try:
                self._cb_port.configure(state="disabled")
            except tk.TclError:
                pass

    def _cascade_state(self, widget: tk.Misc, st: str, combo_state: str) -> None:
        cls = widget.winfo_class()
        try:
            if cls in ("TSpinbox", "TEntry", "TButton", "TCheckbutton"):
                widget.configure(state=st)
            elif cls == "TCombobox":
                # 항구 콤보는 pos==0xFF 정책에 따라 별도 — 여기서는 일반 콤보용
                if widget is not self._cb_port:
                    widget.configure(state=combo_state)
            elif cls == "Treeview":
                # Treeview 는 직접 disabled 상태가 없음 → selectmode 토글
                widget.configure(selectmode="browse" if st == "normal" else "none")
        except tk.TclError:
            pass
        for ch in widget.winfo_children():
            self._cascade_state(ch, st, combo_state)
