# -*- coding: utf-8 -*-
import numpy as np, cv2
from typing import List
from paddleocr import PaddleOCR
from preset import Preset, ROI
from csvmap import LayoutPlan

_ocr = None
def _get_ocr():
    global _ocr
    if _ocr is None:
        _ocr = PaddleOCR(lang='japan', use_angle_cls=True)
    return _ocr

def crop(img: np.ndarray, r: ROI) -> np.ndarray:
    h, w = img.shape[:2]
    x = max(0, min(r.x, w-1))
    y = max(0, min(r.y, h-1))
    x2 = max(0, min(r.x + r.w, w))
    y2 = max(0, min(r.y + r.h, h))
    return img[y:y2, x:x2].copy()

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

def read_text(img: np.ndarray) -> str:
    ocr = _get_ocr()
    res = ocr.ocr(img, cls=True)
    text = ""
    if res and res[0]:
        text = "".join([seg[1][0] for seg in res[0]])
    return text.strip()

def to_cv(qimage) -> np.ndarray:
    # QImage -> ndarray(BGR)
    qimage = qimage.convertToFormat(4)  # QImage::Format_ARGB32
    w = qimage.width(); h = qimage.height()
    ptr = qimage.bits(); ptr.setsize(h * w * 4)
    arr = np.frombuffer(ptr, np.uint8).reshape((h, w, 4))
    bgr = cv2.cvtColor(arr, cv2.COLOR_BGRA2BGR)
    return bgr

def ocr_single_image(qimage, preset: Preset) -> List[List[str]]:
    """
    1画像から、プリセットのROI順にテキストを読んで fields を作る。
    その後、レイアウトプランに従って複数行のCSV行へ展開して返す。
    """
    img = to_cv(qimage)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # 軽めの前処理（必要に応じて強化）
    gray = cv2.bilateralFilter(gray, 7, 50, 50)
    base = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)

    # TODO: アンカーでテンプレ座標へ整列したい場合はここで warpPerspective を挿入

    fields = []
    for r in preset.rois:
        c = crop(base, r)
        c = rotate_if_needed(c, r.orientation)
        # 二値化や拡大など、必要ならここで
        text = read_text(c)
        fields.append(text)

    lp = LayoutPlan(preset.layout_text or "")
    rows = lp.materialize(fields)
    return rows
