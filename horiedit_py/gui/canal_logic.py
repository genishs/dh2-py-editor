"""운하 개통/원상복원 화면의 「결정」 로직 — 위젯과 분리 (단위 시험 대상).

tkinter 를 가져오지 않는다. 입력(게임 폴더, 운하 상태) → 출력(표시 문구·버튼 라벨·활성 여부·
확인 창 본문·결과 문구) 만 다룬다. 실제 파일 변경은 `horiedit_py.data.canal` 이 한다.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple, Union

from horiedit_py.data import canal
from horiedit_py.data.canal import CLOSED, OPEN, UNKNOWN
from horiedit_py.data.ls11 import Ls11Error

WORLDMAP_NAME = "WORLDMAP.LZW"

#: 화면에 나오는 순서
CANAL_ORDER: Tuple[str, ...] = ("suez", "panama")

STATUS_OPEN = "개통됨"
STATUS_CLOSED = "원상(닫힘)"
STATUS_UNKNOWN = "알 수 없음 — 다른 패치가 적용된 것으로 보여 바꾸지 않습니다"
STATUS_UNREADABLE = "확인할 수 없음"

BTN_OPEN = "개통"
BTN_RESTORE = "원상복원"

MSG_NO_WORLDMAP = (
    "게임 폴더에서 지도 파일(WORLDMAP.LZW)을 찾지 못했습니다.\n"
    "저장 파일과 게임이 함께 있는 게임 폴더에서 실행해 주세요."
)
MSG_NO_GAME_DIR = "게임 폴더를 알 수 없어 지도 파일(WORLDMAP.LZW)을 찾지 못했습니다."


#: 운하는 세이브가 아니라 게임 폴더의 지도 파일을 바꾼다 — 안내문(운하 탭·처음 사용 안내)에 쓴다.
SCOPE_NOTE = (
    "운하는 게임 폴더 단위로 적용됩니다. 세이브와 무관하게 그 게임 폴더의 모든 세이브와 새 게임에 똑같이 적용됩니다."
)

#: 원상복원(닫기) 확인 창에만 넣는 경고 — 운하 안에서 저장한 세이브가 있으면 함대가 갇힐 수 있다.
RESTORE_WARNING = (
    "· 운하 안(또는 바로 근처 수로)에서 저장한 세이브가 있다면, 닫은 뒤 그 세이브를 불러오면 "
    "함대가 육지 위에 놓여 갇힐 수 있습니다. 운하를 완전히 빠져나온 곳에서 저장한 뒤 닫으세요."
)


def find_worldmap(game_dir: Union[str, os.PathLike, None]) -> Optional[Path]:
    """게임 폴더 바로 아래에서 WORLDMAP.LZW 를 대소문자 무시로 찾는다. 없으면 None.

    파일만 인정한다(같은 이름의 폴더는 무시). 여러 개면 이름순 첫 번째.
    """
    if game_dir is None:
        return None
    base = Path(game_dir)
    try:
        names = sorted(os.listdir(base))
    except OSError:
        return None
    for name in names:
        if name.lower() == WORLDMAP_NAME.lower() and (base / name).is_file():
            return base / name
    return None


@dataclass(frozen=True)
class RowView:
    """운하 한 줄의 표시 결정."""
    key: str
    name: str            # 「수에즈 운하」
    status_text: str     # 「개통됨」 …
    button_label: str    # 「원상복원」 / 「개통」 / 「」
    button_enabled: bool
    target_mode: Optional[str]  # 버튼을 누르면 가려는 상태 (canal.OPEN / canal.CLOSED), 비활성이면 None


def describe_row(key: str, state: Optional[str]) -> RowView:
    """운하 상태(open/closed/unknown, 읽지 못했으면 None) → 한 줄 표시."""
    name = canal.CANALS[key].name
    if state == OPEN:
        return RowView(key, name, STATUS_OPEN, BTN_RESTORE, True, CLOSED)
    if state == CLOSED:
        return RowView(key, name, STATUS_CLOSED, BTN_OPEN, True, OPEN)
    if state == UNKNOWN:
        return RowView(key, name, STATUS_UNKNOWN, BTN_OPEN, False, None)
    return RowView(key, name, STATUS_UNREADABLE, BTN_OPEN, False, None)


def describe_rows(states: Optional[Dict[str, str]]) -> Tuple[RowView, ...]:
    states = states or {}
    return tuple(describe_row(k, states.get(k)) for k in CANAL_ORDER)


def backup_path(path: Union[str, os.PathLike]) -> Path:
    return Path(str(path) + canal.BACKUP_SUFFIX)


def confirm_message(key: str, target_mode: str, path: Union[str, os.PathLike]) -> str:
    """확인 창 본문: 무엇을 바꾸는지·게임을 끌 것·백업·항구 자동 이동 한계."""
    p = Path(path)
    c = canal.CANALS[key]
    bak = backup_path(p)
    if target_mode == OPEN:
        what = f"{c.name}를 개통합니다. (지도 파일 {p.name} 의 해당 부분만 바꿉니다)"
    else:
        what = f"{c.name}를 원래 상태(닫힘)로 되돌립니다. (지도 파일 {p.name} 의 해당 부분만 바꿉니다)"
    if bak.exists():
        backup_line = f"· 원본 백업({bak.name})이 이미 있어, 다시 만들거나 덮어쓰지 않습니다."
    else:
        backup_line = (
            f"· 첫 변경이므로 원본 백업 {bak.name} 이(가) 같은 폴더에 만들어집니다.\n"
            f"  (나중에 이 파일의 이름을 {p.name} 로 되돌리면 완전한 원상복구입니다.)"
        )
    lines = [
        what,
        "",
        "· 게임(DOSBox)을 완전히 종료한 상태여야 합니다. 켜 둔 채로 바꾸면 반영되지 않거나 오류가 날 수 있습니다.",
        backup_line,
        "· 항구에서 [자동 이동] 으로 가는 항로는 운하를 쓰지 않습니다.",
        "  운하 근처까지 가서 직접 조종해 지나가야 합니다.",
    ]
    if target_mode != OPEN:
        lines.append(RESTORE_WARNING)
    lines += ["", "계속할까요?"]
    return "\n".join(lines)


def confirm_title(key: str, target_mode: str) -> str:
    c = canal.CANALS[key]
    return f"{c.name} {'개통' if target_mode == OPEN else '원상복원'}"


def success_message(key: str, target_mode: str, path: Union[str, os.PathLike]) -> str:
    c = canal.CANALS[key]
    done = "개통했습니다" if target_mode == OPEN else "원래 상태(닫힘)로 되돌렸습니다"
    return (
        f"{c.name}를 {done}.\n\n"
        "게임을 (다시) 실행하면 반영됩니다.\n"
        "· 항구 자동 이동은 운하를 쓰지 않으니, 운하 근처에서 직접 조종해 지나가 보세요."
    )


def changed_underfoot_message(key: str) -> str:
    c = canal.CANALS[key]
    return (
        f"{c.name}의 상태가 화면에 표시된 것과 달라졌습니다(다른 프로그램이 파일을 바꾼 것 같습니다).\n"
        "아무것도 바꾸지 않았고, 화면을 새로 고쳤습니다. 다시 확인해 주세요."
    )


def error_message(exc: BaseException, path: Union[str, os.PathLike]) -> str:
    """예외를 사용자 말로. 항상 「파일은 바뀌지 않았다」 안내를 포함한다."""
    name = Path(path).name
    if isinstance(exc, canal.CanalError):
        # CanalError 메시지는 이미 한국어(「바꾸지 않음」 포함)
        detail = f"{exc}"
        head = "운하를 바꿀 수 없습니다."
    elif isinstance(exc, Ls11Error):
        detail = (
            f"{name} 이(가) 이 도구가 아는 지도 파일 형식이 아닙니다.\n(자세히: {exc})"
        )
        head = "지도 파일을 읽을 수 없습니다."
    elif isinstance(exc, PermissionError):
        detail = (
            f"{name} 에 쓸 수 없습니다. 게임(DOSBox)이 켜져 있거나 파일이 읽기 전용일 수 있습니다.\n"
            "게임을 완전히 종료하고 다시 시도해 주세요."
        )
        head = "파일에 쓸 수 없습니다."
    elif isinstance(exc, OSError):
        detail = f"{name} 을(를) 읽거나 쓰는 중 오류가 났습니다.\n(자세히: {exc})"
        head = "파일 오류가 났습니다."
    else:
        detail = f"예상하지 못한 오류입니다.\n(자세히: {type(exc).__name__}: {exc})"
        head = "운하를 바꾸지 못했습니다."
    return f"{head}\n\n{detail}\n\n{name} 은(는) 바뀌지 않았습니다. (게임 파일은 그대로입니다.)"


#: 상태 읽기·적용에서 사용자 안내로 바꿔 줄 예외 묶음
HANDLED_ERRORS = (canal.CanalError, Ls11Error, OSError)


def read_states(path: Union[str, os.PathLike]) -> Tuple[Optional[Dict[str, str]], Optional[str]]:
    """(운하별 상태, 오류 문구). 읽기에 성공하면 오류 문구는 None, 실패하면 상태는 None."""
    try:
        return canal.file_canal_states(str(path)), None
    except HANDLED_ERRORS as e:
        return None, error_message(e, path)


@dataclass(frozen=True)
class ApplyResult:
    ok: bool
    changed: bool          # 파일을 실제로 바꿨는가
    message: str
    states: Optional[Dict[str, str]]  # 갱신된 상태(읽기 실패 시 None)


def apply_toggle(path: Union[str, os.PathLike], key: str, expected_state: str) -> ApplyResult:
    """화면에 보인 상태(expected_state)에서 반대쪽으로 한 번 바꾼다.

    1) 파일의 지금 상태를 다시 읽어, 화면의 것과 다르면 아무것도 바꾸지 않고 알린다.
    2) UNKNOWN 이면 거부.
    3) `apply_canal_to_file` 로 전환 → 상태를 다시 읽어 목표와 같은지 확인.
    """
    if expected_state == OPEN:
        target = CLOSED
    elif expected_state == CLOSED:
        target = OPEN
    else:
        return ApplyResult(False, False, "이 운하는 바꿀 수 없는 상태입니다.", None)
    try:
        now = canal.file_canal_states(str(path))
        if now.get(key) != expected_state:
            return ApplyResult(False, False, changed_underfoot_message(key), now)
        canal.apply_canal_to_file(str(path), key, target, backup=True)
        after = canal.file_canal_states(str(path))
    except HANDLED_ERRORS as e:
        states, _err = read_states(path)
        return ApplyResult(False, False, error_message(e, path), states)
    if after.get(key) != target:
        return ApplyResult(
            False, True,
            "파일은 썼지만 다시 읽은 결과가 기대와 다릅니다. 원본 백업"
            f"({backup_path(path).name})으로 되돌려 주세요.",
            after,
        )
    return ApplyResult(True, True, success_message(key, target, path), after)
