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

### ⚠️ 알려진 주의사항

- **리스본 (항구 #0) 의 상업치 편집은 권장하지 않습니다.** 항구 경제 테이블의
  시작 위치 (`slot + 0x5DE3`) 가 항구 구조체 배열 끝의 페어웰 (#129) 좌표 영역과
  4 byte overlap 됩니다. 리스본 commerce 를 극단값으로 바꾸면 페어웰의 지도
  좌표가 같이 바뀌어 게임의 지도 표시/이동에 문제가 생길 수 있습니다.
  ([analysis_I §4](analysis/analysis_I_port_economy.md) 참조)
  - 안전: 항구 1..128 의 상업/공업치는 자유 편집 가능.
  - 권장 우회: 리스본의 경제를 키우고 싶다면 다른 항구 (예: 세빌리아) 를
    먼저 시도해 보세요.
  - 본 caveat 의 실제 영향은 사용자 검증 진행 중 — 영향이 없음이 확인되면
    삭제 예정.

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
│  [주인공][인물][선박][항구][게임 설정]  ← 탭        │
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
| 현재 소속 (디코드 라벨) | "조안의 동료" / "(모집 가능)" / "(정착 — 항구이름, 여관·술집(가설))" / "(NPC 카탈로그 #0xNN)" — pos 값 자동 분해 |
| 소속 변경 (Combobox) | 안전한 옵션만 노출: 6 hero 동료 / 모집 가능 / 항구 정착민. 선택 시 pos 자동 설정 |
| 소속 (pos byte) | 0..255 Spinbox — 고급/직접 값. 255 = 정착민 / 254 = 모집 가능 / 0·10·20·30·40·50 = hero / 그 외 0..68 = NPC 카탈로그 (충돌 가능). 인물 #0..#5 변경 비권장 |
| 정착 항구 | 130개 Combobox (`pos == 0xFF` 일 때만 활성, pos 를 255 로 바꾸면 즉시 활성화) |

저장 시 잘못된 입력은 messagebox 로 차단.

### 선박 탭

내부 sub-Notebook 으로 [영웅 함대] / [함선 종류] 두 화면.

**영웅 함대** (`hero_ship_edit` 대응) — 좌측 함대 목록 + 우측 13항목 폼.
함선 종류 변경 시 Ship5.bform 비트 합성 + 모든 클램프 체인 자동 적용,
cargo 자동 재계산.

**함선 종류** (`org_ship_edit` 대응) — 좌측 25종 목록 + 우측 폼.
한도 변경 시 그 종류를 사용 중인 모든 영웅 함대로 클램프 자동 전파.
이름 변경은 `state.ship_name` 캐시도 동기화.

| 항목 | 설명 |
|---|---|
| 배이름 | Ship5.name (18 byte 한글) |
| 추진력 (lsail) | record +3 / Ship4.lsail |
| 선회력 (lrudder) | record +2 / Ship4.lrudder |
| 등장공업치 (kogyo) | record +0 (u8). 표시값 = 저장값 × 10 |
| 최대 내구도 (lhull) | record +1 (u8 직접) |
| 최대 적재량 (capacity) | record +6 (u16 LE) / Ship4.capacity |
| 최대 승무원 (lcrew × 10) | record +4. 저장 시 //10 |
| 필요 승무원 (dcrew) | record +5 / Ship4.dcrew |
| 최대 무기수 (lnowea) | record +8 / Ship4.lnowea |

> 함선당 12 byte record (analysis_G 확정) — 슬롯 내 `+0x528F`,
> `MAIN.EXE @ 0x0407D8`. horiedit.h 의 `ship4_addr = 0x5291` 은 이 record
> 의 +2 (lrudder) 부터 시작 → off-by-2. 첫 두 byte `[kogyo, lhull]` 은
> horiedit 가 다루지 않던 영역.

### 항구 탭

130 항구의 상업치 / 공업치를 슬롯별로 편집 ([`analysis_I`](analysis/analysis_I_port_economy.md)).

| 항목 | 위치 (slot 기준) | 표시 | 비고 |
|---|---|---|---|
| 상업치 | `+0x5DE3 + idx*37 + 0` (u16 LE) | Spinbox 0..65535 | 게임 자연 범위 0..1000 |
| 공업치 | `+0x5DE3 + idx*37 + 4` (u16 LE) | Spinbox 0..65535 | |

> ⚠️ 리스본 (idx 0) 의 상업치는 페어웰 (idx 129) 의 좌표 영역과 데이터가
> overlap. 위의 "알려진 주의사항" 참조.

물가에 영향을 주는 공급 수치 (record 의 +14..+23) 는 [게임 설정] 탭의
"항구 공급 수치 (물가)" sub-tab 에서 편집 가능 (시험 기능).

### 게임 설정 탭 — ⚠️ 시험 기능

분석이 완전치 않거나 가설 단계의 영역을 직접 편집. **게임이 정상 실행되지
않을 수 있으므로 편집 전 KOUKAI2.DAT 와 MAIN.EXE 백업 필수.**

내부 sub-Notebook 3개:

| Sub-tab | 위치 | 검증 | 편집 항목 |
|---|---|---|---|
| **함선 정적 스펙 (Ship4 ROM)** | MAIN.EXE @ 0x0407DA | 확정 | lrudder/lsail/lcrew×10/dcrew/capacity/lnowea |
| **함선 이름·외형 (Ship5 ROM)** | MAIN.EXE @ 0x040566 | 확정 | name(18B)/sform/bform 상위 4비트 |
| **항구 공급 수치 (물가)** ([analysis_J](analysis/analysis_J_port_supply.md)) | slot `+0x5DE3 + idx*37 + 14` | 가설 | 10 byte/port — 표준 항구(0..99) ASCII digit/dot 인코딩 |

read-modify-write 시 `none[*]` 패딩 byte 모두 보존. 항구 공급 수치 sub-tab 은
slot 만 필요 (MAIN.EXE 없어도 사용 가능).

> 등장공업치(요구공업치) 와 최대 내구도(lhull) 는 함선 record (analysis_G)
> 의 +0/+1 byte 임이 확정되어, [선박] 탭의 [원래 함선 정보] 에서 편집한다.
> 이전 v0.3 까지의 "등장공업치" sub-tab (슬롯 +0x06FEB / MAIN.EXE
> 0x42722, 추정) 은 위치가 잘못된 것으로 확인되어 제거되었다.

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
        game.py                MAIN.EXE Ship4/5 ROM, 함선 record (analysis_G)
    gui/                     Tkinter + ttk UI
        __init__.py
        app.py                 메인 윈도우, 탭 컨테이너, 상태바
        slot_select.py         상단 슬롯 선택 라디오
        hero_tab.py            주인공 능력치/자금 편집 (Full)
        person_tab.py          인물 편집 (스텁)
        ship_tab.py            선박 편집 (스텁)
        settings_tab.py        게임 기본 설정 편집 (스텁)
assets/
    icon.ico                 프로그램 아이콘 (Tk 창 + .exe 빌드, jws 제공)
    icon_source.png          원본 PNG (240x240)
analysis/                    원본 분석 노트
    analysis_A_*.md            영웅/인물/메뉴/IO
    analysis_B_*.md            선박/항구
    analysis_C_*.md            MAIN.EXE 함선 ROM
    analysis_D_*.md            등장공업치 후보 위치 (폐기)
    analysis_E_*.md            lhull 재분석 (폐기)
    analysis_F_*.md            Ship4/Ship5 ROM 정정
    analysis_G_*.md            함선 record 구조 확정 (kogyo / lhull)
.github/workflows/release.yml  태그/dispatch 시 .exe 빌드 → Release
build.bat / build.ps1        로컬 빌드 스크립트
LICENSE                      MIT
```

---

## 라이선스

MIT License — 자세한 사항은 [`LICENSE`](LICENSE) 참조.

게임 원본 데이터(`originalgame/`) 는 저작권 사유로 저장소에 포함하지 않는다.

---

## Special thanks to

이슈/PR/아이디어로 프로젝트에 기여해 주신 분들:

- **jws** — 프로그램 아이콘 제공 ([#1](https://github.com/genishs/dh2-py-editor/issues/1))

---

## 버전 히스토리

### v0.4.12 (2026-05-24 — 동료 등록 3차 핫픽스: party 배열 sync ★ 최종 fix)

- **v0.4.11 사용자 검증 결과**: pos + none2[0] + none1 + port 4 byte 를 모두
  맞춰도 게임 인물 목록에 여전히 표시 안 됨. dh2_init (pristine) vs dh2_cust
  (에디터 변환) 두 KOUKAI2.DAT 비교로 외부 배열을 발견:
  - **`slot + 0x21BE` 부터 30 byte 의 party 배열** (각 byte = person_idx, 0xFF=빈)
  - **`slot + 0x21BB` byte = remaining_slots 카운터**
  - 게임은 이 배열로부터 인물 목록 메뉴를 그린다. person.pos 만으로는 부족.
- **수정**: 인물 탭의 commit 가 pos 변경으로 동료 등록/해제가 발생하면
  party 배열에 person_idx 추가/제거 + counter 1 증감 동시 수행.
- **사용자 hex 패치 검증 완료** (Test α): dh2_cust slot 1 에서 필리·라울 의
  party 배열 슬롯을 직접 채우자 게임의 인물 목록에 정상 표시됨 → 가설 확정.
- [`analysis_M_party_array.md`](analysis/analysis_M_party_array.md) 신설,
  [`analysis_K §7`](analysis/analysis_K_companion_mechanism.md) 의
  "별도 companion list 부정" 폐기.

### v0.4.11 (2026-05-24 — 동료 등록 2차 핫픽스: none1 (loyalty) + port 자동 동기화)

- **v0.4.10 사용자 검증 결과**: pos + none2[0] 만 바꿔도 게임 인물 목록에
  여전히 표시 안 됨. 자한 사림 (정상 채용 동료) vs 필리·라울 (에디터 변환)
  byte 비교로 추가 2 byte 가 필요함을 확정:
  - `none1` (+43) = **100** ("동료 풀 안" 마커 / loyalty)
  - `port` (+45) = **0xFF** (항구에 더 이상 없음)
- **수정**: 인물 탭의 commit 가 pos 가 hero catalog / 모집 가능 (0xFE) 로
  바뀔 때 위 2 byte 도 자동 동기화. `data/person.py` 의 `set_companion`
  / `unset_companion` API 도 동일하게.
- [`analysis_K §6-3, §6-4`](analysis/analysis_K_companion_mechanism.md) 갱신.

### v0.4.10 (2026-05-23 — 동료 등록 핫픽스: none2[0] role marker 자동 동기화)

- **v0.4.9 사용자 검증 결과**: pos 만 hero catalog ID 로 바꾸면 게임이 "동료"
  로는 인식 ("제독님" 호칭) 하지만 **인물 목록 (active party 순회) 에는
  표시되지 않음**. `none2[0]` 의 role marker 도 동반 변경 필요.
- **수정**: 인물 탭의 commit 로직이 pos 변경 시 `none2[0]` 도 자동 동기화:
  - hero catalog 동료 → `0x06` (PARTY)
  - free (0xFE) / 정착민 (0xFF) → `0x00` (INACTIVE)
  - 선장 marker (`0x02`) 는 보존 (Ship1/2/3 동반 갱신 없이 demote 시
    game state 불일치 가능 — v0.4.11+ 의 별도 선장 배속 기능에서 안전 처리).
- [`analysis_K §6`](analysis/analysis_K_companion_mechanism.md) 갱신:
  none2[0] 의 역할 코드 (`0x00`/`0x02`/`0x03`/`0x06`) 및 v0.4.9 검증 결과 반영.
- `horiedit_py/data/person.py` 에 `set_companion` / `unset_companion` API 도
  none2[0] 동반 갱신하도록 보완.

### v0.4.9 (2026-05-23 — 인물 동료 등록 + 소속 디코드 표시)

- **인물 탭에 동료 등록/해제 Combobox 추가** ([`analysis_K`](analysis/analysis_K_companion_mechanism.md)).
  agent 가 사용자 save 의 slot 0 (CAT) ↔ slot 1 (JOAN) 을 cross-slot 비교한 결과,
  **`Person.pos` (byte +44) 값이 hero 의 catalog ID 와 같으면 그 hero 의 동료**
  임이 확정되었다 (★★★★★). hero ↔ catalog ID:
  - JOAN 0x00 / CAT 0x0A / OTTO 0x1E / ROPEZ 0x32 / PIET 0x28 / AL 0x14
  - 0xFE = "모집 가능 / free", 0xFF = "항구 정착민"
  - 별도 companion list 없음 — 단 1 byte 변경으로 party 동료 등록 가능.
- **"현재 소속" 디코드 라벨** — Spinbox 의 raw pos 값을 사람이 읽을 수 있게 분해:
  "카탈리나의 동료" / "(모집 가능)" / "(정착 — 마데이라, 여관(가설))" 등.
- **소속 변경 Combobox** — 안전한 옵션 (6 hero + free + port settler) 만 노출.
  raw byte 직접 입력은 기존 Spinbox 로 advanced 사용자만.
- **검색 결과 Treeview 에 "소속" 컬럼 추가** — 인물 목록을 한눈에 분류 가능.
- **술집/여관 추정 표시 (가설)** — pos == 0xFF 정착민의 `none2[1]` bit 7
  (0x80) 이 set 이면 "여관(가설)", clear 면 "술집(가설)". 미구엘 (리스본 여관) +
  필리 (마데이라 여관) 두 anchor 모두 bit 7 set 확인. 확정용 술집 anchor 미확보
  로 "(가설)" 명시. 다음 버전 (v0.4.10) 의 MAIN.EXE catalog 테이블 역공학에서
  확정 예정.

### v0.4.8 (2026-05-23 — 인물 위치/소속 편집 + 항구 공급 가설 폐기 정리)

- **인물 탭 — 소속(pos) 편집 추가.** 기존엔 `pos == 0xFF` 인 인물만 정착 항구
  편집이 가능했고, 그 외 인물 (NPC 카탈로그/주인공/사망 등) 은 위치 변경이
  불가능했다. v0.4.8 부터 **pos 자체를 Spinbox 로 직접 편집** — pos 를 255
  (`0xFF`) 로 바꾸면 정착 항구 콤보가 즉시 활성화되어 해당 인물을 임의 항구로
  옮길 수 있다. 인물 #0..#5 (주인공) 의 pos 는 게임 진행 상태를 의미하므로
  변경 비권장 (UI 에 경고).
- **항구 공급 수치 sub-tab 의 라벨/경고 보정** — v0.4.6 에서 "항구 공급
  수치 (물가)" 로 추가되었던 sub-tab 을 **"항구 공급 수치 (효과 미확인)"** 로
  변경. 사용자 게임 내 검증 (이슈 #4) 결과 byte 변경이 시장 가격에
  즉시적인 영향을 주지 않음을 확정.
- **분석 문서 갱신**:
  - [`analysis_J §7`](analysis/analysis_J_port_supply.md) — supply→가격 가설 폐기
    + 1달 후 byte 자동 갱신 확인 + 평균물가 % 가 매월 1일에만 변동한다는
    사용자 단서 + agent 가 130 ports × 37 byte 전수 검색에서 0x67 (=103)
    한 번도 발견 못 함 등을 새 섹션으로 정리.
  - [`analysis_I §7`](analysis/analysis_I_port_economy.md) — port record 의
    +8..+13 6 byte 가 **6 faction 별 지배국 충성도** 임을 통계 분석으로 확정.
    포르투갈 (+8) / 스페인 (+9) / 잉글랜드 (+11) / 네덜란드 (+13) 매핑 확인,
    +10/+12 는 미확정. 차후 "항구 지배국" 신규 편집 sub-tab 후보.
- 이슈 [#4](https://github.com/genishs/dh2-py-editor/issues/4) 는 사용자 검증
  결과를 반영한 진행 코멘트 게시. 가격 직접 편집은 derived 메커닉 +
  매월 1일 트리거 라는 점이 확인됨 — 현 시점 close 보류 (직접 입력 UI 는
  MAIN.EXE 디스어셈 없이는 불가).

### v0.4.7 (2026-05-12 — 프로젝트 작업 규칙 등재 (CLAUDE.md))

- **CLAUDE.md 신설** — 본 저장소에서 작업하는 AI 에이전트 (또는 협업자) 가
  가장 먼저 읽어야 할 작업 규칙을 한 파일로 정리:
  - 이슈 close 시 6 섹션 상세 코멘트 (보고된 현상 / 예상 원인 / 검토 결과 /
    수정 진행 / 테스트 / 해결된·남겨진 사항) 필수, 사용자 검증 미완료 시 close 금지.
  - 릴리스 cadence (변경 즉시 패치 태그) + `__version__` bump 절차.
  - 기여자 마커 `!!!name!!!` 처리 규칙.
  - 분석 문서 / 탐색 스크립트 명명 규칙.
- 이슈 #4 (물가) reopen — 사용자 게임 내 검증 대기 중.
- 기존 close 된 #1 / #2 / #3 에 retroactive 6-section 상세 코멘트 보강.

### v0.4.6 (2026-05-12 — 항구 공급 수치 (물가 영향) 편집 ([#4](https://github.com/genishs/dh2-py-editor/issues/4)) + 타이틀 버전 표시 수정)

- **항구 공급 수치 편집** ([`analysis_J`](analysis/analysis_J_port_supply.md)) —
  record 의 `+14..+23` 10 byte 는 무역품 슬롯 10개의 공급 수치. 표준 항구
  (idx 0..99) 는 ASCII digit/dot 인코딩: `'.'` (empty), `'/'` 공급 0,
  `'0'..'9'` 공급 1..10. 공급이 낮을수록 게임 표시 가격 상승.
- **시험 기능 분류** — 본 편집은 [게임 설정] 탭의 sub-tab "항구 공급 수치
  (물가)" 로 추가됨. 가격이 base × supply 로 derived 되는 메커닉이라
  사용자는 정확한 가격 입력이 아닌 공급 byte 직접 편집. 가격 직접 편집은
  base price + 공식 역공학 후 별도 분석에서 추가 예정.
- **시험 기능 경고 강화** — [게임 설정] 탭 상단 경고를 게임 실행 오류 가능성을
  명시하도록 수정. KOUKAI2.DAT + MAIN.EXE 백업 강조.
- **타이틀 버전 표시 수정** — 그동안 하드코딩으로 "Ver 0.1" 만 나오던 윈도우
  타이틀이 실제 릴리스 버전 (`horiedit_py.__version__`) 을 표시.

### v0.4.5 (2026-05-12 — README 주의사항 정리 + 항구 탭 문서화)

- **알려진 주의사항** 섹션을 README 상단 (빠른 시작 직후) 에 추가. 리스본
  상업치 편집 caveat 을 강조.
- **항구 탭** 기능 설명을 ## 기능 섹션에 정식 등재 (그동안 버전 히스토리에만 있었음).
- UI 개요 ASCII 다이어그램에 "항구" 탭 추가.
- 이슈 #2 close.

### v0.4.4 (2026-05-12 — CI Node.js 24 액션 업그레이드 ([#3](https://github.com/genishs/dh2-py-editor/issues/3)))

- **GitHub Actions 워크플로** — 2026-06-02 부터 강제되는 Node.js 24 런타임
  대비. 사용 액션 메이저 버전 업:
  - `actions/checkout@v4` → `@v6`
  - `actions/setup-python@v5` → `@v6`
  - `actions/upload-artifact@v4` → `@v7`
  - `actions/download-artifact@v4` → `@v8`
  - `softprops/action-gh-release@v2` → `@v3`
- 결과 `.exe` 는 v0.4.3 과 기능 동일 (CI maintenance only).

### v0.4.3 (2026-05-12 — 항구 상업치/공업치 편집 ([#2](https://github.com/genishs/dh2-py-editor/issues/2)))

- **항구 경제 테이블 발견** ([`analysis_I`](analysis/analysis_I_port_economy.md)) —
  slot 내 `0x5DE3` 시작, 130 항구 × 37 byte stride. commerce u16 LE @ +0,
  industry u16 LE @ +4 확정 (사용자 anchor 4개 100% 일치).
- **항구 탭 신설** — 130 항구 Treeview + 상업치/공업치 Spinbox (0..65535).
  슬롯별 동적 편집. dirty/commit/revert/reload 통합.
- **caveat** — port[0] (리스본) 의 commerce u16 영역이 port[129] (페어웰) 의
  none[5] 후반부와 4 byte overlap. 극단값 편집 시 지도 좌표 영향 가능.
  편집 전 백업 권장.
- **물가 후보 (+14..+23)** 는 다음 버전에서 확정 후 추가 예정.

### v0.4.2 (2026-05-12 — 프로그램 아이콘 추가)

- **프로그램 아이콘** ([#1](https://github.com/genishs/dh2-py-editor/issues/1), jws 제공) —
  `assets/icon.ico` (16/24/32/48/64/128/240 multi-size). PyInstaller `--icon`
  으로 `.exe` 에 임베드, `--add-data` 로 onefile 빌드 런타임에 추출되어
  Tk 창 `iconbitmap` 도 적용. dev / frozen 양쪽에서 `_MEIPASS` 또는
  프로젝트 루트 자동 해석.
- **README** — "Special thanks to" 섹션 신설. 이슈/PR 기여자 누적.

### v0.4.1 (2026-05-10 — 용어 정리 + 선박 가격/분류 + UI 개선)

- **선박 가격 + 분류 위치 확정** ([`analysis_H`](analysis/analysis_H_ship_price.md)) —
  record `+10..+11` (u16 LE × 10) = 가격, `+9` (u8 0..5) = 선박 분류.
  사용자 5-point 검증 100% 일치. record 12 byte 의 `none[3]` 영역이
  완전히 해소되어 모든 byte 가 의미 있음.
- **선박 가격 편집 추가** — "원래 함선 정보" 폼에 0..655,350 (10단위)
  Spinbox. 발사선 1,200 / 다우 1,800 / 지벡 44,000 / 십 320,000 /
  철갑선 140,000 등 25개 함선 가격 편집.
- **선박 분류 표시 (read-only)** — 다음 버전에서 편집 가능 예정.
- **슬롯 선택 UI** — 10개 라디오 → ttk.Combobox 로 변환 (공간 절약),
  정보 패널 가로 폭 확대, 라벨 "메모"→"항해날짜", "항구"→"현재위치".
- **주인공 탭** — "무역 명성" → "교역 명성", 명성 3종 검증 0..50,000.
  친밀도 그룹 라벨 → "각 나라와의 관계", -100..+100 검증.
- **인물 탭** — 능력치 "공구"→"용기", "행운"→"운명". 능력 비트
  "점술"→"교섭", "구급"→"포술", "검술메뉴"→"측량".
- **선박 탭 / 나의 함대** — 11개 라벨 게임 용어로 통일:
  "현재 선원수 / 현재·최대 내구력 / 현재 선회력 / 현재 추진력 /
  현재 포문수 / 최대 적재량 / 최대 선원수 / 최대 포문수 /
  선수상 / 함선종류".
- **게임 설정 탭** — 시험 기능 경고 라벨 추가.

### v0.3.1 (예정 — 함선 record 구조 발견)

- **함선 record 구조 확정** (analysis_G) — horiedit.h 의 ship4_addr (0x5291)
  가 off-by-2 였음을 발견. 실제 record 시작은 0x528F (슬롯) / 0x0407D8
  (MAIN.EXE), 12 byte × 25 구조. 첫 두 byte 는 [요구공업치][최대내구도]
  로 horiedit 가 다루지 않던 영역.
- **선박 탭 / 원래 함선 정보** 폼에 등장공업치 + 최대 내구도 항목 추가.
  이전 추정 위치 (0x424AE / 0x4252A / 0x42722 / 0x06FEB) 들은 모두 폐기.
- **게임 설정 탭** 의 등장공업치 sub-tab 제거 (위치가 잘못되었음).

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
