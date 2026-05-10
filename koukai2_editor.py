"""대항해시대 II (Koukai 2) 세이브 에디터 - GUI 진입점.

원본: HORIEDIT.C (Borland Turbo C / DOS) → Python + Tkinter 재구현.

사용법:
    python koukai2_editor.py [KOUKAI2.DAT 경로]
    koukai2_editor.exe [KOUKAI2.DAT 경로]

경로 미지정 시 다음 순서로 자동 탐지:
    1. 명시 인자
    2. 현재 작업 디렉토리(Path.cwd()) 의 KOUKAI2.DAT
    3. 실행파일(또는 스크립트) 자체 위치 의 KOUKAI2.DAT
    4. 개발 fallback: 스크립트 위치 기준 originalgame/koukai2/KOUKAI2.DAT
모두 실패 시 GUI 파일 선택 대화상자를 띄운다.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _setup_console_utf8() -> None:
    """Windows 콘솔에서 한글이 깨지지 않도록 UTF-8 / CP65001 로 설정.

    GUI 모드에서는 의미가 적지만, 디버그 print 가 있을 때 안전.
    """
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass

    if os.name != "nt":
        return

    try:
        os.system("chcp 65001 >nul")
    except Exception:
        pass

    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleOutputCP(65001)
        kernel32.SetConsoleCP(65001)
    except Exception:
        pass


def _is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def _exe_dir() -> Path:
    return Path(sys.executable).resolve().parent


def _script_dir() -> Path:
    return Path(__file__).resolve().parent


def _candidates_in(base: Path) -> list[Path]:
    return [base / "KOUKAI2.DAT", base / "koukai2.dat"]


def _resolve_save_path(argv: list[str]) -> Path | None:
    """다음 순서로 KOUKAI2.DAT 위치를 찾는다.

    1. 명시 인자
    2. 현재 작업 디렉토리 (Path.cwd())
    3. 동결 실행파일 위치 (sys.executable 의 폴더)
    4. 개발 fallback: 스크립트 폴더 / originalgame/koukai2/

    못 찾으면 None.
    """
    if len(argv) >= 2 and argv[1].strip():
        return Path(argv[1])

    search: list[Path] = []
    search.extend(_candidates_in(Path.cwd()))

    try:
        exe_d = _exe_dir()
        for p in _candidates_in(exe_d):
            if p not in search:
                search.append(p)
    except Exception:
        pass

    try:
        sd = _script_dir()
        dev_fallbacks = [
            sd / "originalgame" / "koukai2" / "KOUKAI2.DAT",
            sd / "originalgame" / "koukai2" / "koukai2.dat",
        ] + _candidates_in(sd)
        for p in dev_fallbacks:
            if p not in search:
                search.append(p)
    except Exception:
        pass

    for c in search:
        try:
            if c.exists():
                return c
        except OSError:
            continue
    return None


def _ask_save_path_via_dialog() -> Path | None:
    """KOUKAI2.DAT 자동 탐지 실패 시 GUI 파일 대화상자."""
    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox
    except Exception:
        return None

    root = tk.Tk()
    root.withdraw()
    try:
        messagebox.showerror(
            "KOUKAI2.DAT 미발견",
            "이 프로그램을 KOUKAI2.DAT 가 있는 게임 폴더에 두고 실행하거나,\n"
            "다음 대화상자에서 직접 선택하세요.",
        )
        picked = filedialog.askopenfilename(
            title="KOUKAI2.DAT 선택",
            filetypes=[
                ("Koukai 2 save", "KOUKAI2.DAT koukai2.dat"),
                ("All", "*.*"),
            ],
        )
    finally:
        try:
            root.destroy()
        except Exception:
            pass
    if not picked:
        return None
    return Path(picked)


def main() -> int:
    _setup_console_utf8()

    save_path = _resolve_save_path(sys.argv)
    if save_path is None or not save_path.exists():
        save_path = _ask_save_path_via_dialog()
        if save_path is None or not save_path.exists():
            return -1

    from horiedit_py.gui.app import run

    return run(save_path)


if __name__ == "__main__":
    sys.exit(main())
