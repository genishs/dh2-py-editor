"""인물(NPC + 동료) 편집 탭.

좌측: 검색 폼 + 결과 Treeview.
우측: 선택된 인물의 편집 폼.

dirty/commit/revert 인터페이스:
- 폼 입력이 변경되면 dirty=True.
- 다른 인물을 새로 로드하기 전에 자체 dirty 가 있으면, app 의 dirty 통합으로
  app 다이얼로그가 처리하도록 한다 (탭 내부에서는 별도 다이얼로그 띄우지 않음).
- commit(): 현재 선택된 인물의 폼 → 디스크.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable, Optional

from horiedit_py.common import EditorState, Person, decode_kr, encode_kr_fixed
from horiedit_py.data.person import (
    HERO_CATALOG_ID,
    HERO_CATALOG_TO_IDX,
    POS_FREE,
    POS_PORT_SETTLER,
    describe_pos,
    find_persons,
    get_ability_bit,
    iter_persons,
    load_person,
    person_count_max,
    save_person,
    set_ability_bit,
)


# 안전한 소속 변경 옵션 (Combobox). 각 항목 → (라벨, pos 값 또는 None).
# None = "(현재값 유지)" 더미 옵션 — Spinbox 로 변경된 raw 값을 그대로 둠.
_POS_COMBO_OPTIONS: list[tuple[str, int | None]] = [
    ("(현재값 유지 — Spinbox 로 직접 변경)", None),
    ("조안의 동료", HERO_CATALOG_ID[0]),
    ("카탈리나의 동료", HERO_CATALOG_ID[1]),
    ("오토의 동료", HERO_CATALOG_ID[2]),
    ("로페즈의 동료", HERO_CATALOG_ID[3]),
    ("피에트로의 동료", HERO_CATALOG_ID[4]),
    ("알의 동료", HERO_CATALOG_ID[5]),
    ("(모집 가능 / free)", POS_FREE),
    ("(항구 정착민)", POS_PORT_SETTLER),
]
_POS_COMBO_LABELS = [lbl for lbl, _ in _POS_COMBO_OPTIONS]
_POS_COMBO_VALUE_TO_LABEL: dict[int, str] = {
    v: lbl for lbl, v in _POS_COMBO_OPTIONS if v is not None
}


# (라벨, Person 속성, 최소, 최대) 8개 능력치 + 2개 레벨
_STAT_FIELDS: list[tuple[str, str, int, int]] = [
    ("통솔", "command", 0, 255),
    ("항해", "sail", 0, 255),
    ("지식", "know", 0, 255),
    ("직감", "hunch", 0, 255),
    ("용기", "tool", 0, 255),
    ("검술", "sword", 0, 255),
    ("매력", "charm", 0, 255),
    ("운명", "death", 0, 255),
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
    ("교섭", "td"),
    ("회계", "ac"),
    ("포술", "gu"),
    ("지도작성", "mp"),
    ("측량", "me"),
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
        self._current_pos: int = 0  # 마지막 로드한 인물의 pos
        self._current_none2: bytes = b"\x00\x00"  # 디스크 값 보존 (술집/여관 표시용)

        self._loading = False
        self._dirty = False
        self._dirty_listeners: list[Callable[[], None]] = []

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
        self._var_pos = tk.IntVar(value=0)
        self._var_pos_combo = tk.StringVar(value=_POS_COMBO_LABELS[0])
        self._var_port = tk.StringVar()

        self._build()
        self._set_inputs_state("disabled")
        self._install_dirty_traces()

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

        # 검색 입력
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

        cols = ("idx", "fname", "lname", "affiliation", "port")
        self._tv = ttk.Treeview(
            tv_frame, columns=cols, show="headings", height=14, selectmode="browse"
        )
        self._tv.heading("idx", text="번호")
        self._tv.heading("fname", text="처음이름")
        self._tv.heading("lname", text="마지막이름")
        self._tv.heading("affiliation", text="소속")
        self._tv.heading("port", text="항구·위치")
        self._tv.column("idx", width=50, anchor="center", stretch=False)
        self._tv.column("fname", width=90, anchor="w")
        self._tv.column("lname", width=90, anchor="w")
        self._tv.column("affiliation", width=140, anchor="w")
        self._tv.column("port", width=130, anchor="w")
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

        # 소속 / 정착 항구
        port_frame = ttk.LabelFrame(right, text="소속 / 정착 항구", padding=8)
        port_frame.grid(row=5, column=0, sticky="ew", pady=4)
        port_frame.columnconfigure(1, weight=1)

        # 현재 소속 (read-only 디코드 라벨, analysis_K)
        ttk.Label(port_frame, text="현재 소속").grid(
            row=0, column=0, sticky="w", padx=2, pady=2
        )
        self._lbl_affiliation = ttk.Label(
            port_frame, text="(인물을 먼저 선택하세요)", foreground="#246"
        )
        self._lbl_affiliation.grid(row=0, column=1, sticky="w", padx=2, pady=2)

        # 소속 변경 Combobox (안전 옵션, analysis_K §9.2)
        ttk.Label(port_frame, text="소속 변경").grid(
            row=1, column=0, sticky="w", padx=2, pady=2
        )
        self._cb_pos = ttk.Combobox(
            port_frame,
            textvariable=self._var_pos_combo,
            state="readonly",
            width=32,
            values=_POS_COMBO_LABELS,
        )
        self._cb_pos.grid(row=1, column=1, sticky="ew", padx=2, pady=2)
        self._cb_pos.bind("<<ComboboxSelected>>", self._on_pos_combo_selected)

        # 소속 raw byte (고급 / 직접 값 입력)
        ttk.Label(port_frame, text="소속 (pos byte)").grid(
            row=2, column=0, sticky="w", padx=2, pady=2
        )
        self._sp_pos = ttk.Spinbox(
            port_frame, from_=0, to=255, textvariable=self._var_pos, width=8
        )
        self._sp_pos.grid(row=2, column=1, sticky="w", padx=2, pady=2)
        ttk.Label(
            port_frame,
            text=(
                "값: 255 = 정착민 (port 활성), 254 = 모집 가능, 0/10/20/30/40/50 = hero 동료 (조안/카탈리나/알/오토/피에트로/로페즈), 0..68 그 외 = NPC 카탈로그 (충돌 가능).\n"
                "* 인물 #0..#5 (주인공) 의 pos 는 게임 진행 상태 — 변경 권장 안 함."
            ),
            foreground="#888",
            justify="left",
        ).grid(row=3, column=0, columnspan=2, sticky="w", padx=2, pady=(0, 4))

        ttk.Label(port_frame, text="정착 항구").grid(row=4, column=0, sticky="w", padx=2, pady=2)
        self._cb_port = ttk.Combobox(
            port_frame,
            textvariable=self._var_port,
            state="disabled",
            width=22,
            values=[],
        )
        self._cb_port.grid(row=4, column=1, sticky="ew", padx=2, pady=2)
        self._cb_port.bind("<<ComboboxSelected>>", self._on_dirty_event)
        self._lbl_port_hint = ttk.Label(
            port_frame,
            text="(pos != 0xFF 이므로 항구 편집 불가)",
            foreground="#888",
        )
        self._lbl_port_hint.grid(row=5, column=0, columnspan=2, sticky="w", padx=2)

    # ---------------- dirty 처리 ----------------

    def _install_dirty_traces(self) -> None:
        # 이름
        for v in (self._var_fname, self._var_lname):
            v.trace_add("write", self._on_var_write)
        # 능력치 / 레벨 / 경험
        for src in (self._var_stats, self._var_levels, self._var_exps,
                    self._var_abilities):
            for v in src.values():
                v.trace_add("write", self._on_var_write)
        # 소속 (pos): dirty + 항구 편집 가능 여부 즉시 갱신
        self._var_pos.trace_add("write", self._on_pos_var_write)

    def _on_var_write(self, *_a: object) -> None:
        if self._loading:
            return
        if not self._slot_loaded or self._person_idx is None:
            return
        self._set_dirty(True)

    def _on_pos_var_write(self, *_a: object) -> None:
        """pos 변경 시: dirty 마크 + 항구 활성/비활성 + 디코드 라벨 + combobox sync."""
        if self._loading:
            return
        # 항구 콤보 상태 + 디코드 라벨은 항상 갱신
        self._update_port_state()
        self._sync_pos_combo_from_var()
        self._refresh_affiliation_label()
        if not self._slot_loaded or self._person_idx is None:
            return
        self._set_dirty(True)

    def _on_pos_combo_selected(self, _event: object = None) -> None:
        """Combobox 선택 → pos 값 설정 ("(현재값 유지)" 면 no-op)."""
        if self._loading:
            return
        if not self._slot_loaded or self._person_idx is None:
            return
        label = self._var_pos_combo.get()
        target_pos = None
        for lbl, v in _POS_COMBO_OPTIONS:
            if lbl == label:
                target_pos = v
                break
        if target_pos is None:
            return  # "(현재값 유지)" or 매칭 실패
        try:
            cur = int(self._var_pos.get())
        except (tk.TclError, ValueError):
            cur = -1
        if cur != target_pos:
            self._var_pos.set(target_pos)  # → _on_pos_var_write 가 dirty/UI 갱신

    def _sync_pos_combo_from_var(self) -> None:
        """현재 _var_pos 값에 해당하는 combobox 라벨로 표시 갱신 (없으면 '현재값 유지')."""
        try:
            cur = int(self._var_pos.get())
        except (tk.TclError, ValueError):
            return
        lbl = _POS_COMBO_VALUE_TO_LABEL.get(cur, _POS_COMBO_LABELS[0])
        if self._var_pos_combo.get() != lbl:
            self._var_pos_combo.set(lbl)

    def _refresh_affiliation_label(self) -> None:
        """현재 폼 상태로 '현재 소속' 디코드 라벨 갱신."""
        if not self._slot_loaded or self._person_idx is None:
            try:
                self._lbl_affiliation.configure(text="(인물을 먼저 선택하세요)")
            except tk.TclError:
                pass
            return
        try:
            cur_pos = int(self._var_pos.get())
        except (tk.TclError, ValueError):
            cur_pos = 0
        try:
            cur_port_text = self._var_port.get()
            cur_port_idx = self._parse_port_selection(cur_port_text)
            if cur_port_idx is None:
                cur_port_idx = 0
        except Exception:
            cur_port_idx = 0
        # describe_pos 는 Person 객체를 요구 — 임시 Person 으로 wrap
        # (none2 는 디스크 값 보존 필요 → _current_pos 갱신 시 같이 저장된 none2 사용)
        tmp = Person(pos=cur_pos, port=cur_port_idx, none2=self._current_none2)
        text = describe_pos(tmp, self._state.hero, self._state.port_name)
        try:
            self._lbl_affiliation.configure(text=f"{text}  (pos=0x{cur_pos:02X})")
        except tk.TclError:
            pass

    def _on_dirty_event(self, _event: object = None) -> None:
        if self._loading:
            return
        if not self._slot_loaded or self._person_idx is None:
            return
        # 항구 콤보 변경 시 디코드 라벨도 즉시 갱신 (항구이름 표시)
        self._refresh_affiliation_label()
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

    # ---------------- 외부 인터페이스 ----------------

    def is_dirty(self) -> bool:
        return self._dirty and self._slot_loaded and self._person_idx is not None

    def add_dirty_listener(self, callback: Callable[[], None]) -> None:
        self._dirty_listeners.append(callback)

    def reload(self) -> None:
        """슬롯이 변경되었을 때 호출. 검색결과/폼 초기화 + 위젯 활성화."""
        self._loading = True
        try:
            self._slot_loaded = True
            self._person_idx = None
            self._current_pos = 0

            self._refresh_port_values()

            self._var_search_fname.set("")
            self._var_search_lname.set("")
            self._clear_results()

            self._clear_form()

            self._hint.grid_remove()
            self._set_inputs_state("normal")
            self._update_port_state()
            self._lbl_current.configure(text="(선택된 인물 없음)")
        finally:
            self._loading = False
        self._set_dirty(False)

    def reset(self) -> None:
        """폼/검색 초기화 + 모든 위젯 비활성. dirty=False."""
        self._loading = True
        try:
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
        finally:
            self._loading = False
        self._set_dirty(False)

    def revert(self) -> None:
        """현재 슬롯/인물의 디스크 값을 다시 폼으로. dirty=False."""
        if not self._slot_loaded:
            return
        if self._person_idx is None:
            self._set_dirty(False)
            return
        self._loading = True
        try:
            self._load_person_into_form(self._person_idx)
        finally:
            self._loading = False
        self._set_dirty(False)

    def commit(self) -> None:
        """현재 인물의 폼 → 디스크. dirty 가 아니면 no-op."""
        if not self._slot_loaded or self._person_idx is None:
            return
        if not self._dirty:
            return
        person = self._collect_form()
        try:
            save_person(self._state, self._person_idx, person)
        except Exception as e:
            raise ValueError(f"인물 저장 실패: {e}") from e

        # 결과 목록의 해당 행도 갱신
        self._refresh_result_row(self._person_idx, person)
        # 디스크 값 캐시 갱신 (라벨 술집/여관 추정에 사용)
        self._current_pos = person.pos
        self._current_none2 = bytes(person.none2)

        fname_s = decode_kr(person.fname)
        lname_s = decode_kr(person.lname)
        affiliation = describe_pos(person, self._state.hero, self._state.port_name)
        self._lbl_current.configure(
            text=f"인물 #{self._person_idx}  {fname_s} {lname_s}  ·  {affiliation}"
        )
        self._refresh_affiliation_label()
        self._set_dirty(False)

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
            affiliation_s = describe_pos(p, self._state.hero, self._state.port_name)
            port_s = ""
            if p.pos == 0xFF and 0 <= p.port < len(self._state.port_name):
                port_s = self._state.port_name[p.port]
            self._tv.insert(
                "", "end", iid=str(idx),
                values=(idx, fname_s, lname_s, affiliation_s, port_s),
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
        # 다른 인물 로드: 기존 폼이 dirty 면 변경분이 폐기된다.
        # (app 가 다이얼로그를 띄우지는 않는다 — 같은 슬롯/탭 내 인물 전환은 일상적이라.)
        self._loading = True
        try:
            self._load_person_into_form(idx)
        finally:
            self._loading = False
        self._set_dirty(False)

    # ---------------- 폼 로드 ----------------

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
        self._current_none2 = bytes(p.none2)  # describe_pos 의 술집/여관 추정용

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

        self._var_pos.set(int(p.pos))
        self._sync_pos_combo_from_var()

        port_idx = p.port if 0 <= p.port < len(self._state.port_name) else 0
        port_name = ""
        if 0 <= port_idx < len(self._state.port_name):
            port_name = f"{port_idx}: {self._state.port_name[port_idx]}"
        self._var_port.set(port_name)
        self._update_port_state()
        self._refresh_affiliation_label()

        fname_s = decode_kr(p.fname)
        lname_s = decode_kr(p.lname)
        affiliation = describe_pos(p, self._state.hero, self._state.port_name)
        self._lbl_current.configure(
            text=f"인물 #{idx}  {fname_s} {lname_s}  ·  {affiliation}"
        )

    def _collect_form(self) -> Person:
        if self._person_idx is None:
            raise ValueError("인물이 선택되지 않았습니다.")

        # 원본 인물을 다시 읽어 패딩/none/pos 등 손대지 않는 필드를 보존
        try:
            p = load_person(self._state, self._person_idx)
        except Exception as e:
            raise ValueError(f"인물 저장 준비 실패: {e}")

        # 이름
        fname_str = self._var_fname.get()
        lname_str = self._var_lname.get()
        try:
            p.fname = encode_kr_fixed(fname_str, 13)
            p.lname = encode_kr_fixed(lname_str, 13)
        except Exception as e:
            raise ValueError(f"인물: 이름 인코딩 실패: {e}")

        # 능력치 / 레벨 / 경험치
        for spec, src in (
            (_STAT_FIELDS, self._var_stats),
            (_LEVEL_FIELDS, self._var_levels),
            (_EXP_FIELDS, self._var_exps),
        ):
            for label, key, lo, hi in spec:
                try:
                    v = int(src[key].get())
                except (tk.TclError, ValueError):
                    raise ValueError(f"인물: {label} 값이 숫자가 아닙니다.")
                if not _in_range(v, lo, hi):
                    raise ValueError(f"인물: {label} 는 {lo}..{hi} 범위여야 합니다.")
                setattr(p, key, v)

        # 비트필드
        for label, key in _ABILITY_FIELDS:
            try:
                bv = int(self._var_abilities[key].get())
            except (tk.TclError, ValueError):
                raise ValueError(f"인물: 능력({label}) 값이 잘못되었습니다.")
            set_ability_bit(p, key, 1 if bv else 0)

        # 소속 (pos) — 사용자 편집 반영
        try:
            new_pos = int(self._var_pos.get())
        except (tk.TclError, ValueError):
            raise ValueError("인물: 소속(pos) 값이 숫자가 아닙니다.")
        if not _in_range(new_pos, 0, 255):
            raise ValueError("인물: 소속(pos) 는 0..255 범위여야 합니다.")
        p.pos = new_pos

        # 항구 (pos==0xFF 일 때만 의미 있음)
        if p.pos == 0xFF:
            port_idx = self._parse_port_selection(self._var_port.get())
            if port_idx is None:
                raise ValueError("인물: 정착 항구를 선택하세요 (pos == 0xFF 인 인물).")
            if not _in_range(port_idx, 0, 129):
                raise ValueError("인물: 항구 인덱스는 0..129 범위여야 합니다.")
            p.port = port_idx

        return p

    def _parse_port_selection(self, text: str) -> Optional[int]:
        text = text.strip()
        if not text:
            return None
        if ":" in text:
            head = text.split(":", 1)[0].strip()
            try:
                return int(head)
            except ValueError:
                pass
        try:
            return int(text)
        except ValueError:
            pass
        names = self._state.port_name
        for i, n in enumerate(names):
            if n == text:
                return i
        return None

    def _refresh_result_row(self, idx: int, p: Person) -> None:
        iid = str(idx)
        if not self._tv.exists(iid):
            return
        fname_s = decode_kr(p.fname)
        lname_s = decode_kr(p.lname)
        affiliation_s = describe_pos(p, self._state.hero, self._state.port_name)
        port_s = ""
        if p.pos == 0xFF and 0 <= p.port < len(self._state.port_name):
            port_s = self._state.port_name[p.port]
        self._tv.item(iid, values=(idx, fname_s, lname_s, affiliation_s, port_s))

    # ---------------- 항구 콤보 ----------------

    def _refresh_port_values(self) -> None:
        names = self._state.port_name
        values = [f"{i}: {n}" for i, n in enumerate(names) if n]
        self._cb_port.configure(values=values)

    def _update_port_state(self) -> None:
        if not self._slot_loaded or self._person_idx is None:
            try:
                self._cb_port.configure(state="disabled")
            except tk.TclError:
                pass
            try:
                self._lbl_port_hint.configure(text="(인물을 먼저 선택하세요)")
            except tk.TclError:
                pass
            return
        # 현재 폼 위에 사용자가 입력한 pos 를 사용. 파싱 실패 시 디스크 값으로 fallback.
        try:
            cur_pos = int(self._var_pos.get())
        except (tk.TclError, ValueError):
            cur_pos = self._current_pos
        if cur_pos == 0xFF:
            self._cb_port.configure(state="readonly")
            self._lbl_port_hint.configure(text="(정착 항구를 선택하세요)")
        else:
            self._cb_port.configure(state="disabled")
            self._lbl_port_hint.configure(
                text=(
                    f"(pos = 0x{cur_pos:02X} 이므로 항구 편집 불가 — "
                    "pos 를 255 (0xFF) 로 변경하면 항구 콤보가 활성화됩니다)"
                )
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
        self._var_pos.set(0)
        self._var_pos_combo.set(_POS_COMBO_LABELS[0])
        self._var_port.set("")
        self._current_none2 = b"\x00\x00"

    def _set_inputs_state(self, st: str) -> None:
        combo_state = "readonly" if st == "normal" else "disabled"
        for child in self.winfo_children():
            self._cascade_state(child, st, combo_state)
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
                if widget is not self._cb_port:
                    widget.configure(state=combo_state)
            elif cls == "Treeview":
                widget.configure(selectmode="browse" if st == "normal" else "none")
        except tk.TclError:
            pass
        for ch in widget.winfo_children():
            self._cascade_state(ch, st, combo_state)
