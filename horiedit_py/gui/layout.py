"""창 크기 대응 레이아웃 공용 도구 — 스크롤 컨테이너 · 창 크기 정하기 · 줄바꿈 따라가기.

모든 탭/패널/대화상자가 같은 규칙을 쓰도록 모아 둔 모듈이다 (탭마다 따로 땜질하지 않는다).
tkinter/ttk 표준 라이브러리만 쓴다.

규칙 요약
---------
1. 내용이 창보다 커질 수 있는 화면은 :class:`ScrollFrame` 에 넣는다 — 안 보이게 잘리는 대신 스크롤바가 생긴다.
   · 내용이 들어가면 안쪽 프레임이 창을 꽉 채운다 (목록·표가 창 크기를 따라 커진다).
   · 안 들어가면 스크롤바가 필요한 방향에만 나타난다.
2. 마우스 휠은 포인터 아래에 있는 스크롤 영역만 움직인다 (중첩돼도 가장 안쪽의 넘치는 영역).
   · Listbox/Treeview/Text 는 자기 휠 처리를 그대로 쓴다 (끝에 닿거나 넘치지 않으면 바깥 영역이 받는다).
   · 콤보박스/스핀박스 위에서는 값이 바뀌지 않는다 — 바깥 영역이 스크롤 가능하면 화면이 스크롤되고, 아니면 무시.
3. 값을 넣는 폼은 창이 커져도 자기 폭을 유지한다 (늘어나는 건 목록·표·텍스트).
4. 「목록 + 상세」 화면은 :class:`SplitPane` — 목록은 창 높이에 묶여 안에서 스크롤하고, 상세 폼은 자기 ScrollFrame 을
   따로 가진다. 화면 전체가 한꺼번에 스크롤되지 않는다.
5. 실행 버튼 줄(저장 / 적용 / 다시 불러오기 …)은 :class:`Page`/:class:`SplitPane` 의 ``footer`` — 스크롤 영역 밖 하단에
   고정돼 있어 어떤 창 크기에서도 스크롤하지 않고 눌 수 있다.
6. 마우스 휠은 콤보박스/스핀박스 값을 절대 바꾸지 않는다 (화살표·키보드로만) — 가장 가까운 스크롤 영역을 움직이거나 아무 일도 안 한다.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional

# 휠을 스스로 처리하는 위젯 (넘칠 때는 우리 핸들러가 끼어들지 않는다)
_SELF_SCROLL = ("Listbox", "Treeview", "Text", "TScrollbar", "Scrollbar")
# 휠로 값이 바뀌는 위젯
_WHEEL_VALUE = ("TCombobox", "TSpinbox")

_installed_on: "set[int]" = set()

#: 스크롤 영역 맨 아래 여백(px)
_BOTTOM_PAD = 10


# ---------------------------------------------------------------------------
# 스크롤 컨테이너
# ---------------------------------------------------------------------------

class ScrollFrame(ttk.Frame):
    """Canvas + Frame + Scrollbar 스크롤 컨테이너.

    사용::

        sf = ScrollFrame(notebook)
        panel = MyPanel(sf.body)      # 내용은 sf.body 를 부모로
        panel.pack(fill="both", expand=True)
        notebook.add(sf, text="…")

    - 안쪽 프레임(``body``) 폭 = 캔버스 폭 (내용 최소 폭보다 좁아지면 가로 스크롤바).
    - 안쪽 프레임 높이 = 캔버스 높이 (내용 최소 높이보다 낮아지면 세로 스크롤바).
    - ``request_width`` 이면 안쪽 내용의 폭만큼(+세로 스크롤바 자리)을 요청 폭으로 삼는다 — grid 의 한 칸에 넣었을 때
      그 칸이 내용 폭을 먼저 받고, 모자랄 때만 가로 스크롤이 생긴다.
    - ``max_body_width`` 를 주면 안쪽 폭의 상한 — 폼만 있는 화면이 2560px 로 늘어나지 않게 하고,
      남는 폭은 ``align`` (``"nw"`` 왼쪽 / ``"n"`` 가운데) 으로 둔다.
    """

    def __init__(
        self,
        master: tk.Misc,
        *,
        max_body_width: Optional[int] = None,
        align: str = "nw",
        request_width: bool = False,
        request_height: bool = False,
        **kw: object,
    ) -> None:
        super().__init__(master, **kw)
        self._max_w = max_body_width
        self._req_width = request_width
        self._req_height = request_height
        #: 다시 배치한 뒤 불리는 콜백 (Page 의 compact 판단용)
        self.on_layout: Optional[Callable[[], None]] = None
        self._center = align in ("n", "center")
        self._last_req = (-1, -1)
        self._bars = (False, False)
        self._last_layout: "tuple[int, int, bool, bool]" = (-1, -1, False, False)

        bg = ttk.Style(self).lookup("TFrame", "background") or self.winfo_toplevel().cget("background")
        # width/height=1: 요청 크기가 작아야 창(노트북)의 최소 크기를 내용이 밀어올리지 않는다.
        self._canvas = tk.Canvas(
            self, highlightthickness=0, borderwidth=0, background=bg, width=1, height=1,
        )
        self._vbar = ttk.Scrollbar(self, orient="vertical", command=self._canvas.yview)
        self._hbar = ttk.Scrollbar(self, orient="horizontal", command=self._canvas.xview)
        self._canvas.configure(yscrollcommand=self._vbar.set, xscrollcommand=self._hbar.set)
        self.body = ttk.Frame(self._canvas)
        self._win = self._canvas.create_window(0, 0, window=self.body, anchor="nw")

        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self._canvas.grid(row=0, column=0, sticky="nsew")
        self._vbar.grid(row=0, column=1, sticky="ns")
        self._hbar.grid(row=1, column=0, sticky="ew")
        self._vbar.grid_remove()
        self._hbar.grid_remove()

        self.bind("<Configure>", self._relayout)
        self.bind("<Map>", self._relayout)
        self.bind("<Destroy>", self._on_destroy, add="+")
        self._poll_id: Optional[str] = None
        _install_wheel(self)
        self._poll_id = self.after(250, self._poll)

    # ----- 레이아웃 -----

    def _on_destroy(self, e: tk.Event) -> None:
        if e.widget is self and self._poll_id is not None:
            try:
                self.after_cancel(self._poll_id)
            except tk.TclError:
                pass
            self._poll_id = None

    def _poll(self) -> None:
        """안쪽 내용의 요청 크기가 바뀌었는지 확인 (캔버스 창 항목은 그 변화를 이벤트로 알리지 않는다)."""
        self._poll_id = None
        try:
            if not self.winfo_exists():
                return
            req = (self.body.winfo_reqwidth(), self.body.winfo_reqheight())
            if req != self._last_req:
                self._relayout()
            self._poll_id = self.after(250, self._poll)
        except tk.TclError:
            pass

    def _regrid_canvas(self) -> None:
        try:
            self._canvas.grid(row=0, column=0, sticky="nsew")
        except tk.TclError:
            pass

    def refresh(self) -> None:
        """내용이 바뀐 뒤 즉시 다시 배치하고 싶을 때 (안 불러도 0.25초 안에 스스로 알아챈다)."""
        self.update_idletasks()
        self._relayout()

    def _relayout(self, _e: object = None) -> None:
        try:
            ow, oh = self.winfo_width(), self.winfo_height()
            rw, rh = self.body.winfo_reqwidth(), self.body.winfo_reqheight()
            self._last_req = (rw, rh)
            vb = self._vbar.winfo_reqwidth()
            hb = self._hbar.winfo_reqheight()
            if self._req_width:
                # 아직 배치 전(ow<=1)이어도 요청 폭부터 정해 둬야 grid 가 이 칸에 폭을 준다
                want = rw + vb
                if int(self._canvas.cget("width")) != want:
                    self._canvas.configure(width=want)
            if self._req_height and int(self._canvas.cget("height")) != rh:
                self._canvas.configure(height=rh)
            if ow <= 1 or oh <= 1:
                return
            need_v = rh > oh
            need_h = rw > ow - (vb if need_v else 0)
            if need_h and not need_v:
                need_v = rh > oh - hb
            cw = ow - (vb if need_v else 0)
            ch = oh - (hb if need_h else 0)

            bars = (need_v, need_h)
            if need_v:
                self._vbar.grid()
            else:
                self._vbar.grid_remove()
            if need_h:
                self._hbar.grid()
            else:
                self._hbar.grid_remove()
            if bars != self._bars:
                self._bars = bars
                # Configure 처리 도중 스크롤바를 빼면 grid 가 캔버스 크기를 다시 계산하지 않는 경우가 있다
                # (창을 줄였다 키우면 캔버스가 옛 크기로 남음) — 캔버스를 다시 grid 해서 강제로 재배치한다.
                self.after_idle(self._regrid_canvas)

            bw = max(cw, rw)
            if self._max_w is not None:
                bw = max(min(bw, self._max_w), rw)
            bh = max(ch, rh)
            x = max(0, (cw - bw) // 2) if self._center else 0
            self._canvas.coords(self._win, x, 0)
            self._canvas.itemconfigure(self._win, width=bw, height=bh)
            # 끝까지 스크롤했을 때 마지막 줄이 하단 푸터에 붙지 않도록 아래 여백을 조금 더 준다
            self._canvas.configure(
                scrollregion=(0, 0, max(bw + x, cw), bh + (_BOTTOM_PAD if need_v else 0)))
            if not need_v:
                self._canvas.yview_moveto(0)
            if not need_h:
                self._canvas.xview_moveto(0)
            self._last_layout = (cw, ch, need_v, need_h)
            if self.on_layout is not None:
                self.on_layout()
        except tk.TclError:
            pass

    # ----- 스크롤 -----

    def can_scroll_y(self) -> bool:
        return self._last_layout[2]

    def can_scroll_x(self) -> bool:
        return self._last_layout[3]

    def scroll_units(self, notches: int, horizontal: bool = False) -> bool:
        """휠 한 칸 단위로 스크롤. 실제로 움직일 수 있었는지 반환."""
        if horizontal:
            if not self.can_scroll_x():
                return False
            self._canvas.xview_scroll(notches * 3, "units")
        else:
            if not self.can_scroll_y():
                return False
            self._canvas.yview_scroll(notches * 3, "units")
        return True

    def reveal(self, widget: tk.Misc) -> None:
        """포커스를 받은 위젯이 가려져 있으면 보이는 위치로 스크롤."""
        if not self.can_scroll_y():
            return
        try:
            self.update_idletasks()
            top = widget.winfo_rooty() - self.body.winfo_rooty()
            bottom = top + widget.winfo_height()
            total = max(1, self.body.winfo_height())
            view = self._canvas.winfo_height()
            y0 = self._canvas.canvasy(0)
            if top < y0:
                self._canvas.yview_moveto(max(0, top - 8) / total)
            elif bottom > y0 + view:
                self._canvas.yview_moveto(min(total - view, bottom - view + 8) / total)
        except tk.TclError:
            pass


class AutoScrollbar(ttk.Scrollbar):
    """내용이 다 보이면(0.0~1.0) 스스로 숨는 스크롤바 — grid 로 놓은 곳에서만 쓴다 (ScrollFrame 과 같은 자동 숨김)."""

    def set(self, lo: object, hi: object) -> None:  # type: ignore[override]
        try:
            if float(lo) <= 0.0 and float(hi) >= 1.0:
                self.grid_remove()
            else:
                self.grid()
        except (tk.TclError, ValueError):
            pass
        super().set(lo, hi)


def _make_footer(parent: tk.Misc, row: int, columnspan: int = 1) -> ttk.Frame:
    """스크롤 영역 밖 하단 고정 버튼 줄 — 위에 구분선. 반환: 버튼들을 넣을 프레임."""
    box = ttk.Frame(parent)
    box.grid(row=row, column=0, columnspan=columnspan, sticky="ew")
    ttk.Separator(box, orient="horizontal").pack(side="top", fill="x", pady=(4, 0))
    bar = ttk.Frame(box)
    bar.pack(side="top", fill="x", pady=(6, 0))
    bar.box = box  # type: ignore[attr-defined]
    return bar


class Page(ttk.Frame):
    """한 줄기 화면: 위는 ScrollFrame(``body``), 아래는 스크롤 밖 고정 푸터(``footer``).

    패널 클래스가 이 클래스를 상속해 ``self.body`` 에 폼을, ``self.footer`` 에 실행 버튼 줄을 넣는다.

    ``compact=True`` : 내용이 창에 다 들어가면 푸터가 창 맨 아래가 아니라 내용 바로 아래에 붙는다 (짧은 화면에서
    입력칸과 버튼 사이가 휑하게 비지 않게). 내용이 넘치면 보통처럼 푸터가 하단에 고정되고 내용만 스크롤된다.
    """

    def __init__(
        self, master: tk.Misc, *, footer: bool = True, compact: bool = False,
        max_body_width: Optional[int] = None, align: str = "nw", **kw: object,
    ) -> None:
        super().__init__(master, **kw)
        self._compact = compact and footer
        self.columnconfigure(0, weight=1)
        self.scroll = ScrollFrame(
            self, max_body_width=max_body_width, align=align, request_height=self._compact,
        )
        self.scroll.grid(row=0, column=0, sticky="nsew")
        self.body = self.scroll.body
        self.footer: Optional[ttk.Frame] = _make_footer(self, 1) if footer else None
        if self._compact:
            self.rowconfigure(0, weight=0)
            self.rowconfigure(2, weight=1)   # 남는 높이는 푸터 아래 빈칸이 가진다
            self.scroll.on_layout = self._balance
            self.bind("<Configure>", self._balance, add="+")
        else:
            self.rowconfigure(0, weight=1)

    def _balance(self, _e: object = None) -> None:
        """내용이 들어가면 (내용 | 푸터 | 빈칸), 아니면 (스크롤 내용 | 푸터)."""
        try:
            need = self.scroll.body.winfo_reqheight() + self.footer.box.winfo_reqheight()  # type: ignore[union-attr]
            fits = need + 36 <= self.winfo_height()
            self.rowconfigure(0, weight=0 if fits else 1)
            self.rowconfigure(2, weight=1 if fits else 0)
        except tk.TclError:
            pass


class SplitPane(ttk.Frame):
    """「목록 + 상세」 화면: ``left``(목록 열) | ``right``(상세 폼, 자체 ScrollFrame) / 아래 고정 ``footer``.

    - ``left`` 는 창 높이에 묶인다 — 안의 목록/표가 남는 높이를 채우고 안에서 스크롤한다.
      검색칸·버튼처럼 고정돼야 할 것은 ``left`` 안에서 grid 로 목록 위·아래에 둔다.
    - ``right`` 는 자기 ScrollFrame 의 body — 폼이 길면 이 열만 스크롤된다.
    - ``grow="left"`` : 목록 열이 남는 폭을 가지고 폼은 내용 폭을 유지 (인물·항구).
      ``grow="right"``: 목록은 내용 폭을 유지하고 폼 열이 남는 폭을 가진다 (함선).
    """

    def __init__(
        self, master: tk.Misc, *, grow: str = "left", footer: bool = True,
        right_max_width: Optional[int] = None, **kw: object,
    ) -> None:
        super().__init__(master, **kw)
        left_grow = grow == "left"
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1 if left_grow else 0)
        self.columnconfigure(1, weight=0 if left_grow else 1)
        self.left = ttk.Frame(self)
        self.left.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        self.scroll = ScrollFrame(self, request_width=left_grow, max_body_width=right_max_width)
        self.scroll.grid(row=0, column=1, sticky="nsew")
        self.right = self.scroll.body
        self.footer: Optional[ttk.Frame] = None
        if footer:
            self.rowconfigure(1, weight=0)
            self.footer = _make_footer(self, 1, columnspan=2)


def add_scroll_page(
    notebook: ttk.Notebook,
    factory: Callable[[tk.Misc], tk.Misc],
    text: str,
    *,
    max_body_width: Optional[int] = None,
    align: str = "nw",
    **add_kw: object,
):
    """노트북에 ``text`` 탭을 만들되 내용을 ScrollFrame 으로 감싼다.

    ``factory(parent)`` 가 만든 패널(부모=ScrollFrame.body)을 돌려준다. 반환: ``(패널, ScrollFrame)``.
    """
    sf = ScrollFrame(notebook, max_body_width=max_body_width, align=align)
    panel = factory(sf.body)
    panel.pack(fill="both", expand=True)
    notebook.add(sf, text=text, **add_kw)
    return panel, sf


# ---------------------------------------------------------------------------
# 휠 / 포커스 처리 (프로그램 전체에서 한 번만 설치)
# ---------------------------------------------------------------------------

def _scroll_frame_of(widget: Optional[tk.Misc]) -> "list[ScrollFrame]":
    """widget 의 조상 중 ScrollFrame 들 (안쪽 → 바깥)."""
    out: "list[ScrollFrame]" = []
    w = widget
    while w is not None:
        if isinstance(w, ScrollFrame):
            out.append(w)
        w = getattr(w, "master", None)
    return out


def _self_scroll_can_move(w: tk.Misc, notches: int) -> bool:
    """Listbox/Treeview/Text 가 이 휠 방향으로 더 움직일 수 있는가."""
    try:
        first, last = w.yview()  # type: ignore[attr-defined]
    except Exception:
        return False
    if first <= 0.0 and last >= 1.0:
        return False  # 넘치지 않음 → 바깥이 받는다
    if notches > 0:   # 위로
        return first > 0.0
    return last < 1.0


def _on_wheel(event: tk.Event, horizontal: bool = False) -> Optional[str]:
    try:
        w = event.widget.winfo_containing(event.x_root, event.y_root)
    except (tk.TclError, KeyError, AttributeError):
        return None
    if w is None:
        return None
    notches = int(event.delta / 120) if event.delta else 0
    if notches == 0:
        notches = 1 if event.delta > 0 else -1
    cls = w.winfo_class()
    if cls in _SELF_SCROLL and not horizontal and _self_scroll_can_move(w, notches):
        return None
    if cls in _WHEEL_VALUE:
        # 클래스 바인딩(_class_wheel)이 이미 처리했다
        return None
    for sf in _scroll_frame_of(w):
        if sf.scroll_units(-notches, horizontal):
            return "break"
    return None


def _class_wheel(event: tk.Event) -> str:
    """콤보박스/스핀박스 휠: 값은 절대 바꾸지 않는다. 가장 가까운 스크롤 영역이 움직일 수 있으면 그것을 스크롤, 아니면 무시."""
    notches = int(event.delta / 120) if event.delta else 0
    for sf in _scroll_frame_of(event.widget):
        if sf.scroll_units(-notches):
            break
    return "break"


def _on_focus_in(event: tk.Event) -> None:
    for sf in _scroll_frame_of(event.widget):
        sf.reveal(event.widget)


def install_wheel_policy(widget: tk.Misc) -> None:
    """휠 정책을 프로그램 전체에 한 번 설치 (ScrollFrame 생성 시 자동, 앱 시작 때 명시 호출도 가능)."""
    _install_wheel(widget)


def _install_wheel(widget: tk.Misc) -> None:
    root = widget.winfo_toplevel()
    key = id(widget._root())  # type: ignore[attr-defined]
    if key in _installed_on:
        return
    _installed_on.add(key)
    root.bind_all("<MouseWheel>", lambda e: _on_wheel(e, False), add="+")
    root.bind_all("<Shift-MouseWheel>", lambda e: _on_wheel(e, True), add="+")
    root.bind_all("<FocusIn>", _on_focus_in, add="+")
    for cls in _WHEEL_VALUE:
        root.bind_class(cls, "<MouseWheel>", _class_wheel)


# ---------------------------------------------------------------------------
# 창 크기 / 위치
# ---------------------------------------------------------------------------

#: 작업표시줄·창 테두리 여유 (화면 가장자리에서 띄우는 픽셀)
_SCREEN_MARGIN = 40


def fit_main_window(
    root: tk.Tk,
    min_size: "tuple[int, int]" = (780, 560),
    pref_size: "tuple[int, int]" = (1180, 780),
    max_frac: float = 0.9,
) -> None:
    """메인 창의 최소/기본 크기와 위치를 화면에 맞춰 정한다.

    기본 크기 = ``pref_size`` 와 (화면 × ``max_frac``) 중 작은 쪽, 최소 크기보다는 작아지지 않는다.
    화면 가운데에 놓는다. 1366x768 에서도 창 전체가 화면 안에 들어온다.
    """
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    min_w = min(min_size[0], sw - _SCREEN_MARGIN)
    min_h = min(min_size[1], sh - _SCREEN_MARGIN - 40)
    w = max(min_w, min(pref_size[0], int(sw * max_frac)))
    h = max(min_h, min(pref_size[1], int(sh * max_frac) - 40))
    x = max(0, (sw - w) // 2)
    y = max(0, (sh - h) // 2 - 20)
    root.minsize(min_w, min_h)
    root.geometry(f"{w}x{h}+{x}+{y}")


def place_dialog(
    win: tk.Toplevel,
    parent: tk.Misc,
    *,
    min_size: "tuple[int, int]" = (360, 200),
    vfrac: float = 0.5,
    resizable: bool = True,
) -> None:
    """대화상자를 내용 크기에 맞추되 화면 밖으로 넘지 않게 하고, 부모 위에 가운데 놓는다.

    내용이 화면보다 크면 창을 화면 크기로 줄인다 (대화상자 안쪽이 스크롤/줄바꿈을 맡는다).
    ``resizable`` 이면 최소 크기를 걸어 둔다.
    """
    win.update_idletasks()
    sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
    w = min(win.winfo_reqwidth(), sw - _SCREEN_MARGIN)
    h = min(win.winfo_reqheight(), sh - _SCREEN_MARGIN - 40)
    try:
        px, py = parent.winfo_rootx(), parent.winfo_rooty()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        x = px + (pw - w) // 2
        y = py + int((ph - h) * vfrac)
    except tk.TclError:
        x, y = (sw - w) // 2, (sh - h) // 3
    x = max(0, min(x, sw - w))
    y = max(0, min(y, sh - h - 40))
    win.geometry(f"{w}x{h}+{x}+{y}")
    if resizable:
        win.minsize(min(min_size[0], w), min(min_size[1], h))


# ---------------------------------------------------------------------------
# 줄바꿈 따라가기
# ---------------------------------------------------------------------------

def track_wraplength(label: tk.Misc, pad: int = 8, min_wrap: int = 160, initial: int = 480) -> None:
    """라벨의 wraplength 를 라벨이 놓인 폭에 맞춰 계속 갱신 (고정 wraplength 로 잘리거나 남는 것 방지).

    라벨은 ``sticky="ew"``/``fill="x"`` 로 폭을 받는 위치에 있어야 한다.
    요청 폭은 1글자로 낮춘다 — 안 그러면 한 번 넓어진 줄바꿈 폭이 요청 폭으로 남아 창을 줄여도 안 줄어든다.
    """
    try:
        label.configure(width=1, wraplength=initial)
    except tk.TclError:
        pass

    def _upd(e: tk.Event) -> None:
        try:
            label.configure(wraplength=max(min_wrap, e.width - pad))
        except tk.TclError:
            pass
    label.bind("<Configure>", _upd, add="+")
