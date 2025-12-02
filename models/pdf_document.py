# -*- coding: utf-8 -*-
"""PDF 문서 래퍼 및 캐시"""

from collections import OrderedDict
from typing import List, Tuple
import fitz  # PyMuPDF
from PIL import Image
from PySide6.QtGui import QPixmap


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

