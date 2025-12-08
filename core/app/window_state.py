# -*- coding: utf-8 -*-

from __future__ import annotations

from PyQt5 import QtCore


class _StateBinder(QtCore.QObject):
    """
    QMainWindow/QWidget の位置・サイズを DataStore に保存/復元するヘルパ。
    DataStore は get_window_state/set_window_state/save を備える必要がある。
    """

    def __init__(
        self,
        win: QtCore.QObject,
        ds,
        default_size=(1200, 780),
        move_into_screen=True,
    ) -> None:
        super().__init__(win)
        self.win = win
        self.ds = ds
        self.default_size = default_size
        self.move_into_screen = move_into_screen

        # 1) デフォルトサイズ
        if self.default_size:
            try:
                w, h = self.default_size
                self.win.resize(w, h)
            except Exception:
                pass

        # 2) DataStore から復元
        try:
            b64, maxed = self.ds.get_window_state()
        except Exception:
            b64, maxed = "", False

        if b64:
            try:
                ba = QtCore.QByteArray.fromBase64(b64.encode("ascii"))
                self.win.restoreGeometry(ba)
            except Exception:
                pass

        if maxed:
            try:
                self.win.showMaximized()
            except Exception:
                pass

        # 3) 画面外に出ていたら戻す
        if move_into_screen:
            try:
                scr = self.win.screen()
                if scr is not None:
                    ag = scr.availableGeometry()
                    fg = self.win.frameGeometry()
                    if not ag.intersects(fg):
                        self.win.move(ag.topLeft() + QtCore.QPoint(50, 50))
            except Exception:
                pass

        # 4) Closeフック
        win.installEventFilter(self)

    def eventFilter(self, obj, ev):
        if obj is self.win and ev.type() == QtCore.QEvent.Close:
            try:
                ba = self.win.saveGeometry()
                b64 = bytes(ba.toBase64()).decode("ascii")
                maximized = bool(self.win.windowState() & QtCore.Qt.WindowMaximized)
                self.ds.set_window_state(b64, maximized)
                if hasattr(self.ds, "save"):
                    self.ds.save()
            except Exception:
                pass

        return super().eventFilter(obj, ev)


def bind_with_datastore(
    win,
    ds,
    default_size=(1200, 780),
    move_into_screen=True,
):
    binder = _StateBinder(
        win=win,
        ds=ds,
        default_size=default_size,
        move_into_screen=move_into_screen,
    )
    setattr(win, "_window_state_binder", binder)
    return binder
