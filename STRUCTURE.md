# 프로젝트 구조

PDF 문서 비교 프로그램의 트리 구조입니다.

## 디렉토리 구조

```
vibe-coding/
├── main.py                    # 진입점
├── python.py                  # 원본 파일 (레거시, 참고용)
├── requirements.txt           # Python 패키지 의존성
├── build_python.spec          # PyInstaller 빌드 설정
├── build_python.sh            # macOS/Linux 빌드 스크립트
├── build_python.bat           # Windows 빌드 스크립트
│
├── models/                    # 데이터 모델
│   ├── __init__.py
│   ├── diff_item.py          # 변경항목 데이터 구조
│   └── pdf_document.py       # PDF 문서 래퍼 및 캐시
│
├── services/                  # 비즈니스 로직
│   ├── __init__.py
│   ├── diff_engine.py        # PDF 비교 엔진
│   ├── report_generator.py   # 리포트 생성기 (Excel/CSV)
│   ├── settings_manager.py   # 사용자 설정 관리
│   └── prompt_templates.py   # 프롬프트 템플릿 생성기
│
└── views/                     # UI 뷰 컴포넌트
    ├── __init__.py
    ├── page_graphics_view.py  # PDF 페이지 그래픽 뷰
    └── main_window.py         # 메인 윈도우
```

## 모듈 설명

### models/ (데이터 모델)
- **diff_item.py**: 변경항목을 나타내는 데이터 클래스
- **pdf_document.py**: PDF 문서 로딩, 렌더링, 단어 추출 및 캐시 관리

### services/ (비즈니스 로직)
- **diff_engine.py**: PDF 문서 비교 로직 (단어 단위, 픽셀 기반 fallback)
- **report_generator.py**: 변경사항을 Excel/CSV로 내보내기
- **settings_manager.py**: 사용자 설정 저장/로드 (JSON)
- **prompt_templates.py**: LLM 연동용 프롬프트 템플릿 생성

### views/ (UI)
- **page_graphics_view.py**: PDF 페이지를 표시하고 하이라이트 오버레이를 그리는 뷰
- **main_window.py**: 메인 윈도우 및 모든 UI 로직

## 실행 방법

```bash
# 직접 실행
python3 main.py

# 빌드
./build_python.sh  # macOS/Linux
build_python.bat   # Windows
```

## 구조의 장점

1. **관심사 분리**: 비즈니스 로직과 UI가 명확히 분리됨
2. **재사용성**: 서비스 레이어는 다른 UI에서도 재사용 가능
3. **테스트 용이성**: 각 모듈을 독립적으로 테스트 가능
4. **유지보수성**: 코드 구조가 명확하여 수정이 쉬움

