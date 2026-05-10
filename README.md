# 대항해시대 II 세이브 에디터 (Python + Tkinter)

코에이 *대항해시대 II* (Koukai 2 / Uncharted Waters 2) 의 세이브 파일
(`KOUKAI2.DAT`) 및 게임 실행 데이터 (`MAIN.EXE`) 를 직접 바이트 단위로 편집하는
GUI 도구.

원본 Borland Turbo C / DOS 시절의 `HORIEDIT.C` 를 분석해 Python 으로 재구현
하고, horiedit 가 다루지 않던 영역(MAIN.EXE 의 함선 ROM 데이터 등)을 추가했다.

- Repository: https://github.com/genishs/dh2-py-editor
- Releases: https://github.com/genishs/dh2-py-editor/releases

---

## 빠른 시작 (배포판 사용)

1. [Releases](https://github.com/genishs/dh2-py-editor/releases) 에서 최신
   `koukai2_editor.exe` 를 받는다.
2. `KOUKAI2.DAT` 가 있는 게임 폴더에 `koukai2_editor.exe` 를 복사한다.
3. 더블클릭 또는 `cmd` / PowerShell 에서 실행 → GUI 창이 뜬다.

> **백업 권장** — 편집 전 `KOUKAI2.DAT` 와 `MAIN.EXE` 를 백업하세요.
> `MAIN.EXE.bak` 가 동봉되어 있으면 그것이 원본이므로 보존하세요.

`.exe` 는 다음 순서로 세이브 파일을 찾고, 모두 실패하면 GUI 파일 선택
대화상자를 띄운다.

1. 명령행 인자로 받은 경로
2. 현재 작업 디렉토리(cwd) 의 `KOUKAI2.DAT` (또는 소문자 `koukai2.dat`)
3. 실행파일 자체가 위치한 폴더의 `KOUKAI2.DAT`
4. (개발 환경) 소스 트리의 `originalgame/koukai2/KOUKAI2.DAT`

---

## 기능

### UI 개요

```
┌────────────────────────────────────────────────────┐
│  [세이브 슬롯]  ① ② ③ ④ ⑤   [프로그램 종료]       │
│                 ⑥ ⑦ ⑧ ⑨ ⑩                          │
├────────────────────────────────────────────────────┤
│  [주인공][인물][선박][게임 설정]  ← 탭              │
│                                                    │
│       ... 선택한 탭의 폼 ...                       │
│                                                    │
├────────────────────────────────────────────────────┤
│  파일: ...\KOUKAI2.DAT | 슬롯: 1 | 주인공: ...     │
└────────────────────────────────────────────────────┘
```

상단 슬롯 라디오를 클릭하면 해당 슬롯이 로드되고 모든 탭 내용이 갱신된다.
빈 슬롯은 비활성 상태로 표시.

### 주인공 탭 (구현 완료)

현재 슬롯의 6명 주인공을 콤보박스로 골라 능력치/자금을 편집.

| 항목 | 위젯 | 비고 |
|---|---|---|
| 무역 명성 | Spinbox | 0~65535 |
| 해적 명성 | Spinbox | |
| 모험 명성 | Spinbox | |
| 친밀도 (포/스/오/잉/이/네) | Spinbox | -100 ~ +100 (저장은 0~200) |
| 작위 (peer) | Combobox | 알(c_hero=5) → 이탈리아 작위, 그 외 → 일반 작위 |
| 자금 | Spinbox | 0 ~ 0xFFFFFFFF, 모든 주인공 공유 |

`[다시 불러오기]` `[저장]` 두 버튼. 저장 시 `fp.flush()` 보장.

### 인물 / 선박 / 게임 설정 탭 (스텁)

다음 단계에서 구현. 데이터 레이어 (`horiedit_py/data/`) 는 모두 준비되어
있어 UI 만 작성하면 된다.

- **인물**: 검색 (성/이름 부분 일치) → 능력치, 경험치, 능력 비트필드, 정착
  항구 편집
- **선박**: 영웅 함대 편집 + 25종 함선 템플릿 편집 (`Ship4`, `Ship5`,
  클램프 체인 포함)
- **게임 설정**: `MAIN.EXE` 의 `Ship4 ROM`(0x40871, 확정), `Ship5 ROM`
  (0x405FD, 확정), 등장공업치 추정 테이블, 슬롯 내 등장공업치 캐시 편집

> ⚠️ **lhull 메뉴는 현재 비활성** — 이전 v0.2 까지의 "신조 시 최대 내구도"
> 위치 추정(`0x424AE`)이 사용자 검증으로 잘못된 것이 확인되었습니다 (실제
> SHIP의 lhull = 81 이지만 그 위치 idx 16 = 20). 정확한 위치는 미확인.
> 자세한 내용은 [`analysis/analysis_E_lhull_table.md`](analysis/analysis_E_lhull_table.md) 참조.

---

## 직접 Python 실행 (개발자)

```
python koukai2_editor.py
```

또는 임의 경로 지정:

```
python koukai2_editor.py "C:\Games\koukai2\KOUKAI2.DAT"
```

런타임 의존성: **Python 3.10 이상, 표준 라이브러리만** (Tkinter 포함).

---

## 빌드

Windows 환경에서 다음 중 하나를 실행하면 단일 실행파일이 만들어진다.

```
build.bat
```

또는 PowerShell:

```
.\build.ps1
```

빌드가 끝나면 `dist\koukai2_editor.exe` 가 생성된다.

빌드에는 Python 3.10 이상과 PyInstaller 가 필요하다. 스크립트가 자동으로
PyInstaller 설치 여부를 확인하고 안내한다.

GitHub Actions (`.github/workflows/release.yml`) 가 `v*` 태그 push 시 또는
`workflow_dispatch` 에서 버전을 입력해 실행 시 Windows 러너에서 빌드해
GitHub Release 에 `.exe` 를 첨부한다.

---

## 디렉토리 구조

```
koukai2_editor.py            GUI 진입점 (KOUKAI2.DAT 자동 탐지 → run())
horiedit_py/
    __init__.py
    common.py                EditorState, 구조체, 주소 상수, 정적 테이블
    data/                    순수 함수형 데이터 액세스 레이어
        __init__.py            select_slot, slot_is_used, slot_init
        hero.py                load_hero / save_hero / hero_index_active
        person.py              iter_persons / find_persons / load/save
        ship.py                load/save_fleet_entry, ship4/5, ship_num
        game.py                MAIN.EXE Ship4/5 ROM, 추정 테이블, kogyo
    gui/                     Tkinter + ttk UI
        __init__.py
        app.py                 메인 윈도우, 탭 컨테이너, 상태바
        slot_select.py         상단 슬롯 선택 라디오
        hero_tab.py            주인공 능력치/자금 편집 (Full)
        person_tab.py          인물 편집 (스텁)
        ship_tab.py            선박 편집 (스텁)
        settings_tab.py        게임 기본 설정 편집 (스텁)
analysis/                    원본 분석 노트
    analysis_A_*.md            영웅/인물/메뉴/IO
    analysis_B_*.md            선박/항구
    analysis_C_*.md            MAIN.EXE 함선 ROM
    analysis_D_*.md            등장공업치 후보 위치
    analysis_E_*.md            lhull 재분석 (위치 미확인)
.github/workflows/release.yml  태그/dispatch 시 .exe 빌드 → Release
build.bat / build.ps1        로컬 빌드 스크립트
LICENSE                      MIT
```

---

## 라이선스

MIT License — 자세한 사항은 [`LICENSE`](LICENSE) 참조.

게임 원본 데이터(`originalgame/`) 는 저작권 사유로 저장소에 포함하지 않는다.

---

## 버전 히스토리

### v0.3.0 (예정 — GUI 전환)

- **GUI 전환 (Tkinter + ttk)** — 콘솔 메뉴를 폐지하고 단일 윈도우 + 탭
  구조로 변경.
  - 상단: 슬롯 선택 라디오 (10개, 빈 슬롯 비활성)
  - 탭: 주인공 / 인물 / 선박 / 게임 설정
  - 하단: 상태바 (파일 경로, 슬롯, 주인공 표시)
- **데이터 레이어 분리** — `horiedit_py/data/` 패키지 신설. UI 비의존
  순수 함수형 인터페이스로 향후 다른 프론트엔드(웹 등) 재사용 가능.
- **주인공 탭 구현 완료**. 인물/선박/게임 설정 탭은 다음 단계에서 구현.
- **lhull 메뉴 제거** — 분석 결과 단일 ROM 테이블이 존재하지 않을 가능성이
  매우 높음을 확인. v0.2 의 잘못된 추정(`0x424AE`) 편집을 더 이상 노출하지
  않음.
- **콘솔 모듈 제거** — `hero_person.py`, `ship_data.py`, `game_settings.py`
  삭제.
- **메뉴 흐름** (참고: GUI 전환으로 의미 약화)
  - 이전 콘솔 흐름의 "1~10 슬롯 / 11 게임 설정 / 0 종료" 는 GUI 의 라디오
    + 종료 버튼으로 대체됨.
- **버전 표시** "Ver 1.4 (Python)" → "Ver 0.1"
- **Release workflow** `workflow_dispatch` 에 `version` 입력 받아 임의 태그로
  release 생성 가능 (GitHub Actions → Release → "Run workflow")

### v0.2.0 (2026-05-10)

- **`org_ship_edit` 에 "신조 시 최대 내구도" 항목 추가** — MAIN.EXE 의
  lhull 테이블(추정 위치 0x424AE) 직접 편집. *(주: v0.3 분석에서 이 추정이
  잘못된 것으로 확인되어 v0.3 부터 제거됨)*
- **`org_ship_edit` 메뉴 재배치 + 표시명 정비**
  - 새 순서: 배이름 → 추진력 → 선회력 → 최대 내구도 → 최대 적재량 →
    최대 승무원 → 필요 승무원 → 최대 무기수
  - 표시명: "최대 돛" → "추진력", "최대 회전력" → "선회력"

### v0.1.0 (2026-05-10)

초기 릴리스.

- **분석** — `horiedit.c` 를 영웅/인물/메뉴(파트 A)와 선박/항구(파트 B)로
  나누어 정밀 명세화. 별도로 MAIN.EXE 의 함선 신조 데이터 위치(파트 C)
  분석.
- **horiedit 기능 100% 호환 재구현** — 영웅 능력치, 인물, 함대, 원본 선박
  템플릿 편집의 모든 메뉴와 클램프 체인 보존.
- **MAIN.EXE 함선 신조 데이터 편집** (`game_settings.py` 4개 메뉴)
  - 항구 공업 수치 요건 (추정), 신조 시 최대 내구도 (추정), Ship4 ROM
    (확정), Ship5 ROM (확정)
- **단일 실행파일 빌드** — PyInstaller `--onefile` 로 8.2 MB `.exe`. 현재
  작업 디렉토리/실행파일 폴더에서 KOUKAI2.DAT 자동 탐지.
- **GitHub Actions 자동 릴리스** — `v*` 태그 push 시 Windows .exe 빌드 후
  Release 생성.
