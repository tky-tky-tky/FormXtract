# -*- coding: utf-8 -*-

"""
App layer public API (slim)

- C: constants モジュールのエイリアス（値のみ定義）
- DataStore: appdata.json のKVストア
- bind_with_datastore: ウィンドウ位置/サイズの保存・復元
- app_data_dir, presets_dir: 各種保存先ディレクトリ
"""

from . import constants as C
from .datastore import DataStore
from .window_state import bind_with_datastore
from .app_paths import appdata_dir, presets_dir

__all__ = [
    "C",
    "DataStore",
    "bind_with_datastore",
    "appdata_dir",
    "presets_dir",
]
