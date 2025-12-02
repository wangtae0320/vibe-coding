#!/bin/bash
# PDF 문서 비교 프로그램 빌드 스크립트
# Python 3.11.4 호환

set -e

echo "=== PDF 문서 비교 프로그램 빌드 시작 ==="

# Python 버전 확인
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo "Python 버전: $PYTHON_VERSION"

# 가상환경 확인 및 생성
if [ ! -d "venv" ]; then
    echo "가상환경 생성 중..."
    python3 -m venv venv
fi

# 가상환경 활성화
echo "가상환경 활성화 중..."
source venv/bin/activate

# Python 버전 재확인
PYTHON_VERSION=$(python --version 2>&1 | awk '{print $2}')
echo "가상환경 Python 버전: $PYTHON_VERSION"

# 필요한 패키지 설치
echo "필요한 패키지 설치 중..."
pip install --upgrade pip
pip install -r requirements.txt

# PyInstaller 설치 확인
if ! command -v pyinstaller &> /dev/null; then
    echo "PyInstaller 설치 중..."
    pip install pyinstaller
fi

# 이전 빌드 결과물 정리
echo "이전 빌드 결과물 정리 중..."
rm -rf build dist __pycache__ *.spec

# PyInstaller로 빌드
echo "PyInstaller로 빌드 중..."
pyinstaller build_python.spec

# 빌드 완료 확인
if [ -f "dist/PDF문서비교프로그램" ] || [ -f "dist/PDF문서비교프로그램.exe" ]; then
    echo ""
    echo "=== 빌드 완료! ==="
    echo "실행 파일 위치: dist/"
    ls -lh dist/
else
    echo ""
    echo "=== 빌드 실패 ==="
    exit 1
fi

