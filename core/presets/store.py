# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import List, Tuple

from core.app.app_paths import presets_dir, ensure_dir
from .models import Preset


def _normalize_name(name_or_stem: str) -> str:
    """
    入力が "foo.json" でも "foo" でも stem を返す。
    """
    stem = name_or_stem
    if stem.lower().endswith(".json"):
        stem = stem[:-5]
    return stem


def _preset_path(stem: str) -> Path:
    return presets_dir() / f"{stem}.json"


def exists(name_or_stem: str) -> bool:
    stem = _normalize_name(name_or_stem)
    return _preset_path(stem).exists()


def list_names() -> List[str]:
    """
    プルダウン表示用のプリセット名一覧（拡張子抜き、名前順）。
    """
    d = presets_dir()
    names = [p.stem for p in d.glob("*.json")]
    names.sort()
    return names


def load(name_or_stem: str) -> Preset:
    stem = _normalize_name(name_or_stem)
    p = _preset_path(stem)

    if not p.exists():
        raise FileNotFoundError(f"Preset not found: {p}")

    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)

    preset = Preset.from_dict(data)
    # ファイル名を正として上書き
    preset.name = stem
    return preset


def _atomic_write_json(path: Path, payload: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")

    text = json.dumps(payload, ensure_ascii=False, indent=2)

    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)

    os.replace(tmp, path)


def save(preset: Preset, name_or_stem: str) -> None:
    """
    指定名で JSON 保存。上書き保存。
    - JSON 内の "name" は参考として name を入れる
    """
    stem = _normalize_name(name_or_stem)
    p = _preset_path(stem)
    ensure_dir(p.parent)

    payload = preset.to_dict()
    payload["name"] = stem

    _atomic_write_json(p, payload)


def _unique_copy_name(base_stem: str) -> str:
    """
    複製時の自動採番:
    - "<name>_copy"
    - "<name>_copy2", "<name>_copy3", ...
    """
    candidate = f"{base_stem}_copy"
    if not exists(candidate):
        return candidate

    i = 2
    while True:
        cand = f"{base_stem}_copy{i}"
        if not exists(cand):
            return cand
        i += 1


def duplicate(name_or_stem: str) -> str:
    """
    指定プリセットを同フォルダ内に複製し、新しい stem を返す。
    """
    stem = _normalize_name(name_or_stem)
    src = _preset_path(stem)

    if not src.exists():
        raise FileNotFoundError(f"Preset not found: {src}")

    new_stem = _unique_copy_name(stem)
    dst = _preset_path(new_stem)

    shutil.copy2(str(src), str(dst))

    # JSON 内の name をファイル名に合わせて更新（任意）
    try:
        preset = load(new_stem)
        save(preset, new_stem)
    except Exception:
        # 読み直し失敗しても致命ではないので無視
        pass

    return new_stem


def delete(name_or_stem: str) -> None:
    stem = _normalize_name(name_or_stem)
    p = _preset_path(stem)

    if not p.exists():
        raise FileNotFoundError(f"Preset not found: {p}")

    p.unlink()


def rename(old_name: str, new_name: str) -> str:
    """
    既存 preset を改名する。重複がある場合は自動採番して衝突回避。
    戻り値は最終的に採用された stem。
    """
    old_stem = _normalize_name(old_name)
    new_stem = _normalize_name(new_name)

    src = _preset_path(old_stem)
    if not src.exists():
        raise FileNotFoundError(f"Preset not found: {src}")

    # 同名が既にある場合は "_2", "_3", ... を付与
    final_stem = new_stem
    if exists(final_stem):
        i = 2
        while True:
            candidate = f"{new_stem}_{i}"
            if not exists(candidate):
                final_stem = candidate
                break
            i += 1

    dst = _preset_path(final_stem)
    src.rename(dst)

    # JSON 内の name をファイル名に合わせて更新（任意）
    try:
        preset = load(final_stem)
        save(preset, final_stem)
    except Exception:
        pass

    return final_stem
