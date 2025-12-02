@echo off
REM PDF 문서 비교 프로그램 빌드 스크립트 (Windows)
REM Python 3.11.4 호환

echo === PDF 문서 비교 프로그램 빌드 시작 ===

REM Python 버전 확인
python --version
if errorlevel 1 (
    echo Python이 설치되어 있지 않습니다.
    exit /b 1
)

REM 가상환경 확인 및 생성
if not exist "venv" (
    echo 가상환경 생성 중...
    python -m venv venv
)

REM 가상환경 활성화
echo 가상환경 활성화 중...
call venv\Scripts\activate.bat

REM Python 버전 재확인
python --version

REM 필요한 패키지 설치
echo 필요한 패키지 설치 중...
python -m pip install --upgrade pip
pip install -r requirements.txt

REM PyInstaller 설치 확인
where pyinstaller >nul 2>&1
if errorlevel 1 (
    echo PyInstaller 설치 중...
    pip install pyinstaller
)

REM 이전 빌드 결과물 정리
echo 이전 빌드 결과물 정리 중...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist __pycache__ rmdir /s /q __pycache__
del /q *.spec 2>nul

REM PyInstaller로 빌드
echo PyInstaller로 빌드 중...
pyinstaller build_python.spec

REM 빌드 완료 확인
if exist "dist\PDF문서비교프로그램.exe" (
    echo.
    echo === 빌드 완료! ===
    echo 실행 파일 위치: dist\
    dir dist\
) else (
    echo.
    echo === 빌드 실패 ===
    exit /b 1
)

pause

