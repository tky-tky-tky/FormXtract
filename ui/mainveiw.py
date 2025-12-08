# path: ui/mainveiw.py
# -*- coding: utf-8 -*-

from __future__ import annotations

import os
from typing import List, Optional

from PyQt5 import QtWidgets, QtGui, QtCore

from core.app import C, DataStore, bind_with_datastore, presets_dir
from core.image.io_utils import deduplicate_file_list, is_image_ext
from core.presets import (
    list_names as preset_list_names,
    load as preset_load,
    save as preset_save,
    duplicate as preset_duplicate,
    delete as preset_delete,
    rename as preset_rename,
    Preset,
)
from core.ocr import OCRTask, OCRWorker

from ui.preset import PresetEditorDialog


class FileListWidget(QtWidgets.QListWidget):
    request_preview = QtCore.pyqtSignal(object)
    request_delete_rows = QtCore.pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setSelectionMode(self.ExtendedSelection)
        self.setAcceptDrops(True)
        self.viewport().setAcceptDrops(True)
        self.setDragEnabled(False)
        self.setDragDropMode(QtWidgets.QAbstractItemView.DropOnly)

        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._on_ctx)
        self.itemSelectionChanged.connect(self._emit_preview)

    def add_qimage(self, qimg: QtGui.QImage, name: str, src_path: Optional[str] = None):
        item = QtWidgets.QListWidgetItem(name)
        payload = {"qimage": qimg, "name": name, "src_path": src_path or ""}
        item.setData(QtCore.Qt.UserRole, payload)
        self.addItem(item)

    def current_payload(self):
        it = self.currentItem()
        if not it:
            return None
        return it.data(QtCore.Qt.UserRole)

    def selected_rows_desc(self) -> List[int]:
        return sorted([i.row() for i in self.selectedIndexes()], reverse=True)

    def _on_ctx(self, pos):
        m = QtWidgets.QMenu(self)
        act_del = m.addAction("選択項目を削除")
        act_clear = m.addAction("リストをクリア")
        act = m.exec_(self.mapToGlobal(pos))

        if act == act_del:
            rows = self.selected_rows_desc()
            if rows:
                self.request_delete_rows.emit(rows)

        elif act == act_clear:
            rows = list(range(self.count()))
            rows.reverse()
            if rows:
                self.request_delete_rows.emit(rows)

    def _emit_preview(self):
        it = self.currentItem()
        if not it:
            return
        payload = it.data(QtCore.Qt.UserRole)
        self.request_preview.emit(payload)

    # ---- D&D ----
    def dragEnterEvent(self, e: QtGui.QDragEnterEvent):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
        else:
            e.ignore()

    def dragMoveEvent(self, e: QtGui.QDragMoveEvent):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
        else:
            e.ignore()

    def dropEvent(self, e: QtGui.QDropEvent):
        if not e.mimeData().hasUrls():
            e.ignore()
            return

        paths = [u.toLocalFile() for u in e.mimeData().urls()]
        paths = deduplicate_file_list(paths)

        if not paths:
            e.ignore()
            return

        loaded = 0
        for p in paths:
            try:
                if not is_image_ext(p):
                    continue

                qimg = QtGui.QImage(p)
                if qimg.isNull():
                    continue

                name = os.path.basename(p)
                self.add_qimage(qimg, name=name, src_path=p)
                loaded += 1
            except Exception:
                pass

        if loaded > 0:
            e.acceptProposedAction()
        else:
            e.ignore()

    # ---- Deleteキー対応 ----
    def keyPressEvent(self, e: QtGui.QKeyEvent):
        if e.key() in (QtCore.Qt.Key_Delete, QtCore.Qt.Key_Backspace):
            rows = self.selected_rows_desc()
            if rows:
                self.request_delete_rows.emit(rows)
                return
        super().keyPressEvent(e)


class MainView(QtWidgets.QMainWindow):
    def __init__(self, datastore: DataStore, parent=None):
        super().__init__(parent)

        self.ds = datastore
        self.setWindowTitle(f"{C.APP_NAME} {C.APP_VERSION}")

        # 左：ファイルリスト
        self.listw = FileListWidget()
        self.listw.request_preview.connect(self.on_preview)
        self.listw.request_delete_rows.connect(self.on_delete_rows)

        # 右：プリセット＋プレビュー
        self.combo_preset = QtWidgets.QComboBox()
        self.btn_new = QtWidgets.QPushButton("作成")
        self.btn_edit = QtWidgets.QPushButton("編集")
        self.btn_dup = QtWidgets.QPushButton("複製")
        self.btn_del = QtWidgets.QPushButton("削除")

        self.preview = QtWidgets.QLabel(alignment=QtCore.Qt.AlignCenter)
        self.preview.setMinimumSize(500, 360)
        self.preview.setFrameShape(QtWidgets.QFrame.StyledPanel)

        # ボタン（指定の配置）
        # 左リスト上：削除／クリア（横に広げて均等割り）
        self.btn_del_item = QtWidgets.QPushButton("削除")
        self.btn_clear    = QtWidgets.QPushButton("クリア")
        for b in (self.btn_del_item, self.btn_clear):
            b.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)

        # プレビュー下：一括OCR／一項目OCR（横に広げて中央で均等割り）
        self.btn_ocr_all  = QtWidgets.QPushButton("一括OCR")
        self.btn_ocr_one  = QtWidgets.QPushButton("一項目OCR")
        for b in (self.btn_ocr_all, self.btn_ocr_one):
            b.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)

        # CSV UI
        self.lbl_csv    = QtWidgets.QLabel("保存先：")
        self.edit_csv   = QtWidgets.QLineEdit(self.ds.get("last_csv_path", ""))
        self.btn_csv    = QtWidgets.QPushButton("参照")
        self.chk_append = QtWidgets.QCheckBox("指定したCSVに追記する")
        self.chk_append.setChecked(bool(self.ds.get("csv_append", C.CSV_APPEND_DEFAULT)))

        # 進捗・ログ
        self.progress = QtWidgets.QProgressBar()
        self.log = QtWidgets.QTextEdit()
        self.log.setReadOnly(True)

        # プリセット上段
        top = QtWidgets.QHBoxLayout()
        top.addWidget(QtWidgets.QLabel("プリセット"))
        top.addWidget(self.combo_preset, 1)
        top.addWidget(self.btn_new)
        top.addWidget(self.btn_edit)
        top.addWidget(self.btn_dup)
        top.addWidget(self.btn_del)

        # プレビュー下：OCRボタン2つ（均等割り）
        hocr = QtWidgets.QHBoxLayout()
        hocr.addWidget(self.btn_ocr_all, 1)
        hocr.addWidget(self.btn_ocr_one, 1)

        # CSV列（参照の右隣に「指定したCSVに追記する」）
        hcsv = QtWidgets.QHBoxLayout()
        hcsv.addWidget(self.lbl_csv)
        hcsv.addWidget(self.edit_csv, 1)
        hcsv.addWidget(self.btn_csv)
        hcsv.addSpacing(8)
        hcsv.addWidget(self.chk_append)

        # 右ペインまとめ
        right = QtWidgets.QVBoxLayout()
        right.addLayout(top)
        right.addWidget(self.preview, 4)
        right.addLayout(hocr)
        right.addLayout(hcsv)
        right.addWidget(self.progress)
        right.addWidget(self.log, 2)

        # 左右に分割
        sp = QtWidgets.QSplitter()
        wl = QtWidgets.QWidget()
        _l = QtWidgets.QVBoxLayout(wl)

        # 左上に「削除／クリア」を左右に配置（均等割り）
        hleft = QtWidgets.QHBoxLayout()
        hleft.addWidget(self.btn_del_item, 1)
        hleft.addWidget(self.btn_clear, 1)

        _l.addLayout(hleft)
        _l.addWidget(self.listw)

        wr = QtWidgets.QWidget()
        _r = QtWidgets.QVBoxLayout(wr)
        _r.addLayout(right)

        sp.addWidget(wl)
        sp.addWidget(wr)
        sp.setStretchFactor(0, 1)
        sp.setStretchFactor(1, 2)

        central = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(central)
        lay.addWidget(sp)
        self.setCentralWidget(central)

        # signals
        self.btn_csv.clicked.connect(self.on_browse_csv)
        self.btn_del_item.clicked.connect(self._ui_delete_selected)
        self.btn_clear.clicked.connect(self._ui_delete_all)
        self.btn_new.clicked.connect(self.on_preset_new)
        self.btn_edit.clicked.connect(self.on_preset_edit)
        self.btn_dup.clicked.connect(self.on_preset_dup)
        self.btn_del.clicked.connect(self.on_preset_del)
        self.btn_ocr_one.clicked.connect(self.on_ocr_one)
        self.btn_ocr_all.clicked.connect(self.on_ocr_all)

        # ファイル監視（プリセットフォルダの変更を即反映）
        self._watcher = QtCore.QFileSystemWatcher(self)
        self._watcher.addPath(str(presets_dir()))
        self._watcher.directoryChanged.connect(lambda _: self.refresh_preset_combo())

        # 初期ロード
        self.refresh_preset_combo(self.ds.get("last_preset_name", ""))

        # window state
        bind_with_datastore(self, self.ds, default_size=(1280, 800))

        self.worker: Optional[OCRWorker] = None

    # ========== UI handlers ==========
    def on_preview(self, payload: dict):
        qimage: QtGui.QImage = payload.get("qimage")
        if not isinstance(qimage, QtGui.QImage) or qimage.isNull():
            self.preview.clear()
            return

        pix = QtGui.QPixmap.fromImage(qimage)
        self.preview.setPixmap(
            pix.scaled(self.preview.size(), QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
        )

    def resizeEvent(self, e: QtGui.QResizeEvent):
        super().resizeEvent(e)
        self.on_preview(self.listw.current_payload() or {})

    def on_browse_csv(self):
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "CSV保存先", "", "CSV (*.csv)")
        if path:
            self.edit_csv.setText(path)
            self.ds.set("last_csv_path", path)
            self.ds.save()

    def on_delete_rows(self, rows_desc: List[int]):
        for r in rows_desc:
            it = self.listw.takeItem(r)
            del it

    def _ui_delete_selected(self):
        rows = self.listw.selected_rows_desc()
        if rows:
            self.on_delete_rows(rows)

    def _ui_delete_all(self):
        rows = list(range(self.listw.count()))
        rows.reverse()
        if rows:
            self.on_delete_rows(rows)

    def refresh_preset_combo(self, select_name: str = ""):
        names = preset_list_names()
        self.combo_preset.blockSignals(True)
        self.combo_preset.clear()
        for n in names:
            self.combo_preset.addItem(n)
        self.combo_preset.blockSignals(False)

        if select_name:
            ix = self.combo_preset.findText(select_name)
            if ix >= 0:
                self.combo_preset.setCurrentIndex(ix)

    def _current_preset_name(self) -> str:
        ix = self.combo_preset.currentIndex()
        if ix < 0:
            return ""
        return self.combo_preset.itemText(ix)

    # ----- Preset ops -----
    def on_preset_new(self):
        payload = self.listw.current_payload()

        if not payload or not isinstance(payload.get("qimage"), QtGui.QImage) or payload["qimage"].isNull():
            QtWidgets.QMessageBox.information(self, C.APP_NAME, "エディタを開くには画像を一つ選択してください。")
            return

        base_img = payload["qimage"]

        try:
            dlg = PresetEditorDialog(base_image=base_img, preset=None, parent=self, datastore=self.ds)
            if dlg.exec_() != QtWidgets.QDialog.Accepted:
                return

            result_preset, result_name = dlg.result()

            if not result_name:
                QtWidgets.QMessageBox.information(self, C.APP_NAME, "プリセット名を入力してください。")
                return

            self.log.append(f"プリセット作成: {result_name}")
            preset_save(result_preset, result_name)
            self.refresh_preset_combo(result_name)
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, C.APP_NAME, f"[error] プリセット作成に失敗: {e}")

    def on_preset_edit(self):
        name = self._current_preset_name()
        if not name:
            QtWidgets.QMessageBox.information(self, C.APP_NAME, "プリセットを選択してください。")
            return

        try:
            p = preset_load(name)
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, C.APP_NAME, f"プリセット読込に失敗: {e}")
            return

        payload = self.listw.current_payload()
        base_img = payload.get("qimage") if payload else None

        try:
            dlg = PresetEditorDialog(base_image=base_img, preset=p, parent=self, datastore=self.ds)
            if dlg.exec_() != QtWidgets.QDialog.Accepted:
                return

            result_preset, result_name = dlg.result()

            if result_name != name:
                final_name = preset_rename(name, result_name)
                preset_save(result_preset, final_name)
                self.refresh_preset_combo(final_name)
                self.log.append(f"プリセット改名: {name} → {final_name}")
                self.ds.set("last_preset_name", final_name)
                self.ds.save()
                return

            preset_save(result_preset, name)
            self.refresh_preset_combo(name)
            self.log.append(f"プリセット更新: {name}")
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, C.APP_NAME, f"[error] プリセット更新に失敗: {e}")

    def on_preset_dup(self):
        name = self._current_preset_name()
        if not name:
            QtWidgets.QMessageBox.information(self, C.APP_NAME, "プリセットを選択してください。")
            return

        try:
            new_name = preset_duplicate(name)
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, C.APP_NAME, f"複製に失敗: {e}")
            return

        self.refresh_preset_combo(new_name)
        self.log.append(f"プリセット複製: {name} → {new_name}")

    def on_preset_del(self):
        name = self._current_preset_name()
        if not name:
            return

        if QtWidgets.QMessageBox.question(self, C.APP_NAME, f"プリセット「{name}」を削除しますか？") != QtWidgets.QMessageBox.Yes:
            return

        try:
            preset_delete(name)
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, C.APP_NAME, f"削除に失敗: {e}")
            return

        self.refresh_preset_combo("")
        self.log.append(f"プリセット削除: {name}")

    # ----- OCR -----
    def _collect_selected_or_current(self) -> List[dict]:
        sels = self.listw.selectedItems()
        if sels:
            items = sels
        else:
            it = self.listw.currentItem()
            items = [it] if it else []

        out = []
        for it in items:
            payload = it.data(QtCore.Qt.UserRole)
            if payload:
                out.append(payload)
        return out

    def _load_current_preset(self) -> Optional[Preset]:
        name = self._current_preset_name()
        if not name:
            self.log.append("プリセットが選択されていません")
            return None

        try:
            p = preset_load(name)
            return p
        except Exception as e:
            self.log.append(f"[error] プリセット読込失敗: {e}")
            return None

    def on_ocr_one(self):
        payloads = self._collect_selected_or_current()
        if not payloads:
            self.log.append("項目が選択されていません")
            return

        p = self._load_current_preset()
        if not p:
            return

        csv_path = self.edit_csv.text().strip()
        if not csv_path:
            self.log.append("CSV保存先を指定してください")
            return

        tasks = [OCRTask(qimage=payloads[0]["qimage"], preset=p, display_name=payloads[0]["name"])]
        self._run_worker(tasks, csv_path)

    def on_ocr_all(self):
        p = self._load_current_preset()
        if not p:
            return

        csv_path = self.edit_csv.text().strip()
        if not csv_path:
            self.log.append("CSV保存先を指定してください")
            return

        tasks = []
        for i in range(self.listw.count()):
            it = self.listw.item(i)
            pl = it.data(QtCore.Qt.UserRole)
            if pl:
                tasks.append(OCRTask(qimage=pl["qimage"], preset=p, display_name=pl["name"]))

        if not tasks:
            self.log.append("リストが空です")
            return

        self._run_worker(tasks, csv_path)

    def _run_worker(self, tasks: List[OCRTask], csv_path: str):
        if hasattr(self, "worker") and self.worker and self.worker.isRunning():
            self.log.append("処理中です")
            return

        self.progress.setValue(0)
        self.worker = OCRWorker(tasks)
        self.worker.sig_progress.connect(self.progress.setValue)
        self.worker.sig_log.connect(self.log.append)
        self.worker.sig_done.connect(lambda processed: self._on_worker_done(processed, csv_path))
        self.worker.start()
        self.log.append(f"OCR開始: {len(tasks)}件")

    def _on_worker_done(self, processed: List[dict], csv_path: str):
        rows = []
        for it in processed:
            for r in it.get("rows", []):
                rows.append(r)

        if rows:
            try:
                appended = bool(self.chk_append.isChecked())
                from core.csvio.writer import write_rows
                n = write_rows(csv_path, rows, append=appended)
                self.log.append(f"CSVへ{'追記' if appended else '上書き'}: {n}行 -> {csv_path}")
            except Exception as e:
                self.log.append(f"[error] CSV書込み失敗: {e}")
        else:
            self.log.append("書き込む行がありません")

        self.ds.set("csv_append", bool(self.chk_append.isChecked()))
        self.ds.set("last_csv_path", self.edit_csv.text().strip())
        self.ds.set("last_preset_name", self._current_preset_name())
        self.ds.save()

        self.log.append("OCR完了")
