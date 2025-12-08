# path: ui/preset.py
# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import Callable, List, Optional, Tuple

from PyQt5 import QtWidgets, QtGui, QtCore

try:
    from PyQt5.QtWidgets import QOpenGLWidget  # Optional
    HAS_OPENGL = True
except Exception:
    HAS_OPENGL = False

from core.presets import Preset, ROI
from core.app import C, DataStore  # ★ DataStore 追加

ROI_MIN_W = C.ROI_MIN_W
ROI_MIN_H = C.ROI_MIN_H
ZOOM_STEP_RATIO = C.ZOOM_STEP_RATIO
UNDO_STACK_LIMIT = C.UNDO_STACK_LIMIT

USE_OPENGL_VIEWPORT = getattr(C, "USE_OPENGL_VIEWPORT", False)
VIEWPORT_UPDATE_MODE = getattr(
    C,
    "VIEWPORT_UPDATE_MODE",
    int(QtWidgets.QGraphicsView.FullViewportUpdate),
)

# ★ スプリッター状態の保存キー（appdata.json に保存）
_SPLIT_H_KEY = "preset_editor_splitter_h_b64"
_SPLIT_V_KEY = "preset_editor_splitter_v_b64"


# ------------------------------
# ROI Item
# ------------------------------
class ROIItem(QtWidgets.QGraphicsRectItem):
    """
    ドラッグ移動と四隅ハンドルによるリサイズができるROI矩形。
    - ペン幅はズームしても一定（cosmetic pen）
    - 左上に大きめの番号ラベル
    - 角ハンドルはズームしても視認性を維持するサイズ
    """

    HANDLE_BASE = 24
    current_scale: float = 1.0

    def __init__(self, rect: QtCore.QRectF, index: int, on_change: Optional[Callable] = None):
        super().__init__(rect)

        self.setFlags(
            QtWidgets.QGraphicsItem.ItemIsSelectable
            | QtWidgets.QGraphicsItem.ItemIsMovable
            | QtWidgets.QGraphicsItem.ItemSendsGeometryChanges
        )
        self.setAcceptHoverEvents(True)
        self.setZValue(10)

        self._index = index
        self._on_change = on_change
        self._dragging_handle: Optional[int] = None

        pen = QtGui.QPen(QtGui.QColor(50, 150, 255), 3)
        pen.setCosmetic(True)
        self.setPen(pen)
        self.setBrush(QtGui.QBrush(QtCore.Qt.NoBrush))

        self.setCacheMode(QtWidgets.QGraphicsItem.DeviceCoordinateCache)

    @staticmethod
    def handle_px() -> int:
        s = ROIItem.current_scale if ROIItem.current_scale > 0 else 1.0
        px = int(round(ROIItem.HANDLE_BASE / s))
        return max(12, min(32, px))

    def _handle_points(self) -> List[QtCore.QPointF]:
        r = self.rect()
        return [
            QtCore.QPointF(r.left(),  r.top()),
            QtCore.QPointF(r.right(), r.top()),
            QtCore.QPointF(r.left(),  r.bottom()),
            QtCore.QPointF(r.right(), r.bottom()),
        ]

    def _hit_handle(self, pos: QtCore.QPointF) -> Optional[int]:
        hs = self.handle_px()
        for i, hp in enumerate(self._handle_points()):
            rect = QtCore.QRectF(hp.x() - hs / 2, hp.y() - hs / 2, hs, hs)
            if rect.contains(pos):
                return i
        return None

    def paint(self, painter: QtGui.QPainter, option, widget=None):
        super().paint(painter, option, widget)

        r = self.rect()

        # 左上ラベル（ズームに潰れないサイズ）
        painter.save()
        s = max(ROIItem.current_scale, 1e-6)

        label_h = max(28, int(round(32 / s)))
        label_w_target = int(max(64, min(r.width() * 0.35, 220)))
        label_w = max(44, int(round(label_w_target)))

        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(QtGui.QColor(50, 150, 255, 95))
        painter.drawRect(QtCore.QRectF(r.left(), r.top(), label_w, label_h))

        painter.setPen(QtGui.QColor(255, 255, 255))
        font = painter.font()
        font.setBold(True)
        font.setPixelSize(max(14, int(round(label_h * 0.7))))
        painter.setFont(font)
        painter.drawText(
            QtCore.QRectF(r.left(), r.top(), label_w, label_h),
            QtCore.Qt.AlignVCenter | QtCore.Qt.AlignHCenter,
            str(self._index),
        )
        painter.restore()

        # 角ハンドル（ズームに潰れない）
        hp = self.handle_px()
        painter.setBrush(QtGui.QColor(255, 200, 0))
        painter.setPen(QtGui.QPen(QtGui.QColor(255, 200, 0)))
        for p in self._handle_points():
            painter.drawRect(QtCore.QRectF(p.x() - hp / 2, p.y() - hp / 2, hp, hp))

    def hoverMoveEvent(self, e: QtWidgets.QGraphicsSceneHoverEvent):
        which = self._hit_handle(e.pos())
        if which is None:
            self.setCursor(QtCore.Qt.SizeAllCursor if self.isSelected() else QtCore.Qt.ArrowCursor)
        else:
            if which in (0, 3):
                self.setCursor(QtCore.Qt.SizeFDiagCursor)
            else:
                self.setCursor(QtCore.Qt.SizeBDiagCursor)
        super().hoverMoveEvent(e)

    def mousePressEvent(self, e: QtWidgets.QGraphicsSceneMouseEvent):
        self._dragging_handle = self._hit_handle(e.pos())
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e: QtWidgets.QGraphicsSceneMouseEvent):
        if self._dragging_handle is None:
            super().mouseMoveEvent(e)
            return

        r = QtCore.QRectF(self.rect())
        p = e.pos()

        if self._dragging_handle == 0:
            r.setTopLeft(p)
        elif self._dragging_handle == 1:
            r.setTopRight(p)
        elif self._dragging_handle == 2:
            r.setBottomLeft(p)
        elif self._dragging_handle == 3:
            r.setBottomRight(p)

        if r.width() < ROI_MIN_W:
            r.setWidth(ROI_MIN_W)

        if r.height() < ROI_MIN_H:
            r.setHeight(ROI_MIN_H)

        self.setRect(r)
        self.update()

    def mouseReleaseEvent(self, e: QtWidgets.QGraphicsSceneMouseEvent):
        self._dragging_handle = None
        super().mouseReleaseEvent(e)
        if callable(self._on_change):
            self._on_change()

    def itemChange(self, change, value):
        if change == QtWidgets.QGraphicsItem.ItemPositionHasChanged:
            if callable(self._on_change):
                self._on_change()
        return super().itemChange(change, value)

    def set_index(self, i: int):
        self._index = i
        self.update()


# ------------------------------
# Graphics View
# ------------------------------
class OverlayView(QtWidgets.QGraphicsView):
    zoomChanged = QtCore.pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setRenderHints(
            QtGui.QPainter.Antialiasing
            | QtGui.QPainter.HighQualityAntialiasing
            | QtGui.QPainter.SmoothPixmapTransform
            | QtGui.QPainter.TextAntialiasing
        )

        try:
            mode = QtWidgets.QGraphicsView.ViewportUpdateMode(VIEWPORT_UPDATE_MODE)
            self.setViewportUpdateMode(mode)
        except Exception:
            self.setViewportUpdateMode(QtWidgets.QGraphicsView.FullViewportUpdate)

        if USE_OPENGL_VIEWPORT and HAS_OPENGL:
            try:
                self.setViewport(QOpenGLWidget())
            except Exception:
                pass

        self.setDragMode(QtWidgets.QGraphicsView.RubberBandDrag)
        self.setMouseTracking(True)

        self._scale = 1.0
        self._panning = False
        self._pan_start = QtCore.QPoint()

    def fit_to_item(self, item: QtWidgets.QGraphicsItem):
        if item is None:
            return

        self.resetTransform()

        br = item.sceneBoundingRect()
        if br.isNull():
            return

        view_rect = self.viewport().rect()
        if view_rect.isNull():
            return

        margin = 12
        target = QtCore.QRectF(
            br.x() - margin,
            br.y() - margin,
            br.width() + margin * 2,
            br.height() + margin * 2,
        )
        self.fitInView(target, QtCore.Qt.KeepAspectRatio)

        self._scale = self.transform().m11()
        self.zoomChanged.emit(self._scale)

    def wheelEvent(self, e: QtGui.QWheelEvent):
        anchor_before = self.mapToScene(e.pos())

        if e.angleDelta().y() > 0:
            f = ZOOM_STEP_RATIO
        else:
            f = 1.0 / ZOOM_STEP_RATIO

        self.scale(f, f)
        self._scale *= f
        self.zoomChanged.emit(self._scale)

        anchor_after = self.mapToScene(e.pos())
        delta = anchor_after - anchor_before
        self.translate(delta.x(), delta.y())

    def mousePressEvent(self, e: QtGui.QMouseEvent):
        if e.button() == QtCore.Qt.MiddleButton:
            self._panning = True
            self.setCursor(QtCore.Qt.ClosedHandCursor)
            self._pan_start = e.pos()
            e.accept()
            return

        super().mousePressEvent(e)

    def mouseMoveEvent(self, e: QtGui.QMouseEvent):
        if self._panning:
            delta = e.pos() - self._pan_start
            self._pan_start = e.pos()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            e.accept()
            return

        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e: QtGui.QMouseEvent):
        if e.button() == QtCore.Qt.MiddleButton and self._panning:
            self._panning = False
            self.setCursor(QtCore.Qt.ArrowCursor)
            e.accept()
            return

        super().mouseReleaseEvent(e)

    def keyPressEvent(self, e: QtGui.QKeyEvent):
        if e.key() == QtCore.Qt.Key_Space:
            self.setDragMode(QtWidgets.QGraphicsView.ScrollHandDrag)
            e.accept()
            return

        super().keyPressEvent(e)

    def keyReleaseEvent(self, e: QtGui.QKeyEvent):
        if e.key() == QtCore.Qt.Key_Space:
            self.setDragMode(QtWidgets.QGraphicsView.RubberBandDrag)
            e.accept()
            return

        super().keyReleaseEvent(e)


# ------------------------------
# Preset Editor Dialog
# ------------------------------
class PresetEditorDialog(QtWidgets.QDialog):
    """
    プリセットエディタ（画像上でROIの追加・移動・リサイズ、CSVレイアウト編集）
    - 既存ROI上の操作を優先（その間は新規作成しない）
    - 新規作成ドラッグ中はガイド枠を表示
    - Ctrl+Z で確実に Undo（ショートカットで保証）
    - 左（上：ROIビュー、下：ボタン+リスト）/ 右（設定） を QSplitter で分割
    """

    def __init__(self, base_image: QtGui.QImage, preset: Optional[Preset], parent=None, datastore: Optional[DataStore] = None):
        super().__init__(parent)

        # 「？」非表示、最大化/最小化ボタンを付与
        flags = self.windowFlags()
        flags = flags & ~QtCore.Qt.WindowContextHelpButtonHint
        flags = flags | QtCore.Qt.WindowMinMaxButtonsHint | QtCore.Qt.WindowSystemMenuHint
        self.setWindowFlags(flags)

        self.setWindowTitle("プリセットエディタ")
        self.resize(1100, 740)

        # ★ DataStore（未指定なら既定の appdata.json を使用）
        self.ds: DataStore = datastore if isinstance(datastore, DataStore) else DataStore()

        self._base_image = base_image
        self._preset = preset if preset else Preset(name="new_preset")

        self._snapshots: List[Preset] = []
        self._undo_limit = max(1, int(UNDO_STACK_LIMIT))

        # 右側：名前とレイアウト
        self.edit_name = QtWidgets.QLineEdit(self._preset.name or "preset")
        self.edit_layout = QtWidgets.QPlainTextEdit(self._preset.layout_text or "{1}{2}{3}")
        self.lbl_help = QtWidgets.QLabel("CSVレイアウト: 行ごとに {n} プレースホルダ。空欄は {} を使用")

        # 左側：画像＋ROI
        self.view = OverlayView()
        self.scene = QtWidgets.QGraphicsScene(self.view)
        self.view.setScene(self.scene)
        self.view.zoomChanged.connect(self._on_view_scale_changed)
        self._pix: Optional[QtWidgets.QGraphicsPixmapItem] = None

        # ROI一覧とボタン（下段）
        self.list_rois = QtWidgets.QListWidget()
        self.list_rois.setSelectionMode(self.list_rois.ExtendedSelection)
        self.list_rois.setDragDropMode(self.list_rois.InternalMove)

        self.btn_dup = QtWidgets.QPushButton("複製")
        self.btn_del = QtWidgets.QPushButton("削除")

        # ---- レイアウト：左上(ビュー) / 左下(ボタン+リスト) を縦Splitter ----
        left_top = QtWidgets.QWidget()
        left_top_layout = QtWidgets.QVBoxLayout(left_top)
        left_top_layout.setContentsMargins(0, 0, 0, 0)
        left_top_layout.addWidget(self.view)

        left_bottom = QtWidgets.QWidget()
        left_bottom_layout = QtWidgets.QVBoxLayout(left_bottom)
        left_bottom_layout.setContentsMargins(0, 0, 0, 0)
        hbtn = QtWidgets.QHBoxLayout()
        hbtn.addStretch(1)
        hbtn.addWidget(self.btn_dup)
        hbtn.addWidget(self.btn_del)
        left_bottom_layout.addLayout(hbtn)
        left_bottom_layout.addWidget(self.list_rois, 1)

        self.left_splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)  # ★ 識別名保持
        self.left_splitter.addWidget(left_top)
        self.left_splitter.addWidget(left_bottom)
        self.left_splitter.setStretchFactor(0, 7)
        self.left_splitter.setStretchFactor(1, 3)

        # ---- 右ペイン（設定） ----
        right_widget = QtWidgets.QWidget()
        right = QtWidgets.QVBoxLayout(right_widget)
        right.addWidget(QtWidgets.QLabel("プリセット名"))
        right.addWidget(self.edit_name)
        right.addWidget(self.lbl_help)
        right.addWidget(self.edit_layout, 4)
        right.addStretch(1)
        hr = QtWidgets.QHBoxLayout()
        self.btn_ok = QtWidgets.QPushButton("保存")
        self.btn_cancel = QtWidgets.QPushButton("キャンセル")
        hr.addStretch(1)
        hr.addWidget(self.btn_ok)
        hr.addWidget(self.btn_cancel)
        right.addLayout(hr)

        # ---- 左右Splitter ----
        self.main_splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal, self)  # ★ 識別名保持
        self.main_splitter.addWidget(self.left_splitter)
        self.main_splitter.addWidget(right_widget)
        self.main_splitter.setStretchFactor(0, 7)
        self.main_splitter.setStretchFactor(1, 3)

        # ダイアログ本体レイアウト
        body = QtWidgets.QVBoxLayout(self)
        body.setContentsMargins(6, 6, 6, 6)
        body.addWidget(self.main_splitter)

        # 初期構築
        try:
            self._setup_base_pixmap()
            if self._base_image and not self._base_image.isNull():
                self._preset.image_w = self._base_image.width()
                self._preset.image_h = self._base_image.height()
            self._sync_rois_to_scene()
            self._sync_list_from_preset()
            if self._pix is not None:
                self.view.fit_to_item(self._pix)
        except Exception:
            pass

        # ★ スプリッター状態の復元
        self._restore_splitter_state()

        # signals
        self.btn_dup.clicked.connect(self.on_dup_selected)
        self.btn_del.clicked.connect(self.on_del_selected)
        self.btn_ok.clicked.connect(self.accept)
        self.btn_cancel.clicked.connect(self.reject)

        self.list_rois.currentRowChanged.connect(self._on_list_current_changed)
        self.list_rois.model().rowsMoved.connect(self._on_list_rows_moved)  # ★ ドラッグで順序変更を反映
        self.scene.selectionChanged.connect(self._on_scene_selection_changed)

        # マウスでROI追加（ガイド表示）
        self.view.viewport().installEventFilter(self)
        self._dragging = False
        self._drag_start = QtCore.QPoint()
        self._drag_rect_item: Optional[QtWidgets.QGraphicsRectItem] = None

        # Undo / Delete をショートカットで保証
        QtWidgets.QShortcut(QtGui.QKeySequence.Undo,   self, activated=self._snapshot_undo)
        QtWidgets.QShortcut(QtGui.QKeySequence.Delete, self, activated=self.on_del_selected)

        # 起動直後のスナップショット
        self._snapshot_push()

    # ---------- Scene / ROI ----------

    def _setup_base_pixmap(self):
        self.scene.clear()

        if self._base_image and not self._base_image.isNull():
            pix = QtGui.QPixmap.fromImage(self._base_image)
        else:
            pix = QtGui.QPixmap(960, 540)
            pix.fill(QtGui.QColor(30, 30, 30))

        self._pix = self.scene.addPixmap(pix)
        self._pix.setZValue(0)
        self._pix.setTransformationMode(QtCore.Qt.SmoothTransformation)

        self.scene.setSceneRect(self._pix.boundingRect())

    def _on_view_scale_changed(self, scale: float):
        ROIItem.current_scale = max(1e-6, float(scale))
        for it in self._roi_items():
            it.update()

    def _roi_items(self) -> List[ROIItem]:
        out = [it for it in self.scene.items() if isinstance(it, ROIItem)]
        out.sort(key=lambda x: x._index)
        return out

    def _sync_rois_to_scene(self):
        for i, r in enumerate(self._preset.rois, start=1):
            it = ROIItem(
                QtCore.QRectF(r.x, r.y, r.w, r.h),
                i,
                on_change=self._on_item_changed
            )
            self.scene.addItem(it)

    def _sync_list_from_preset(self):
        # ★ シーンの ROIItem と対応付けた QListWidgetItem を作成（並べ替えに必要）
        self.list_rois.clear()
        for it in self._roi_items():
            r = it.rect()
            item = QtWidgets.QListWidgetItem(
                f"{it._index}: x={int(r.left())}, y={int(r.top())}, w={int(r.width())}, h={int(r.height())}"
            )
            item.setData(QtCore.Qt.UserRole, it)  # ← ROIItem への参照を保持
            self.list_rois.addItem(item)

    def _renumber_and_update(self):
        idx = 1
        for it in self._roi_items():
            it.set_index(idx)
            idx += 1

        self._update_preset_from_scene()
        self._sync_list_from_preset()

    def _update_preset_from_scene(self):
        rois: List[ROI] = []
        items = sorted(self._roi_items(), key=lambda a: a._index)
        for it in items:
            r = it.rect()
            rois.append(
                ROI(
                    x=int(round(r.left())),
                    y=int(round(r.top())),
                    w=int(round(r.width())),
                    h=int(round(r.height())),
                    orientation="auto",
                )
            )
        self._preset.rois = rois
        self._snapshot_push_lazy()

    def _on_item_changed(self):
        self._update_preset_from_scene()
        self._snapshot_push()

    # ---------- イベント（新規作成は“何もない所”のみ） ----------

    def eventFilter(self, obj, ev):
        if obj is self.view.viewport():
            if ev.type() == QtCore.QEvent.MouseButtonPress:
                if ev.button() == QtCore.Qt.LeftButton:
                    if ev.modifiers() & (QtCore.Qt.ShiftModifier | QtCore.Qt.ControlModifier):
                        return False

                    scene_pos = self.view.mapToScene(ev.pos())
                    hit = self.scene.itemAt(scene_pos, self.view.transform())

                    if isinstance(hit, ROIItem):
                        return False

                    self._dragging = True
                    self._drag_start = ev.pos()
                    pen = QtGui.QPen(QtGui.QColor(255, 200, 0), 2)
                    pen.setCosmetic(True)
                    self._drag_rect_item = self.scene.addRect(
                        QtCore.QRectF(
                            self.view.mapToScene(self._drag_start),
                            self.view.mapToScene(self._drag_start)
                        ),
                        pen
                    )
                    self._drag_rect_item.setBrush(QtGui.QBrush(QtCore.Qt.NoBrush))
                    self._drag_rect_item.setZValue(1000)
                    return True

            if ev.type() == QtCore.QEvent.MouseMove:
                if self._dragging and self._drag_rect_item is not None:
                    p1 = self.view.mapToScene(self._drag_start)
                    p2 = self.view.mapToScene(ev.pos())
                    rect = QtCore.QRectF(p1, p2).normalized()
                    self._drag_rect_item.setRect(rect)
                    return True

            if ev.type() == QtCore.QEvent.MouseButtonRelease:
                if self._dragging and self._drag_rect_item is not None:
                    rect = self._drag_rect_item.rect()
                    self.scene.removeItem(self._drag_rect_item)
                    self._drag_rect_item = None
                    self._dragging = False

                    if rect.width() >= ROI_MIN_W and rect.height() >= ROI_MIN_H:
                        it = ROIItem(rect, len(self._roi_items()) + 1, on_change=self._on_item_changed)
                        self.scene.addItem(it)
                        self._renumber_and_update()
                        self._snapshot_push()
                    return True

        return super().eventFilter(obj, ev)

    # ---------- リスト連携 / 操作 ----------

    def _scene_item_by_index(self, index_one_based: int) -> Optional[ROIItem]:
        for it in self._roi_items():
            if it._index == index_one_based:
                return it
        return None

    def _on_list_current_changed(self, row: int):
        if row < 0:
            return

        # リスト -> シーン選択へ反映
        for it in self._roi_items():
            it.setSelected(False)

        idxs = sorted({i.row() for i in self.list_rois.selectedIndexes()})
        if not idxs and row >= 0:
            idxs = [row]

        for r in idxs:
            it = self._scene_item_by_index(r + 1)
            if it is not None:
                it.setSelected(True)

    def _on_scene_selection_changed(self):
        # シーン -> リスト選択へ反映
        selected = {it._index - 1 for it in self._roi_items() if it.isSelected()}
        self.list_rois.blockSignals(True)
        self.list_rois.clearSelection()
        for i in selected:
            item = self.list_rois.item(i)
            if item is not None:
                item.setSelected(True)
        self.list_rois.blockSignals(False)

    def _on_list_rows_moved(self, *args):
        """
        ★ 重要：リストのドラッグ順を実順に反映
        QListWidgetItem に埋め込んだ ROIItem 参照を取り出し、
        0..N-1 の行順に index を 1..N に振り直す。
        """
        for row in range(self.list_rois.count()):
            item = self.list_rois.item(row)
            it = item.data(QtCore.Qt.UserRole)
            if isinstance(it, ROIItem):
                it.set_index(row + 1)

        self._update_preset_from_scene()
        self._sync_list_from_preset()

    def on_dup_selected(self):
        # 1) リスト選択優先
        rows = sorted({i.row() for i in self.list_rois.selectedIndexes()})
        if rows:
            for r in rows:
                src = self._scene_item_by_index(r + 1)
                if src is None:
                    continue
                rect = src.rect()
                new_rect = QtCore.QRectF(rect.left() + 10, rect.top() + 10, rect.width(), rect.height())
                self.scene.addItem(ROIItem(new_rect, len(self._roi_items()) + 1, on_change=self._on_item_changed))

            self._renumber_and_update()
            self._snapshot_push()
            return

        # 2) シーン選択でもOK
        sel = [it for it in self.scene.selectedItems() if isinstance(it, ROIItem)]
        if not sel:
            return

        for it in sel:
            r = it.rect()
            new_rect = QtCore.QRectF(r.left() + 10, r.top() + 10, r.width(), r.height())
            self.scene.addItem(ROIItem(new_rect, len(self._roi_items()) + 1, on_change=self._on_item_changed))

        self._renumber_and_update()
        self._snapshot_push()

    def on_del_selected(self):
        # 1) リスト選択優先
        rows = sorted({i.row() for i in self.list_rois.selectedIndexes()}, reverse=True)
        if rows:
            for r in rows:
                it = self._scene_item_by_index(r + 1)
                if it is not None:
                    self.scene.removeItem(it)
            self._renumber_and_update()
            self._snapshot_push()
            return

        # 2) シーン選択でもOK
        sel = [it for it in self.scene.selectedItems() if isinstance(it, ROIItem)]
        if not sel:
            return

        for it in sel:
            self.scene.removeItem(it)

        self._renumber_and_update()
        self._snapshot_push()

    # ---------- Undo ----------

    def _snapshot_clone(self) -> Preset:
        return Preset(
            name=self.edit_name.text().strip(),
            image_w=self._preset.image_w,
            image_h=self._preset.image_h,
            rois=[ROI(x=r.x, y=r.y, w=r.w, h=r.h, orientation=r.orientation) for r in self._preset.rois],
            layout_text=self.edit_layout.toPlainText(),
        )

    def _snapshot_push(self):
        snap = self._snapshot_clone()
        self._snapshots.append(snap)
        if len(self._snapshots) > self._undo_limit:
            self._snapshots.pop(0)

    def _snapshot_push_lazy(self):
        pass

    def _snapshot_undo(self):
        if len(self._snapshots) <= 1:
            return

        self._snapshots.pop()
        snap = self._snapshots[-1]

        self._preset = Preset(
            name=snap.name,
            image_w=snap.image_w,
            image_h=snap.image_h,
            rois=[ROI(x=r.x, y=r.y, w=r.w, h=r.h, orientation=r.orientation) for r in snap.rois],
            layout_text=snap.layout_text,
        )

        self.edit_name.setText(self._preset.name or "preset")
        self.edit_layout.setPlainText(self._preset.layout_text or "")

        self._setup_base_pixmap()
        self._sync_rois_to_scene()
        self._sync_list_from_preset()
        if self._pix is not None:
            self.view.fit_to_item(self._pix)

    # ---------- Splitter state (appdata) ----------

    def _restore_splitter_state(self):
        try:
            b64 = self.ds.get(_SPLIT_H_KEY, "")
            if b64:
                ba = QtCore.QByteArray.fromBase64(b64.encode("ascii"))
                self.main_splitter.restoreState(ba)
        except Exception:
            pass
        try:
            b64 = self.ds.get(_SPLIT_V_KEY, "")
            if b64:
                ba = QtCore.QByteArray.fromBase64(b64.encode("ascii"))
                self.left_splitter.restoreState(ba)
        except Exception:
            pass

    def _save_splitter_state(self):
        try:
            ba = self.main_splitter.saveState()
            self.ds.set(_SPLIT_H_KEY, bytes(ba.toBase64()).decode("ascii"))
        except Exception:
            pass
        try:
            ba = self.left_splitter.saveState()
            self.ds.set(_SPLIT_V_KEY, bytes(ba.toBase64()).decode("ascii"))
        except Exception:
            pass
        try:
            self.ds.save()
        except Exception:
            pass

    def accept(self):
        self._save_splitter_state()
        super().accept()

    def reject(self):
        self._save_splitter_state()
        super().reject()

    # ---------- 結果 ----------

    def result(self) -> Tuple[Preset, str]:
        self._update_preset_from_scene()
        out = self._snapshot_clone()
        out.name = self.edit_name.text().strip() or "preset"
        out.layout_text = self.edit_layout.toPlainText()
        return out, out.name
