# -*- coding: utf-8 -*-

from __future__ import annotations

from PyQt5 import QtGui
import numpy as np
import cv2


def qimage_to_bgr(qimage: QtGui.QImage) -> np.ndarray:
    """
    QImage(any) -> ndarray(BGR, uint8)
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
