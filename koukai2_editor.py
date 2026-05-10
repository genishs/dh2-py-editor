"""대항해시대 II (Koukai 2) 세이브 에디터 - Python 재구현 진입점.

원본: HORIEDIT.C main() (Borland Turbo C / DOS).

사용법:
    python koukai2_editor.py [KOUKAI2.DAT 경로]
    koukai2_editor.exe [KOUKAI2.DAT 경로]

경로 미지정 시 다음 순서로 자동 탐지:
    1. 명시 인자
    2. 현재 작업 디렉토리(Path.cwd()) 의 KOUKAI2.DAT
    3. 실행파일(또는 스크립트) 자체 위치 의 KOUKAI2.DAT
    4. 개발 fallback: 스크립트 위치 기준 originalgame/koukai2/KOUKAI2.DAT
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from horiedit_py.common import state
from horiedit_py.hero_person import sel_save, select_menu


def _setup_console_utf8() -> None:
    """Windows 콘솔에서 한글이 깨지지 않도록 UTF-8 / CP65001 로 설정.

    cmd / PowerShell / Windows Terminal 어디서 실행되어도 동작.
    Windows 외 환경에서는 영향 없음.
    """
    # 1) stdout/stderr 를 UTF-8 로 재구성 (Python 3.7+)
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass

    # 2) Windows 한정: 콘솔 코드페이지를 65001(UTF-8)로
    if os.name != "nt":
        return

    # chcp 시도 (cmd 등에서 효과)
    try:
        os.system("chcp 65001 >nul")
    except Exception:
        pass

    # Windows API 직접 호출 (가장 확실)
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleOutputCP(65001)
        kernel32.SetConsoleCP(65001)
    except Exception:
        pass


def _is_frozen() -> bool:
    """PyInstaller 등으로 동결된 실행파일에서 실행 중인지."""
    return bool(getattr(sys, "frozen", False))


def _exe_dir() -> Path:
    """동결된 실행파일의 위치 디렉토리.

    PyInstaller --onefile 에서 sys._MEIPASS 는 임시 압축 해제 폴더라 부적절.
    실행파일 자체 위치는 sys.executable 에 들어 있다.
    """
    return Path(sys.executable).resolve().parent


def _script_dir() -> Path:
    """소스 스크립트 위치 (개발 환경)."""
    return Path(__file__).resolve().parent


def _candidates_in(base: Path) -> list[Path]:
    return [base / "KOUKAI2.DAT", base / "koukai2.dat"]


def _resolve_save_path(argv: list[str]) -> Path | None:
    """다음 순서로 KOUKAI2.DAT 위치를 찾는다.

    1. 명시 인자
    2. 현재 작업 디렉토리 (Path.cwd())
    3. 동결 실행파일 위치 (sys.executable 의 폴더) — frozen 일 때만
    4. 개발 fallback: 스크립트 폴더 기준 originalgame/koukai2/KOUKAI2.DAT
       및 스크립트 폴더 자체

    못 찾으면 None.
    """
    # 1) 명시 인자
    if len(argv) >= 2 and argv[1].strip():
        return Path(argv[1])

    search: list[Path] = []

    # 2) 현재 작업 디렉토리
    search.extend(_candidates_in(Path.cwd()))

    # 3) 실행파일 자체 위치 (frozen 인 경우 우선; 개발 시에도 유용)
    try:
        exe_d = _exe_dir()
        for p in _candidates_in(exe_d):
            if p not in search:
                search.append(p)
    except Exception:
        pass

    # 4) 개발 fallback
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


def _print_not_found_help() -> None:
    print("KOUKAI2.DAT 를 찾지 못했습니다.")
    print("이 프로그램을 KOUKAI2.DAT 가 있는 게임 폴더에 두고 실행하거나,")
    print("경로를 인자로 지정해 주세요.")
    print()
    print("사용법:")
    print("    koukai2_editor.exe [KOUKAI2.DAT 경로]")
    print("    python koukai2_editor.py [KOUKAI2.DAT 경로]")


def main() -> int:
    _setup_console_utf8()

    save_path = _resolve_save_path(sys.argv)
    if save_path is None:
        _print_not_found_help()
        return -1

    if not save_path.exists():
        print(f"세이브 파일을 찾지 못했습니다: {save_path}")
        _print_not_found_help()
        return -1

    try:
        fp = open(save_path, "r+b")
    except OSError as e:
        print(f"세이브 파일을 열 수 없습니다: {save_path}\n{e}")
        return -1

    state.fp = fp
    state.page = 0
    state.eXit = 0
    # 같은 디렉토리의 MAIN.EXE 등을 편집할 수 있도록 게임 폴더 경로 보관
    state.game_dir = save_path.resolve().parent

    try:
        # sel_save → select_menu 반복. select_menu 가 0(처음 메뉴) 으로
        # 빠져나오면 sel_save 를 다시 보여주고, sel_save 의 0(종료) 에서만
        # 루프를 빠져나간다.
        while True:
            sel_save(state)
            if state.eXit == 1:
                break
            select_menu(state)
    finally:
        fp.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
