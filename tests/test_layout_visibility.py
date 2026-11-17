"""회귀 시험 — 실행 버튼이 스크롤 없이 보이는가 / 가로 스크롤이 생기지 않는가 (실제 앱 + 세이브 복사본).

「스크롤바로 닿을 수 있으면 OK」 로 세면 놓치는 문제를 잡는다: 버튼이 스크롤 영역 안에 있어 접힌 아래로 밀리거나,
불러온 데이터(긴 문구)가 폼의 요청 폭을 키워 가로 스크롤이 생기는 경우.

- 창 크기 1180×780 · 1366×768 · 1280×720 (그리고 최소 크기 800×620) 에서
  모든 탭/sub-tab, 인물·함선·항구를 불러온 상태까지 확인한다.
- 화면(Tk)이 없거나 `originalgame/koukai2/KOUKAI2.DAT` 가 없으면 건너뛴다.
"""
import os
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import tkinter as tk  # noqa: E402
from tkinter import ttk  # noqa: E402

GAME = ROOT / "originalgame" / "koukai2"
def _make_root():
    """Tk 루트 생성. 화면이 없으면 건너뛴다. (tk.tcl 읽기가 드물게 일시 실패하는 환경이 있어 몇 번 다시 시도)"""
    last = None
    for _ in range(4):
        try:
            return tk.Tk()
        except tk.TclError as e:
            last = e
            time.sleep(0.4)
    raise unittest.SkipTest(f"Tk 화면 없음: {last}")


SIZES_MUST = ("1180x780", "1366x768", "1280x720")
SIZES_MIN = ("800x620",)


def _walk(w):
    yield w
    for c in w.winfo_children():
        yield from _walk(c)


def _outside(w):
    """w 가 조상 위젯들의 실제 영역 안에 다 들어 있지 않으면 설명 문자열, 아니면 None."""
    x0, y0 = w.winfo_rootx(), w.winfo_rooty()
    x1, y1 = x0 + w.winfo_width(), y0 + w.winfo_height()
    p = w.master
    while p is not None:
        px0, py0 = p.winfo_rootx(), p.winfo_rooty()
        px1, py1 = px0 + p.winfo_width(), py0 + p.winfo_height()
        if x0 < px0 - 1 or y0 < py0 - 1 or x1 > px1 + 1 or y1 > py1 + 1:
            return f"{p.winfo_class()} {str(p)[-36:]} 밖으로 나감 w=({x0},{y0},{x1},{y1}) p=({px0},{py0},{px1},{py1})"
        p = getattr(p, "master", None)
    return None


@unittest.skipUnless((GAME / "KOUKAI2.DAT").is_file(), "originalgame/koukai2/KOUKAI2.DAT 없음")
class ButtonVisibilityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="dh2-layout-")
        for name in ("KOUKAI2.DAT", "MAIN.EXE", "WORLDMAP.LZW", "worldmap.lzw"):
            src = GAME / name
            if src.is_file() and not (Path(cls.tmp) / name).exists():
                shutil.copy(src, Path(cls.tmp) / name)
        (Path(cls.tmp) / ".dh2editor_seen").write_text("0", encoding="utf-8")

        from horiedit_py.common import state
        from horiedit_py.data import slot_is_used
        from horiedit_py.gui import app as appmod, shortcut_ui
        cls._orig_prompt = shortcut_ui.maybe_prompt_on_start
        shortcut_ui.maybe_prompt_on_start = lambda *a, **k: None
        save = Path(cls.tmp) / "KOUKAI2.DAT"
        state.fp = open(save, "r+b")
        state.page = 0
        state.eXit = 0
        state.game_dir = save.resolve().parent
        cls.state = state
        cls.root = _make_root()
        cls.app = appmod.EditorApp(cls.root, save, False)
        cls.root.update()
        used = [i for i in range(10) if slot_is_used(state, i)]
        if not used:
            raise unittest.SkipTest("사용 중인 세이브 칸 없음")
        cls.app._on_slot_request(used[0])
        cls.root.update()

    @classmethod
    def tearDownClass(cls):
        from horiedit_py.gui import shortcut_ui
        try:
            cls.app._cancel_tip()
            cls.root.destroy()
        except Exception:
            pass
        try:
            cls.state.fp.close()
        except Exception:
            pass
        shortcut_ui.maybe_prompt_on_start = cls._orig_prompt
        shutil.rmtree(cls.tmp, ignore_errors=True)

    # ---- helpers ----

    def _settle(self, n=6):
        for _ in range(n):
            self.root.update_idletasks()
            self.root.update()
            time.sleep(0.02)

    def _resize(self, size):
        w, h = map(int, size.split("x"))
        self.root.state("normal")
        self.root.geometry(f"{w}x{h}+10+10")
        self._settle(8)

    def _all_tabs(self):
        nb = self.app._notebook
        out = []
        for t in nb.tabs():
            name = nb.tab(t, "text")
            subs = [d for d in _walk(nb.nametowidget(t)) if isinstance(d, ttk.Notebook)]
            if not subs:
                out.append((name, t, None, None))
            else:
                sub = subs[0]
                for st in sub.tabs():
                    out.append((f"{name}/{sub.tab(st, 'text')}", t, sub, st))
        return out

    def _audit(self, label):
        """현재 보이는 탭의 문제 목록: 잘린 버튼, 가로 스크롤."""
        from horiedit_py.gui.layout import ScrollFrame
        page = self.app._notebook.nametowidget(self.app._notebook.select())
        problems = []
        for b in _walk(page):
            if b.winfo_class() in ("TButton", "Button") and b.winfo_viewable():
                why = _outside(b)
                if why:
                    problems.append(f"[{label}] 버튼 '{b.cget('text')}' {why}")
        for s in _walk(page):
            if not (isinstance(s, ScrollFrame) and s.winfo_viewable()):
                continue
            if s.can_scroll_x():
                problems.append(f"[{label}] 가로 스크롤 발생: {str(s)[-40:]} body_req={s.body.winfo_reqwidth()}")
            c = s._canvas
            ch, cw = c.winfo_height(), c.winfo_width()
            # 잘리는데 스크롤바가 없음 (스크롤바로 닿을 수 있어야 한다)
            if s.body.winfo_reqheight() > ch + 1 and not s._vbar.winfo_ismapped():
                problems.append(f"[{label}] 세로로 잘리는데 스크롤바 없음: {str(s)[-40:]} req_h={s.body.winfo_reqheight()} view_h={ch}")
            # 캔버스가 자기 컨테이너를 못 채움 (창 크기를 줄였다 키운 뒤의 옛 크기 잔류)
            bar_w = s._vbar.winfo_width() if s._vbar.winfo_ismapped() else 0
            bar_h = s._hbar.winfo_height() if s._hbar.winfo_ismapped() else 0
            if abs(cw - (s.winfo_width() - bar_w)) > 2 or abs(ch - (s.winfo_height() - bar_h)) > 2:
                problems.append(f"[{label}] 스크롤 캔버스가 컨테이너를 못 채움: {str(s)[-40:]} canvas={cw}x{ch} outer={s.winfo_width()}x{s.winfo_height()}")
        return problems

    def _load_states(self, size):
        """사람·함선·항구를 불러온 상태에서도 확인 (긴 문구가 폼 폭을 키우는지)."""
        app, out = self.app, []
        pt = app._person_tab
        app._notebook.select(app._notebook.tabs()[1])   # 인물
        self._settle()
        pt._on_all_clicked()
        self._settle()
        kids = pt._tv.get_children()
        self.assertTrue(kids, "인물 목록이 비어 있음")
        for k in (0, 3, 6):
            if k < len(kids):
                pt._tv.selection_set(kids[k])
                pt._tv.focus(kids[k])
                pt._on_select_clicked()
                self._settle(8)
                out += self._audit(f"{size} 인물 불러옴 #{k}")
        app._notebook.select(app._notebook.tabs()[2])   # 선박
        app._ship_tab._notebook.select(1)
        self._settle()
        org = app._ship_tab._org
        org._listbox.selection_clear(0, "end")
        org._listbox.selection_set(3)
        org._listbox.event_generate("<<ListboxSelect>>")
        self._settle()
        out += self._audit(f"{size} 선박 선택")
        app._notebook.select(app._notebook.tabs()[3])   # 항구
        app._port_tab._nb.select(1)
        self._settle()
        sup = app._port_tab._supply
        sup._listbox.selection_clear(0, "end")
        sup._listbox.selection_set(5)
        sup._listbox.event_generate("<<ListboxSelect>>")
        self._settle()
        out += self._audit(f"{size} 항구 공급 수치 선택")
        return out

    def _run(self, sizes):
        problems = []
        for size in sizes:
            self._resize(size)
            for name, t, sub, st in self._all_tabs():
                self.app._notebook.select(t)
                if sub is not None:
                    sub.select(st)
                self._settle()
                problems += self._audit(f"{size} {name}")
            problems += self._load_states(size)
        return problems

    # ---- tests ----

    def test_buttons_visible_and_no_hscroll_at_common_sizes(self):
        problems = self._run(SIZES_MUST)
        self.assertEqual(problems, [], "\n".join(problems))

    def test_buttons_visible_and_no_hscroll_at_minimum_size(self):
        self.assertGreaterEqual(self.root.minsize()[0], 800)
        problems = self._run(SIZES_MIN)
        self.assertEqual(problems, [], "\n".join(problems))

    def test_person_form_does_not_widen_after_load(self):
        """인물을 불러와도(긴 소속 문구) 폼의 요청 폭이 커지지 않는다 — 가로 스크롤의 원인."""
        self._resize("1180x780")
        pt = self.app._person_tab
        self.app._notebook.select(self.app._notebook.tabs()[1])   # 인물
        self._settle()
        pt._on_all_clicked()
        self._settle()
        before = pt.scroll.body.winfo_reqwidth()
        kids = pt._tv.get_children()
        for k in (0, 3, 6):
            pt._tv.selection_set(kids[k])
            pt._tv.focus(kids[k])
            pt._on_select_clicked()
            self._settle(8)
            self.assertLessEqual(pt.scroll.body.winfo_reqwidth(), before + 2, f"인물 #{k} 불러온 뒤 폼 폭이 커짐")
        self.assertFalse(pt.scroll.can_scroll_x())

    @unittest.skipUnless(sys.platform == "win32", "Windows 휠 이벤트")
    def test_wheel_never_changes_spinbox_or_combobox_value(self):
        """휠은 콤보박스/스핀박스 값을 바꾸지 않는다 (페이지가 스크롤 가능하든 아니든)."""
        self._resize("1180x780")
        hero = self.app._hero_tab
        self.app._notebook.select(self.app._notebook.tabs()[0])
        self._settle()
        spins = [w for w in _walk(hero) if w.winfo_class() == "TSpinbox" and w.winfo_viewable()]
        combos = [w for w in _walk(hero) if w.winfo_class() == "TCombobox" and w.winfo_viewable()]
        self.assertTrue(spins and combos)
        for w in (spins[0], combos[-1]):
            v0 = w.get()
            for delta in (-120, 120, -360):
                w.event_generate("<MouseWheel>", delta=delta, x=3, y=3)
                self._settle(2)
            self.assertEqual(w.get(), v0, f"{w.winfo_class()} 값이 휠로 바뀜")
        self.assertFalse(self.app._any_tab_dirty(), "휠이 값을 바꿔 dirty 가 됨")


if __name__ == "__main__":
    unittest.main()
