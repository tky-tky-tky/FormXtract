# -*- coding: utf-8 -*-

"""
OCR package:
- preprocess: image preprocessing helpers
- engines: concrete OCR engines (paddle, ...)
- pipeline: ROI → OCR → postprocess → layout materialization
- worker: background OCR worker (QThread)
"""

from .pipeline import ocr_single_image
from .worker import OCRTask, OCRWorker

__all__ = ["ocr_single_image", "OCRTask", "OCRWorker"]