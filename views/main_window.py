# -*- coding: utf-8 -*-
"""메인 윈도우(UI)"""

import os
import json
from typing import List, Tuple, Optional, Dict
from PySide6.QtCore import Qt, QSize, QPointF
from PySide6.QtGui import QAction, QKeySequence, QColor
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QSplitter, QVBoxLayout, QFileDialog, QLabel,
    QToolBar, QStatusBar, QLineEdit, QPushButton, QTreeWidget, QTreeWidgetItem,
    QMessageBox, QProgressBar, QStyle
)

from models.pdf_document import PDFDocument
from models.diff_item import DiffItem
from services.settings_manager import SettingsManager
from services.diff_engine import DiffEngine
from services.report_generator import ReportGenerator
from services.prompt_templates import PromptTemplates
from views.page_graphics_view import PageGraphicsView


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

        # UI 초기화
        self._init_ui()

    def _init_ui(self):
        # 좌/중/우 스플리터
        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.setCentralWidget(splitter)

        # 좌: 원본
        self.view_old = PageGraphicsView(role="old")
        self.view_old.set_zoom(self.default_zoom)
        self.view_old.fileDropped.connect(self.load_old_pdf)
        self.view_old.pageChanged.connect(self.sync_right_summary_to_page)
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
        self._init_toolbar()

        # 상태바
        status = QStatusBar()
        self.setStatusBar(status)
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedWidth(240)
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        status.addWidget(self.progress_bar)

    def _init_toolbar(self):
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

        # 동시 페이지 이동 토글 버튼
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
        if not self.sync_pages or self._sync_changing:
            return
        try:
            self._sync_changing = True
            if self.view_new.doc:
                self.view_new.goto_page(page_index)
        finally:
            self._sync_changing = False

    def on_view_new_page_changed(self, page_index: int):
        if not self.sync_pages or self._sync_changing:
            return
        try:
            self._sync_changing = True
            if self.view_old.doc:
                self.view_old.goto_page(page_index)
        finally:
            self._sync_changing = False

    def on_view_old_zoom_changed(self, z: float):
        if not self.sync_pages or self._sync_changing:
            return
        try:
            self._sync_changing = True
            if self.view_new.doc:
                self.view_new.set_zoom(z)
        finally:
            self._sync_changing = False

    def on_view_new_zoom_changed(self, z: float):
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

