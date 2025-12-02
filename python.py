 
# -*- coding: utf-8 -*-
"""
PDF 문서 비교 GUI 프로그램 (단일 .py)
 
- 좌(원본), 중(수정본), 우(변경사항 요약) 3열 구조
- 드래그&드롭으로 PDF 파일 로드 (좌: 수정 전, 중: 수정 후)
- 자동 비교: 텍스트 단어 단위로 추가/삭제/변경 하이라이트
- 페이지 단위 보기, 좌/우 화살표로 이동 (← 이전 / → 다음)
- 마우스 휠:
  * Ctrl + 휠: 확대/축소
  * Ctrl 없이 휠: 페이지 이동 (위: 이전, 아래: 다음)
- 변경사항 클릭 시 좌/중 뷰 동시 해당 위치로 스크롤
- 리포트 출력: Excel/CSV만
- 사용자 설정(JSON) 저장/로드 (줌, 최근 폴더 등)
- 대용량(100페이지+) 대응: 지연 로딩/스레드 비교/렌더링 캐시
- 프롬프트 템플릿(JSON) 내보내기 기능 (System/Developer/User + 스키마/색상/Few-shot)
 
필요 라이브러리:
 PySide6, pymupdf (fitz), pillow (PIL), pandas, openpyxl, numpy
"""
import sys
import os
import json
import time
import threading
import traceback
from collections import OrderedDict
from dataclasses import dataclass
from typing import List, Tuple, Optional, Dict
 
# GUI
from PySide6.QtCore import Qt, QSize, QRectF, QPointF, QObject, Signal
from PySide6.QtGui import QAction, QKeySequence, QPainter, QColor, QBrush, QPen, QPixmap, QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QSplitter, QVBoxLayout, QGraphicsView,
    QGraphicsScene, QGraphicsRectItem, QGraphicsPixmapItem, QFileDialog, QLabel,
    QToolBar, QStatusBar, QLineEdit, QPushButton, QTreeWidget, QTreeWidgetItem,
    QMessageBox, QProgressBar, QStyle
)
 
# PDF & Imaging
import fitz  # PyMuPDF
from PIL import Image
import numpy as np
 
# Data/report
import pandas as pd
 
# --------------------------------------------
# 프롬프트 템플릿 생성기 (LLM 연동용)
# --------------------------------------------
class PromptTemplates:
    """LLM용 프롬프트 패키지(System/Developer/User + 스키마/색상/예시) 생성기"""
    @staticmethod
    def system_prompt() -> str:
        return (
            "당신은 PDF 문서 비교 엔진의 분석 모듈이다.\n"
            "목표: 두 문서의 차이를 최대한 정확하게 식별하고, \"추가(add) / 삭제(delete) / 교체(replace) / 시각 변경(visual_change)\"을 "
            "신뢰도(confidence)와 함께 구조화하여 JSON으로만 반환하라.\n\n"
            "원칙:\n"
            "- 비교 단위: 단어 단위로 정밀 비교하되, 문장 단위로 그룹화하여 사람이 읽기 쉽게 묶어라.\n"
            "- 서식 변화(폰트/색/크기)와 공백/줄바꿈은 기본적으로 무시하라. 단, 사용자가 요청 시 포함 가능.\n"
            "- 표/이미지 변경은 텍스트 비교 불가 시 \"visual_change\"로 표기하고 근사 bbox와 근거(reasoning)를 제공.\n"
            "- 중복/잡음 최소화, 논리적으로 연결된 변경은 하나의 문장/문단 변경으로 병합.\n"
            "- 동일 페이지 내 인접 변경은 자연스러운 범위로 병합, 불명확한 경우 confidence를 낮춰라.\n\n"
            "출력(JSON만 허용):\n"
            "{\n"
            '  "meta": {\n'
            '    "source_name": "<원본 문서명>",\n'
            '    "target_name": "<수정 문서명>",\n'
            '    "page_count_compared": <int>,\n'
            '    "compare_mode": "word_sentence_grouped"\n'
            "  },\n"
            '  "changes": [\n'
            "    {\n"
            '      "page": <int>,\n'
            '      "type": "add\\ndelete\\nreplace\\nvisual_change",\n'
            '      "scope": "word\\nsentence\\nparagraph\\ntable\\nimage",\n'
            '      "old_text": "<원본 내용 또는 null>",\n'
            '      "new_text": "<수정본 내용 또는 null>",\n'
            '      "bbox_old": [x0,y0,x1,y1] \\n null,\n'
            '      "bbox_new": [x0,y0,x1,y1] \\n null,\n'
            '      "reasoning": "<변경 판별 근거(간략)>",\n'
            '      "confidence": 0.0~1.0,\n'
            '      "group_id": "<연관 변경 묶음 ID>"\n'
            "    }\n"
            "  ],\n"
            '  "summary": {\n'
            '    "total_add": <int>,\n'
            '    "total_delete": <int>,\n'
            '    "total_replace": <int>,\n'
            '    "total_visual_change": <int>,\n'
            '    "notes": ["리뷰시 주의사항 등"]\n'
            "  }\n"
            "}\n"
            "응답은 반드시 위 JSON만 반환하라. 설명 텍스트는 금지."
        )
 
    @staticmethod
    def developer_prompt() -> str:
        return (
            "엔진 튜닝 지시:\n"
            "- 토큰 기준: 단어 단위 토큰화 → 문장 경계는 마침표/개행/블록으로 추정하여 그룹화.\n"
            "- 교체 판별: 같은 위치 범위에서 old/new 텍스트가 모두 존재하며, 문자 유사도 0.3~0.85 사이면 replace.\n"
            "- 추가/삭제 판별: 시퀀스 매칭 삽입/삭제를 문장 경계 내 병합.\n"
            "- 표/이미지: 텍스트 부재 또는 레이아웃 블록 차이 크면 visual_change로 표기, bbox는 근사.\n"
            "- 중복 제거: 동일 페이지·문장 내 연속 변경은 하나로 병합.\n"
            "- 신뢰도 기준(예): 단어 정확 매칭 0.9+, 문장 유사도 0.7~0.9, 레이아웃 추정 0.5~0.7, 픽셀 차이 0.4~0.6.\n"
            "- 시각 규칙 메타:\n"
            "  delete=#FF0000(alpha 0.7), add=#FFEB3B(0.5), replace=#00BFFF(0.7), visual_change=#AB47BC(0.4)\n"
            "- 좌표: bbox는 PDF pt 기준(뷰어에서 zoom 곱해 사용).\n"
            "예외:\n"
            "- 스캔 PDF 등 텍스트 부재 시 visual_change로 대체\n"
            "- 숫자 값 미세 변경은 문맥에 따라 묶고 confidence 낮춤\n"
            "- 표/리스트 번호 자동 재정렬은 낮은 우선순위"
        )
 
    @staticmethod
    def user_prompt(
        source_name: str, target_name: str,
        page_range: str = "전체",
        include_tables_images: bool = True,
        include_format_changes: bool = False,
        grouping: str = "문장",
        confidence_threshold: float = 0.6,
        max_items: int = 100,
        key_phrases: Optional[List[str]] = None,
        sensitive_terms: Optional[List[str]] = None
    ) -> str:
        key_phrases = key_phrases or []
        sensitive_terms = sensitive_terms or []
        return (
            f"[입력]\n"
            f"- 원본 문서명: \"{source_name}\"\n"
            f"- 수정 문서명: \"{target_name}\"\n"
            f"- 비교 범위: {page_range}\n"
            f"- 표/이미지 변경 포함: {'YES' if include_tables_images else 'NO'}\n"
            f"- 서식 변화 포함(폰트/크기/색): {'YES' if include_format_changes else 'NO'}\n"
            f"- 중요 문구 목록: {json.dumps(key_phrases, ensure_ascii=False)}\n"
            f"- 민감 용어: {json.dumps(sensitive_terms, ensure_ascii=False)}\n\n"
            f"[출력 옵션]\n"
            f"- 그룹화 수준: {grouping}\n"
            f"- 변경 유형: ADD/DELETE/REPLACE/VISUAL_CHANGE\n"
            f"- confidence 임계값: {confidence_threshold}\n"
            f"- 최대 결과 수: {max_items}\n\n"
            "위 조건으로 비교를 수행하고, System Prompt에서 정의한 JSON만 반환해줘."
        )
 
    @staticmethod
    def json_schema() -> Dict:
        return {
            "meta": {
                "source_name": "old.pdf",
                "target_name": "new.pdf",
                "page_count_compared": 0,
                "compare_mode": "word_sentence_grouped"
            },
            "changes": [{
                "page": 1,
                "type": "add\ndelete\nreplace\nvisual_change",
                "scope": "word\nsentence\nparagraph\ntable\nimage",
                "old_text": None,
                "new_text": None,
                "bbox_old": None,
                "bbox_new": None,
                "reasoning": "",
                "confidence": 0.0,
                "group_id": ""
            }],
            "summary": {
                "total_add": 0,
                "total_delete": 0,
                "total_replace": 0,
                "total_visual_change": 0,
                "notes": []
            }
        }
 
    @staticmethod
    def colors() -> Dict:
        return {
            "delete": {"hex": "#FF0000", "alpha": 0.7},
            "add": {"hex": "#FFEB3B", "alpha": 0.5},
            "replace": {"hex": "#00BFFF", "alpha": 0.7},
            "visual_change": {"hex": "#AB47BC", "alpha": 0.4},
        }
 
    @staticmethod
    def few_shot_examples() -> List[Dict]:
        return [
            {
                "meta": {"source_name": "spec_v1.pdf", "target_name": "spec_v2.pdf",
                         "page_count_compared": 1, "compare_mode": "word_sentence_grouped"},
                "changes": [{
                    "page": 1, "type": "replace", "scope": "sentence",
                    "old_text": "투여량은 하루 500 mg 입니다.",
                    "new_text": "투여량은 하루 600 mg 입니다.",
                    "bbox_old": [210, 420, 540, 448],
                    "bbox_new": [208, 418, 542, 446],
                    "reasoning": "숫자 값 변경(문맥 동일)", "confidence": 0.88, "group_id": "p1_s3"
                }],
                "summary": {"total_add": 0, "total_delete": 0, "total_replace": 1, "total_visual_change": 0, "notes": []}
            },
            {
                "meta": {"source_name": "leaflet_old.pdf", "target_name": "leaflet_new.pdf",
                         "page_count_compared": 1, "compare_mode": "word_sentence_grouped"},
                "changes": [
                    {"page": 1, "type": "add", "scope": "sentence",
                     "old_text": None,
                     "new_text": "임산부는 복용 전 반드시 전문가와 상담하세요.",
                     "bbox_old": None, "bbox_new": [100, 680, 520, 708],
                     "reasoning": "새 문장 삽입", "confidence": 0.92, "group_id": "p1_s6"},
                    {"page": 1, "type": "delete", "scope": "sentence",
                     "old_text": "복용 전 의사와 상담이 필요합니다.",
                     "new_text": None, "bbox_old": [98, 640, 518, 668],
                     "bbox_new": None, "reasoning": "의미 중복 문장 삭제",
                     "confidence": 0.78, "group_id": "p1_s6"}
                ],
                "summary": {"total_add": 1, "total_delete": 1, "total_replace": 0, "total_visual_change": 0, "notes": []}
            },
            {
                "meta": {"source_name": "label_old.pdf", "target_name": "label_new.pdf",
                         "page_count_compared": 1, "compare_mode": "word_sentence_grouped"},
                "changes": [{
                    "page": 1, "type": "visual_change", "scope": "image",
                    "old_text": None, "new_text": None,
                    "bbox_old": [60, 120, 520, 350], "bbox_new": [60, 120, 520, 350],
                    "reasoning": "이미지/로고 색상 및 형태 변경 감지", "confidence": 0.58, "group_id": "p1_img1"
                }],
                "summary": {"total_add": 0, "total_delete": 0, "total_replace": 0, "total_visual_change": 1,
                            "notes": ["시각 요소 변경: 디자인 승인 필요"]}
            }
        ]
 
    @staticmethod
    def build_package(
        source_name: str, target_name: str,
        page_range: str = "전체",
        include_tables_images: bool = True,
        include_format_changes: bool = False,
        grouping: str = "문장",
        confidence_threshold: float = 0.6,
        max_items: int = 100,
        key_phrases: Optional[List[str]] = None,
        sensitive_terms: Optional[List[str]] = None
    ) -> Dict:
        """프롬프트 패키지(JSON) 생성"""
        return {
            "system": PromptTemplates.system_prompt(),
            "developer": PromptTemplates.developer_prompt(),
            "user": PromptTemplates.user_prompt(
                source_name, target_name,
                page_range, include_tables_images, include_format_changes,
                grouping, confidence_threshold, max_items,
                key_phrases or [], sensitive_terms or []
            ),
            "schema": PromptTemplates.json_schema(),
            "colors": PromptTemplates.colors(),
            "few_shot": PromptTemplates.few_shot_examples()
        }
 
# --------------------------------------------
# 설정 관리자 (사용자 설정 저장/로드)
# --------------------------------------------
class SettingsManager:
    """사용자 설정(JSON) 저장/로드 관리자"""
    def __init__(self, app_name="PDFDiffViewer"):
        self.app_name = app_name
        self.settings = {
            "zoom": 1.25,
            "last_open_dir": "",
            "max_cache_pages": 8,
            "compare_mode": "lazy",   # 'lazy': 현재 페이지부터 순차 비교, 'all': 전체 즉시 비교
        }
        self.path = self._settings_path()
        self.load()
 
    def _settings_path(self) -> str:
        appdata = os.getenv("APPDATA") or os.path.expanduser("~")
        cfg_dir = os.path.join(appdata, self.app_name)
        os.makedirs(cfg_dir, exist_ok=True)
        return os.path.join(cfg_dir, "settings.json")
 
    def load(self):
        try:
            if os.path.exists(self.path):
                with open(self.path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        self.settings.update(data)
        except Exception:
            pass
 
    def save(self):
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
 
    def get(self, key, default=None):
        return self.settings.get(key, default)
 
    def set(self, key, value):
        self.settings[key] = value
        self.save()
 
# --------------------------------------------
# 데이터 구조 (변경항목)
# --------------------------------------------
@dataclass
class DiffItem:
    """변경항목 데이터 구조"""
    page: int
    change_type: str  # 'add', 'delete', 'replace', 'visual_change'
    text: str
    bbox_old: Optional[Tuple[float, float, float, float]] = None  # 원본 문서 내 영역 (PDF pt)
    bbox_new: Optional[Tuple[float, float, float, float]] = None  # 수정 문서 내 영역 (PDF pt)
 
    def summary(self) -> str:
        return f"p.{self.page+1} [{self.change_type}] {self.text}"
 
# --------------------------------------------
# PDF 문서 래퍼 및 캐시
# --------------------------------------------
class PDFDocument:
    """PDF 문서 로딩/렌더링/단어 추출 + 렌더 캐시(LRU)"""
    def __init__(self, path: str, max_cache_pages: int = 8):
        self.path = path
        self.doc = fitz.open(path)
        self.page_count = self.doc.page_count
        self.cache = OrderedDict()
        self.max_cache_pages = max_cache_pages
 
    def close(self):
        try:
            self.doc.close()
        except Exception:
            pass
 
    def get_words(self, page_index: int) -> List[Tuple[float, float, float, float, str]]:
        """
        단어별 bbox와 텍스트 추출
        반환 형식: [(x0,y0,x1,y1, text), ...] (PDF 좌표 단위: pt)
        """
        page = self.doc.load_page(page_index)
        words = page.get_text("words")  # (x0,y0,x1,y1, "word", block_no, line_no, word_no)
        return [(w[0], w[1], w[2], w[3], w[4]) for w in words]
 
    def render_page_pixmap(self, page_index: int, zoom: float = 1.0) -> QPixmap:
        """
        QPixmap 반환 (GUI 표시용). 캐시 사용.
        """
        key = (page_index, round(zoom, 2))
        if key in self.cache:
            pix = self.cache[key]
            self.cache.move_to_end(key)
            return pix
        page = self.doc.load_page(page_index)
        mat = fitz.Matrix(zoom, zoom)
        pm = page.get_pixmap(matrix=mat, alpha=False)  # RGB
        img = QPixmap()
        img.loadFromData(pm.tobytes("png"))
        self.cache[key] = img
        if len(self.cache) > self.max_cache_pages:
            self.cache.popitem(last=False)
        return img
 
    def render_page_pil(self, page_index: int, zoom: float = 1.0) -> Image.Image:
        """리포트 이미지 생성용 PIL Image 반환"""
        page = self.doc.load_page(page_index)
        mat = fitz.Matrix(zoom, zoom)
        pm = page.get_pixmap(matrix=mat, alpha=False)
        img = Image.frombytes("RGB", [pm.width, pm.height], pm.samples)
        return img
 
# --------------------------------------------
# 그래픽 뷰 (페이지 표시 + 오버레이)
# --------------------------------------------
class PageGraphicsView(QGraphicsView):
    """
    PDF 페이지를 이미지로 렌더링하여 표시하고,
    변경 하이라이트(사각형) 오버레이를 추가로 표시.
 
    - 마우스 휠:
      * Ctrl + Wheel → 확대/축소
      * Ctrl 없이 Wheel → 페이지 이동 (위: 이전, 아래: 다음)
    - 좌/우 화살표 → 페이지 이동
    - 드래그&드롭: PDF 파일 열기
    """
    fileDropped = Signal(str)
    pageChanged = Signal(int)
    zoomChanged = Signal(float)
 
    def __init__(self, parent=None, role="old"):
        super().__init__(parent)
        self.role = role  # 'old' or 'new'
        self.setRenderHint(QPainter.Antialiasing, False)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setAcceptDrops(True)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.doc: Optional[PDFDocument] = None
        self.current_page = 0
        self.zoom = 1.25
        self.image_item: Optional[QGraphicsPixmapItem] = None
        self.overlay_items: List[QGraphicsRectItem] = []
 
    def sizeHint(self):
        return QSize(600, 800)
 
    def clear(self):
        self.scene.clear()
        self.image_item = None
        self.overlay_items.clear()
 
    def set_document(self, doc: PDFDocument):
        self.doc = doc
        self.current_page = 0
        self.refresh_page()
 
    def set_zoom(self, value: float):
        self.zoom = max(0.5, min(3.0, float(value)))
        self.refresh_page()
        self.zoomChanged.emit(self.zoom)
 
    def add_highlights(self, rects_pt: List[Tuple[float, float, float, float]], color: QColor):
        """
        rect 좌표는 PDF pt 기준(문서 좌표). 현재 줌을 반영해 픽셀 좌표로 변환하여 오버레이.
        """
        z = self.zoom
        for r in rects_pt:
            x0, y0, x1, y1 = r
            rx0, ry0, rx1, ry1 = x0 * z, y0 * z, x1 * z, y1 * z
            rect_item = QGraphicsRectItem(QRectF(rx0, ry0, rx1 - rx0, ry1 - ry0))
            rect_item.setBrush(QBrush(color))
            rect_item.setPen(QPen(Qt.GlobalColor.transparent))
            rect_item.setOpacity(color.alphaF())
            self.scene.addItem(rect_item)
            self.overlay_items.append(rect_item)
 
    def refresh_page(self):
        self.scene.clear()
        self.overlay_items.clear()
        if not self.doc:
            return
        self.current_page = max(0, min(self.current_page, self.doc.page_count - 1))
        pixmap = self.doc.render_page_pixmap(self.current_page, self.zoom)
        self.image_item = QGraphicsPixmapItem(pixmap)
        self.scene.addItem(self.image_item)
 
    # --- Wheel 이벤트
    def wheelEvent(self, event):
        # Ctrl + Wheel → 줌
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            if delta > 0:
                self.set_zoom(self.zoom * 1.10)
            else:
                self.set_zoom(self.zoom / 1.10)
            event.accept()
            return
 
        # Ctrl 없이 Wheel → 페이지 이동
        delta = event.angleDelta().y()
        if delta == 0:
            # 트랙패드 등 일부 환경을 위해 pixelDelta 보조 확인
            pdelta = event.pixelDelta().y()
            delta = pdelta
        if delta > 0:
            # 위로 스크롤 → 이전 페이지
            self.goto_page(self.current_page - 1)
        else:
            # 아래로 스크롤 → 다음 페이지
            self.goto_page(self.current_page + 1)
        event.accept()
 
    def keyPressEvent(self, event):
        key = event.key()
        # 좌/우 화살표로 페이지 이동
        if key == Qt.Key.Key_Right:
            self.goto_page(self.current_page + 1)
            event.accept()
            return
        if key == Qt.Key.Key_Left:
            self.goto_page(self.current_page - 1)
            event.accept()
            return
        # 기존 PageUp/PageDown 동작 비활성화(원하면 유지 가능)
        if key in (Qt.Key.Key_PageUp, Qt.Key.Key_PageDown):
            event.accept()
            return
        super().keyPressEvent(event)
 
    def goto_page(self, page_index: int):
        if not self.doc:
            return
        page_index = max(0, min(page_index, self.doc.page_count - 1))
        if page_index != self.current_page:
            self.current_page = page_index
            self.refresh_page()
            self.pageChanged.emit(self.current_page)
 
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls and urls[0].toLocalFile().lower().endswith(".pdf"):
                event.acceptProposedAction()
 
    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            if path.lower().endswith(".pdf"):
                self.fileDropped.emit(path)
 
# --------------------------------------------
# 비교 엔진 (스레드)
# --------------------------------------------
class DiffEngine(QObject):
    """
    PDF 비교 엔진
    - 단어 수준 비교(difflib) + bbox로 하이라이트 생성
    - 텍스트가 거의 없을 경우 픽셀 기반 차이(간단)로 fallback
    - 비동기 실행(스레드) + 진행률 콜백
    - 하이라이트 좌표는 모두 PDF pt 기준으로 저장
    """
    finished = Signal(object, object, object)  # (old_highlights: dict, new_highlights: dict, summary: list[DiffItem])
    progress = Signal(int, int)                # processed_pages, total_pages
    error = Signal(str)
 
    def __init__(self):
        super().__init__()
        self._thread: Optional[threading.Thread] = None
        self._abort = False
 
    def abort(self):
        self._abort = True
 
    @staticmethod
    def _tokenize_words(words: List[Tuple[float, float, float, float, str]]) -> List[str]:
        return [w[4] for w in words]
 
    def _pixel_diff_regions(self, img_old: Image.Image, img_new: Image.Image, thresh: int = 30) -> List[Tuple[int, int, int, int]]:
        """
        간단한 픽셀 기반 차이 영역 검출:
        - 두 이미지를 같은 크기로 맞춘 뒤 차이 이미지를 계산
        - 임계값 초과 영역의 바운딩 박스를 찾음 (블록 기반)
        """
        w = min(img_old.width, img_new.width)
        h = min(img_old.height, img_new.height)
        a = img_old.crop((0, 0, w, h)).convert("L")
        b = img_new.crop((0, 0, w, h)).convert("L")
        arr = np.abs(np.array(a, dtype=np.int16) - np.array(b, dtype=np.int16))
        mask = (arr > thresh).astype(np.uint8)
        step = max(20, int(min(w, h) * 0.02))
        regions = []
        for y in range(0, h, step):
            for x in range(0, w, step):
                block = mask[y:y+step, x:x+step]
                if block.sum() > (step*step*0.05):  # 5% 이상 달라지면 변경으로 간주
                    regions.append((x, y, x+step, y+step))
        return regions
 
    def compare(self, old_doc: PDFDocument, new_doc: PDFDocument, zoom_for_pix: float, mode: str = "lazy"):
        """
        비교 실행 (별도 스레드)
        mode:
        - 'lazy' : 현재 페이지부터 순차 처리(대용량 대응)
        - 'all'  : 전체 페이지 즉시 처리
 
        NOTE:
        - 텍스트 비교 결과 하이라이트는 PDF pt 좌표로 저장
        - 픽셀 비교 fallback도 PDF pt 좌표로 저장(렌더링 시 사용한 zoom_for_pix 로 나눠 pt 변환)
        """
        def run():
            try:
                total = min(old_doc.page_count, new_doc.page_count)
                old_hls: Dict[int, Dict[str, List[Tuple[float, float, float, float]]]] = {}
                new_hls: Dict[int, Dict[str, List[Tuple[float, float, float, float]]]] = {}
                summary: List[DiffItem] = []
 
                for i in range(total):
                    if self._abort:
                        return
 
                    words_old = old_doc.get_words(i)
                    words_new = new_doc.get_words(i)
                    tokens_old = self._tokenize_words(words_old)
                    tokens_new = self._tokenize_words(words_new)
 
                    page_old_add_rects_pt: List[Tuple[float, float, float, float]] = []
                    page_old_del_rects_pt: List[Tuple[float, float, float, float]] = []
                    page_old_vis_rects_pt: List[Tuple[float, float, float, float]] = []
 
                    page_new_add_rects_pt: List[Tuple[float, float, float, float]] = []
                    page_new_del_rects_pt: List[Tuple[float, float, float, float]] = []
                    page_new_vis_rects_pt: List[Tuple[float, float, float, float]] = []
 
                    # 텍스트가 없는 페이지 → 픽셀기반 차이
                    if len(tokens_old) == 0 and len(tokens_new) == 0:
                        img_old = old_doc.render_page_pil(i, zoom_for_pix)
                        img_new = new_doc.render_page_pil(i, zoom_for_pix)
                        regions_px = self._pixel_diff_regions(img_old, img_new)
                        for (x0, y0, x1, y1) in regions_px:
                            # PDF pt 좌표로 환산
                            x0_pt, y0_pt, x1_pt, y1_pt = x0/zoom_for_pix, y0/zoom_for_pix, x1/zoom_for_pix, y1/zoom_for_pix
                            di = DiffItem(
                                page=i, change_type="visual_change", text="[visual change]",
                                bbox_old=(x0_pt, y0_pt, x1_pt, y1_pt),
                                bbox_new=(x0_pt, y0_pt, x1_pt, y1_pt)
                            )
                            summary.append(di)
                            page_old_vis_rects_pt.append((x0_pt, y0_pt, x1_pt, y1_pt))
                            page_new_vis_rects_pt.append((x0_pt, y0_pt, x1_pt, y1_pt))
                    else:
                        import difflib
                        sm = difflib.SequenceMatcher(None, tokens_old, tokens_new, autojunk=False)
                        opcodes = sm.get_opcodes()
 
                        for tag, i1, i2, j1, j2 in opcodes:
                            if tag == 'equal':
                                continue
 
                            # 삭제/교체 → 원본에 'delete'로 하이라이트
                            if tag in ('delete', 'replace'):
                                # 단어별 bbox 수집(PDF pt)
                                for k in range(i1, i2):
                                    if k < len(words_old):
                                        x0, y0, x1, y1, _ = words_old[k]
                                        page_old_del_rects_pt.append((x0, y0, x1, y1))
 
                                txt_old = " ".join(tokens_old[i1:i2])[:200]
                                if txt_old.strip():
                                    bbox_old = None
                                    if i2 > i1 and i1 < len(words_old) and (i2-1) < len(words_old):
                                        bbox_old = (words_old[i1][0], words_old[i1][1], words_old[i2-1][2], words_old[i2-1][3])
                                    summary.append(DiffItem(page=i, change_type="delete", text=txt_old, bbox_old=bbox_old))
 
                            # 삽입/교체 → 수정본에 'add'로 하이라이트
                            if tag in ('insert', 'replace'):
                                for k in range(j1, j2):
                                    if k < len(words_new):
                                        x0, y0, x1, y1, _ = words_new[k]
                                        page_new_add_rects_pt.append((x0, y0, x1, y1))
 
                                txt_new = " ".join(tokens_new[j1:j2])[:200]
                                if txt_new.strip():
                                    bbox_new = None
                                    if j2 > j1 and j1 < len(words_new) and (j2-1) < len(words_new):
                                        bbox_new = (words_new[j1][0], words_new[j1][1], words_new[j2-1][2], words_new[j2-1][3])
                                    summary.append(DiffItem(page=i, change_type="add", text=txt_new, bbox_new=bbox_new))
 
                    # 페이지별 하이라이트 저장(PDF pt)
                    old_hls[i] = {
                        "delete": page_old_del_rects_pt,
                        "add": page_old_add_rects_pt,
                        "visual_change": page_old_vis_rects_pt,
                    }
                    new_hls[i] = {
                        "delete": page_new_del_rects_pt,
                        "add": page_new_add_rects_pt,
                        "visual_change": page_new_vis_rects_pt,
                    }
 
                    self.progress.emit(i+1, total)
                    if mode == "lazy":
                        time.sleep(0.001)
 
                self.finished.emit(old_hls, new_hls, summary)
 
            except Exception as e:
                tb = traceback.format_exc()
                self.error.emit(f"{e}\n{tb}")
            finally:
                self._abort = False
 
        self._thread = threading.Thread(target=run, daemon=True)
        self._thread.start()
 
# --------------------------------------------
# 리포트 생성기 (Excel/CSV만)
# --------------------------------------------
class ReportGenerator:
    """리포트 파일(Excel/CSV) 생성"""
    def __init__(self, old_doc: PDFDocument, new_doc: PDFDocument, old_hls, new_hls, summary: List[DiffItem], zoom: float):
        self.old_doc = old_doc
        self.new_doc = new_doc
        self.old_hls = old_hls
        self.new_hls = new_hls
        self.summary = summary
        self.zoom = zoom
 
    @staticmethod
    def _ensure_dir(path: str):
        os.makedirs(path, exist_ok=True)
 
    def export_csv_excel(self, outdir: str, basename: str = "diff_changes"):
        """변경사항 목록을 CSV와 Excel로 내보내기"""
        self._ensure_dir(outdir)
        rows = []
        for di in self.summary:
            rows.append({
                "Page": di.page + 1,
                "Type": di.change_type,
                "Text": di.text,
                "BBox_Old": di.bbox_old,
                "BBox_New": di.bbox_new,
            })
        df = pd.DataFrame(rows)
        csv_path = os.path.join(outdir, f"{basename}.csv")
        xlsx_path = os.path.join(outdir, f"{basename}.xlsx")
        df.to_csv(csv_path, index=False, encoding="utf-8-sig")
        df.to_excel(xlsx_path, index=False, engine="openpyxl")
        return csv_path, xlsx_path
 
# --------------------------------------------
# 메인 윈도우(UI)
# --------------------------------------------
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PDF 문서 비교 뷰어")
        self.resize(1600, 900)
 
        # 설정
        self.settings = SettingsManager()
        self.default_zoom = float(self.settings.get("zoom", 1.25))
        self.max_cache_pages = int(self.settings.get("max_cache_pages", 8))
        self.compare_mode = self.settings.get("compare_mode", "lazy")
 
        # 상태
        self.old_doc: Optional[PDFDocument] = None
        self.new_doc: Optional[PDFDocument] = None
        self.old_highlights: Dict[int, Dict[str, List[Tuple[float, float, float, float]]]] = {}
        self.new_highlights: Dict[int, Dict[str, List[Tuple[float, float, float, float]]]] = {}
        self.summary_items: List[DiffItem] = []
 
        self.diff_engine = DiffEngine()
        self.diff_engine.finished.connect(self.on_diff_finished)
        self.diff_engine.progress.connect(self.on_diff_progress)
        self.diff_engine.error.connect(self.on_diff_error)
 
        # --- 두 문서 동시 페이지/줌 이동 토글
        self.sync_pages: bool = False
        self._sync_changing: bool = False  # 내부 가드(피드백 루프 방지)
 
        # 좌/중/우 스플리터
        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.setCentralWidget(splitter)
 
        # 좌: 원본
        self.view_old = PageGraphicsView(role="old")
        self.view_old.set_zoom(self.default_zoom)
        self.view_old.fileDropped.connect(self.load_old_pdf)
        # 기존 summary 연동 시그널은 유지
        self.view_old.pageChanged.connect(self.sync_right_summary_to_page)
        # 동시 페이지 이동을 위한 별도 슬롯 연결
        self.view_old.pageChanged.connect(self.on_view_old_page_changed)
        self.view_old.zoomChanged.connect(self.on_view_old_zoom_changed)
        splitter.addWidget(self._wrap_with_title(self.view_old, "수정 전 문서"))
 
        # 중: 수정본
        self.view_new = PageGraphicsView(role="new")
        self.view_new.set_zoom(self.default_zoom)
        self.view_new.fileDropped.connect(self.load_new_pdf)
        self.view_new.pageChanged.connect(self.sync_right_summary_to_page)
        self.view_new.pageChanged.connect(self.on_view_new_page_changed)
        self.view_new.zoomChanged.connect(self.on_view_new_zoom_changed)
        splitter.addWidget(self._wrap_with_title(self.view_new, "수정 후 문서"))
 
        # 우: 변경사항 요약
        self.summary_panel = QTreeWidget()
        self.summary_panel.setHeaderLabels(["페이지", "유형", "내용"])
        self.summary_panel.itemClicked.connect(self.on_summary_item_clicked)
        splitter.addWidget(self._wrap_with_title(self.summary_panel, "변경사항 요약"))
        splitter.setSizes([700, 700, 200])
 
        # 툴바
        toolbar = QToolBar("도구")
        toolbar.setIconSize(QSize(16, 16))
        self.addToolBar(toolbar)
 
        open_old_act = QAction(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton), "원본 열기", self)
        open_old_act.triggered.connect(lambda: self.open_pdf_dialog(target="old"))
        toolbar.addAction(open_old_act)
 
        open_new_act = QAction(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton), "수정본 열기", self)
        open_new_act.triggered.connect(lambda: self.open_pdf_dialog(target="new"))
        toolbar.addAction(open_new_act)
 
        compare_act = QAction("비교 실행", self)
        compare_act.setShortcut(QKeySequence("Ctrl+D"))
        compare_act.triggered.connect(self.start_compare)
        toolbar.addAction(compare_act)
 
        # Excel/CSV 리포트
        export_tab_act = QAction("Excel/CSV 리포트", self)
        export_tab_act.triggered.connect(self.export_table_report)
        toolbar.addAction(export_tab_act)
 
        # 프롬프트 패키지(JSON) 내보내기
        export_prompt_act = QAction("프롬프트 패키지(JSON)", self)
        export_prompt_act.triggered.connect(self.export_prompt_templates)
        toolbar.addAction(export_prompt_act)
 
        toolbar.addSeparator()
 
        # Zoom 입력
        self.zoom_edit = QLineEdit(f"{self.default_zoom:.2f}")
        self.zoom_edit.setFixedWidth(60)
        self.zoom_edit.setToolTip("줌 배율 (0.5~3.0)")
        self.zoom_edit.returnPressed.connect(self.apply_zoom_from_edit)
        toolbar.addWidget(QLabel("Zoom:"))
        toolbar.addWidget(self.zoom_edit)
 
        # 동시 페이지 이동 토글 버튼 (Zoom 옆)
        toolbar.addWidget(QLabel(" "))
        self.sync_btn = QPushButton("Sync OFF")
        self.sync_btn.setCheckable(True)
        self.sync_btn.setToolTip("두 문서를 동시에 좌/우 페이지 이동 (OFF/ON)")
        self.sync_btn.toggled.connect(self.on_sync_toggled)
        toolbar.addWidget(self.sync_btn)
 
        # 비교 모드 토글 (Lazy / All)
        toolbar.addWidget(QLabel(" "))
        self.mode_btn = QPushButton("Mode: Lazy")
        self.mode_btn.setCheckable(True)
        self.mode_btn.setToolTip("비교 모드 전환 (Lazy/All)")
        self.mode_btn.toggled.connect(self.on_mode_toggled)
        toolbar.addWidget(self.mode_btn)
        if self.compare_mode == "all":
            self.mode_btn.setChecked(True)
            self.mode_btn.setText("Mode: All")
 
        # 상태바
        status = QStatusBar()
        self.setStatusBar(status)
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedWidth(240)
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        status.addWidget(self.progress_bar)
 
    def _wrap_with_title(self, widget: QWidget, title: str) -> QWidget:
        wrapper = QWidget()
        v = QVBoxLayout(wrapper)
        v.setContentsMargins(6, 6, 6, 6)
        lbl = QLabel(f"📂 {title}")
        v.addWidget(lbl)
        v.addWidget(widget)
        return wrapper
 
    # -------------------- 파일 로딩 --------------------
    def open_pdf_dialog(self, target="old"):
        last_dir = self.settings.get("last_open_dir", "")
        path, _ = QFileDialog.getOpenFileName(self, "PDF 파일 선택", last_dir, "PDF Files (*.pdf)")
        if not path:
            return
        self.settings.set("last_open_dir", os.path.dirname(path))
        if target == "old":
            self.load_old_pdf(path)
        else:
            self.load_new_pdf(path)
 
    def load_old_pdf(self, path: str):
        try:
            if self.old_doc:
                self.old_doc.close()
            self.old_doc = PDFDocument(path, self.max_cache_pages)
            self.view_old.set_document(self.old_doc)
            self.statusBar().showMessage(f"원본 로드: {os.path.basename(path)} ({self.old_doc.page_count}p)")
            self.maybe_auto_compare()
        except Exception as e:
            QMessageBox.critical(self, "오류", f"원본 PDF 로드 실패:\n{e}")
 
    def load_new_pdf(self, path: str):
        try:
            if self.new_doc:
                self.new_doc.close()
            self.new_doc = PDFDocument(path, self.max_cache_pages)
            self.view_new.set_document(self.new_doc)
            self.statusBar().showMessage(f"수정본 로드: {os.path.basename(path)} ({self.new_doc.page_count}p)")
            self.maybe_auto_compare()
        except Exception as e:
            QMessageBox.critical(self, "오류", f"수정본 PDF 로드 실패:\n{e}")
 
    def maybe_auto_compare(self):
        # 두 파일 모두 로드되면 자동 비교
        if self.old_doc and self.new_doc:
            self.start_compare()
 
    # -------------------- 비교 --------------------
    def start_compare(self):
        if not (self.old_doc and self.new_doc):
            QMessageBox.information(self, "안내", "원본과 수정본 PDF를 모두 로드해주세요.")
            return
        self.summary_panel.clear()
        self.old_highlights.clear()
        self.new_highlights.clear()
        self.summary_items.clear()
        self.progress_bar.setValue(0)
        total = min(self.old_doc.page_count, self.new_doc.page_count)
        self.progress_bar.setMaximum(total)
        # 픽셀 비교 fallback 시 사용할 렌더 줌: 현재 좌측 뷰의 줌(오버레이 비율 일치 목적)
        pix_zoom = self.view_old.zoom
        self.diff_engine.compare(self.old_doc, self.new_doc, pix_zoom, mode=self.compare_mode)
        self.statusBar().showMessage("비교 실행 중...")
 
    def on_diff_progress(self, done: int, total: int):
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(done)
 
    def on_diff_error(self, msg: str):
        QMessageBox.critical(self, "비교 오류", msg)
        self.statusBar().showMessage("비교 오류")
 
    def on_diff_finished(self, old_hls, new_hls, summary: List[DiffItem]):
        self.old_highlights = old_hls
        self.new_highlights = new_hls
        self.summary_items = summary
        self.statusBar().showMessage("비교 완료")
        self.apply_highlights_for_page(self.view_old.current_page)
        self.apply_highlights_for_page(self.view_new.current_page)
        self.populate_summary_panel()
 
    def _color(self, hex_code: str, alpha_float: float) -> QColor:
        c = QColor(hex_code)
        c.setAlphaF(alpha_float)
        return c
 
    def apply_highlights_for_page(self, page_index: int):
        # 좌(삭제/빨강 + 시각 변경/보라) / 중(추가/노랑 + 시각 변경/보라)
        # 좌
        if self.view_old.doc and page_index in self.old_highlights:
            self.view_old.refresh_page()
            red = self._color("#FF0000", 0.70)          # delete
            purple = self._color("#AB47BC", 0.40)       # visual_change
            rects_del = self.old_highlights[page_index].get("delete", [])
            rects_vis = self.old_highlights[page_index].get("visual_change", [])
            if rects_del:
                self.view_old.add_highlights(rects_del, red)
            if rects_vis:
                self.view_old.add_highlights(rects_vis, purple)
 
        # 중
        if self.view_new.doc and page_index in self.new_highlights:
            self.view_new.refresh_page()
            yellow = self._color("#FFEB3B", 0.50)       # add
            purple = self._color("#AB47BC", 0.40)       # visual_change
            rects_add = self.new_highlights[page_index].get("add", [])
            rects_vis = self.new_highlights[page_index].get("visual_change", [])
            if rects_add:
                self.view_new.add_highlights(rects_add, yellow)
            if rects_vis:
                self.view_new.add_highlights(rects_vis, purple)
 
    def populate_summary_panel(self):
        self.summary_panel.clear()
        grouped: Dict[int, List[DiffItem]] = {}
        for di in self.summary_items:
            grouped.setdefault(di.page, []).append(di)
        for page in sorted(grouped.keys()):
            page_item = QTreeWidgetItem(self.summary_panel, [str(page+1), "", ""])
            for di in grouped[page]:
                child = QTreeWidgetItem(page_item, [
                    str(di.page+1),
                    di.change_type,
                    di.text
                ])
                child.setData(0, Qt.ItemDataRole.UserRole, di)
            page_item.setExpanded(True)
 
    def on_summary_item_clicked(self, item: QTreeWidgetItem, col: int):
        di: DiffItem = item.data(0, Qt.ItemDataRole.UserRole)
        if not di:
            return
        # 요약 클릭 시 두 문서 같은 페이지로 이동
        self.view_old.goto_page(di.page)
        self.view_new.goto_page(di.page)
 
        def center_on_bbox(view: PageGraphicsView, bbox: Optional[Tuple[float, float, float, float]]):
            if not bbox:
                return
            x0, y0, x1, y1 = bbox
            z = view.zoom
            cx = (x0 + x1) / 2.0 * z
            cy = (y0 + y1) / 2.0 * z
            view.centerOn(QPointF(cx, cy))
 
        center_on_bbox(self.view_old, di.bbox_old)
        center_on_bbox(self.view_new, di.bbox_new)
 
    def sync_right_summary_to_page(self, page_index: int):
        # 해당 페이지 하이라이트 적용
        self.apply_highlights_for_page(page_index)
 
    # -------------------- 동기화 로직 --------------------
    def on_sync_toggled(self, checked: bool):
        self.sync_pages = checked
        self.sync_btn.setText("Sync ON" if checked else "Sync OFF")
        self.statusBar().showMessage("동시 페이지 이동: ON" if checked else "동시 페이지 이동: OFF")
 
    def on_view_old_page_changed(self, page_index: int):
        # Sync ON 상태에서만 수정본 페이지를 동일하게 맞춤
        if not self.sync_pages or self._sync_changing:
            return
        try:
            self._sync_changing = True
            if self.view_new.doc:
                self.view_new.goto_page(page_index)
        finally:
            self._sync_changing = False
 
    def on_view_new_page_changed(self, page_index: int):
        # Sync ON 상태에서만 원본 페이지를 동일하게 맞춤
        if not self.sync_pages or self._sync_changing:
            return
        try:
            self._sync_changing = True
            if self.view_old.doc:
                self.view_old.goto_page(page_index)
        finally:
            self._sync_changing = False
 
    def on_view_old_zoom_changed(self, z: float):
        # Sync ON 상태에서만 수정본 줌을 동일하게 맞춤
        if not self.sync_pages or self._sync_changing:
            return
        try:
            self._sync_changing = True
            if self.view_new.doc:
                self.view_new.set_zoom(z)
        finally:
            self._sync_changing = False
 
    def on_view_new_zoom_changed(self, z: float):
        # Sync ON 상태에서만 원본 줌을 동일하게 맞춤
        if not self.sync_pages or self._sync_changing:
            return
        try:
            self._sync_changing = True
            if self.view_old.doc:
                self.view_old.set_zoom(z)
        finally:
            self._sync_changing = False
 
    # -------------------- 줌 설정 --------------------
    def apply_zoom_from_edit(self):
        try:
            z = float(self.zoom_edit.text().strip())
            z = max(0.5, min(3.0, z))
            self.view_old.set_zoom(z)
            self.view_new.set_zoom(z)
            self.settings.set("zoom", z)
        except Exception:
            QMessageBox.information(self, "안내", "줌 값은 0.5~3.0 사이의 숫자를 입력하세요.")
 
    # -------------------- 리포트 (Excel/CSV만) --------------------
    def _select_output_dir(self) -> Optional[str]:
        last_dir = self.settings.get("last_open_dir", "")
        outdir = QFileDialog.getExistingDirectory(self, "리포트 출력 폴더 선택", last_dir)
        if outdir:
            self.settings.set("last_open_dir", outdir)
            return outdir
        return None
 
    def export_table_report(self):
        if not self.summary_items:
            QMessageBox.information(self, "안내", "먼저 비교를 실행하여 변경사항을 생성해주세요.")
            return
        outdir = self._select_output_dir()
        if not outdir:
            return
        try:
            rg = ReportGenerator(self.old_doc, self.new_doc, self.old_highlights, self.new_highlights, self.summary_items, self.view_old.zoom)
            csv_path, xlsx_path = rg.export_csv_excel(outdir)
            QMessageBox.information(self, "완료", f"CSV/Excel 리포트 생성 완료:\n{csv_path}\n{xlsx_path}")
        except Exception as e:
            QMessageBox.critical(self, "오류", f"CSV/Excel 리포트 생성 실패:\n{e}")
 
    # -------------------- 프롬프트 템플릿 내보내기 --------------------
    def export_prompt_templates(self):
        if not (self.old_doc and self.new_doc):
            QMessageBox.information(self, "안내", "프롬프트 생성을 위해 원본과 수정본 PDF를 모두 로드해주세요.")
            return
        outdir = self._select_output_dir()
        if not outdir:
            return
        try:
            source_name = os.path.basename(self.old_doc.path)
            target_name = os.path.basename(self.new_doc.path)
            package = PromptTemplates.build_package(
                source_name=source_name,
                target_name=target_name,
                page_range="전체",
                include_tables_images=True,
                include_format_changes=False,
                grouping="문장",
                confidence_threshold=0.6,
                max_items=100,
                key_phrases=[],
                sensitive_terms=[]
            )
            out_path = os.path.join(outdir, "prompt_package.json")
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(package, f, ensure_ascii=False, indent=2)
            QMessageBox.information(self, "완료", f"프롬프트 템플릿 내보내기 완료:\n{out_path}")
        except Exception as e:
            QMessageBox.critical(self, "오류", f"프롬프트 템플릿 생성 실패:\n{e}")
 
    # -------------------- 비교 모드 토글 --------------------
    def on_mode_toggled(self, checked: bool):
        self.compare_mode = "all" if checked else "lazy"
        self.mode_btn.setText("Mode: All" if checked else "Mode: Lazy")
        self.settings.set("compare_mode", self.compare_mode)
        self.statusBar().showMessage(f"비교 모드: {self.compare_mode}")
 
# --------------------------------------------
# 진입점
# --------------------------------------------
def main():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())
 
if __name__ == "__main__":
    main()
 
