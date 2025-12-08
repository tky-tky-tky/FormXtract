# -*- coding: utf-8 -*-
"""
PDF → QImage 変換ユーティリティ（Poppler不要・同階層完結）
PyMuPDF(fitz)で各ページを画像化し、QImageとして返す
"""
from typing import List
from PyQt5 import QtGui
import fitz  # PyMuPDF
from PIL import Image
import io, os

def pdf_to_qimages(pdf_path: str, dpi=300, poppler_path=None) -> List[QtGui.QImage]:
    """
    指定したPDFをページ単位でQImageリストに変換
    dpi: 解像度（300が標準）
    poppler_path: 無視（互換のため残しているだけ）
    """
    if not os.path.exists(pdf_path):
        print(f"[warn] PDF not found: {pdf_path}")
        return []

    zoom = dpi / 72.0  # PDFのデフォルト解像度は72dpi
    images: List[QtGui.QImage] = []

    try:
        with fitz.open(pdf_path) as doc:
            for page in doc:
                mat = fitz.Matrix(zoom, zoom)
                pix = page.get_pixmap(matrix=mat, alpha=True)
                img_bytes = pix.tobytes("png")

                # PillowでRGBA化
                pil_img = Image.open(io.BytesIO(img_bytes)).convert("RGBA")
                w, h = pil_img.size
                data = pil_img.tobytes("raw", "RGBA")

                qimg = QtGui.QImage(data, w, h, QtGui.QImage.Format_RGBA8888)
                images.append(qimg.copy())
        print(f"[info] PDF converted: {pdf_path} ({len(images)} pages)")
    except Exception as e:
        print(f"[error] PyMuPDF conversion failed: {e}")

    return images
