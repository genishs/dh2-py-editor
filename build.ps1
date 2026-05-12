# 대항해시대 II 세이브 에디터 - PyInstaller 단일 .exe 빌드 스크립트 (PowerShell)
#
# 사용:
#     .\build.ps1
#
# 결과:
#     dist\koukai2_editor.exe

$ErrorActionPreference = "Stop"

# 스크립트가 위치한 디렉토리로 이동 (프로젝트 루트 기준 빌드)
Set-Location -Path $PSScriptRoot

Write-Host "=== 대항해시대 II 세이브 에디터 빌드 시작 ===" -ForegroundColor Cyan

# Python 존재 확인
$pythonCmd = $null
foreach ($cand in @("python", "py")) {
    $found = Get-Command $cand -ErrorAction SilentlyContinue
    if ($found) { $pythonCmd = $cand; break }
}

if (-not $pythonCmd) {
    Write-Host "Python 을 찾을 수 없습니다." -ForegroundColor Red
    Write-Host "https://www.python.org/downloads/ 에서 Python 3.10 이상을 설치하세요." -ForegroundColor Yellow
    exit 1
}

Write-Host "Python: $pythonCmd" -ForegroundColor Green

# PyInstaller 설치 확인 (없으면 설치 안내)
& $pythonCmd -m PyInstaller --version > $null 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "PyInstaller 가 설치되어 있지 않습니다." -ForegroundColor Yellow
    Write-Host "설치 명령:" -ForegroundColor Yellow
    Write-Host "    $pythonCmd -m pip install --upgrade pyinstaller" -ForegroundColor Yellow
    $resp = Read-Host "지금 설치할까요? [Y/n]"
    if ($resp -eq "" -or $resp -match "^[Yy]") {
        & $pythonCmd -m pip install --upgrade pyinstaller
        if ($LASTEXITCODE -ne 0) {
            Write-Host "PyInstaller 설치에 실패했습니다." -ForegroundColor Red
            exit 1
        }
    } else {
        exit 1
    }
}

# 빌드 실행
Write-Host "PyInstaller 빌드 중..." -ForegroundColor Cyan
& $pythonCmd -m PyInstaller `
    --onefile `
    --console `
    --name koukai2_editor `
    --icon assets\icon.ico `
    --add-data "assets\icon.ico;assets" `
    --noconfirm `
    --clean `
    koukai2_editor.py

if ($LASTEXITCODE -ne 0) {
    Write-Host "빌드 실패." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "=== 빌드 완료 ===" -ForegroundColor Green
Write-Host "결과물: dist\koukai2_editor.exe" -ForegroundColor Green
Write-Host ""
Write-Host "사용법:" -ForegroundColor Cyan
Write-Host "  1. dist\koukai2_editor.exe 를 KOUKAI2.DAT 가 있는 게임 폴더에 복사"
Write-Host "  2. 더블클릭 또는 cmd 에서 실행"
