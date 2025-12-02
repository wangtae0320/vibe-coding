# -*- coding: utf-8 -*-
"""프롬프트 템플릿 생성기 (LLM 연동용)"""

import json
from typing import List, Dict, Optional


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

