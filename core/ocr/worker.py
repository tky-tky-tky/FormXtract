# path: core/ocr/worker.py
# -*- coding: utf-8 -*-

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict, Any

from PyQt5 import QtCore

from core.ocr.pipeline import ocr_single_image
from core.app.constants import ALLOW_INTERRUPT


@dataclass
class OCRTask:
    """
    OCR の単位処理。
    - qimage: 入力画像 (QImage)
    - preset: 使用プリセット
    - display_name: ログ/進捗表示用（ファイル名や "page #1/3" など）
    """
    qimage: Any
    preset: Any
    display_name: str = ""


class OCRWorker(QtCore.QThread):
    """
    OCR をバックグラウンドで順次実行するワーカー。
    進捗は 0..100 の整数で通知。
    完了時は processed の一覧（dictの配列）を sig_done で返す。
    """

    sig_progress = QtCore.pyqtSignal(int)
    sig_log = QtCore.pyqtSignal(str)
    sig_done = QtCore.pyqtSignal(list)

    def __init__(self, tasks: List[OCRTask]):
        super().__init__()
        self._tasks = tasks or []

    def run(self) -> None:
        total = len(self._tasks)

        if total <= 0:
            self.sig_progress.emit(100)
            self.sig_done.emit([])
            return

        processed: List[Dict[str, Any]] = []

        for i, t in enumerate(self._tasks, start=1):
            if ALLOW_INTERRUPT and self.isInterruptionRequested():
                self.sig_log.emit("処理が中断されました")
                break

            try:
                rows = ocr_single_image(t.qimage, t.preset)
                processed.append({
                    "name": t.display_name or f"item#{i}",
                    "rows": rows,
                    "ok": True,
                    "error": "",
                })
                self.sig_log.emit(f"OCR OK: {t.display_name or f'item#{i}'} -> {len(rows)} 行")
            except Exception as e:
                processed.append({
                    "name": t.display_name or f"item#{i}",
                    "rows": [],
                    "ok": False,
                    "error": str(e),
                })
                self.sig_log.emit(f"OCR 失敗: {t.display_name or f'item#{i}'} / {e}")

            pct = int(i * 100 / total)
            self.sig_progress.emit(pct)

        self.sig_done.emit(processed)
