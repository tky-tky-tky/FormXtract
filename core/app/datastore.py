# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Tuple

from .app_paths import appdata_json_path, ensure_dir, storage_root


class DataStore:
    """
    非同期アクセスの少ない小規模設定用の簡易KVストア。
    - 読み込みは起動時に1回
    - 保存は明示save()またはWindowClose時に1回
    - 上書きは原子的(os.replace)に行う
    """

    def __init__(self) -> None:
        self._path = appdata_json_path()
        ensure_dir(self._path.parent)
        self._data: Dict[str, Any] = {}
        self.load()

    # --------- Window State (window_state.py 用IF) ---------
    def get_window_state(self) -> Tuple[str, bool]:
        b64 = self._data.get("window_geometry_b64", "")
        maxed = bool(self._data.get("window_maximized", False))
        return b64, maxed

    def set_window_state(self, b64: str, maximized: bool) -> None:
        self._data["window_geometry_b64"] = b64
        self._data["window_maximized"] = bool(maximized)

    # --------- Generic KV ---------
    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value

    # --------- IO ---------
    def load(self) -> None:
        p = self._path
        if not p.exists():
            self._data = {}
            return

        try:
            with open(p, "r", encoding="utf-8") as f:
                self._data = json.load(f)
        except Exception:
            # 壊れている場合は初期化
            self._data = {}

    def save(self) -> None:
        p = self._path
        tmp = p.with_suffix(".tmp")

        try:
            payload = json.dumps(self._data, ensure_ascii=False, indent=2)
        except Exception:
            # シリアライズ失敗時は保存しない
            return

        try:
            with open(tmp, "w", encoding="utf-8", newline="\n") as f:
                f.write(payload)
            os.replace(tmp, p)
        except Exception:
            # 書き込み失敗時はtmpを放置しない
            try:
                if tmp.exists():
                    tmp.unlink()
            except Exception:
                pass
