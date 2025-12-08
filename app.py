# -*- coding: utf-8 -*-
import sys, os, mimetypes, csv
from typing import List
from PyQt5 import QtWidgets, QtGui, QtCore

APP_TITLE = "OCR Batch Tool"

# ========= Poppler の場所を必要なら指定（未導入なら None のままでOK） =========
# 例: r"C:\tools\poppler\Library\bin"
POPPLER_PATH = None

# ========= 依存モジュール =========
from preset import Preset, load_presets, save_preset
from editor import PresetEditorDialog

# pdf_utils が無い/未設定でも起動できるようにする
try:
    from pdf_utils import pdf_to_qimages
except Exception as e:
    print("[info] pdf_utils のインポートに失敗しました。PDFドロップは無視します:", e)
    def pdf_to_qimages(pdf_path: str, dpi=300, poppler_path=None):
        return []

from workers import OCRWorker, OCRTask
from ocr_core import ocr_single_image
from csvmap import LayoutPlan


# ========= ユーティリティ =========
def is_image_ext(path: str) -> bool:
    ext = os.path.splitext(path)[1].lower()
    return ext in [".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"]

def is_pdf_ext(path: str) -> bool:
    return os.path.splitext(path)[1].lower() == ".pdf"


# ========= モデル =========
class FileItem:
    def __init__(self, src_path, qimage: QtGui.QImage, page_index=None, total_pages=None):
        self.src_path = src_path
        self.qimage = qimage
        self.page_index = page_index
        self.total_pages = total_pages
        self.status = "ready"
        self.result_rows: List[List[str]] = []  # CSVへ書く行（レイアウト展開後）

    def display_name(self):
        base = os.path.basename(self.src_path)
        if self.page_index is not None and self.total_pages:
            return f"{base}  #{self.page_index+1}/{self.total_pages}"
        return base


# ========= D&D 対応リスト =========
class FileListWidget(QtWidgets.QListWidget):
    request_preview = QtCore.pyqtSignal(object)
    request_delete  = QtCore.pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSelectionMode(self.ExtendedSelection)
        # D&D 受け取り設定
        self.setAcceptDrops(True)
        self.viewport().setAcceptDrops(True)
        self.setDragEnabled(False)
        self.setDragDropMode(QtWidgets.QAbstractItemView.DropOnly)

        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._on_context_menu)
        self.itemSelectionChanged.connect(self._emit_preview)

    # リストに項目を追加
    def add_file_items(self, items: List[FileItem]):
        for it in items:
            lw = QtWidgets.QListWidgetItem(it.display_name())
            lw.setData(QtCore.Qt.UserRole, it)
            self.addItem(lw)

    # 右クリックメニュー
    def _on_context_menu(self, pos):
        m = QtWidgets.QMenu(self)
        act_del = m.addAction("選択項目を削除")
        act_clear = m.addAction("リストをクリア")
        act = m.exec_(self.mapToGlobal(pos))
        if act == act_del:
            self._delete_selected()
        elif act == act_clear:
            self._delete_all()

    def _delete_selected(self):
        rows = sorted([i.row() for i in self.selectedIndexes()], reverse=True)
        if rows:
            self.request_delete.emit(rows)

    def _delete_all(self):
        rows = list(range(self.count()))
        rows.reverse()
        if rows:
            self.request_delete.emit(rows)

    def _emit_preview(self):
        it = self.currentItem()
        if not it: return
        fobj = it.data(QtCore.Qt.UserRole)
        self.request_preview.emit(fobj)

    # --- D&D イベント ---
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
            e.ignore(); return

        paths = [u.toLocalFile() for u in e.mimeData().urls()]
        print("dropEvent paths:", paths)

        loaded = []
        for p in paths:
            if not p:
                continue
            try:
                if is_image_ext(p):
                    qimg = QtGui.QImage(p)
                    if not qimg.isNull():
                        loaded.append(FileItem(p, qimg))
                    else:
                        print(f"[warn] 画像読み込み失敗: {p}")
                elif is_pdf_ext(p):
                    pages = []
                    try:
                        pages = pdf_to_qimages(p, dpi=300, poppler_path=POPPLER_PATH)
                    except Exception as ex:
                        print(f"[error] PDF変換例外: {p} / {ex}")
                    if not pages:
                        print(f"[warn] PDF変換0枚: {p}（Poppler未設定の可能性）")
                    total = len(pages)
                    for i, qimg in enumerate(pages):
                        loaded.append(FileItem(p, qimg, page_index=i, total_pages=total))
                else:
                    print(f"[skip] 未対応拡張子: {p}")
            except Exception as ex:
                print(f"[error] drop処理中例外: {p} / {ex}")

        if loaded:
            self.add_file_items(loaded)
            e.acceptProposedAction()
        else:
            e.ignore()


# ========= メインウィンドウ =========
class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.resize(1280, 800)

        # 左：ファイルリスト
        self.listw = FileListWidget()
        self.listw.request_preview.connect(self.on_preview)
        self.listw.request_delete.connect(self.on_delete_rows)

        # 右：プリセット選択 + プレビュー
        self.combo_preset = QtWidgets.QComboBox()
        self.btn_preset_new = QtWidgets.QPushButton("プリセット作成")
        self.btn_preset_edit = QtWidgets.QPushButton("編集")
        self.btn_preset_dup  = QtWidgets.QPushButton("複製")
        self.btn_preset_del  = QtWidgets.QPushButton("削除")

        self.preview = QtWidgets.QLabel(alignment=QtCore.Qt.AlignCenter)
        self.preview.setMinimumSize(500, 360)
        self.preview.setFrameShape(QtWidgets.QFrame.StyledPanel)

        # 実行ボタン
        self.btn_ocr_one  = QtWidgets.QPushButton("1項目OCR")
        self.btn_ocr_all  = QtWidgets.QPushButton("一括OCR")
        self.btn_del_item = QtWidgets.QPushButton("項目を削除")
        self.btn_clear    = QtWidgets.QPushButton("リストをクリア")

        # CSV保存先（追記のみ）
        self.edit_csv = QtWidgets.QLineEdit()
        self.btn_csv  = QtWidgets.QPushButton("保存先...")

        # 進捗 & ログ
        self.progress = QtWidgets.QProgressBar()
        self.log = QtWidgets.QTextEdit(); self.log.setReadOnly(True)

        # 右の上段（プリセット）
        right_top = QtWidgets.QHBoxLayout()
        right_top.addWidget(QtWidgets.QLabel("プリセット"))
        right_top.addWidget(self.combo_preset, 1)
        right_top.addWidget(self.btn_preset_new)
        right_top.addWidget(self.btn_preset_edit)
        right_top.addWidget(self.btn_preset_dup)
        right_top.addWidget(self.btn_preset_del)

        # 右のコントロール
        right_ctrl = QtWidgets.QGridLayout()
        right_ctrl.addWidget(self.btn_ocr_one, 0, 0)
        right_ctrl.addWidget(self.btn_ocr_all, 0, 1)
        right_ctrl.addWidget(self.btn_del_item, 1, 0)
        right_ctrl.addWidget(self.btn_clear,    1, 1)
        right_ctrl.addWidget(QtWidgets.QLabel("CSV保存先（追記）"), 2, 0)
        hcsv = QtWidgets.QHBoxLayout()
        hcsv.addWidget(self.edit_csv, 1)
        hcsv.addWidget(self.btn_csv)
        right_ctrl.addLayout(hcsv, 2, 1)
        right_ctrl.addWidget(self.progress, 3, 0, 1, 2)

        # 右ペインまとめ
        right = QtWidgets.QVBoxLayout()
        right.addLayout(right_top)
        right.addWidget(self.preview, 4)
        right.addLayout(right_ctrl)
        right.addWidget(self.log, 2)

        # スプリッタで左右配置
        sp = QtWidgets.QSplitter()
        wl = QtWidgets.QWidget(); l = QtWidgets.QVBoxLayout(wl); l.addWidget(self.listw)
        wr = QtWidgets.QWidget(); r = QtWidgets.QVBoxLayout(wr); r.addLayout(right)
        sp.addWidget(wl); sp.addWidget(wr)
        sp.setStretchFactor(0, 1); sp.setStretchFactor(1, 2)

        central = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(central); lay.addWidget(sp)
        self.setCentralWidget(central)

        # シグナル接続
        self.btn_csv.clicked.connect(self.on_browse_csv)
        self.btn_del_item.clicked.connect(self.listw._delete_selected)
        self.btn_clear.clicked.connect(self.listw._delete_all)
        self.btn_preset_new.clicked.connect(self.on_preset_new)
        self.btn_preset_edit.clicked.connect(self.on_preset_edit)
        self.btn_preset_dup.clicked.connect(self.on_preset_dup)
        self.btn_preset_del.clicked.connect(self.on_preset_del)
        self.btn_ocr_one.clicked.connect(self.on_ocr_one)
        self.btn_ocr_all.clicked.connect(self.on_ocr_all)

        # プリセット読込
        self.presets: List[Preset] = load_presets()
        self.refresh_preset_combo()

        self.worker: OCRWorker = None

    # ---------- UI handlers ----------
    def on_preview(self, fi: FileItem):
        pix = QtGui.QPixmap.fromImage(fi.qimage)
        self.preview.setPixmap(pix.scaled(self.preview.size(), QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))

    def on_browse_csv(self):
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "CSV保存先", "", "CSV (*.csv)")
        if path:
            self.edit_csv.setText(path)

    def on_delete_rows(self, rows):
        for r in rows:
            it = self.listw.takeItem(r)
            del it

    def refresh_preset_combo(self, select_name: str = None):
        self.combo_preset.clear()
        for p in self.presets:
            self.combo_preset.addItem(p.name)
        if select_name:
            ix = self.combo_preset.findText(select_name)
            if ix >= 0: self.combo_preset.setCurrentIndex(ix)

    def current_preset(self) -> Preset:
        ix = self.combo_preset.currentIndex()
        if ix < 0 or ix >= len(self.presets): return None
        return self.presets[ix]

    # ---------- プリセット ----------
    def on_preset_new(self):
        it = self.listw.currentItem()
        if not it:
            QtWidgets.QMessageBox.information(self, APP_TITLE, "エディタを開くには画像を一つ選択してください。")
            return
        fi: FileItem = it.data(QtCore.Qt.UserRole)
        dlg = PresetEditorDialog(base_image=fi.qimage, preset=None, parent=self)
        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            p = dlg.result_preset()
            self.presets.append(p)
            save_preset(p)
            self.refresh_preset_combo(p.name)
            self._log(f"プリセット作成: {p.name}")

    def on_preset_edit(self):
        p = self.current_preset()
        if not p:
            QtWidgets.QMessageBox.information(self, APP_TITLE, "プリセットを選択してください。")
            return
        it = self.listw.currentItem()
        base_img = it.data(QtCore.Qt.UserRole).qimage if it else None
        dlg = PresetEditorDialog(base_image=base_img, preset=p, parent=self)
        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            updated = dlg.result_preset()
            for i, pp in enumerate(self.presets):
                if pp.name == updated.name:
                    self.presets[i] = updated
            save_preset(updated)
            self._log(f"プリセット更新: {updated.name}")

    def on_preset_dup(self):
        p = self.current_preset()
        if not p:
            QtWidgets.QMessageBox.information(self, APP_TITLE, "プリセットを選択してください。")
            return
        dup = p.copy_with_new_name(p.name + "_copy")
        self.presets.append(dup)
        save_preset(dup)
        self.refresh_preset_combo(dup.name)
        self._log(f"プリセット複製: {dup.name}")

    def on_preset_del(self):
        p = self.current_preset()
        if not p: return
        if QtWidgets.QMessageBox.question(self, APP_TITLE, f"プリセット「{p.name}」を削除しますか？") != QtWidgets.QMessageBox.Yes:
            return
        self.presets = [x for x in self.presets if x.name != p.name]
        self.refresh_preset_combo()
        p.delete_file_if_exists()
        self._log(f"プリセット削除: {p.name}")

    # ---------- OCR ----------
    def on_ocr_one(self):
        it = self.listw.currentItem()
        if not it:
            self._log("項目が選択されていません")
            return
        p = self.current_preset()
        if not p:
            self._log("プリセットが選択されていません")
            return
        csv_path = self.edit_csv.text().strip()
        if not csv_path:
            self._log("CSV保存先を指定してください")
            return
        fi: FileItem = it.data(QtCore.Qt.UserRole)
        self._run_worker([fi], p, csv_path)

    def on_ocr_all(self):
        p = self.current_preset()
        if not p:
            self._log("プリセットが選択されていません")
            return
        csv_path = self.edit_csv.text().strip()
        if not csv_path:
            self._log("CSV保存先を指定してください")
            return
        items = []
        for i in range(self.listw.count()):
            fi: FileItem = self.listw.item(i).data(QtCore.Qt.UserRole)
            items.append(fi)
        if not items:
            self._log("リストが空です")
            return
        self._run_worker(items, p, csv_path)

    def _run_worker(self, items: List[FileItem], preset: Preset, csv_path: str):
        if hasattr(self, "worker") and self.worker and self.worker.isRunning():
            self._log("処理中です")
            return
        self.progress.setValue(0)
        tasks = [OCRTask(item=i, preset=preset) for i in items]
        self.worker = OCRWorker(tasks)
        self.worker.sig_progress.connect(self.progress.setValue)
        self.worker.sig_log.connect(self._log)
        self.worker.sig_done.connect(lambda: self._on_worker_done(csv_path))
        self.worker.start()
        self._log(f"OCR開始: {len(tasks)}件")

    def _on_worker_done(self, csv_path: str):
        # 一括追記（ヘッダー無し）
        rows = []
        for i in range(self.listw.count()):
            fi: FileItem = self.listw.item(i).data(QtCore.Qt.UserRole)
            for r in getattr(fi, "result_rows", []):
                rows.append(r)
        if rows:
            try:
                os.makedirs(os.path.dirname(csv_path) or ".", exist_ok=True)
                with open(csv_path, "a", newline="", encoding="utf-8-sig") as f:
                    w = csv.writer(f)
                    for r in rows:
                        w.writerow(r)
                self._log(f"CSVへ追記: {len(rows)}行 -> {csv_path}")
            except Exception as e:
                self._log(f"[error] CSV書き込み失敗: {e}")
        else:
            self._log("書き込む行がありません")
        self._log("OCR完了")

    def _log(self, msg: str):
        self.log.append(msg)


# ========= エントリポイント =========
def main():
    app = QtWidgets.QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
