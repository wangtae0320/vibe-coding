# -*- coding: utf-8 -*-
"""사용자 설정 저장/로드 관리자"""

import os
import json


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

