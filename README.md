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

### 인물 탭

좌우 분할. 좌측에서 처음/마지막 이름 부분 일치로 검색해 결과 Treeview
(번호·이름·항구) 표시. 행 선택 시 우측 폼으로 로드.

| 그룹 | 필드 |
|---|---|
| 이름 | 처음 이름 / 마지막 이름 (각 13 byte EUC-KR) |
| 능력치 | 통솔, 항해, 지식, 직감, 공구, 검술, 매력, 행운 (Spinbox 0~255) |
| 레벨/경험 | 항해 레벨/경험, 전투 레벨/경험 |
| 능력 (비트) | 점술 / 회계 / 구급 / 지도작성 / 검술메뉴 (Checkbutton) |
| 정착 항구 | 130개 Combobox (`pos == 0xFF` 일 때만 활성) |

저장 시 잘못된 입력은 messagebox 로 차단.

### 선박 탭

내부 sub-Notebook 으로 [영웅 함대] / [함선 종류] 두 화면.

**영웅 함대** (`hero_ship_edit` 대응) — 좌측 함대 목록 + 우측 13항목 폼.
함선 종류 변경 시 Ship5.bform 비트 합성 + 모든 클램프 체인 자동 적용,
cargo 자동 재계산.

**함선 종류** (`org_ship_edit` 대응) — 좌측 25종 목록 + 우측 7항목 폼
(배이름/추진력/선회력/최대 적재량/최대 승무원/필요 승무원/최대 무기수).
한도 변경 시 그 종류를 사용 중인 모든 영웅 함대로 클램프 자동 전파.
이름 변경은 `state.ship_name` 캐시도 동기화. **lhull 항목 없음** (분석
결과 위치 미확인).

### 게임 설정 탭

`MAIN.EXE` 가 같은 폴더에 있어야 활성. 내부 sub-Notebook 3개:

| Sub-tab | 위치 | 검증 | 편집 항목 |
|---|---|---|---|
| **함선 정적 스펙 (Ship4 ROM)** | MAIN.EXE @ 0x40871 | 확정 | lrudder/lsail/lcrew×10/dcrew/capacity/lnowea |
| **함선 이름·외형 (Ship5 ROM)** | MAIN.EXE @ 0x405FD | 확정 | name(18B)/sform/bform 상위 4비트 |
| **등장공업치** | 슬롯 + 0x06FEB / MAIN.EXE @ 0x42722 | 추정 | 25개 함선의 저장값 (×10 = 표시값). MAIN.EXE 동기화 체크박스 |

read-modify-write 시 `none[*]` 패딩 byte 모두 보존.

> ⚠️ **lhull 메뉴는 의도적으로 제외** — 이전 v0.2 까지의 "신조 시 최대 내구도"
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

### v0.3.0 (2026-05-10 — GUI 전환 완료)

- **Tkinter + ttk GUI 전환** — 콘솔 메뉴를 폐지하고 단일 윈도우 + 탭
  구조로 전면 전환.
  - 상단: 슬롯 선택 라디오 (10개, 빈 슬롯 비활성)
  - 탭: **주인공 / 인물 / 선박 / 게임 설정** (4개 모두 구현)
  - 하단: 상태바 (파일 경로, 슬롯, 주인공 표시)
- **데이터 레이어 분리** — `horiedit_py/data/` 패키지 신설. UI 비의존
  순수 함수형 인터페이스로 향후 다른 프론트엔드(웹 등) 재사용 가능.
- **인물 탭** — 부분 일치 검색 + Treeview + 능력치/경험치/비트필드/항구
  편집.
- **선박 탭** — sub-Notebook 으로 영웅 함대(13항목 + 클램프 체인) 와
  함선 종류 25종 템플릿(7항목, 한도 변경 시 함대 자동 클램프 전파) 분리.
- **게임 설정 탭** — sub-Notebook 으로 Ship4 ROM (확정) / Ship5 ROM
  (확정) / 등장공업치 (추정, MAIN.EXE 동기 옵션) 분리.
- **lhull 메뉴 제거** — 분석 결과 단일 ROM 테이블이 존재하지 않을 가능성이
  매우 높음을 확인. v0.2 의 잘못된 추정(`0x424AE`) 편집을 더 이상 노출하지
  않음 ([`analysis/analysis_E_lhull_table.md`](analysis/analysis_E_lhull_table.md)).
- **콘솔 모듈 제거** — `hero_person.py`, `ship_data.py`, `game_settings.py`
  삭제.
- **버전 표시** "Ver 1.4 (Python)" → "Ver 0.1"
- **Release workflow** `workflow_dispatch` 에 `version` 입력 받아 임의 태그로
  release 생성 가능.
- **자동 탐지 실패 시** GUI 파일 선택 대화상자.

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
