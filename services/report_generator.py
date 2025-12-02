# -*- coding: utf-8 -*-
"""리포트 생성기 (Excel/CSV)"""

import os
import pandas as pd
from typing import List

from models.pdf_document import PDFDocument
from models.diff_item import DiffItem


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

