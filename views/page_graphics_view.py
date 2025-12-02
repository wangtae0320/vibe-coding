# -*- coding: utf-8 -*-
"""그래픽 뷰 (페이지 표시 + 오버레이)"""

from typing import List, Tuple, Optional
from PySide6.QtCore import Qt, QSize, QRectF, QPointF, Signal
from PySide6.QtGui import QPainter, QColor, QBrush, QPen, QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsRectItem, QGraphicsPixmapItem

from models.pdf_document import PDFDocument


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

