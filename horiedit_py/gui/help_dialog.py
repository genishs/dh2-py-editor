"""도움말 다이얼로그 모음.

- show_features_dialog: 편집 가능한 항목 안내
- show_experimental_warning: 시험 기능 경고
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

_FEATURES_TEXT = """\
[ 슬롯 데이터 편집 — 노트북 탭 ]

▶ 주인공
  · 6 주인공별 데이터 (조안 / 카탈리나 / 오토 / 로페즈 / 피에트로 / 알)
  · 명성치 (무역 / 해적 / 모험)
  · 국가 친밀도 (포르투갈 / 스페인 / 오스만 / 잉글랜드 / 이탈리아 / 네덜란드)
  · 작위 (peer)
  · 보유 자금
  · c_hero (현재 활성 주인공) 표시

▶ 인물
  · 119 명 NPC / 동료 검색 + 편집
  · 능력치 8 가지 (통솔 / 항해 / 지식 / 직감 / 용기 / 검술 / 매력 / 운명)
  · 항해 / 전투 레벨 + 경험치
  · 비트 능력 5 가지 (교섭 / 회계 / 포술 / 지도작성 / 측량)
  · 소속 변경: hero 동료 등록 / 해제, 항구 정착민 변경
  · 동료 등록 시 6 byte 자동 동기화 (pos / none1 / port / none2[0] + party 배열)

▶ 선박
  · 함대 함선 6 척 편집 (현재 주인공)
  · ship1: 선원 수, 내구도, 키, 돛, 무기 등 현재 상태
  · ship2: 선장, 컨디션, 진형
  · ship3: 함선 이름, 화물, 무기 사거리
  · 원래 함선 정보 (12 byte record): 등장 공업치, 최대 내구도, 가격, 분류

▶ 항구
  · 130 개 항구
  · 항구 카탈로그 (등장 공업치, 인구, 발전도 등)
  · 항구 경제 데이터

▶ 게임 설정 (MAIN.EXE 의 함선 ROM)
  · 함선 정적 스펙 (Ship4 ROM): lrudder / lsail / lcrew / dcrew / capacity / lnowea
  · 함선 이름·외형 (Ship5 ROM): ship_name, sform, bform
  · 항구 공급 수치 (효과 미확인, 시험)


[ 전역 패치 — 도구 메뉴 ]

▶ 최대 내구도 수정 (issue #5)
  · 조선소 신조 청구 내구력 cap (게임 기본 100) 을 1..255 로 변경
  · MAIN.EXE 의 'MOV DX, 100' instruction 2 곳을 자동 탐색
  · 슬롯과 무관 — 게임 전체에 영향
  · 첫 적용 시 MAIN.EXE.beforeHullCap 자동 백업
"""


_WARNINGS_TEXT = """\
⚠️ 시험 기능 / 가설 단계 — 주의사항

▶ 백업 필수
  - 편집 전 KOUKAI2.DAT 와 MAIN.EXE 를 반드시 복사해 두세요.
  - 일부 편집은 게임 동작에 부작용을 일으킬 수 있습니다 (특히 분석이 가설 단계인 영역).
  - 최대 내구도 수정 기능은 첫 패치 시 .beforeHullCap 백업을 자동 생성합니다.

▶ 시험 기능 (효과 미확인 / 의미 불명)
  - 항구 공급 수치 (게임 설정 → 항구 공급 수치) — 변경 효과가 게임 내 가격에
    즉시 반영되지 않음 (평균물가는 derived, 매월 1일 갱신 가설).
  - 의미 불명 byte 의 임의 변경 — 분석 문서 (analysis/) 에 가설 단계인 영역
    이 표시되어 있습니다.

▶ 충돌 가능성
  - 인물 탭 의 pos byte 를 NPC 카탈로그 ID (0x01..0x44) 로 변경 시 두 인물이
    같은 catalog 로 인식되어 충돌 가능. Combobox 의 안전 옵션만 권장.
  - 주인공 인물 (idx 0..5) 의 pos 변경 권장 안 함.

▶ 동료 등록의 6 byte 동기화 (v0.4.12)
  - pos / none1 / port / none2[0] / party 배열 entry / party counter
  - 한 byte 라도 누락되면 게임 인물 목록에 표시 안 됨.
  - 에디터의 Combobox 사용 시 자동 동기화되니 raw byte 편집 (Spinbox) 보다 권장.

▶ MAIN.EXE 패치 (도구 메뉴)
  - MAIN.EXE 빌드가 다를 경우 signature 미발견 → 다이얼로그가 "찾지 못함" 표시.
  - signature 가 발견되더라도 다른 빌드/언어 버전에서는 의미가 다를 수 있음.
  - 백업에서 복원으로 언제든 되돌릴 수 있도록 설계됨.

▶ 문제 발견 시
  - GitHub 이슈로 신고: https://github.com/genishs/dh2-py-editor/issues
  - 가능하면 KOUKAI2.DAT (가능하면 MAIN.EXE 도) 와 함께 첨부.
"""


_ABOUT_TEXT_FMT = """\
대항해시대 II 세이브 에디터

버전: {version}

원본: Borland Turbo C 시절의 HORIEDIT.C
재구현: Python + Tkinter
빌드: PyInstaller --onefile

저장소: {github}
이슈 / 문의: {issues}

분석 문서: analysis/ 디렉토리 (저장소)
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
) -> None:
    """타이틀 + 스크롤 텍스트 + 닫기 (선택: 추가 버튼) 다이얼로그."""
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

    btns = ttk.Frame(outer)
    btns.pack(fill="x", pady=(8, 0))
    if extra_button is not None:
        label, cmd = extra_button
        ttk.Button(btns, text=label, command=cmd).pack(side="left", padx=4)
    ttk.Button(btns, text="닫기", command=win.destroy).pack(side="right", padx=4)

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

def show_features_dialog(parent: tk.Misc) -> None:
    _show_scrolling_text(parent, "편집 가능한 항목", _FEATURES_TEXT)


def show_experimental_warning(parent: tk.Misc) -> None:
    _show_scrolling_text(
        parent, "시험 기능 / 가설 단계 경고", _WARNINGS_TEXT,
        extra_button=("GitHub 이슈 열기", lambda: webbrowser.open(ISSUES_URL)),
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
