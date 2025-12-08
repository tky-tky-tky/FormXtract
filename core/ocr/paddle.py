# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import List
import numpy as np

from paddleocr import PaddleOCR

from core.app.constants import (
    PADDLE_LANG,
    PADDLE_USE_ANGLE_CLS,
)


class PaddleEngine:
    """
    シンプルな PaddleOCR ラッパ。
    1インスタンスをシングルトンで使い回す前提。
    """

    def __init__(self) -> None:
        self._ocr = PaddleOCR(
            lang=PADDLE_LANG,
            use_angle_cls=bool(PADDLE_USE_ANGLE_CLS),
        )

    def read_text(self, img_rgb_uint8: np.ndarray) -> str:
        """
        img_rgb_uint8: RGB, uint8, HxWx3
        """
        res = self._ocr.ocr(img_rgb_uint8, cls=True)

        text = ""
        if res and res[0]:
            parts = [seg[1][0] for seg in res[0]]
            text = "".join(parts)

        return text.strip()
