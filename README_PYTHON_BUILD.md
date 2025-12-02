# PDF 문서 비교 프로그램 - Python 빌드 가이드

Python 3.11.4에서 실행 파일로 빌드하는 방법입니다.

## 사전 요구사항

- Python 3.11.4 이상
- pip (Python 패키지 관리자)

## 빌드 방법

### macOS / Linux

```bash
# 빌드 스크립트 실행
./build_python.sh
```

또는 수동으로:

```bash
# 가상환경 생성
python3 -m venv venv

# 가상환경 활성화
source venv/bin/activate

# 패키지 설치
pip install -r requirements.txt

# 빌드
pyinstaller build_python.spec
```

### Windows

```cmd
# 빌드 스크립트 실행
build_python.bat
```

또는 수동으로:

```cmd
# 가상환경 생성
python -m venv venv

# 가상환경 활성화
venv\Scripts\activate

# 패키지 설치
pip install -r requirements.txt

# 빌드
pyinstaller build_python.spec
```

## 빌드 결과물

빌드가 완료되면 `dist/` 폴더에 실행 파일이 생성됩니다:

- **macOS/Linux**: `PDF문서비교프로그램`
- **Windows**: `PDF문서비교프로그램.exe`

## 실행

빌드된 실행 파일을 더블클릭하거나 터미널에서 실행하세요:

```bash
# macOS/Linux
./dist/PDF문서비교프로그램

# Windows
dist\PDF문서비교프로그램.exe
```

## 문제 해결

### PyInstaller를 찾을 수 없는 경우

```bash
pip install pyinstaller
```

### 모듈을 찾을 수 없다는 오류가 발생하는 경우

`build_python.spec` 파일의 `hiddenimports` 섹션에 누락된 모듈을 추가하세요.

### 빌드된 실행 파일이 너무 큰 경우

`build_python.spec` 파일에서 `upx=True`를 `upx=False`로 변경하거나, UPX를 설치하세요.

## 추가 옵션

### 아이콘 추가

`build_python.spec` 파일에서 `icon=None` 부분을 다음과 같이 변경:

```python
icon='path/to/icon.ico',  # Windows
icon='path/to/icon.icns',  # macOS
```

### 단일 파일로 빌드 (기본값)

현재 설정은 단일 실행 파일로 빌드됩니다. 폴더 형태로 빌드하려면 `build_python.spec`의 `exe` 섹션을 수정하세요.

