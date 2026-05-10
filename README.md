# 대항해시대 II 세이브 에디터 (Python)

코에이 *대항해시대 II* (Koukai 2) 의 세이브 파일(`KOUKAI2.DAT`) 편집기.
원본 Borland Turbo C / DOS 시절의 `HORIEDIT.C` 를 Python 으로 재구현한 버전.

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

빌드에는 Python 3.10 이상과 PyInstaller 가 필요하다 (스크립트가 자동으로
PyInstaller 설치 여부를 확인하고 안내한다).

## 사용 (배포)

1. `dist\koukai2_editor.exe` 를 게임 폴더(`KOUKAI2.DAT` 가 있는 곳) 에 복사
2. 더블클릭 또는 `cmd` / PowerShell 에서 실행
3. 메뉴에 따라 슬롯을 선택하고 편집

`.exe` 는 다음 순서로 세이브 파일을 찾는다.

1. 명령행 인자로 받은 경로
2. 현재 작업 디렉토리(cwd)의 `KOUKAI2.DAT` (또는 소문자 `koukai2.dat`)
3. 실행파일 자체가 위치한 폴더의 `KOUKAI2.DAT`
4. (개발 환경) 소스 트리의 `originalgame/koukai2/KOUKAI2.DAT`

## 백업 권장

편집 전 `KOUKAI2.DAT` 와 `MAIN.EXE` 를 백업하세요.

## 직접 Python 실행 (개발자)

```
python koukai2_editor.py
```

또는 임의 경로 지정:

```
python koukai2_editor.py "C:\Games\koukai2\KOUKAI2.DAT"
```

## 메뉴

- `0` 게임 기본 설정 변경: `KOUKAI2.DAT` 이외 (`MAIN.EXE` 등) 의 파일을 편집
  (확장 중)
- `1` ~ `10` 세이브 슬롯 선택 → 영웅 / 인물 / 선박 편집

## 의존성

- 런타임: Python 3.10 이상, 표준 라이브러리만 사용
- 빌드: PyInstaller (`pip install -r requirements.txt`)

## 디렉토리 구조

```
koukai2_editor.py            진입점
horiedit_py/
    __init__.py
    common.py                EditorState, 구조체, 주소 상수
    hero_person.py           영웅 / 인물 / 메뉴 / 슬롯 선택
    ship_data.py             선박 편집
    game_settings.py         게임 기본 설정 메뉴
analysis/                    원본 분석 노트
originalgame/koukai2/        개발용 테스트 데이터 (배포에는 포함하지 않음)
```
