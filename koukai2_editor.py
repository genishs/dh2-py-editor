"""대항해시대 II (Koukai 2) 세이브 에디터 - GUI 진입점.

원본: HORIEDIT.C (Borland Turbo C / DOS) → Python + Tkinter 재구현.

사용법:
    python koukai2_editor.py [KOUKAI2.DAT 경로]
    koukai2_editor.exe [KOUKAI2.DAT 경로]
    koukai2_editor.exe --remove-shortcuts     (GUI 없이 바탕화면 바로가기 제거)

--remove-shortcuts 는 이 프로그램이 만든 바로가기(대상이 koukai2-editor.exe /
koukai2_editor.exe 인 .lnk)만 찾아 지운다. winget uninstall 전에 실행하면 깔끔하다.
이 옵션이 있으면 다른 인자는 무시하고 KOUKAI2.DAT 를 열지 않는다.

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


REMOVE_SHORTCUTS_FLAG = "--remove-shortcuts"


def _attach_ancestor_console(kernel32) -> bool:
    """조상 프로세스 중 콘솔을 가진 것에 붙는다 (터미널에서 실행한 경우 그 터미널).

    PyInstaller --onefile 은 바깥 부트로더가 안쪽 프로세스를 자식으로 띄운다. 바깥 부트로더는
    GUI 라 콘솔이 없으므로 ATTACH_PARENT_PROCESS 만으로는 붙지 못하고, 한 단계 위(셸)까지
    올라가야 한다.
    """
    import ctypes
    from ctypes import wintypes

    if kernel32.AttachConsole(0xFFFFFFFF):  # ATTACH_PARENT_PROCESS (비 onefile)
        return True

    class _PE(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD), ("th32DefaultHeapID", ctypes.c_size_t),
            ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD), ("pcPriClassBase", wintypes.LONG),
            ("dwFlags", wintypes.DWORD), ("szExeFile", wintypes.WCHAR * 260),
        ]

    kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    snap = kernel32.CreateToolhelp32Snapshot(0x2, 0)  # TH32CS_SNAPPROCESS
    if not snap or snap == wintypes.HANDLE(-1).value:
        return False
    parents: dict[int, int] = {}
    try:
        pe = _PE()
        pe.dwSize = ctypes.sizeof(_PE)
        ok = kernel32.Process32FirstW(wintypes.HANDLE(snap), ctypes.byref(pe))
        while ok:
            parents[pe.th32ProcessID] = pe.th32ParentProcessID
            ok = kernel32.Process32NextW(wintypes.HANDLE(snap), ctypes.byref(pe))
    finally:
        kernel32.CloseHandle(wintypes.HANDLE(snap))

    pid = os.getpid()
    for _ in range(8):
        pid = parents.get(pid, 0)
        if not pid:
            return False
        if kernel32.AttachConsole(pid):
            return True
    return False


def _std_output_usable() -> bool:
    """표준 출력이 실제로 어딘가(콘솔·파일·파이프)에 연결돼 있는가.

    --windowed exe 를 터미널에서 `start` 등으로 띄우면 표준 핸들이 비어 있어서
    sys.stdout 이 None 이거나, 객체가 있어도 아무 데도 가지 않는다 — 그럴 땐 부모 콘솔에 붙는다.
    `> 파일` / `| 파이프` 로 리디렉션했으면 그대로 둔다.
    """
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        kernel32.GetStdHandle.restype = ctypes.c_void_p
        h = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
        if h in (None, 0, 0xFFFFFFFF, 0xFFFFFFFFFFFFFFFF):
            return False
        # 1=DISK 2=CHAR(콘솔) 3=PIPE
        return kernel32.GetFileType(ctypes.c_void_p(h)) in (1, 2, 3)
    except Exception:
        return sys.stdout is not None


def _run_remove_shortcuts_cli() -> int:
    """`--remove-shortcuts` — GUI 없이 바로가기를 지우고 결과를 출력, 종료 코드로 성공(0)/실패(1).

    exe 는 --windowed(GUI 서브시스템) 로 빌드되어 콘솔이 없으므로, 터미널에서 실행한
    경우 부모 콘솔에 붙어 출력한다. 부모 콘솔이 없으면(탐색기 더블클릭 등) 출력 없이
    동작만 하고 종료 코드만 남긴다.
    """
    restore_cp = None
    if os.name == "nt" and not _std_output_usable():
        try:
            import ctypes

            kernel32 = ctypes.windll.kernel32
            if _attach_ancestor_console(kernel32):
                restore_cp = kernel32.GetConsoleOutputCP()
                kernel32.SetConsoleOutputCP(65001)
                sys.stdout = open("CONOUT$", "w", encoding="utf-8", buffering=1)
                sys.stderr = sys.stdout
        except Exception:
            pass
    else:
        for name in ("stdout", "stderr"):
            reconfigure = getattr(getattr(sys, name, None), "reconfigure", None)
            if reconfigure is not None:
                try:
                    reconfigure(encoding="utf-8", errors="replace")
                except Exception:
                    pass

    try:
        from horiedit_py.shortcut import run_remove_cli

        return run_remove_cli()
    finally:
        if restore_cp:
            try:
                sys.stdout.flush()
                ctypes.windll.kernel32.SetConsoleOutputCP(restore_cp)
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
    # 우선 처리: 바로가기 제거 (GUI·세이브 탐색 없이). 기존 「첫 인자 = KOUKAI2.DAT 경로」
    # 규칙과는 이 정확한 플래그 문자열로만 구분한다.
    if any(a.lower() == REMOVE_SHORTCUTS_FLAG for a in sys.argv[1:]):
        return _run_remove_shortcuts_cli()

    _setup_console_utf8()

    # 명령줄 인자나 파일 선택 창으로 직접 고른 세이브인가 (False = 현재/exe 폴더에서 자동 탐지)
    explicit_arg = len(sys.argv) >= 2 and bool(sys.argv[1].strip())
    found_by_dialog = explicit_arg

    save_path = _resolve_save_path(sys.argv)
    if save_path is None or not save_path.exists():
        save_path = _ask_save_path_via_dialog()
        found_by_dialog = True
        if save_path is None or not save_path.exists():
            return -1

    from horiedit_py.gui.app import run

    return run(save_path, found_by_dialog)


if __name__ == "__main__":
    sys.exit(main())
