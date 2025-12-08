# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import Tuple
import numpy as np
import cv2
from PyQt5 import QtGui

from core.app.constants import (
    PREPROCESS_BILATERAL,
    PREPROCESS_BINARIZE,
    UPSCALE_FACTOR,
)


def qimage_to_bgr(qimage: QtGui.QImage) -> np.ndarray:
    """
    QImage(任意) -> ndarray(BGR, uint8)
    """
    img = qimage.convertToFormat(QtGui.QImage.Format_ARGB32)
    w = img.width()
    h = img.height()

    ptr = img.bits()
    ptr.setsize(h * w * 4)

    arr = np.frombuffer(ptr, np.uint8).reshape((h, w, 4))
    bgr = cv2.cvtColor(arr, cv2.COLOR_BGRA2BGR)
    return bgr


def bgr_to_rgb(bgr: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)


def to_gray(bgr: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)


def bilateral(gray: np.ndarray) -> np.ndarray:
    if not PREPROCESS_BILATERAL:
        return gray

    # 7, 50, 50 は無難な既定。必要なら constants で拡張
    return cv2.bilateralFilter(gray, 7, 50, 50)


def binarize(gray: np.ndarray) -> np.ndarray:
    if not PREPROCESS_BINARIZE:
        return gray

    # Otsu 二値化
    _, th = cv2.threshold(gray, 0, 255, cv2.THRESH_OTSU | cv2.THRESH_BINARY)
    return th


def upscale(img: np.ndarray) -> np.ndarray:
    if UPSCALE_FACTOR is None:
        return img

    if UPSCALE_FACTOR <= 1.0:
        return img

    h, w = img.shape[:2]
    nh = int(round(h * UPSCALE_FACTOR))
    nw = int(round(w * UPSCALE_FACTOR))

    if nh <= 0 or nw <= 0:
        return img

    return cv2.resize(img, (nw, nh), interpolation=cv2.INTER_CUBIC)


def rotate_if_needed(img: np.ndarray, orientation: str) -> np.ndarray:
    if orientation == "0" or orientation == "auto":
        return img

    if orientation == "90":
        return cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)

    if orientation == "180":
        return cv2.rotate(img, cv2.ROTATE_180)

    if orientation == "270":
        return cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)

    return img


def crop_to_roi(img: np.ndarray, x: int, y: int, w: int, h: int) -> np.ndarray:
    ih, iw = img.shape[:2]

    x1 = max(0, min(x, iw - 1))
    y1 = max(0, min(y, ih - 1))
    x2 = max(0, min(x + w, iw))
    y2 = max(0, min(y + h, ih))

    if x2 <= x1 or y2 <= y1:
        return img[0:0, 0:0].copy()

    return img[y1:y2, x1:x2].copy()
