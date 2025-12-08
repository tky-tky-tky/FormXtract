# path: main.py  （差し替え：import 行のみ変更）
# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
from PyQt5 import QtWidgets

from core.app import C, DataStore
from ui import MainView


def main():
    app = QtWidgets.QApplication(sys.argv)

    ds = DataStore()
    w = MainView(datastore=ds)
    w.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
