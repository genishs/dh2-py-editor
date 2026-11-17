"""창 크기 대응 레이아웃(layout.py) + 게임 전체 탭 배치 시험.

위젯이 필요한 시험은 화면(Tk)이 없으면 건너뛴다. 실행:  python -m unittest discover -s tests -v
"""
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import tkinter as tk  # noqa: E402
from tkinter import ttk  # noqa: E402

from horiedit_py.gui import layout  # noqa: E402

GUI_DIR = Path(__file__).resolve().parent.parent / "horiedit_py" / "gui"


class _FakeRoot:
    """fit_main_window 가 쓰는 부분만 흉내 — 화면 크기별 결과를 화면 없이 확인."""

    def __init__(self, sw, sh):
        self._sw, self._sh = sw, sh
        self.min = None
        self.geom = None

    def winfo_screenwidth(self):
        return self._sw

    def winfo_screenheight(self):
        return self._sh

    def minsize(self, w, h):
        self.min = (w, h)

    def geometry(self, g):
        self.geom = g


def _parse(geom):
    size, x, y = geom.replace("+", " ").split()
    w, h = size.split("x")
    return int(w), int(h), int(x), int(y)


class FitMainWindowTest(unittest.TestCase):
    def _fit(self, sw, sh):
        r = _FakeRoot(sw, sh)
        layout.fit_main_window(r, (800, 620), (1180, 780))
        w, h, x, y = _parse(r.geom)
        return r.min, (w, h, x, y)

    def test_fits_1366x768(self):
        (mw, mh), (w, h, x, y) = self._fit(1366, 768)
        self.assertGreaterEqual(w, mw)
        self.assertGreaterEqual(h, mh)
        # 작업표시줄(약 40px) 을 빼도 창 전체가 화면 안에 있다
        self.assertLessEqual(x + w, 1366)
        self.assertLessEqual(y + h, 768 - 40)
        self.assertGreaterEqual(x, 0)
        self.assertGreaterEqual(y, 0)

    def test_large_screen_uses_preferred_size_and_centers(self):
        (mw, mh), (w, h, x, y) = self._fit(2560, 1600)
        self.assertEqual((w, h), (1180, 780))     # 큰 화면이라도 선호 크기 — 늘리지 않는다
        self.assertAlmostEqual(x, (2560 - 1180) // 2, delta=2)

    def test_min_never_exceeds_screen(self):
        (mw, mh), _ = self._fit(1024, 600)
        self.assertLessEqual(mw, 1024)
        self.assertLessEqual(mh, 600)


class ScrollFrameTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.root = tk.Tk()
        except tk.TclError as e:  # 화면 없음
            raise unittest.SkipTest(f"Tk 화면 없음: {e}")
        cls.root.geometry("+0+0")

    @classmethod
    def tearDownClass(cls):
        try:
            cls.root.destroy()
        except Exception:
            pass

    def _make(self, content_w, content_h, win_w, win_h, **kw):
        sf = layout.ScrollFrame(self.root, **kw)
        sf.pack(fill="both", expand=True)
        inner = tk.Frame(sf.body, width=content_w, height=content_h, background="#ccc")
        inner.pack_propagate(False)
        inner.pack(fill="both", expand=True)
        self.root.geometry(f"{win_w}x{win_h}")
        for _ in range(4):
            self.root.update_idletasks()
            self.root.update()
        return sf, inner

    def test_no_scrollbars_when_content_fits_and_body_fills(self):
        sf, inner = self._make(300, 200, 600, 500)
        try:
            self.assertFalse(sf.can_scroll_y())
            self.assertFalse(sf.can_scroll_x())
            self.assertFalse(sf._vbar.winfo_ismapped())
            self.assertFalse(sf._hbar.winfo_ismapped())
            # 안쪽이 창을 꽉 채운다 (목록·표가 창 크기를 따라 커진다)
            self.assertGreaterEqual(inner.winfo_width(), 590)
            self.assertGreaterEqual(inner.winfo_height(), 490)
        finally:
            sf.destroy()

    def test_vertical_scrollbar_when_too_tall(self):
        sf, inner = self._make(300, 900, 600, 400)
        try:
            self.assertTrue(sf.can_scroll_y())
            self.assertTrue(sf._vbar.winfo_ismapped())
            self.assertFalse(sf._hbar.winfo_ismapped())
            self.assertEqual(inner.winfo_height(), 900)   # 내용은 잘리지 않고 제 높이를 가진다
            self.assertTrue(sf.scroll_units(1))
            self.assertGreater(sf._canvas.yview()[0], 0.0)
        finally:
            sf.destroy()

    def test_horizontal_scrollbar_when_too_wide(self):
        sf, inner = self._make(1000, 100, 500, 400)
        try:
            self.assertTrue(sf.can_scroll_x())
            self.assertTrue(sf._hbar.winfo_ismapped())
            self.assertEqual(inner.winfo_width(), 1000)
        finally:
            sf.destroy()

    def test_scrollbar_disappears_when_window_grows(self):
        sf, inner = self._make(300, 500, 600, 300)
        try:
            self.assertTrue(sf._vbar.winfo_ismapped())
            self.root.geometry("600x700")
            for _ in range(4):
                self.root.update_idletasks()
                self.root.update()
            self.assertFalse(sf._vbar.winfo_ismapped())
            self.assertEqual(sf._canvas.yview()[0], 0.0)
        finally:
            sf.destroy()

    def test_max_body_width_caps_and_left_aligns(self):
        sf, inner = self._make(300, 100, 1200, 400, max_body_width=500)
        try:
            self.assertEqual(inner.winfo_width(), 500)
        finally:
            sf.destroy()

    def test_content_growth_is_noticed(self):
        sf, inner = self._make(300, 100, 600, 300)
        try:
            self.assertFalse(sf._vbar.winfo_ismapped())
            inner.configure(height=800)
            sf.refresh()                       # 즉시 반영
            self.assertTrue(sf.can_scroll_y())
            self.root.update()
            self.assertTrue(sf._vbar.winfo_ismapped())
            inner.configure(height=100)        # refresh 없이도 폴링이 알아챈다
            import time
            end = time.time() + 1.0
            while time.time() < end and sf._vbar.winfo_ismapped():
                self.root.update()
                time.sleep(0.05)
            self.assertFalse(sf._vbar.winfo_ismapped())
        finally:
            sf.destroy()

    def test_wheel_scrolls_only_container_under_pointer(self):
        """중첩된 스크롤 영역에서 안쪽이 넘칠 때만 안쪽이, 아니면 바깥이 받는다."""
        outer = layout.ScrollFrame(self.root)
        outer.pack(fill="both", expand=True)
        tk.Frame(outer.body, width=300, height=1500).pack()
        self.root.geometry("500x300")
        for _ in range(4):
            self.root.update_idletasks()
            self.root.update()
        try:
            self.assertTrue(outer.scroll_units(1))
            self.assertGreater(outer._canvas.yview()[0], 0.0)
            outer._canvas.yview_moveto(0)
            inner_only = layout.ScrollFrame(self.root)   # 안 넘치는 컨테이너는 휠을 소비하지 않는다
            self.assertFalse(inner_only.scroll_units(1))
            inner_only.destroy()
        finally:
            outer.destroy()


class GameWidePlacementTest(unittest.TestCase):
    """[게임 전체] 탭 구성 · [항구] 탭에 공급 수치 · 운하 정식 기능화."""

    @classmethod
    def setUpClass(cls):
        try:
            cls.root = tk.Tk()
        except tk.TclError as e:
            raise unittest.SkipTest(f"Tk 화면 없음: {e}")

    @classmethod
    def tearDownClass(cls):
        try:
            cls.root.destroy()
        except Exception:
            pass

    def test_game_wide_subtab_order_and_missing_mainexe(self):
        from horiedit_py.common import EditorState
        from horiedit_py.gui.settings_tab import SettingsTab
        st = EditorState()          # game_dir 없음 → MAIN.EXE 없음
        tab = SettingsTab(self.root, st)
        try:
            nb = tab._notebook
            texts = [nb.tab(i, "text") for i in range(len(nb.tabs()))]
            self.assertEqual(texts, ["함선 기본 성능", "함선 이름·모양", "신조 내구도 상한", "운하"])
            # MAIN.EXE 가 없어도 sub-tab 은 모두 있다 (운하는 WORLDMAP.LZW 만 필요)
            self.assertIsNotNone(tab._canal_panel)
            self.assertIsNotNone(tab._hull_cap_panel)
            self.assertIsNone(tab._ship4_panel)
            # 이 탭에는 세이브 칸 데이터(항구 공급 수치)가 없다
            self.assertFalse(hasattr(tab, "_supply_panel"))
            self.assertFalse(tab.is_dirty())
            tab.select_subtab("canal")
            self.assertEqual(nb.select(), str(tab._sub_pages["canal"]))
        finally:
            tab.destroy()

    def test_port_tab_has_supply_and_shares_dirty(self):
        from horiedit_py.common import EditorState
        from horiedit_py.gui.port_tab import PortTab
        tab = PortTab(self.root, EditorState())
        try:
            nb = tab._nb
            texts = [nb.tab(i, "text") for i in range(len(nb.tabs()))]
            self.assertEqual(texts, ["상업치 · 공업치", "공급 수치 (효과 불확실)"])
            seen = []
            tab.add_dirty_listener(lambda: seen.append(1))
            # 공급 수치 패널의 dirty 가 [항구] 탭의 dirty 로 보이고 리스너(메인 저장 버튼)에 전달된다
            sup = tab._supply
            sup._enabled = True
            sup._set_dirty(True)
            self.assertTrue(tab.is_dirty())
            self.assertTrue(seen)
        finally:
            tab.destroy()


class CanalOfficialWordingTest(unittest.TestCase):
    """운하는 정식 기능 — 「시험 기능」 문구가 없고, 안전 문구(원상복원 경고·게임 폴더 단위)는 남아 있다."""

    def test_no_experimental_wording_for_canal(self):
        panel = (GUI_DIR / "canal_panel.py").read_text(encoding="utf-8")
        self.assertNotIn("시험", panel)
        help_src = (GUI_DIR / "help_dialog.py").read_text(encoding="utf-8")
        for line in help_src.splitlines():
            if "운하" in line:
                self.assertNotIn("시험", line, line)

    def test_safety_texts_kept(self):
        from horiedit_py.gui import canal_logic as L
        panel = (GUI_DIR / "canal_panel.py").read_text(encoding="utf-8")
        self.assertIn("logic.SCOPE_NOTE", panel)
        self.assertIn("갇힐 수 있습니다", L.RESTORE_WARNING)
        self.assertIn("게임 폴더 단위", L.SCOPE_NOTE)

    def test_apply_mode_stated(self):
        panel = (GUI_DIR / "canal_panel.py").read_text(encoding="utf-8")
        self.assertIn("바로 게임 파일(WORLDMAP.LZW)에 반영", panel)
        hull = (GUI_DIR / "hull_cap_panel.py").read_text(encoding="utf-8")
        self.assertIn("바로 게임 파일(MAIN.EXE)에 반영", hull)
        st = (GUI_DIR / "settings_tab.py").read_text(encoding="utf-8")
        self.assertIn("[저장]을 눌러야 반영", st)


if __name__ == "__main__":
    unittest.main()
