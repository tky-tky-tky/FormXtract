# -*- coding: utf-8 -*-
import re
from typing import List

_placeholder = re.compile(r"\{(\d*)\}")  # {} or {12}

class LayoutPlan:
    """
    layout_text を各行ごとにパースし、[[idx or None, ...], ...] を返す
    例: "(1){1}{2}{3}\n(2){4}{}{5}" -> [[1,2,3],[4,None,5]]
    """
    def __init__(self, text: str):
        self.rows: List[List[int|None]] = []
        for line in text.splitlines():
            cols = []
            for m in _placeholder.finditer(line):
                g = m.group(1)
                if g == "":
                    cols.append(None)   # 空セル
                else:
                    cols.append(int(g))
            if cols:
                self.rows.append(cols)

    def materialize(self, fields: List[str]) -> List[List[str]]:
        # fields は 1-based 参照を想定（{1} が fields[0]）
        out = []
        for row in self.rows:
            out.append([ (fields[i-1] if i else "") for i in row ])
        return out
