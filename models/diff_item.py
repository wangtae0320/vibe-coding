# -*- coding: utf-8 -*-
"""변경항목 데이터 구조"""

from dataclasses import dataclass
from typing import Optional, Tuple


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

