"""horiedit_py.shortcut 단위 시험 (이슈 #17).

실제 바탕화면을 건드리지 않는다 — 모든 시험이 임시 폴더를 바탕화면/시작 메뉴 대신 주입한다.
.lnk 는 실제 PowerShell WScript.Shell 로 만들고 다시 읽어 속성을 검증한다 (Windows 전용).

실행:  python -m unittest discover -s tests -v
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from horiedit_py import shortcut as sc  # noqa: E402
from horiedit_py.shortcut import State  # noqa: E402

WIN = os.name == "nt"
NOTEPAD = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "notepad.exe"


def _touch(p: Path) -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"MZ")
    return p


class PureLogicTests(unittest.TestCase):
    def test_is_our_exe(self):
        for t in (r"C:\x\koukai2_editor.exe", r"C:\x\KOUKAI2-EDITOR.EXE",
                  "D:/a b/koukai2-editor.exe", r"C:\한글 폴더\koukai2_editor.exe"):
            self.assertTrue(sc.is_our_exe(t), t)
        for t in ("", r"C:\Windows\notepad.exe", r"C:\x\koukai2_editor.exe.bak",
                  r"C:\koukai2_editor.exe\notepad.exe", r"C:\x\koukai2_editor2.exe",
                  r"C:\x\python.exe"):
            self.assertFalse(sc.is_our_exe(t), t)

    def test_same_path_normalizes(self):
        self.assertTrue(sc.same_path(r"D:\Game\Koukai2", "d:/game/koukai2/"))
        self.assertFalse(sc.same_path(r"D:\Game\Koukai2", r"D:\Game\Koukai2b"))
        self.assertFalse(sc.same_path("", ""))

    def test_should_ask_matrix(self):
        ask = sc.should_ask_automatically
        # 자동 탐지(found_by_dialog=False): 없거나 끊겼을 때만
        self.assertTrue(ask(State.MISSING, False))
        self.assertTrue(ask(State.BROKEN, False))
        self.assertFalse(ask(State.DIFFERENT, False))
        self.assertFalse(ask(State.CURRENT, False))
        self.assertFalse(ask(State.FOREIGN, False))
        # 파일 선택 창으로 고름: 시작 위치가 다르면 묻는다, 이미 같으면 안 묻는다
        self.assertTrue(ask(State.MISSING, True))
        self.assertTrue(ask(State.BROKEN, True))
        self.assertTrue(ask(State.DIFFERENT, True))
        self.assertFalse(ask(State.CURRENT, True))
        self.assertFalse(ask(State.FOREIGN, True))

    def test_current_exe_none_when_not_frozen(self):
        self.assertFalse(getattr(sys, "frozen", False))
        self.assertIsNone(sc.current_exe())

    def test_classify_with_fake_info(self):
        exe = r"C:\App\koukai2_editor.exe"
        save = r"D:\Game"

        def mk(target, wd):
            return sc.LinkInfo(Path("x.lnk"), target, wd)

        def yes(p):
            return True

        def no(p):
            return False

        self.assertIs(sc.classify(None, exe, save, yes), State.MISSING)
        self.assertIs(sc.classify(mk(exe, save), exe, save, yes), State.CURRENT)
        self.assertIs(sc.classify(mk(exe.lower(), save.upper()), exe, save, yes), State.CURRENT)
        self.assertIs(sc.classify(mk(exe, r"D:\Other"), exe, save, yes), State.DIFFERENT)
        self.assertIs(sc.classify(mk(r"E:\Moved\koukai2_editor.exe", save), exe, save, yes), State.DIFFERENT)
        self.assertIs(sc.classify(mk(r"E:\Gone\koukai2_editor.exe", save), exe, save, no), State.BROKEN)
        self.assertIs(sc.classify(mk(r"C:\Windows\notepad.exe", save), exe, save, yes), State.FOREIGN)
        self.assertIs(sc.classify(sc.LinkInfo(Path("x.lnk"), "", "", error=True), exe, save, yes), State.FOREIGN)


class DesktopResolutionTests(unittest.TestCase):
    """바탕화면 경로 결정 로직 — OneDrive 리디렉션을 흉내내 주입."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="dh2sc_desk_"))
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def test_onedrive_known_folder_wins_over_userprofile_desktop(self):
        od = self.tmp / "OneDrive" / "바탕 화면"
        od.mkdir(parents=True)
        (self.tmp / "profile" / "Desktop").mkdir(parents=True)  # 옛 로컬 바탕화면이 남은 경우
        env = {"USERPROFILE": str(self.tmp / "profile")}
        kw = dict(known_folder=lambda fid: str(od), powershell_desktop=lambda: None, env=env)
        cands = sc.desktop_candidates(**kw)
        self.assertEqual(cands[0], od)                 # 만들 곳 = Windows 가 알려준 OneDrive 경로
        self.assertEqual(len(cands), 2)                # 지울 때는 옛 폴더도 훑는다
        self.assertEqual(sc.resolve_desktop_dir(**kw), od)

    def test_dedupe_when_userprofile_desktop_is_same_folder(self):
        d = self.tmp / "profile" / "Desktop"
        d.mkdir(parents=True)
        cands = sc.desktop_candidates(known_folder=lambda fid: str(d).upper(),
                                      powershell_desktop=lambda: None,
                                      env={"USERPROFILE": str(self.tmp / "profile")})
        self.assertEqual(len(cands), 1)

    def test_fallback_to_powershell_then_userprofile(self):
        ps = self.tmp / "ps_desktop"
        ps.mkdir()
        c = sc.desktop_candidates(known_folder=lambda fid: None,
                                  powershell_desktop=lambda: str(ps), env={})
        self.assertEqual(c, [ps])
        up = self.tmp / "profile" / "Desktop"
        up.mkdir(parents=True)
        c = sc.desktop_candidates(known_folder=lambda fid: str(self.tmp / "nonexistent"),
                                  powershell_desktop=lambda: None,
                                  env={"USERPROFILE": str(self.tmp / "profile")})
        self.assertEqual(c, [up])

    def test_none_when_nothing_exists(self):
        self.assertIsNone(sc.resolve_desktop_dir(known_folder=lambda fid: None,
                                                 powershell_desktop=lambda: None, env={}))

    @unittest.skipUnless(WIN, "Windows 전용")
    def test_real_known_folder_returns_existing_dir(self):
        p = sc._known_folder_path(sc._FOLDERID_DESKTOP)
        self.assertTrue(p and Path(p).is_dir(), p)


@unittest.skipUnless(WIN, "Windows 전용 (PowerShell WScript.Shell)")
class LnkTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="dh2sc_"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.desktop = self.tmp / "바탕 화면"          # 한글+공백 경로
        self.desktop.mkdir()
        self.exe = _touch(self.tmp / "app dir" / "koukai2_editor.exe")
        self.game = self.tmp / "game folder 한글"
        self.game.mkdir()
        self.lnk = self.desktop / sc.SHORTCUT_NAME

    def _read(self, p: Path) -> sc.LinkInfo:
        infos = sc.read_links([p])
        self.assertEqual(len(infos), 1)
        return infos[0]

    def test_create_and_read_back_properties(self):
        res = sc.create_or_update(self.desktop, self.exe, self.game)
        self.assertTrue(res.ok, res.message)
        self.assertTrue(self.lnk.is_file())
        info = self._read(self.lnk)
        self.assertTrue(sc.same_path(info.target, self.exe), info.target)
        self.assertTrue(sc.same_path(info.working_dir, self.game), info.working_dir)   # 시작 위치 = 세이브 폴더
        self.assertEqual(info.icon.lower(), f"{self.exe},0".lower())                    # 아이콘 = 프로그램 exe
        self.assertEqual(self.lnk.name, "대항해시대 II 세이브 에디터.lnk")
        self.assertIs(sc.classify(info, self.exe, self.game), State.CURRENT)

    def test_no_duplicate_when_current(self):
        sc.create_or_update(self.desktop, self.exe, self.game)
        mtime = self.lnk.stat().st_mtime_ns
        calls = []
        res = sc.create_or_update(self.desktop, self.exe, self.game,
                                  writer=lambda *a: calls.append(a) or True)
        self.assertTrue(res.ok)
        self.assertIn("이미", res.message)
        self.assertEqual(calls, [])                          # 다시 쓰지 않았다
        self.assertEqual(self.lnk.stat().st_mtime_ns, mtime)
        self.assertEqual(len(list(self.desktop.glob("*.lnk"))), 1)

    def test_workdir_changed_is_detected_and_updated(self):
        sc.create_or_update(self.desktop, self.exe, self.game)
        other = self.tmp / "other game"
        other.mkdir()
        state, _ = sc.inspect_desktop(self.desktop, self.exe, other)
        self.assertIs(state, State.DIFFERENT)
        res = sc.create_or_update(self.desktop, self.exe, other)
        self.assertTrue(res.ok, res.message)
        self.assertIn("갱신", res.message)
        info = self._read(self.lnk)
        self.assertTrue(sc.same_path(info.working_dir, other))
        self.assertEqual(len(list(self.desktop.glob("*.lnk"))), 1)  # 새로 만들지 않고 고쳤다

    def test_moved_exe_is_broken_then_updated(self):
        sc.create_or_update(self.desktop, self.exe, self.game)
        new_exe = _touch(self.tmp / "moved" / "koukai2_editor.exe")
        self.exe.unlink()
        state, _ = sc.inspect_desktop(self.desktop, new_exe, self.game)
        self.assertIs(state, State.BROKEN)
        self.assertTrue(sc.create_or_update(self.desktop, new_exe, self.game).ok)
        self.assertTrue(sc.same_path(self._read(self.lnk).target, new_exe))

    def test_foreign_same_name_lnk_is_left_alone(self):
        self.assertTrue(sc.write_link(self.lnk, NOTEPAD, self.game))   # 이름만 같고 대상은 메모장
        before = self._read(self.lnk)
        res = sc.create_or_update(self.desktop, self.exe, self.game)
        self.assertFalse(res.ok)
        after = self._read(self.lnk)
        self.assertEqual((before.target, before.working_dir), (after.target, after.working_dir))
        self.assertTrue(sc.same_path(after.target, NOTEPAD))

    def test_failure_does_not_raise(self):
        def boom(*a):
            raise OSError("access denied")
        res = sc.create_or_update(self.desktop, self.exe, self.game, writer=boom)
        self.assertFalse(res.ok)
        self.assertIn("만들지 못했습니다", res.message)
        res = sc.create_or_update(self.desktop, self.exe, self.game, writer=lambda *a: False)
        self.assertFalse(res.ok)
        res = sc.create_or_update(self.desktop, self.tmp / "nope.exe", self.game)
        self.assertFalse(res.ok)

    def test_write_to_missing_desktop_fails_gracefully(self):
        self.assertFalse(sc.write_link(self.tmp / "없는폴더" / sc.SHORTCUT_NAME, self.exe, self.game))

    def test_remove_only_ours(self):
        start = self.tmp / "Start Menu" / "Programs"
        (start / "Sub").mkdir(parents=True)
        # 우리 것 3개: 기본 이름 / 이름 바꾼 것(하이픈 exe) / 시작 메뉴 하위 폴더
        hy_exe = _touch(self.tmp / "app dir" / "koukai2-editor.exe")
        sc.create_or_update(self.desktop, self.exe, self.game)
        renamed = self.desktop / "내가 바꾼 이름.lnk"
        self.assertTrue(sc.write_link(renamed, hy_exe, self.game))
        in_start = start / "Sub" / "에디터.lnk"
        self.assertTrue(sc.write_link(in_start, self.exe, self.game))
        # 남아야 하는 것: 메모장 대상(같은 기본 이름은 다른 폴더에), 다른 이름·다른 대상, 깨진 .lnk, 일반 파일
        foreign_same_name = start / sc.SHORTCUT_NAME
        self.assertTrue(sc.write_link(foreign_same_name, NOTEPAD, self.game))
        foreign_other = self.desktop / "메모장.lnk"
        self.assertTrue(sc.write_link(foreign_other, NOTEPAD, self.game))
        script_lnk = self.desktop / "python 으로 실행.lnk"
        self.assertTrue(sc.write_link(script_lnk, Path(sys.executable), self.game))
        broken = self.desktop / "깨짐.lnk"
        broken.write_text("not a shortcut", encoding="utf-8")
        plain = self.desktop / "memo.txt"
        plain.write_text("x", encoding="utf-8")

        items = sc.remove_links([self.desktop, start])
        self.assertIsNotNone(items)
        removed = {i.path for i in items if i.removed}
        self.assertEqual(removed, {self.lnk, renamed, in_start})
        self.assertFalse(any(not i.removed for i in items))
        for keep in (foreign_same_name, foreign_other, script_lnk, broken, plain):
            self.assertTrue(keep.exists(), f"지워지면 안 됨: {keep}")
        # 이름만 같은 메모장 바로가기의 대상이 그대로인지
        self.assertTrue(sc.same_path(self._read(foreign_same_name).target, NOTEPAD))

    def test_remove_when_none(self):
        self.assertEqual(sc.remove_links([self.desktop]), [])

    def test_remove_cli_outputs_and_exit_code(self):
        sc.create_or_update(self.desktop, self.exe, self.game)
        lines: list[str] = []
        flag_base = self.tmp / "localappdata"
        sc.set_prompt_disabled(True, base=flag_base)
        rc = sc.run_remove_cli(out=lines.append, dirs=[self.desktop], flag_base=flag_base)
        self.assertEqual(rc, 0)
        text = "\n".join(lines)
        self.assertIn("[삭제]", text)
        self.assertIn(str(self.lnk), text)
        self.assertFalse(self.lnk.exists())
        self.assertFalse(sc.prompt_disabled(flag_base))           # 설정 파일도 정리
        self.assertFalse((flag_base / "Koukai2Editor").exists())  # 빈 폴더도 정리
        # 지울 것이 없어도 성공(0)
        lines.clear()
        self.assertEqual(sc.run_remove_cli(out=lines.append, dirs=[self.desktop], flag_base=flag_base), 0)
        self.assertIn("없습니다", lines[0])

    def test_remove_cli_failure_exit_code(self):
        sc.create_or_update(self.desktop, self.exe, self.game)
        lines: list[str] = []

        def deny(p):
            raise PermissionError("denied")

        rc = sc.run_remove_cli(out=lines.append, dirs=[self.desktop], delete=deny,
                               flag_base=self.tmp / "x")
        self.assertEqual(rc, 1)
        self.assertTrue(self.lnk.exists())
        self.assertTrue(any("[실패]" in l for l in lines))
        # PowerShell 실패 → 1
        lines.clear()
        rc = sc.run_remove_cli(out=lines.append, dirs=[self.desktop], reader=lambda paths: None,
                               flag_base=self.tmp / "x")
        self.assertEqual(rc, 1)


class PromptFlagTests(unittest.TestCase):
    def test_roundtrip(self):
        base = Path(tempfile.mkdtemp(prefix="dh2sc_flag_"))
        self.addCleanup(shutil.rmtree, base, True)
        self.assertFalse(sc.prompt_disabled(base))
        self.assertTrue(sc.set_prompt_disabled(True, base))
        self.assertTrue(sc.prompt_disabled(base))
        self.assertTrue(sc.set_prompt_disabled(False, base))
        self.assertFalse(sc.prompt_disabled(base))

    def test_unwritable_base_does_not_raise(self):
        f = Path(tempfile.mkdtemp(prefix="dh2sc_flag_")) / "file"
        f.write_text("x")
        self.addCleanup(shutil.rmtree, f.parent, True)
        self.assertFalse(sc.set_prompt_disabled(True, base=f))   # 폴더가 아닌 곳 → 실패해도 예외 없음
        self.assertFalse(sc.prompt_disabled(f))


if __name__ == "__main__":
    unittest.main()
