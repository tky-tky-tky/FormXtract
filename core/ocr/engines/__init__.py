# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import Protocol
from core.app.constants import OCR_IMPL


class OCRReadable(Protocol):
    def read_text(self, img_rgb_uint8) -> str:
        """
        img_rgb_uint8: numpy ndarray, uint8, RGB
        returns recognized string (single line, stripped)
        """
        ...


_engine_singleton = None


def get_engine():
    """
    Select OCR engine by constants.OCR_IMPL
    """
    global _engine_singleton

    if _engine_singleton is not None:
        return _engine_singleton

    if OCR_IMPL == "paddle":
        from .paddle import PaddleEngine
        _engine_singleton = PaddleEngine()
        return _engine_singleton

    # 既定: paddle
    from .paddle import PaddleEngine
    _engine_singleton = PaddleEngine()
    return _engine_singleton
