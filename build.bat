@echo off
REM 대항해시대 II 세이브 에디터 - PyInstaller 단일 .exe 빌드 스크립트 (cmd)
REM
REM 사용:
REM     build.bat
REM
REM 결과:
REM     dist\koukai2_editor.exe

setlocal

REM 스크립트가 위치한 디렉토리로 이동
cd /d "%~dp0"

echo === 대항해시대 II 세이브 에디터 빌드 시작 ===

REM Python 존재 확인
set "PYTHON_CMD="
where python >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    set "PYTHON_CMD=python"
) else (
    where py >nul 2>nul
    if %ERRORLEVEL% EQU 0 (
        set "PYTHON_CMD=py"
    )
)

if "%PYTHON_CMD%"=="" (
    echo.
    echo [ERROR] Python 을 찾을 수 없습니다.
    echo https://www.python.org/downloads/ 에서 Python 3.10 이상을 설치하세요.
    exit /b 1
)

echo Python: %PYTHON_CMD%

REM PyInstaller 설치 확인
%PYTHON_CMD% -m PyInstaller --version >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo PyInstaller 가 설치되어 있지 않습니다.
    echo 설치 명령:
    echo     %PYTHON_CMD% -m pip install --upgrade pyinstaller
    echo.
    set /p RESP="지금 설치할까요? [Y/n] "
    if /i "%RESP%"=="" set RESP=Y
    if /i "%RESP%"=="Y" (
        %PYTHON_CMD% -m pip install --upgrade pyinstaller
        if %ERRORLEVEL% NEQ 0 (
            echo [ERROR] PyInstaller 설치 실패.
            exit /b 1
        )
    ) else (
        exit /b 1
    )
)

REM 빌드 실행
echo PyInstaller 빌드 중...
%PYTHON_CMD% -m PyInstaller --onefile --windowed --name koukai2_editor --icon assets\icon.ico --add-data "assets\icon.ico;assets" --noconfirm --clean koukai2_editor.py
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] 빌드 실패.
    exit /b 1
)

echo.
echo === 빌드 완료 ===
echo 결과물: dist\koukai2_editor.exe
echo.
echo 사용법:
echo   1. dist\koukai2_editor.exe 를 KOUKAI2.DAT 가 있는 게임 폴더에 복사
echo   2. 더블클릭 또는 cmd 에서 실행

endlocal
