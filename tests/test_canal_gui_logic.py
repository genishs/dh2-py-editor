"""운하 화면 결정 로직 단위 시험 (위젯 없음) — canal_logic + canal 파일 적용 연동.

실행:  python -m unittest discover -s tests -v
"""
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))

from horiedit_py.data import canal, ls11  # noqa: E402
from horiedit_py.gui import canal_logic as L  # noqa: E402
from test_ls11_canal import ORIG, _synthetic_parts  # noqa: E402


def _write_synth(path, closed=True):
    with open(path, "wb") as f:
        f.write(ls11.encode_pack(_synthetic_parts(closed)))


def _read(path):
    with open(path, "rb") as f:
        return f.read()


class FindWorldmapTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_case_insensitive(self):
        for i, name in enumerate(("WORLDMAP.LZW", "worldmap.lzw", "WorldMap.Lzw")):
            d = self.dir / f"d{i}"
            d.mkdir()
            (d / name).write_bytes(b"x")
            found = L.find_worldmap(d)
            self.assertIsNotNone(found)
            self.assertEqual(found.name, name)

    def test_missing_none_and_dir_ignored(self):
        self.assertIsNone(L.find_worldmap(self.dir))
        (self.dir / "WORLDMAP.LZW").mkdir()  # 같은 이름의 폴더는 지도 파일이 아니다
        self.assertIsNone(L.find_worldmap(self.dir))
        self.assertIsNone(L.find_worldmap(None))
        self.assertIsNone(L.find_worldmap(self.dir / "없는폴더"))

    def test_does_not_match_backup_or_other_names(self):
        (self.dir / "WORLDMAP.LZW.canal-orig").write_bytes(b"x")
        (self.dir / "WORLDMAP.LZW.bak").write_bytes(b"x")
        self.assertIsNone(L.find_worldmap(self.dir))


class DescribeRowTest(unittest.TestCase):
    def test_open(self):
        r = L.describe_row("suez", canal.OPEN)
        self.assertEqual((r.name, r.status_text, r.button_label, r.button_enabled, r.target_mode),
                         ("수에즈 운하", "개통됨", "원상복원", True, canal.CLOSED))

    def test_closed(self):
        r = L.describe_row("panama", canal.CLOSED)
        self.assertEqual((r.name, r.status_text, r.button_label, r.button_enabled, r.target_mode),
                         ("파나마 운하", "원상(닫힘)", "개통", True, canal.OPEN))

    def test_unknown_disabled(self):
        r = L.describe_row("suez", canal.UNKNOWN)
        self.assertFalse(r.button_enabled)
        self.assertIsNone(r.target_mode)
        self.assertEqual(r.status_text, "알 수 없음 — 다른 패치가 적용된 것으로 보여 바꾸지 않습니다")

    def test_unreadable_disabled(self):
        for rows in (L.describe_rows(None), L.describe_rows({})):
            self.assertEqual([r.key for r in rows], ["suez", "panama"])
            self.assertTrue(all(not r.button_enabled and r.target_mode is None for r in rows))

    def test_rows_independent(self):
        rows = L.describe_rows({"suez": canal.OPEN, "panama": canal.UNKNOWN})
        self.assertTrue(rows[0].button_enabled)
        self.assertFalse(rows[1].button_enabled)


class MessageTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.p = Path(self.tmp.name) / "worldmap.lzw"
        self.p.write_bytes(b"x")

    def tearDown(self):
        self.tmp.cleanup()

    def test_confirm_has_required_points(self):
        for mode in (canal.OPEN, canal.CLOSED):
            m = L.confirm_message("suez", mode, self.p)
            self.assertIn("수에즈 운하", m)
            self.assertIn("DOSBox", m)
            self.assertIn("worldmap.lzw.canal-orig", m)   # 실제 파일 이름 대소문자 그대로
            self.assertIn("자동 이동", m)
            self.assertIn("직접 조종", m)
        self.assertIn("개통합니다", L.confirm_message("suez", canal.OPEN, self.p))
        self.assertIn("원래 상태(닫힘)", L.confirm_message("panama", canal.CLOSED, self.p))

    def test_restore_confirm_warns_about_saves_inside_canal(self):
        """원상복원(닫기) 확인 창에만 「운하 안에서 저장한 세이브 → 함대가 갇힘」 경고가 들어간다."""
        for key in ("suez", "panama"):
            closing = L.confirm_message(key, canal.CLOSED, self.p)
            self.assertIn(L.RESTORE_WARNING, closing)
            for frag in ("운하 안(또는 바로 근처 수로)에서 저장한 세이브", "함대가 육지 위에 놓여 갇힐 수 있습니다",
                         "완전히 빠져나온 곳에서 저장한 뒤 닫으세요"):
                self.assertIn(frag, closing)
            opening = L.confirm_message(key, canal.OPEN, self.p)
            self.assertNotIn("갇힐", opening)
            self.assertNotIn(L.RESTORE_WARNING, opening)
        # 경고는 마지막 질문 바로 앞에 와서 눈에 띈다
        closing = L.confirm_message("suez", canal.CLOSED, self.p)
        self.assertLess(closing.index(L.RESTORE_WARNING), closing.index("계속할까요?"))

    def test_scope_note_is_per_game_folder(self):
        """「게임 폴더 단위」 안내가 정의돼 있고 운하 탭 안내문·처음 사용 안내에 실려 있다."""
        self.assertIn("게임 폴더 단위", L.SCOPE_NOTE)
        self.assertIn("모든 세이브", L.SCOPE_NOTE)
        self.assertIn("새 게임", L.SCOPE_NOTE)
        import pathlib
        root = pathlib.Path(__file__).resolve().parent.parent / "horiedit_py" / "gui"
        panel_src = (root / "canal_panel.py").read_text(encoding="utf-8")
        self.assertIn("logic.SCOPE_NOTE", panel_src)          # 탭 상단 안내문(_INTRO)에 포함
        help_src = (root / "help_dialog.py").read_text(encoding="utf-8")
        self.assertIn("게임 폴더 단위", help_src)            # 처음 사용 안내
        readme = (root.parent.parent / "README.md").read_text(encoding="utf-8")
        self.assertIn("게임 폴더 단위", readme)              # README 운하 절

    def test_confirm_mentions_existing_backup(self):
        self.assertIn("첫 변경", L.confirm_message("suez", canal.OPEN, self.p))
        L.backup_path(self.p).write_bytes(b"orig")
        m = L.confirm_message("suez", canal.OPEN, self.p)
        self.assertIn("이미 있어", m)
        self.assertNotIn("첫 변경", m)

    def test_error_messages_say_file_unchanged(self):
        errs = [canal.CanalError("x: 바꾸지 않음"), ls11.Ls11Error("bad"),
                PermissionError("denied"), OSError("io"), RuntimeError("boom")]
        for e in errs:
            m = L.error_message(e, self.p)
            self.assertIn("바뀌지 않았습니다", m)
            self.assertIn("worldmap.lzw", m)
        self.assertIn("DOSBox", L.error_message(PermissionError("d"), self.p))


class ApplyToggleScenarioTest(unittest.TestCase):
    """닫힘 → 개통 → 원상복원 (합성 파일)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.path = self.dir / "worldmap.lzw"
        _write_synth(self.path, closed=True)

    def tearDown(self):
        self.tmp.cleanup()

    def states(self):
        s, err = L.read_states(self.path)
        self.assertIsNone(err)
        return s

    def test_closed_open_restore(self):
        orig = _read(self.path)
        self.assertEqual(self.states(), {"suez": "closed", "panama": "closed"})
        # 개통
        r = L.apply_toggle(self.path, "suez", canal.CLOSED)
        self.assertTrue(r.ok and r.changed)
        self.assertEqual(r.states, {"suez": "open", "panama": "closed"})
        self.assertEqual(_read(L.backup_path(self.path)), orig)
        # 다른 운하도 개통
        r = L.apply_toggle(self.path, "panama", canal.CLOSED)
        self.assertEqual(r.states, {"suez": "open", "panama": "open"})
        # 백업은 처음 것 그대로
        self.assertEqual(_read(L.backup_path(self.path)), orig)
        # 원상복원
        for key in ("suez", "panama"):
            r = L.apply_toggle(self.path, key, canal.OPEN)
            self.assertTrue(r.ok, r.message)
        self.assertEqual(self.states(), {"suez": "closed", "panama": "closed"})
        self.assertEqual(sorted(p.name for p in self.dir.iterdir()),
                         ["worldmap.lzw", "worldmap.lzw.canal-orig"])  # 임시 파일 없음
        a = ls11.decode_pack(orig)
        b = ls11.decode_pack(_read(self.path))
        self.assertEqual(a, b)

    def test_unknown_refused_file_untouched(self):
        parts = _synthetic_parts(True)
        parts = [bytearray(p) for p in parts]
        e = canal.SUEZ.edits[0]
        parts[e.file][e.offset] = 0x12  # 전도 후도 아닌 값
        with open(self.path, "wb") as f:
            f.write(ls11.encode_pack([bytes(p) for p in parts]))
        before = _read(self.path)
        self.assertEqual(self.states()["suez"], canal.UNKNOWN)
        r = L.apply_toggle(self.path, "suez", canal.UNKNOWN)
        self.assertFalse(r.ok)
        self.assertEqual(_read(self.path), before)
        self.assertFalse(L.backup_path(self.path).exists())
        # 다른 운하는 여전히 바꿀 수 있다
        r = L.apply_toggle(self.path, "panama", canal.CLOSED)
        self.assertTrue(r.ok)

    def test_stale_screen_state_does_nothing(self):
        L.apply_toggle(self.path, "suez", canal.CLOSED)   # 파일은 이미 open
        before = _read(self.path)
        r = L.apply_toggle(self.path, "suez", canal.CLOSED)  # 화면은 아직 closed 라고 믿음
        self.assertFalse(r.ok or r.changed)
        self.assertIn("달라졌습니다", r.message)
        self.assertEqual(_read(self.path), before)
        self.assertEqual(r.states["suez"], canal.OPEN)

    def test_corrupt_file_friendly_error(self):
        self.path.write_bytes(b"not an ls11 file at all")
        s, err = L.read_states(self.path)
        self.assertIsNone(s)
        self.assertIn("바뀌지 않았습니다", err)
        self.assertTrue(all(not r.button_enabled for r in L.describe_rows(s)))
        before = _read(self.path)
        r = L.apply_toggle(self.path, "suez", canal.CLOSED)
        self.assertFalse(r.ok)
        self.assertEqual(_read(self.path), before)

    def test_write_failure_leaves_file_and_no_tmp(self):
        before = _read(self.path)
        with mock.patch("horiedit_py.data.canal.os.replace",
                        side_effect=PermissionError("locked by DOSBox")):
            r = L.apply_toggle(self.path, "suez", canal.CLOSED)
        self.assertFalse(r.ok)
        self.assertIn("DOSBox", r.message)
        self.assertEqual(_read(self.path), before)
        self.assertFalse(Path(str(self.path) + ".canal-tmp").exists())
        self.assertEqual(r.states, {"suez": "closed", "panama": "closed"})


@unittest.skipUnless(os.path.exists(ORIG), "originalgame 없음")
class RealFileScenarioTest(unittest.TestCase):
    def test_scenario_on_copy(self):
        with tempfile.TemporaryDirectory() as td:
            gd = Path(td)
            shutil.copy2(ORIG, gd / "worldmap.lzw")  # 소문자 이름으로 둔다
            before = _read(gd / "worldmap.lzw")
            found = L.find_worldmap(gd)
            self.assertEqual(found.name, "worldmap.lzw")
            s, _ = L.read_states(found)
            self.assertEqual(s, {"suez": "closed", "panama": "closed"})
            L.apply_toggle(found, "suez", canal.CLOSED)
            L.apply_toggle(found, "panama", canal.CLOSED)
            self.assertEqual(L.read_states(found)[0], {"suez": "open", "panama": "open"})
            L.apply_toggle(found, "suez", canal.OPEN)
            L.apply_toggle(found, "panama", canal.OPEN)
            self.assertEqual(L.read_states(found)[0], {"suez": "closed", "panama": "closed"})
            self.assertEqual(_read(found), before)          # 바이트까지 원복
            self.assertEqual(_read(L.backup_path(found)), before)


if __name__ == "__main__":
    unittest.main()
