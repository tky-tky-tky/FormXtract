# -*- coding: utf-8 -*-

from __future__ import annotations

import re
from typing import List, Optional

# {} or {12}
_PLACEHOLDER = re.compile(r"\{(\d*)\}")


class LayoutPlan:
    """
    layout_text を各行ごとにパースし、[[idx or None, ...], ...] を内部保持。
    例: "{1}{2}{3}\n{4}{}{5}" -> rows = [[1,2,3],[4,None,5]]

    非プレースホルダ文字は無視し、列としては扱わない。
    """

    def __init__(self, text: str) -> None:
        self.rows: List[List[Optional[int]]] = []

        for line in text.splitlines():
            cols: List[Optional[int]] = []

            for m in _PLACEHOLDER.finditer(line):
                g = m.group(1)
                if g == "":
                    cols.append(None)
                else:
                    try:
                        idx = int(g)
                    except Exception:
                        idx = 0

                    cols.append(idx)

            if cols:
                self.rows.append(cols)

    def materialize(self, fields: List[str]) -> List[List[str]]:
        """
        fields は 1-based 参照を想定（{1} が fields[0]）。
        0 以下、または範囲外の参照は空文字にする。
        """
        out: List[List[str]] = []

        n = len(fields)

        for row in self.rows:
            vals: List[str] = []

            for idx in row:
                if idx is None:
                    vals.append("")
                    continue

                if idx <= 0:
                    vals.append("")
                    continue

                if idx > n:
                    vals.append("")
                    continue

                vals.append(fields[idx - 1])

            out.append(vals)

        return out
