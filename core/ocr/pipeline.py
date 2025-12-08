# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import List

import numpy as np

from core.presets.models import Preset, ROI
from core.csvio.layout import LayoutPlan
from core.ocr.preprocess import (
    qimage_to_bgr,
    bgr_to_rgb,
    to_gray,
    bilateral,
    binarize,
    upscale,
    rotate_if_needed,
    crop_to_roi,
)
from core.ocr.engines import get_engine

# ポストプロセス（安全系と列別ルール）
# 実装は後続の core/postprocess.py 側に用意
from core.postprocess import normalize_global, apply_rules_to_row


def _prepare_roi_image(bgr: np.ndarray, roi: ROI) -> np.ndarray:
    """
    BGR → ROI抽出 → 回転 → 前処理 → RGB
    """
    patch = crop_to_roi(bgr, roi.x, roi.y, roi.w, roi.h)
    patch = rotate_if_needed(patch, roi.orientation)

    gray = to_gray(patch)
    gray = bilateral(gray)
    gray = binarize(gray)

    proc = gray
    proc = upscale(proc)

    if proc.ndim == 2:
        proc = np.stack([proc, proc, proc], axis=2)

    rgb = bgr_to_rgb(proc)
    return rgb


def ocr_single_image(qimage, preset: Preset) -> List[List[str]]:
    """
    1画像からプリセット順でフィールドを読み、レイアウトに従って行へ展開して返す。
    - ROIごとの値は normalize_global() を通す
    - 展開後の行は apply_rules_to_row() で列別ルールを適用
    """
    engine = get_engine()

    bgr = qimage_to_bgr(qimage)

    fields: List[str] = []
    for roi in preset.rois:
        rgb = _prepare_roi_image(bgr, roi)
        text = engine.read_text(rgb)
        text = normalize_global(text)
        fields.append(text)

    lp = LayoutPlan(preset.layout_text or "")
    rows = lp.materialize(fields)

    # 列ごとの追加ルール適用（constants.PP_BY_COL を参照）
    out_rows = []
    for row in rows:
        out_rows.append(apply_rules_to_row(row))

    return out_rows
