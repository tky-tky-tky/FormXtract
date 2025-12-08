# -*- coding: utf-8 -*-

from __future__ import annotations

import os
from typing import Iterable, List

from core.app.constants import IMAGE_EXTS, ALLOW_DUPLICATE_DROPS


def is_image_ext(path: str) -> bool:
    ext = os.path.splitext(path)[1].lower()
    return ext in IMAGE_EXTS


def deduplicate_file_list(paths: Iterable[str], allow_duplicate: bool | None = None) -> List[str]:
    """
    D&D などで渡ってきたパス群から、画像だけ抽出。
    既定では重複を除外する（constants.ALLOW_DUPLICATE_DROPS 参照）。
    """
    if allow_duplicate is None:
        allow_duplicate = bool(ALLOW_DUPLICATE_DROPS)

    out: List[str] = []
    seen = set()

    for p in paths:
        if not p:
            continue

        if not is_image_ext(p):
            continue

        if allow_duplicate:
            out.append(p)
            continue

        if p in seen:
            continue

        seen.add(p)
        out.append(p)

    return out
