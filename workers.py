# -*- coding: utf-8 -*-
from PyQt5 import QtCore
from typing import List
from ocr_core import ocr_single_image
from preset import Preset

class OCRTask:
    def __init__(self, item, preset: Preset):
        self.item = item
        self.preset = preset

class OCRWorker(QtCore.QThread):
    sig_progress = QtCore.pyqtSignal(int)
    sig_log = QtCore.pyqtSignal(str)
    sig_done = QtCore.pyqtSignal()

    def __init__(self, tasks: List[OCRTask]):
        super().__init__()
        self.tasks = tasks

    def run(self):
        total = len(self.tasks)
        for i, t in enumerate(self.tasks, start=1):
            try:
                rows = ocr_single_image(t.item.qimage, t.preset)
                t.item.result_rows = rows
                self.sig_log.emit(f"OCR OK: {t.item.display_name()} -> {len(rows)}行")
            except Exception as e:
                t.item.result_rows = []
                self.sig_log.emit(f"OCR 失敗: {t.item.display_name()} / {e}")
            self.sig_progress.emit(int(i * 100 / total))
        self.sig_done.emit()
