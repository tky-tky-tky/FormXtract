# -*- coding: utf-8 -*-
from typing import List, Tuple
from PyQt5 import QtWidgets, QtGui, QtCore
from preset import Preset, ROI
from csvmap import LayoutPlan

class OverlayLabel(QtWidgets.QLabel):
    """画像上にROIを描いて番号透かしを重ねるプレビュー"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.base = QtGui.QPixmap()
        self.rois: List[ROI] = []
        self.temp_rect = None

    def set_image(self, qimage: QtGui.QImage):
        self.base = QtGui.QPixmap.fromImage(qimage)
        self.update()

    def set_rois(self, rois: List[ROI]):
        self.rois = rois
        self.update()

    def paintEvent(self, e):
        super().paintEvent(e)
        if self.base.isNull(): return
        p = QtGui.QPainter(self)
        scaled = self.base.scaled(self.size(), QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
        xoff = (self.width() - scaled.width()) // 2
        yoff = (self.height() - scaled.height()) // 2
        p.drawPixmap(xoff, yoff, scaled)

        if not self.rois: return
        # スケール計算
        sx = scaled.width() / self.base.width()
        sy = scaled.height() / self.base.height()
        p.setRenderHint(QtGui.QPainter.Antialiasing, True)
        font = QtGui.QFont(); font.setBold(True)
        p.setFont(font)

        for i, r in enumerate(self.rois, start=1):
            # {x,y,w,h} は基準画像座標。表示座標へ
            rx = int(xoff + r.x * sx); ry = int(yoff + r.y * sy)
            rw = int(r.w * sx);        rh = int(r.h * sy)
            # 枠（青）
            pen = QtGui.QPen(QtGui.QColor(50, 150, 255), 2)
            p.setPen(pen); p.setBrush(QtCore.Qt.NoBrush)
            p.drawRect(rx, ry, rw, rh)
            # 透かし番号（半透明）
            p.setPen(QtCore.Qt.NoPen)
            p.setBrush(QtGui.QColor(50, 150, 255, 80))
            p.drawRect(rx, ry, 28, 20)
            p.setPen(QtGui.QColor(255, 255, 255))
            p.drawText(rx+5, ry+16, str(i))
        p.end()

        if self.temp_rect:
            p = QtGui.QPainter(self)
            pen = QtGui.QPen(QtGui.QColor(255, 200, 0), 2)
            p.setPen(pen)
            p.setBrush(QtCore.Qt.NoBrush)
            p.drawRect(self.temp_rect)
            p.end()

class PresetEditorDialog(QtWidgets.QDialog):
    def __init__(self, base_image: QtGui.QImage, preset: Preset, parent=None):
        super().__init__(parent)
        self.setWindowTitle("プリセットエディタ")
        self.resize(1000, 700)

        self.base_image = base_image
        self.preset = preset.copy() if preset else Preset(name="new_preset")

        # 右：CSVレイアウト入力
        self.edit_name = QtWidgets.QLineEdit(self.preset.name)
        self.edit_layout = QtWidgets.QPlainTextEdit(self.preset.layout_text or "(1){1}{2}{3}")
        self.lbl_help = QtWidgets.QLabel("CSVレイアウト: 行ごとに1行出力。空欄は {} を使用。例: (1){1}{2}{3}")

        # 左：画像＋ROI追加
        self.view = OverlayLabel()
        if base_image:
            self.view.set_image(base_image)
            # サイズ差異があっても相対変換で保存できる運用に
            self.preset.image_w = base_image.width()
            self.preset.image_h = base_image.height()

        self.list_rois = QtWidgets.QListWidget()
        self.btn_add = QtWidgets.QPushButton("ROI追加")
        self.btn_del = QtWidgets.QPushButton("ROI削除")
        self.btn_up  = QtWidgets.QPushButton("↑")
        self.btn_dn  = QtWidgets.QPushButton("↓")

        # OK/Cancel
        self.btn_ok = QtWidgets.QPushButton("保存")
        self.btn_cancel = QtWidgets.QPushButton("キャンセル")

        # 配置
        left = QtWidgets.QVBoxLayout()
        left.addWidget(self.view, 4)
        hl = QtWidgets.QHBoxLayout()
        hl.addWidget(self.btn_add); hl.addWidget(self.btn_del); hl.addWidget(self.btn_up); hl.addWidget(self.btn_dn)
        left.addLayout(hl)
        left.addWidget(self.list_rois, 2)

        right = QtWidgets.QVBoxLayout()
        right.addWidget(QtWidgets.QLabel("プリセット名"))
        right.addWidget(self.edit_name)
        right.addWidget(self.lbl_help)
        right.addWidget(self.edit_layout, 4)
        right.addStretch(1)
        hr = QtWidgets.QHBoxLayout(); hr.addStretch(1); hr.addWidget(self.btn_ok); hr.addWidget(self.btn_cancel)
        right.addLayout(hr)

        body = QtWidgets.QHBoxLayout(self)
        body.addLayout(left, 3); body.addLayout(right, 2)

        # 初期表示
        self._sync_list_from_preset()

        # 事件
        self.btn_add.clicked.connect(self.on_add_roi)
        self.btn_del.clicked.connect(self.on_del_roi)
        self.btn_up.clicked.connect(lambda: self._move_selected(-1))
        self.btn_dn.clicked.connect(lambda: self._move_selected(+1))
        self.btn_ok.clicked.connect(self.accept)
        self.btn_cancel.clicked.connect(self.reject)
        self.list_rois.currentRowChanged.connect(lambda _: self.view.update())

        # 矩形追加のための簡易モード（クリックドラッグ）
        self.view.setMouseTracking(True)
        self.view.mousePressEvent = self._start_rect
        self.view.mouseMoveEvent = self._drag_rect
        self.view.mouseReleaseEvent = self._end_rect
        self._dragging = False
        self._rect_start = None
        self._last_rect = None

    def _img_to_view_scale(self):
        if not self.base_image or self.view.base.isNull(): return 1.0, 1.0, 0, 0
        scaled = self.view.base.scaled(self.view.size(), QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
        xoff = (self.view.width() - scaled.width()) // 2
        yoff = (self.view.height() - scaled.height()) // 2
        sx = scaled.width() / self.base_image.width()
        sy = scaled.height() / self.base_image.height()
        return sx, sy, xoff, yoff

    def _start_rect(self, e):
        self._dragging = True
        self._rect_start = e.pos()
        self._last_rect = QtCore.QRect(self._rect_start, self._rect_start)

    def _drag_rect(self, e):
        if not self._dragging:
            return
        self._last_rect = QtCore.QRect(self._rect_start, e.pos()).normalized()
        self.view.temp_rect = self._last_rect  # 一時枠をオーバーレイに描かせる
        self.view.update()

    def _end_rect(self, e):
        if not self._dragging:
            return
        self._dragging = False

        # ドラッグ中のガイド枠を消す
        self.view.temp_rect = None
        self.view.update()

        rect = self._last_rect
        if not rect or rect.isNull():
            return

        # === 表示座標 -> 画像座標 ===
        sx, sy, xoff, yoff = self._img_to_view_scale()
        # 左上・右下（表示座標）
        vx1, vy1 = rect.left(),  rect.top()
        vx2, vy2 = rect.right(), rect.bottom()

        # 画像座標（float→int 正規化）
        ix1 = int((vx1 - xoff) / sx)
        iy1 = int((vy1 - yoff) / sy)
        ix2 = int((vx2 - xoff) / sx)
        iy2 = int((vy2 - yoff) / sy)
        if ix1 > ix2: ix1, ix2 = ix2, ix1
        if iy1 > iy2: iy1, iy2 = iy2, iy1

        # 画像サイズ（presetに無ければ基準画像から）
        iw = self.preset.image_w or (self.base_image.width()  if self.base_image else 0)
        ih = self.preset.image_h or (self.base_image.height() if self.base_image else 0)
        if iw <= 0 or ih <= 0:
            # 画像情報が取れない場合は追加しない
            return

        # 画像境界にクリップ
        ix1 = max(0, min(ix1, iw - 1))
        iy1 = max(0, min(iy1, ih - 1))
        ix2 = max(0, min(ix2, iw))
        iy2 = max(0, min(iy2, ih))

        w = max(1, ix2 - ix1)
        h = max(1, iy2 - iy1)

        # 最小サイズしきい値（小さすぎる誤操作を無視）
        MIN_W, MIN_H = 5, 5
        if w < MIN_W or h < MIN_H:
            return

        # ROIを追加（向きは既定auto）
        self.preset.rois.append(ROI(x=ix1, y=iy1, w=w, h=h, orientation="auto"))

        # リスト＆オーバーレイ更新
        self._sync_list_from_preset()
        self.view.set_rois(self.preset.rois)
        self.view.update()


    def _sync_list_from_preset(self):
        self.list_rois.clear()
        for i, r in enumerate(self.preset.rois, start=1):
            self.list_rois.addItem(f"{i}: x={r.x}, y={r.y}, w={r.w}, h={r.h}")
        self.view.set_rois(self.preset.rois)

    def on_add_roi(self):
        # NO-OP: マウスドラッグで追加
        pass

    def on_del_roi(self):
        ix = self.list_rois.currentRow()
        if ix < 0: return
        del self.preset.rois[ix]
        self._sync_list_from_preset()

    def _move_selected(self, d: int):
        ix = self.list_rois.currentRow()
        if ix < 0: return
        j = ix + d
        if j < 0 or j >= len(self.preset.rois): return
        self.preset.rois[ix], self.preset.rois[j] = self.preset.rois[j], self.preset.rois[ix]
        self._sync_list_from_preset()
        self.list_rois.setCurrentRow(j)

    def result_preset(self) -> Preset:
        out = self.preset.copy()
        out.name = self.edit_name.text().strip() or "preset"
        out.layout_text = self.edit_layout.toPlainText()
        return out
