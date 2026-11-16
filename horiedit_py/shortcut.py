"""바탕화면 바로가기 만들기 / 찾아 지우기 (이슈 #17).

GUI(tkinter) 에 의존하지 않는 순수 로직 모듈 — 시험하기 쉽도록 바탕화면 폴더·
실행 파일 경로를 모두 인자로 주입할 수 있다.

설계 요점
---------
- .lnk 읽기/쓰기는 추가 설치 없이 **PowerShell 의 WScript.Shell COM** 으로 한다.
  (Windows 10/11 기본 탑재. 한글 경로가 깨지지 않도록 경로는 명령줄이 아니라
  환경변수로, 결과는 UTF-8 로 주고받는다.)
- 바탕화면 경로는 고정값이 아니라 Windows(SHGetKnownFolderPath) 가 알려주는
  실제 경로 — 바탕화면이 OneDrive 로 옮겨진 PC 에서도 올바른 위치가 된다.
- 「우리 바로가기」 = **대상이 우리 exe**(koukai2-editor.exe / koukai2_editor.exe) 인
  .lnk. 이름이 같아도 다른 대상을 가리키는 .lnk 는 우리 것이 아니므로 만들 때
  덮어쓰지 않고, 지울 때 건드리지 않는다.
"""

from __future__ import annotations

import ctypes
import os
import subprocess
import sys
import uuid
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable, Iterable, Mapping, Optional

SHORTCUT_NAME = "대항해시대 II 세이브 에디터.lnk"

# 우리 exe 의 파일 이름 (소문자 비교). winget 별칭은 하이픈, 릴리스 exe 는 밑줄.
OUR_EXE_NAMES = frozenset({"koukai2-editor.exe", "koukai2_editor.exe"})

# 「다시 묻지 않기」 저장 파일 (사용자별 — 모듈 docstring 아래 _prompt_flag_path 참고)
_PROMPT_FLAG_DIRNAME = "Koukai2Editor"
_PROMPT_FLAG_FILENAME = "shortcut_prompt.txt"

# KNOWNFOLDERID
_FOLDERID_DESKTOP = "B4BFCC3A-DB2C-424C-B029-7FE99A87C641"
_FOLDERID_PROGRAMS = "A77F5D77-2E2B-44C3-A6A2-ABA601054A51"  # 시작 메뉴\프로그램 (사용자)

_CREATE_NO_WINDOW = 0x08000000
_PS_TIMEOUT_SEC = 30


# ---------------------------------------------------------------------------
# 데이터 모델
# ---------------------------------------------------------------------------

class State(Enum):
    """바탕화면에 같은 이름의 바로가기가 어떤 상태인지."""

    MISSING = "missing"      # 없음 → 새로 만들기
    BROKEN = "broken"        # 우리 바로가기인데 대상 exe 가 없어짐 (exe 를 옮김) → 갱신
    DIFFERENT = "different"  # 우리 바로가기인데 대상 exe 또는 시작 위치가 다름 → 갱신(물어봄)
    CURRENT = "current"      # 우리 바로가기이고 대상·시작 위치가 모두 같음 → 할 일 없음
    FOREIGN = "foreign"      # 같은 이름인데 대상이 우리 exe 가 아님 → 건드리지 않음


@dataclass(frozen=True)
class LinkInfo:
    path: Path
    target: str
    working_dir: str
    icon: str = ""
    error: bool = False


@dataclass(frozen=True)
class Result:
    ok: bool
    message: str
    path: Optional[Path] = None


@dataclass(frozen=True)
class RemoveItem:
    path: Path
    removed: bool
    error: str = ""


# ---------------------------------------------------------------------------
# 경로 도우미
# ---------------------------------------------------------------------------

def _norm(p: "str | os.PathLike[str]") -> str:
    """경로 비교용 정규화 (대소문자 무시·구분자 통일·끝 슬래시 제거)."""
    s = os.path.expandvars(str(p))
    if not s:
        return ""
    return os.path.normcase(os.path.normpath(s))


def same_path(a: "str | os.PathLike[str]", b: "str | os.PathLike[str]") -> bool:
    na, nb = _norm(a), _norm(b)
    return bool(na) and na == nb


def is_our_exe(target: str) -> bool:
    """.lnk 의 대상 경로가 우리 exe 인가 (파일 이름으로만 판정)."""
    if not target:
        return False
    name = os.path.basename(os.path.expandvars(target).replace("/", "\\"))
    return name.lower() in OUR_EXE_NAMES


def current_exe() -> Optional[Path]:
    """바로가기의 대상으로 쓸 실행 파일. 동결(PyInstaller) 실행일 때만 돌려준다.

    소스 실행(python koukai2_editor.py) 이면 sys.executable 이 python.exe 이므로
    바로가기를 만들지 않도록 None.
    """
    if os.name != "nt" or not getattr(sys, "frozen", False):
        return None
    try:
        return Path(sys.executable).resolve()
    except OSError:
        return Path(sys.executable)


# ---------------------------------------------------------------------------
# 바탕화면 / 시작 메뉴 경로 (OneDrive 대응)
# ---------------------------------------------------------------------------

def _known_folder_path(folder_id: str) -> Optional[str]:
    """SHGetKnownFolderPath — OneDrive 로 리디렉션된 실제 경로까지 돌려준다."""
    if os.name != "nt":
        return None
    try:
        from ctypes import wintypes

        class _GUID(ctypes.Structure):
            _fields_ = [
                ("Data1", wintypes.DWORD),
                ("Data2", wintypes.WORD),
                ("Data3", wintypes.WORD),
                ("Data4", ctypes.c_ubyte * 8),
            ]

        u = uuid.UUID(folder_id)
        guid = _GUID(u.time_low, u.time_mid, u.time_hi_version,
                     (ctypes.c_ubyte * 8)(*u.bytes[8:]))
        ppath = ctypes.c_wchar_p()
        shell32 = ctypes.windll.shell32
        shell32.SHGetKnownFolderPath.argtypes = [
            ctypes.c_void_p, wintypes.DWORD, wintypes.HANDLE,
            ctypes.POINTER(ctypes.c_wchar_p),
        ]
        hr = shell32.SHGetKnownFolderPath(ctypes.byref(guid), 0, None, ctypes.byref(ppath))
        try:
            if hr != 0 or not ppath.value:
                return None
            return ppath.value
        finally:
            ctypes.windll.ole32.CoTaskMemFree(ppath)
    except Exception:
        return None


def _powershell_exe() -> str:
    root = os.environ.get("SystemRoot") or r"C:\Windows"
    cand = Path(root) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
    return str(cand) if cand.is_file() else "powershell.exe"


def _run_powershell(script: str, env_extra: Mapping[str, str]) -> Optional[str]:
    """PowerShell 스크립트를 숨김 창으로 실행해 stdout(UTF-8) 을 돌려준다. 실패 시 None."""
    import base64

    if os.name != "nt":
        return None
    encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    env = dict(os.environ)
    env.update(env_extra)
    try:
        cp = subprocess.run(
            [_powershell_exe(), "-NoProfile", "-NonInteractive",
             "-ExecutionPolicy", "Bypass", "-EncodedCommand", encoded],
            capture_output=True, env=env, timeout=_PS_TIMEOUT_SEC,
            creationflags=_CREATE_NO_WINDOW, stdin=subprocess.DEVNULL,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if cp.returncode != 0:
        return None
    return cp.stdout.decode("utf-8", errors="replace")


def _desktop_via_powershell() -> Optional[str]:
    out = _run_powershell(
        "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8;"
        "[Environment]::GetFolderPath('Desktop')", {},
    )
    return out.strip() if out and out.strip() else None


def desktop_candidates(
    known_folder: Callable[[str], Optional[str]] = _known_folder_path,
    powershell_desktop: Callable[[], Optional[str]] = _desktop_via_powershell,
    env: Optional[Mapping[str, str]] = None,
) -> list[Path]:
    """바탕화면으로 볼 만한 폴더들 (우선순위 순, 실제로 존재하는 것만, 중복 제거).

    1) SHGetKnownFolderPath(Desktop)  — OneDrive 리디렉션 반영 (정답)
    2) PowerShell [Environment]::GetFolderPath('Desktop') — 1) 이 실패할 때
    3) %USERPROFILE%\\Desktop — 최후 수단

    OneDrive 로 옮긴 PC 에는 옛 %USERPROFILE%\\Desktop 이 남아 있기도 하므로, 지울 때는
    이 목록 전체를 훑고, 만들 때는 첫 번째(`resolve_desktop_dir`)만 쓴다.
    """
    env = os.environ if env is None else env
    found: list[Path] = []

    def _add(p: Optional[str]) -> None:
        if not p:
            return
        path = Path(p)
        try:
            if not path.is_dir():
                return
        except OSError:
            return
        if not any(same_path(path, q) for q in found):
            found.append(path)

    _add(known_folder(_FOLDERID_DESKTOP))
    if not found:
        _add(powershell_desktop())
    up = env.get("USERPROFILE")
    if up:
        _add(str(Path(up) / "Desktop"))
    return found


def resolve_desktop_dir(**kwargs) -> Optional[Path]:
    """바로가기를 만들 바탕화면 폴더. 못 찾으면 None."""
    c = desktop_candidates(**kwargs)
    return c[0] if c else None


def start_menu_programs_dir() -> Optional[Path]:
    p = _known_folder_path(_FOLDERID_PROGRAMS)
    if p and Path(p).is_dir():
        return Path(p)
    return None


# ---------------------------------------------------------------------------
# .lnk 읽기 / 쓰기 (PowerShell WScript.Shell)
# ---------------------------------------------------------------------------

_READ_SCRIPT = r"""
[Console]::OutputEncoding=[System.Text.Encoding]::UTF8
$sh=New-Object -ComObject WScript.Shell
foreach($p in ($env:DH2_LNK_PATHS -split '\|')){
  if(-not $p){continue}
  try{ $s=$sh.CreateShortcut($p); "{0}`t{1}`t{2}`t{3}" -f $p,$s.TargetPath,$s.WorkingDirectory,$s.IconLocation }
  catch{ "{0}`t`t`tERR" -f $p }
}
"""

_WRITE_SCRIPT = r"""
$ErrorActionPreference='Stop'
$sh=New-Object -ComObject WScript.Shell
$s=$sh.CreateShortcut($env:DH2_LNK_PATH)
$s.TargetPath=$env:DH2_LNK_TARGET
$s.WorkingDirectory=$env:DH2_LNK_WORKDIR
$s.IconLocation=$env:DH2_LNK_TARGET + ',0'
$s.Description=$env:DH2_LNK_DESC
$s.Save()
"""


def read_links(paths: Iterable["str | os.PathLike[str]"]) -> Optional[list[LinkInfo]]:
    """여러 .lnk 의 속성을 한 번의 PowerShell 호출로 읽는다. PowerShell 실패 시 None."""
    plist = [str(p) for p in paths]
    if not plist:
        return []
    out = _run_powershell(_READ_SCRIPT, {"DH2_LNK_PATHS": "|".join(plist)})
    if out is None:
        return None
    infos: list[LinkInfo] = []
    for line in out.splitlines():
        parts = line.rstrip("\r").split("\t")
        if len(parts) < 4:
            continue
        p, target, workdir, icon = parts[0], parts[1], parts[2], parts[3]
        if icon == "ERR" and not target:
            infos.append(LinkInfo(Path(p), "", "", "", error=True))
        else:
            infos.append(LinkInfo(Path(p), target, workdir, icon))
    return infos


def write_link(lnk_path: Path, target: Path, working_dir: Path) -> bool:
    """.lnk 를 만든다/덮어쓴다 (아이콘 = 대상 exe 의 첫 아이콘). 성공 여부."""
    out = _run_powershell(_WRITE_SCRIPT, {
        "DH2_LNK_PATH": str(lnk_path),
        "DH2_LNK_TARGET": str(target),
        "DH2_LNK_WORKDIR": str(working_dir),
        "DH2_LNK_DESC": "대항해시대 II 세이브 에디터 — 시작 위치의 KOUKAI2.DAT 를 바로 엽니다",
    })
    return out is not None and lnk_path.is_file()


# ---------------------------------------------------------------------------
# 상태 판정 / 만들기
# ---------------------------------------------------------------------------

def classify(
    info: Optional[LinkInfo],
    exe: "str | os.PathLike[str]",
    save_dir: "str | os.PathLike[str]",
    target_exists: Callable[[str], bool] = os.path.exists,
) -> State:
    """같은 이름의 .lnk(info, 없으면 None) 가 지금 실행 환경(exe·세이브 폴더)에 대해 어떤 상태인가."""
    if info is None:
        return State.MISSING
    if info.error or not is_our_exe(info.target):
        return State.FOREIGN
    if not target_exists(os.path.expandvars(info.target)):
        return State.BROKEN
    if same_path(info.target, exe) and same_path(info.working_dir, save_dir):
        return State.CURRENT
    return State.DIFFERENT


def inspect_desktop(
    desktop: Path,
    exe: "str | os.PathLike[str]",
    save_dir: "str | os.PathLike[str]",
    reader: Callable[[Iterable[Path]], Optional[list[LinkInfo]]] = read_links,
) -> tuple[Optional[State], Optional[LinkInfo]]:
    """desktop 의 SHORTCUT_NAME 상태. PowerShell 이 실패하면 (None, None)."""
    lnk = desktop / SHORTCUT_NAME
    if not lnk.exists():
        return State.MISSING, None
    infos = reader([lnk])
    if infos is None:
        return None, None
    info = infos[0] if infos else LinkInfo(lnk, "", "", error=True)
    return classify(info, exe, save_dir), info


def should_ask_automatically(state: State, found_by_dialog: bool) -> bool:
    """시작 때 자동으로 「바로가기 만들까요」 를 물을지.

    - MISSING / BROKEN : 항상 (없거나 끊겼으니 만들어야 의미가 있다)
    - DIFFERENT        : 사용자가 파일 선택 창(또는 인자)으로 직접 고른 세이브일 때만.
                         게임 폴더에서 자동으로 찾은 경우엔 이미 바로가기가 있으므로 묻지 않는다.
    - CURRENT / FOREIGN: 묻지 않는다.
    """
    if state in (State.MISSING, State.BROKEN):
        return True
    if state is State.DIFFERENT:
        return found_by_dialog
    return False


def create_or_update(
    desktop: Path,
    exe: Path,
    save_dir: Path,
    writer: Callable[[Path, Path, Path], bool] = write_link,
    reader: Callable[[Iterable[Path]], Optional[list[LinkInfo]]] = read_links,
) -> Result:
    """바로가기를 만들거나 갱신한다. 실패해도 예외를 내지 않고 Result 로 돌려준다."""
    lnk = desktop / SHORTCUT_NAME
    state, _ = inspect_desktop(desktop, exe, save_dir, reader=reader)
    if state is None:
        return Result(False, "기존 바로가기를 확인하지 못했습니다 (PowerShell 실행 실패).")
    if state is State.FOREIGN:
        return Result(
            False,
            f"같은 이름의 다른 바로가기가 이미 있어 만들지 않았습니다.\n{lnk}",
            lnk,
        )
    if state is State.CURRENT:
        return Result(True, f"이미 만들어져 있습니다.\n{lnk}", lnk)
    if not exe.is_file():
        return Result(False, f"실행 파일을 찾을 수 없습니다.\n{exe}")
    if not save_dir.is_dir():
        return Result(False, f"세이브 폴더를 찾을 수 없습니다.\n{save_dir}")
    try:
        ok = writer(lnk, exe, save_dir)
    except Exception as e:  # 어떤 실패도 프로그램 실행을 막지 않는다
        return Result(False, f"바로가기를 만들지 못했습니다: {e}")
    if not ok:
        return Result(False, "바로가기를 만들지 못했습니다 (바탕화면에 쓸 수 없거나 PowerShell 실행 실패).")
    verb = "갱신" if state in (State.BROKEN, State.DIFFERENT) else "생성"
    return Result(True, f"바로가기를 {verb}했습니다.\n{lnk}", lnk)


# ---------------------------------------------------------------------------
# 제거
# ---------------------------------------------------------------------------

def scan_dirs() -> list[Path]:
    """제거 때 훑을 폴더들 — 바탕화면 후보 전부 + 시작 메뉴(프로그램)."""
    dirs = list(desktop_candidates())
    sm = start_menu_programs_dir()
    if sm is not None and not any(same_path(sm, d) for d in dirs):
        dirs.append(sm)
    return dirs


def _iter_lnk_files(base: Path, max_depth: int) -> Iterable[Path]:
    """base 아래 .lnk 파일 (심볼릭 링크 폴더는 따라가지 않고, 깊이 제한)."""
    base_depth = len(base.parts)
    try:
        for root, dirs, files in os.walk(base, followlinks=False):
            depth = len(Path(root).parts) - base_depth
            if depth >= max_depth:
                dirs[:] = []
            for f in files:
                if f.lower().endswith(".lnk"):
                    yield Path(root) / f
    except OSError:
        return


def find_our_links(
    dirs: Iterable[Path],
    reader: Callable[[Iterable[Path]], Optional[list[LinkInfo]]] = read_links,
    max_depth: int = 2,
) -> Optional[list[LinkInfo]]:
    """dirs 안의 .lnk 중 대상이 우리 exe 인 것. PowerShell 실패 시 None."""
    all_lnks: list[Path] = []
    seen: set[str] = set()
    for d in dirs:
        for p in _iter_lnk_files(d, max_depth):
            k = _norm(p)
            if k not in seen:
                seen.add(k)
                all_lnks.append(p)
    if not all_lnks:
        return []
    infos = reader(all_lnks)
    if infos is None:
        return None
    return [i for i in infos if not i.error and is_our_exe(i.target)]


def remove_links(
    dirs: Optional[Iterable[Path]] = None,
    reader: Callable[[Iterable[Path]], Optional[list[LinkInfo]]] = read_links,
    delete: Callable[[Path], None] = os.remove,
) -> Optional[list[RemoveItem]]:
    """우리 바로가기만 찾아 지운다. 스캔 실패(PowerShell) 시 None, 아니면 항목별 결과."""
    ours = find_our_links(scan_dirs() if dirs is None else dirs, reader=reader)
    if ours is None:
        return None
    return delete_links(ours, delete=delete)


def delete_links(
    links: Iterable[LinkInfo],
    delete: Callable[[Path], None] = os.remove,
) -> list[RemoveItem]:
    """find_our_links 가 찾아 준 .lnk 들을 지운다 (대상 확인은 찾을 때 이미 끝났다)."""
    items: list[RemoveItem] = []
    for info in links:
        try:
            delete(info.path)
            items.append(RemoveItem(info.path, True))
        except OSError as e:
            items.append(RemoveItem(info.path, False, str(e)))
    return items


# ---------------------------------------------------------------------------
# 「다시 묻지 않기」 저장 — 사용자별 (%LOCALAPPDATA%\Koukai2Editor\shortcut_prompt.txt)
# ---------------------------------------------------------------------------
# .dh2editor_seen(게임 폴더 옆) 과 달리 사용자 폴더에 둔다:
#  - 바로가기는 사용자별 바탕화면의 것이라, 게임 폴더(여러 Windows 사용자가 공유하거나
#    읽기 전용일 수 있음)에 두면 다른 사용자의 질문까지 꺼 버린다.
#  - 게임 폴더가 여러 개여도 「이 PC·이 사용자에게 묻지 않기」 는 한 번이면 충분하다.
# 값은 "1"(묻지 않음) 한 가지. 파일이 없거나 읽기 실패면 「묻는다」.
# --remove-shortcuts 가 이 파일도 함께 지운다.

def _prompt_flag_path(base: Optional[Path] = None) -> Optional[Path]:
    if base is None:
        la = os.environ.get("LOCALAPPDATA")
        if not la:
            return None
        base = Path(la)
    return base / _PROMPT_FLAG_DIRNAME / _PROMPT_FLAG_FILENAME


def prompt_disabled(base: Optional[Path] = None) -> bool:
    p = _prompt_flag_path(base)
    if p is None:
        return False
    try:
        return p.read_text(encoding="utf-8").strip() == "1"
    except Exception:
        return False


def set_prompt_disabled(value: bool, base: Optional[Path] = None) -> bool:
    """True 면 「다시 묻지 않기」 저장, False 면 해제. 쓰기 실패해도 예외 없음(False 반환)."""
    p = _prompt_flag_path(base)
    if p is None:
        return False
    try:
        if value:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("1", encoding="utf-8")
        elif p.exists():
            p.unlink()
        return True
    except Exception:
        return False


def clear_prompt_flag(base: Optional[Path] = None) -> bool:
    """제거 시 우리 설정 파일(과 비어 있는 폴더)도 지운다. 지웠으면 True."""
    p = _prompt_flag_path(base)
    if p is None or not p.exists():
        return False
    try:
        p.unlink()
        try:
            p.parent.rmdir()  # 비어 있을 때만 성공
        except OSError:
            pass
        return True
    except OSError:
        return False


# ---------------------------------------------------------------------------
# 명령줄 --remove-shortcuts
# ---------------------------------------------------------------------------

def run_remove_cli(
    out: Callable[[str], None] = print,
    dirs: Optional[Iterable[Path]] = None,
    reader: Callable[[Iterable[Path]], Optional[list[LinkInfo]]] = read_links,
    delete: Callable[[Path], None] = os.remove,
    flag_base: Optional[Path] = None,
    clear_flag: bool = True,
) -> int:
    """GUI 없이 우리 바로가기를 찾아 지우고 결과를 out 으로 출력.

    종료 코드: 0 = 성공(지울 것이 없었던 경우 포함) / 1 = 실패(스캔 불가 또는 일부 삭제 실패).
    """
    if os.name != "nt":
        out("이 기능은 Windows 에서만 동작합니다.")
        return 1
    items = remove_links(dirs, reader=reader, delete=delete)
    if items is None:
        out("[실패] 바로가기를 확인하지 못했습니다 (PowerShell 실행 실패).")
        return 1
    if not items:
        out("지울 바로가기가 없습니다. (바탕화면·시작 메뉴에서 이 프로그램을 가리키는 바로가기를 찾지 못했습니다)")
    failed = 0
    for it in items:
        if it.removed:
            out(f"[삭제] {it.path}")
        else:
            failed += 1
            out(f"[실패] {it.path} — {it.error}")
    if clear_flag and clear_prompt_flag(flag_base):
        out("[삭제] 「다시 묻지 않기」 설정 파일")
    if items:
        out(f"바로가기 {len(items) - failed}개를 지웠습니다." + (f" ({failed}개 실패)" if failed else ""))
    return 1 if failed else 0
