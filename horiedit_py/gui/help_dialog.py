"""도움말 다이얼로그 모음.

- show_getting_started: 처음 사용 안내 (설치 / 실행 / 첫 편집)
- show_features_dialog: 편집 가능한 항목 안내
- show_experimental_warning: 시험 기능 / 주의 사항
- show_whats_new: 새 기능 소개 (최초 실행 / 버전업 시 1회)
- show_about: 버전 / GitHub 링크
"""

from __future__ import annotations

import tkinter as tk
import webbrowser
from tkinter import ttk

from horiedit_py import __version__


GITHUB_URL = "https://github.com/genishs/dh2-py-editor"
ISSUES_URL = f"{GITHUB_URL}/issues"


# ---------------------------------------------------------------------------
# 콘텐츠
# ---------------------------------------------------------------------------

_GETTING_STARTED_TEXT = """\
처음 사용 안내 — 설치부터 첫 편집까지

이 프로그램은 게임 폴더에 설치할 필요가 없습니다.
아무 곳에나 두고 실행한 뒤, 게임의 저장 파일만
선택하면 됩니다.

──────────────────────────────────────────
[ 1. 설치하기 — 둘 중 편한 방법으로 ]

▶ 방법 A. 명령 한 줄로 설치 (권장)
   브라우저가 다운로드를 막는 경고를 아예 만나지
   않는 방법입니다.
   ① 키보드에서 [윈도우 키]를 누르고 "터미널"을
      입력해 터미널(또는 PowerShell)을 엽니다.
   ② 아래 한 줄을 붙여넣고 Enter:
        winget install genishs.Koukai2Editor
   ③ 설치 후에는 터미널에 koukai2-editor 를
      입력하면 언제든 실행됩니다.

▶ 방법 B. 직접 다운로드
   ① GitHub 의 Releases 페이지에서
      koukai2_editor-windows.zip 을 받습니다.
   ② 압축을 원하는 아무 폴더에나 풉니다.
      (게임 폴더가 아니어도 됩니다!)
   ③ koukai2_editor.exe 를 더블클릭합니다.
   · "위험할 수 있다"는 경고가 떠도 바이러스가
     발견된 것이 아닙니다 — 개인 취미 프로그램이라
     유료 서명 인증서가 없어서 뜨는 경고입니다.
     파란 SmartScreen 창이 뜨면
     [추가 정보] → [실행] 을 누르면 됩니다.

──────────────────────────────────────────
[ 2. 처음 실행했을 때 ]

   ① 프로그램을 실행하면 저장 파일을 고르는 창이
      뜹니다.
   ② 게임이 설치된 폴더에서 KOUKAI2.DAT 파일을
      찾아 선택합니다.
      (대항해시대 II 를 설치/압축해제한 폴더 안에
      있습니다. 게임에서 한 번이라도 저장해야
      편집할 내용이 생깁니다.)
   ③ 편집할 저장 칸(슬롯)을 고릅니다.
   ④ 원하는 탭(주인공/인물/선박/항구)에서 값을
      바꾸고 [저장] 을 누릅니다.
   ⑤ 게임을 다시 실행해 저장 칸을 불러오면 바뀐
      내용이 적용되어 있습니다.

──────────────────────────────────────────
[ 3. 꼭 알아두세요 ]

▶ 편집 전 백업
   저장 파일(KOUKAI2.DAT)을 다른 곳에 복사해
   두세요. 게임 본체(MAIN.EXE)를 건드리는 기능을
   쓸 때는 MAIN.EXE 도 함께 백업하세요.

▶ 게임을 켠 채로 편집하지 마세요
   게임(DOSBox 등)을 완전히 종료한 뒤 편집하고,
   편집이 끝난 뒤 게임을 실행하세요.

▶ 막히면 물어보세요
   [도움말] ▸ [GitHub 이슈 보기] 에서 질문을
   남기면 답변해 드립니다.
"""


_FEATURES_TEXT = """\
[ 세이브 칸 데이터 편집 — 탭 ]

▶ 주인공
  · 6 주인공별 데이터 (조안 / 카탈리나 / 오토 / 로페즈 / 피에트로 / 알)
  · 명성치 (무역 / 해적 / 모험)
  · 국가 친밀도 (포르투갈 / 스페인 / 오스만 / 잉글랜드 / 이탈리아 / 네덜란드)
  · 작위
  · 보유 자금
  · 현재 주인공 표시

▶ 인물
  · 119 명 NPC / 동료 검색 + 편집
  · 능력치 8 가지 (통솔 / 항해 / 지식 / 직감 / 용기 / 검술 / 매력 / 운명)
  · 항해 / 전투 레벨 + 경험치
  · 특수 능력 5 가지 (교섭 / 회계 / 포술 / 지도작성 / 측량)
  · 소속 변경: 주인공 동료 등록 / 해제, 항구 정착민 변경
  · 동료로 등록하면 게임에 필요한 값이 자동으로 맞춰집니다.

▶ 선박
  · 함대 함선 6 척 편집 (현재 주인공)
  · 현재 상태: 선원 수, 내구도, 키, 돛, 무기 등
  · 선장, 컨디션, 진형
  · 함선 이름, 화물, 무기 사거리
  · 원래 함선 정보: 등장 공업치, 최대 내구도, 가격, 종류

▶ 항구
  · 130 개 항구
  · 항구 정보 (등장 공업치, 인구, 발전도 등)
  · 항구 경제 데이터 (상업치 / 공업치)

▶ 게임 설정 (함선 기본 데이터)
  · 함선 기본 성능: 회전력 / 돛 / 승무원 / 적재량 / 무기수 등
  · 함선 이름·모양
  · 항구 공급 수치 (효과 불확실, 시험)


[ 게임 전체 설정 — 도구 메뉴 ]

▶ 최대 내구도 상한 바꾸기
  · 조선소에서 새 배를 만들 때의 내구도 상한(기본 100)을 1~255 로 변경
  · 게임 본체 파일에서 해당 부분을 자동으로 찾아 바꿉니다
  · 세이브 칸과 무관 — 게임 전체에 적용
  · 처음 적용할 때 원본 백업(MAIN.EXE.beforeHullCap)을 자동으로 만듭니다
"""


_WARNINGS_TEXT = """\
⚠️ 시험 기능 / 주의 사항

▶ 백업 필수
  - 편집 전 저장 파일(KOUKAI2.DAT)과 게임 본체 파일(MAIN.EXE)을 반드시 복사해 두세요.
  - 일부 편집은 게임 동작에 부작용을 일으킬 수 있습니다 (특히 분석이 덜 된 영역).
  - 최대 내구도 상한 바꾸기 기능은 처음 적용할 때 .beforeHullCap 백업을 자동으로 만듭니다.

▶ 시험 기능 (효과 불확실)
  - 항구 공급 수치 (게임 설정 → 항구 공급 수치) — 바꿔도 게임 내 가격에
    바로 영향이 나타나지 않았습니다 (평균물가는 매월 1일에만 갱신).
  - 용도가 분명하지 않은 값의 임의 변경 — 자세한 분석 자료는 GitHub 를 참고하세요.

▶ 충돌 가능성
  - 인물 탭에서 소속을 직접 숫자로 바꾸면 두 인물이 충돌할 수 있습니다.
    가능하면 [소속 변경] 목록만 사용하세요.
  - 1~6번 주인공의 소속은 바꾸지 않는 것을 권합니다.

▶ 동료 등록 자동 맞춤
  - 동료로 바꾸면 게임에 필요한 값이 자동으로 함께 바뀝니다.
  - 한 가지라도 누락되면 게임 인물 목록에 표시되지 않으므로,
    직접 숫자 입력보다 [소속 변경] 목록 사용을 권합니다.

▶ 게임 본체 파일 수정 (도구 메뉴)
  - 게임 버전이 다르면 해당 부분을 찾지 못할 수 있고, 다이얼로그가 "찾지 못함" 을 표시합니다.
  - 찾더라도 다른 버전에서는 의미가 다를 수 있습니다.
  - [백업에서 복원] 으로 언제든 되돌릴 수 있도록 설계되었습니다.

▶ 문제 발견 시
  - GitHub 이슈로 신고: https://github.com/genishs/dh2-py-editor/issues
  - 가능하면 저장 파일(KOUKAI2.DAT)을, 되도록 게임 본체 파일(MAIN.EXE)도 함께 첨부해 주세요.
"""


_ABOUT_TEXT_FMT = """\
대항해시대 II 세이브 에디터

버전: {version}

원본: Borland Turbo C 시절의 HORIEDIT.C
재구현: Python + Tkinter

저장소: {github}
이슈 / 문의: {issues}

자세한 분석 자료는 GitHub 저장소를 참고하세요.
"""


_WHATS_NEW_TEXT = """\
대항해시대 II 세이브 에디터 — 새로워진 기능 안내

이 창은 처음 실행할 때, 그리고 새 버전으로 올라갈 때
한 번씩 보입니다. [도움말] ▸ [새 기능 소개] 에서
언제든 다시 볼 수 있어요.

──────────────────────────────────────────
★ 이번 버전에서 새로워진 것
   · winget 한 줄 설치 지원:
       winget install genishs.Koukai2Editor
     브라우저 다운로드 경고 없이 설치됩니다.
   · [도움말] ▸ [처음 사용 안내] — 설치부터
     첫 편집까지 차근차근 안내합니다.
   · 이름 입력 시 마지막 한글이 깨지던 버그를
     고쳤습니다.

──────────────────────────────────────────
1. 창 맨 위에 메뉴가 생겼어요
   [파일] [도구] [도움말] 에서 전체 기능을
   한눈에 찾을 수 있습니다.

2. 최대 내구도 상한 바꾸기
   [도구] ▸ [최대 내구도 상한 바꾸기...] 에서
   조선소에서 새로 만드는 배의 내구도 상한
   (기본 100)을 1~255 로 바꿀 수 있어요.
   · 게임 전체에 적용되며 세이브 칸과 무관합니다.
   · 처음 적용할 때 원본 백업을 자동으로 만들어
     두니 언제든 되돌릴 수 있습니다.

3. 인물을 내 동료로 등록 (인물 탭)
   [인물] 탭에서 인물을 고른 뒤 '소속 변경'에서
   원하는 주인공의 동료로 바로 등록/해제할 수
   있어요. 필요한 값이 자동으로 함께 맞춰지므로
   게임 안 동료 목록에 제대로 표시됩니다.

4. 도움말 메뉴
   · 편집 가능한 항목 — 전체 기능 목록
   · 시험 기능 / 주의 사항 — 편집 전 꼭 읽어주세요
   · GitHub 이슈 보기 / 버전 정보

──────────────────────────────────────────
편집 전에는 저장 파일(KOUKAI2.DAT)과 게임 본체
파일(MAIN.EXE)을 꼭 복사해 두세요.
문제가 있으면 [도움말] ▸ [GitHub 이슈 보기] 로
알려주세요.
"""


# ---------------------------------------------------------------------------
# 다이얼로그 helper
# ---------------------------------------------------------------------------

def _show_scrolling_text(
    parent: tk.Misc,
    title: str,
    body: str,
    width: int = 78,
    height: int = 28,
    extra_button: tuple[str, "object"] | None = None,
    checkbox_label: str | None = None,
    checkbox_initial: bool = False,
    on_close: "object" = None,
) -> None:
    """타이틀 + 스크롤 텍스트 + 닫기 (선택: 추가 버튼 / 체크박스) 다이얼로그.

    checkbox_label 이 주어지면 하단에 체크박스를 표시하고, 창을 닫을 때
    on_close(checked: bool) 콜백을 호출한다 (X 버튼 포함).
    checkbox_initial 로 체크박스 초기 상태를 지정한다.
    """
    win = tk.Toplevel(parent)
    win.title(title)
    win.transient(parent)
    win.resizable(True, True)

    outer = ttk.Frame(win, padding=10)
    outer.pack(fill="both", expand=True)

    text_frame = ttk.Frame(outer)
    text_frame.pack(fill="both", expand=True)
    txt = tk.Text(
        text_frame, width=width, height=height, wrap="word",
        font=("Malgun Gothic", 10),
    )
    sb = ttk.Scrollbar(text_frame, orient="vertical", command=txt.yview)
    txt.configure(yscrollcommand=sb.set)
    txt.insert("1.0", body)
    txt.configure(state="disabled")
    txt.pack(side="left", fill="both", expand=True)
    sb.pack(side="right", fill="y")

    check_var = tk.BooleanVar(value=checkbox_initial)

    def _do_close() -> None:
        if on_close is not None:
            try:
                on_close(bool(check_var.get()))
            except Exception:
                pass
        win.destroy()

    btns = ttk.Frame(outer)
    btns.pack(fill="x", pady=(8, 0))
    if checkbox_label is not None:
        ttk.Checkbutton(
            btns, text=checkbox_label, variable=check_var,
        ).pack(side="left", padx=4)
    if extra_button is not None:
        label, cmd = extra_button
        ttk.Button(btns, text=label, command=cmd).pack(side="left", padx=4)
    ttk.Button(btns, text="닫기", command=_do_close).pack(side="right", padx=4)

    win.protocol("WM_DELETE_WINDOW", _do_close)
    win.grab_set()
    win.focus_set()

    # 부모 중앙 정렬
    win.update_idletasks()
    try:
        px = parent.winfo_rootx()
        py = parent.winfo_rooty()
        pw = parent.winfo_width()
        ph = parent.winfo_height()
        w = win.winfo_width()
        h = win.winfo_height()
        win.geometry(f"+{px + (pw - w) // 2}+{py + max(0, (ph - h) // 4)}")
    except tk.TclError:
        pass


# ---------------------------------------------------------------------------
# 공개 API
# ---------------------------------------------------------------------------

def show_getting_started(parent: tk.Misc) -> None:
    _show_scrolling_text(
        parent, "처음 사용 안내", _GETTING_STARTED_TEXT, height=30,
        extra_button=("GitHub 열기", lambda: webbrowser.open(GITHUB_URL)),
    )


def show_features_dialog(parent: tk.Misc) -> None:
    _show_scrolling_text(parent, "편집 가능한 항목", _FEATURES_TEXT)


def show_experimental_warning(parent: tk.Misc) -> None:
    _show_scrolling_text(
        parent, "시험 기능 / 주의 사항", _WARNINGS_TEXT,
        extra_button=("GitHub 이슈 열기", lambda: webbrowser.open(ISSUES_URL)),
    )


def show_whats_new(
    parent: tk.Misc,
    show_on_startup: bool = True,
    on_close: "object" = None,
) -> None:
    """새 기능 소개 창.

    하단에 '프로그램 시작 시 새 기능 소개 창 열기' 체크박스를 표시한다.
    체크박스 초기 상태는 show_on_startup, 창을 닫을 때 on_close(checked: bool)
    를 호출해 설정을 저장한다 (X 버튼 포함). 자동 표시 경로와 [도움말] 메뉴
    경로 모두 동일한 체크박스를 쓴다.
    """
    _show_scrolling_text(
        parent, "새 기능 소개", _WHATS_NEW_TEXT, height=30,
        extra_button=(
            "편집 가능한 항목 전체 보기",
            lambda: show_features_dialog(parent),
        ),
        checkbox_label="프로그램 시작 시 새 기능 소개 창 열기",
        checkbox_initial=show_on_startup,
        on_close=on_close,
    )


def show_about(parent: tk.Misc) -> None:
    body = _ABOUT_TEXT_FMT.format(
        version=__version__, github=GITHUB_URL, issues=ISSUES_URL,
    )
    _show_scrolling_text(
        parent, "버전 정보", body, height=14,
        extra_button=("GitHub 열기", lambda: webbrowser.open(GITHUB_URL)),
    )


def open_issues_page() -> None:
    webbrowser.open(ISSUES_URL)
