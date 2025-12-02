# -*- coding: utf-8 -*-
"""PDF 비교 엔진"""

import time
import threading
import traceback
import difflib
from typing import List, Tuple, Optional, Dict
from PySide6.QtCore import QObject, Signal
from PIL import Image
import numpy as np

from models.pdf_document import PDFDocument
from models.diff_item import DiffItem


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

