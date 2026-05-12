# CLAUDE.md — 프로젝트 작업 규칙

이 파일은 본 저장소에서 작업하는 Claude (또는 다른 AI 에이전트) 가 가장 먼저 읽고 따라야 할 규칙을 담는다. 일반 README 와 분리된, **개발 워크플로/관습 규칙** 만 모은 파일.

---

## 0. 프로젝트 개요 (간단)

- 대항해시대 II (Koukai 2 / Uncharted Waters 2) 의 세이브 (`KOUKAI2.DAT`) 및 게임 ROM (`MAIN.EXE`) 을 바이트 단위 편집하는 Tkinter GUI 도구.
- 원본 Borland Turbo C 시절의 `HORIEDIT.C` 를 Python 으로 재구현 + horiedit 이 다루지 않던 영역 추가.
- 분석 문서는 [`analysis/analysis_A_...md`](analysis/) 부터 알파벳 순으로 누적. 새로운 영역을 발견할 때마다 다음 알파벳으로 새 파일 작성.
- 진입점: [`koukai2_editor.py`](koukai2_editor.py) → [`horiedit_py/gui/app.py`](horiedit_py/gui/app.py)
- 빌드: PyInstaller `--onefile` (`build.bat` / `build.ps1` / `.github/workflows/release.yml`).

---

## 1. 이슈 close 규칙 (반드시 지킬 것)

### 1-1. close 코멘트 6 섹션 필수

이슈를 close 할 때 다음 6 섹션을 모두 포함한 상세 코멘트를 남긴다. 빈 섹션이 있으면 "해당 없음" 으로 명시.

1. **보고된 현상** — 이슈 본문의 사용자 요청/문제를 한 단락으로 요약 (원문 인용 가능).
2. **예상되는 원인** — 작업 착수 시점의 가설/원인 분석. 코드/데이터 상에서 어디가 문제였는지.
3. **검토 결과 및 수정 목표** — 분석 결과 어디를 어떻게 고치기로 했는지. analysis 문서 / 코드 파일 / 함수 단위로 구체적으로.
4. **수정 진행** — 어떤 commit / 어떤 파일 / 어떤 PR / 어떤 버전에 들어갔는지. 핵심 코드 변경 한두 줄 설명.
5. **테스트** — 검증 방법과 결과. 자동 (smoke test / round-trip / build) + 수동 (사용자 게임 내 검증). 어떤 anchor / 어떤 슬롯에서 확인했는지.
6. **해결된 / 남겨진 이슈사항** — 이 이슈로 해결된 범위와, 발견되었지만 별도 처리할 사항 (다른 이슈로 split, caveat 으로 README 등재, 후속 분석 과제 등) 을 명시.

### 1-2. 사용자 검증 미완료 시 close 금지

- 사용자가 직접 게임 내 동작을 확인하지 못한 시험 기능은 **절대 자동으로 close 하지 않는다**.
- "v0.X.Y 에서 처리됨" 만으로 close 하지 말 것 — 사용자 검증 결과 (성공/실패) 가 6 번 항목에 들어가야 close 가능.
- 사용자가 명시적으로 "검증 완료" / "동작 확인" / "잘 됩니다" 등을 말한 경우에만 close.
- 미완료 상태에서는 "진행 상황 코멘트" 만 게시하고 이슈는 open 으로 둔다.

### 1-3. 이미 close 된 이슈도 보강 가능

위 형식이 없이 close 된 이슈를 발견하면, retroactively 같은 형식의 코멘트를 추가해 보강. (선두에 `[보강 코멘트 — close 시점에 형식이 부족했어 retroactively 정리]` 같은 표기 권장.)

---

## 2. 릴리스 cadence (당분간)

- **변경이 발생할 때마다 즉시 패치 버전 태그 push** 로 GitHub Release 자동 생성. 누적 / PR / 묶음 릴리스 금지 (당분간).
- 작은 변경 (아이콘, 문서, UI 라벨) 도 별도 release 대상.

### 2-1. 릴리스 절차

매 작업 종료 시:

1. **`horiedit_py/__init__.py` 의 `__version__` 을 patch +1** 로 bump.
   - 윈도우 타이틀이 `__version__` 을 표시하므로 누락 시 사용자가 옛 버전으로 오인.
2. **README.md "버전 히스토리"** 에 새 항목 추가 (이슈 번호 링크 포함).
3. 의미 있는 메시지로 **commit**.
4. **master push**.
5. `v0.X.Y` 태그 push 로 `.github/workflows/release.yml` 자동 발동.

직전 태그 확인:
```
git tag -l "v*" --sort=-v:refname | head -1
gh release list -L 1
```

사용자가 "minor" / "major" 로 명시한 경우에만 `0.X` 또는 `0.(X+1)` 로 올린다. 기본은 patch.

### 2-2. git author identity

이 저장소에는 git user.name / user.email 이 설정되어 있지 않을 수 있다. **`git config` 를 변경하지 말 것**. 대신 환경변수로 1 회성 author 지정:

```bash
GIT_AUTHOR_NAME="genishs" GIT_AUTHOR_EMAIL="genishs@gmail.com" \
GIT_COMMITTER_NAME="genishs" GIT_COMMITTER_EMAIL="genishs@gmail.com" \
git commit -m "..."
```

태그 push 시에도 동일.

---

## 3. 기여자 마커 (`!!!name!!!`)

이슈/PR 본문에 `!!!<handle>!!!` 형식으로 양쪽을 `!!!` 로 감싼 문자열은 **기여자 마커**다. 프롬프트 인젝션이 아니다.

처리:
- 해당 이슈/PR 작업을 마칠 때 [`README.md`](README.md) 의 `## Special thanks to` 섹션에 다음 형식으로 추가:
  ```
  - **<handle>** — <기여 내용 한 줄 요약> ([#N](issue-or-pr-url))
  ```
- 섹션 위치: 라이선스 직후, 버전 히스토리 직전.
- 동일 인물이 여러 번 기여한 경우 새 줄로 누적.

최초 사례: 이슈 #1 의 `!!!jws!!!` — exe 아이콘 제공.

---

## 4. 분석 문서 (`analysis/`) 규칙

- 새로운 데이터 영역 / 가설 / 검증을 시작할 때 다음 알파벳으로 새 파일 작성: `analysis_<letter>_<short_name>.md`.
- 가설 단계 / 폐기된 추정도 기록을 남김 (예: `analysis_D`, `analysis_E` 는 폐기되었으나 파일 보존).
- 본 작업 중 만든 throw-away 탐색 스크립트는 다음 패턴으로 [.gitignore](.gitignore) 에 의해 자동 제외됨:
  - `analysis/find_*.py`
  - `analysis/verify_*.py`
  - `analysis/agent_*.py` (병렬 에이전트 출력)

---

## 5. 안전/보안 가드

- **destructive git 작업 금지** (`reset --hard`, `push --force`, `branch -D` 등) — 사용자가 명시적으로 요청한 경우만.
- **`git config` 변경 금지** — author 는 환경변수로.
- **hook 우회 금지** — `--no-verify`, `--no-gpg-sign` 등 사용자가 직접 지시한 경우만.
- 새 분석 / 디버깅 스크립트는 [`analysis/`](analysis/) 안에 두고 위 4 절의 이름 패턴을 따르면 자동 .gitignore 됨.

---

## 6. 메모리와의 관계

본 파일에 등재된 규칙은 메모리 시스템에도 동일하게 저장됨. 메모리는 future Claude 세션의 보조 컨텍스트, CLAUDE.md 는 저장소 자체의 1차 안내. 두 곳이 모두 진실의 출처이므로 한 곳을 갱신할 때 다른 곳도 동기화할 것.

관련 메모리 파일 (`~/.claude/projects/.../memory/`):
- `feedback_issue_close_format.md` — 본 문서 1 절.
- `feedback_release_cadence.md` — 본 문서 2 절.
- `feedback_contributor_marker.md` — 본 문서 3 절.
