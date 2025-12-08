# -*- coding: utf-8 -*-

from __future__ import annotations

import os
import sys
import shutil
from pathlib import Path
from typing import Optional, Iterable

from .constants import (
    APP_NAME,
    ORG_NAME,
    DEV_MODE,
    MIGRATE_BUILTIN_PRESETS,
)

def _project_root() -> Path:
    """
    プロジェクトのルート推定。
    - 通常: このファイルから2つ上: core/app/ → core/ → root/
    - frozen: 実行ファイルの隣を優先
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent

    return Path(__file__).resolve().parents[2]


def appdata_dir() -> Path:
    """
    OSごとのユーザーデータディレクトリ。
    """
    if os.name == "nt":
        root = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if not root:
            root = str(Path.home() / "AppData" / "Local")
        return Path(root) / ORG_NAME / APP_NAME

    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME

    xdg = os.environ.get("XDG_DATA_HOME")
    return (Path(xdg) if xdg else Path.home() / ".local" / "share") / APP_NAME


def storage_root() -> Path:
    """
    ストレージのルート。
    - DEV_MODE=False なら AppData
    - それ以外で frozen なら exe の隣
    - それ以外はプロジェクトルート
    """
    if not DEV_MODE:
        base = appdata_dir()
    elif getattr(sys, "frozen", False):
        base = Path(sys.executable).resolve().parent
    else:
        base = _project_root()

    base.mkdir(parents=True, exist_ok=True)
    return base


def ensure_dir(p: Path) -> Path:
    p.mkdir(parents=True, exist_ok=True)
    return p


def presets_dir() -> Path:
    """
    正式なプリセット保存先。
    初回に限り、旧配置（assets/presets 等）からJSONを移行することがある。
    """
    dst = ensure_dir(storage_root() / "presets")

    if MIGRATE_BUILTIN_PRESETS:
        try:
            candidates = [
                _project_root() / "assets" / "presets",
                _project_root() / "presets",  # 旧root直下に置いていた場合
            ]
            for src in candidates:
                if not src.exists():
                    continue
                _copy_jsons_if_missing(src, dst)
        except Exception:
            # 失敗は致命ではないため握りつぶす（ログは上位で）
            pass

    return dst


def _copy_jsons_if_missing(src_dir: Path, dst_dir: Path) -> None:
    for fn in src_dir.glob("*.json"):
        target = dst_dir / fn.name
        if target.exists():
            continue
        try:
            shutil.copy2(str(fn), str(target))
        except Exception:
            # 一部だけ失敗しても続行
            continue


def appdata_json_path() -> Path:
    return storage_root() / "appdata.json"
