# 대항해시대 II 세이브 에디터 (Python)

코에이 *대항해시대 II* (Koukai 2 / Uncharted Waters 2) 의 세이브 파일 (`KOUKAI2.DAT`)
및 게임 실행 데이터 (`MAIN.EXE`) 를 직접 바이트 단위로 편집하는 도구.

원본 Borland Turbo C / DOS 시절의 `HORIEDIT.C` 를 Python 으로 재구현하고
horiedit 가 다루지 않던 영역(MAIN.EXE 의 함선 신조 데이터 등)을 추가했다.

- Repository: https://github.com/genishs/dh2-py-editor
- Releases: https://github.com/genishs/dh2-py-editor/releases

---

## 빠른 시작 (배포판 사용)

1. [Releases](https://github.com/genishs/dh2-py-editor/releases) 에서 최신
   `koukai2_editor.exe` 를 받는다.
2. `KOUKAI2.DAT` 가 있는 게임 폴더에 `koukai2_editor.exe` 를 복사한다.
3. 더블클릭 또는 `cmd` / PowerShell 에서 실행.

> **백업 권장** — 편집 전 `KOUKAI2.DAT` 와 `MAIN.EXE` 를 백업하세요.
> `MAIN.EXE.bak` 가 동봉되어 있으면 그것이 원본이므로 보존하세요.

`.exe` 는 다음 순서로 세이브 파일을 찾는다.

1. 명령행 인자로 받은 경로
2. 현재 작업 디렉토리(cwd) 의 `KOUKAI2.DAT` (또는 소문자 `koukai2.dat`)
3. 실행파일 자체가 위치한 폴더의 `KOUKAI2.DAT`
4. (개발 환경) 소스 트리의 `originalgame/koukai2/KOUKAI2.DAT`

---

## 기능

### 메뉴 트리

```
[세이브 선택 화면]
  1) ~ 10) 세이브 슬롯 1~10 선택
       └─ [메인 메뉴]
            1) 주인공 데이터 에디트
            2) 인물 데이터 에디트
            3) 주인공 선박 에디트
            4) 오리지날 선박 에디트
            5) 다른 세이브 번호 선택
            0) 처음 메뉴로 돌아가기
 11) 게임 기본 설정 변경  → MAIN.EXE 편집
  0) 프로그램 종료
```

### 1) 주인공 데이터 (`hero_abil_edit`)

현재 활성 주인공(`c_hero`) 의 능력치를 편집.

| 항목 | 자료형 | 비고 |
|---|---|---|
| 무역 명성  | uint16 | 0~65535 |
| 해적 명성  | uint16 | |
| 모험 명성  | uint16 | |
| 친밀도 (포르투갈/스페인/오스만/잉글랜드/이탈리아/네덜란드) | uint8 | 표시: -100 ~ +100 (저장은 0~200) |
| 작위 (peer) | 0~9 | 알(c_hero=5)만 이탈리아 작위표(Ipeer), 나머지는 일반 작위표(Epeer) |
| 자금 (money) | uint32 | 모든 주인공 공유 |

### 2) 인물 데이터 (`person_edit`)

이름으로 인물을 검색하여 편집. 이름의 일부만 입력해도 매치, `y/n` 으로 다음
매치로 이동.

- 능력치: 통솔, 항해, 지식, 직감, 공구, 검술, 매력, 행운
- 항해/전투 레벨 + 경험치 (uint16)
- 능력 비트필드: 점술/회계/구급/지도작성/검술메뉴
- 위치 항구 (`pos == 0xFF` 인 인물 한정, 130개 항구 중 선택)

### 3) 주인공 선박 (`hero_ship_edit`)

현재 주인공이 보유한 함대(0~N척) 의 한 척을 골라 편집. horiedit 의
13개 항목을 그대로 구현, 클램프 체인(상한 자동 보정)도 원본과 동일.

| 항목 | 비고 |
|---|---|
| 현재 승무원 / 현재·최대 선체 / 회전력 / 돛 / 무기수 / 컨디션 | Ship1/Ship2 |
| 최대 적재 승무원 / 최대 적재 무기수 | Ship3 |
| 현재 무기 / 진형 / 함선 종류 / 함선 이름 | Ship1/2/3 + 카탈로그 |

함선 종류 변경 시 `Ship5.bform` 의 상위 4비트가 새 종류 값으로 합성되고,
모든 한도가 새 종류에 맞게 자동 재클램프되며 cargo 가 재계산된다.

### 4) 오리지날 선박 (`org_ship_edit`)

현재 슬롯의 25종 함선 템플릿(`Ship4` + `Ship5`) 을 편집. 한도(추진력/선회력
/적재량/승무원/무기수) 변경 시 그 종류를 사용 중인 모든 함대 인스턴스의
값이 자동 클램프된다.

**v0.2 부터 메뉴 순서:**

| 번호 | 항목 | 데이터 위치 |
|---|---|---|
| 1 | 배이름           | KOUKAI2.DAT (Ship5.name) |
| 2 | 추진력           | KOUKAI2.DAT (Ship4.lsail) |
| 3 | 선회력           | KOUKAI2.DAT (Ship4.lrudder) |
| 4 | **최대 내구도**  | **MAIN.EXE @ 0x424AE** (추정 — 검증 필요) |
| 5 | 최대 적재량      | KOUKAI2.DAT (Ship4.capacity) |
| 6 | 최대 승무원      | KOUKAI2.DAT (Ship4.lcrew × 10) |
| 7 | 필요 승무원      | KOUKAI2.DAT (Ship4.dcrew) |
| 8 | 최대 무기수      | KOUKAI2.DAT (Ship4.lnowea) |

> **주의** — 4번 "최대 내구도" 는 분석가 추정 위치(MAIN.EXE 의 lhull 테이블)
> 에 직접 씁니다. 검증되지 않았으므로 이상 동작 시 `MAIN.EXE.bak` 으로
> 복구하세요.

### 0) 게임 기본 설정 변경

KOUKAI2.DAT 가 아닌 `MAIN.EXE` 의 함선 ROM 데이터를 직접 편집. 새 게임
시작 시점의 25종 함선 스펙에 영향을 준다.

| 메뉴 | 위치 | 검증 상태 |
|---|---|---|
| 항구 공업 수치 요건 (uint16 × 25) | MAIN.EXE @ 0x42722 | 추정 |
| 신조 시 최대 내구도 (uint16 × 25)  | MAIN.EXE @ 0x424AE | 추정 |
| Ship4 ROM (12B × 25)              | MAIN.EXE @ 0x40871 | 확정 |
| Ship5 ROM (25B × 25)              | MAIN.EXE @ 0x405FD | 확정 |

분석 근거는 [`analysis/analysis_C_mainexe_ship_build.md`](analysis/analysis_C_mainexe_ship_build.md)
참조.

---

## 직접 Python 실행 (개발자)

```
python koukai2_editor.py
```

또는 임의 경로 지정:

```
python koukai2_editor.py "C:\Games\koukai2\KOUKAI2.DAT"
```

런타임 의존성: Python 3.10 이상, 표준 라이브러리만.

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

GitHub Actions (`.github/workflows/release.yml`) 가 `v*` 태그 push 시
Windows 러너에서 빌드해 GitHub Release 에 `.exe` 를 첨부한다.

---

## 디렉토리 구조

```
koukai2_editor.py            진입점
horiedit_py/
    __init__.py
    common.py                EditorState, 구조체, 주소 상수
    hero_person.py           영웅 / 인물 / 메뉴 / 슬롯 선택
    ship_data.py             선박 편집 (hero_ship_edit, org_ship_edit)
    game_settings.py         게임 기본 설정 메뉴 (MAIN.EXE 편집)
analysis/                    원본 분석 노트 (A: 영웅/인물, B: 선박, C: MAIN.EXE)
.github/workflows/release.yml  태그 push 시 .exe 빌드 → Release 자동화
build.bat / build.ps1        로컬 빌드 스크립트
LICENSE                      MIT
```

---

## 라이선스

MIT License — 자세한 사항은 [`LICENSE`](LICENSE) 참조.

게임 원본 데이터(`originalgame/`) 는 저작권 사유로 저장소에 포함하지 않는다.

---

## 버전 히스토리

### v0.3.0 (예정)

- **메뉴 흐름 개선**
  - 첫 화면: `1`~`10` 슬롯 / `11` 게임 기본 설정 / `0` 프로그램 종료
  - 메인 메뉴 `0` = "처음 메뉴로 돌아가기" (기존 종료 → sel_save 재진입)
- **버전 표시** "Ver 1.4 (Python)" → "Ver 0.1"
- **Release workflow** `workflow_dispatch` 에 `version` 입력 받아 임의 태그로
  release 생성 가능 (GitHub Actions → Release → "Run workflow")

### v0.2.0 (2026-05-10)

- **`org_ship_edit` 에 "신조 시 최대 내구도" 항목 추가** — MAIN.EXE 의
  lhull 테이블(추정 위치 0x424AE) 직접 편집. 같은 화면에서 함선 1척의
  핵심 스펙을 모두 다룰 수 있다.
- **`org_ship_edit` 메뉴 재배치 + 표시명 정비**
  - 새 순서: 배이름 → 추진력 → 선회력 → 최대 내구도 → 최대 적재량 →
    최대 승무원 → 필요 승무원 → 최대 무기수
  - 표시명: "최대 돛" → "추진력", "최대 회전력" → "선회력"
  - 자주 손대는 핵심 스펙을 위쪽에 배치.

### v0.1.0 (2026-05-10)

초기 릴리스.

- **분석** — `horiedit.c` 를 영웅/인물/메뉴(파트 A)와 선박/항구(파트 B)
  로 나누어 정밀 명세화. 별도로 MAIN.EXE 의 함선 신조 데이터 위치(파트 C)
  분석.
- **horiedit 기능 100% 호환 재구현** — 영웅 능력치, 인물, 함대, 원본
  선박 템플릿 편집의 모든 메뉴와 클램프 체인 보존.
- **MAIN.EXE 함선 신조 데이터 편집** (`game_settings.py` 4개 메뉴)
  - 항구 공업 수치 요건 (추정)
  - 신조 시 최대 내구도 (추정)
  - Ship4 ROM (확정)
  - Ship5 ROM (확정)
- **단일 실행파일 빌드** — PyInstaller `--onefile` 로 8.2 MB `.exe`.
  현재 작업 디렉토리/실행파일 폴더에서 KOUKAI2.DAT 자동 탐지.
- **GitHub Actions 자동 릴리스** — `v*` 태그 push 시 Windows .exe 빌드 후
  Release 생성.
