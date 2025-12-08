# path: core/csvio/writer.py
# -*- coding: utf-8 -*-

from __future__ import annotations

import csv
import os
from pathlib import Path
from typing import Iterable, List

from core.app.constants import CSV_BOM_UTF8, CSV_NEWLINE


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _to_text_cells(row: Iterable) -> List[str]:
    out: List[str] = []

    for x in row:
        if x is None:
            out.append("")
            continue

        if isinstance(x, str):
            out.append(x)
            continue

        out.append(str(x))

    return out


def _write_csv_rows(fp, rows: List[List[str]]) -> None:
    writer = csv.writer(fp)
    for r in rows:
        writer.writerow(_to_text_cells(r))


def write_rows(
    csv_path: str | Path,
    rows: List[List[str]],
    append: bool,
    bom_utf8: bool = CSV_BOM_UTF8,
    newline: str = CSV_NEWLINE,
) -> int:
    """
    rows を CSV に書き込む。
    - append=True なら追記（ファイルが無ければ新規作成）
      新規作成時のみ BOM 付与を検討する
    - append=False なら上書き（原子的に置換）
    戻り値は書き込み行数。
    """
    if not rows:
        return 0

    path = Path(csv_path)
    _ensure_parent(path)

    if append:
        exists = path.exists()

        if exists:
            encoding = "utf-8"
        else:
            encoding = "utf-8-sig" if bom_utf8 else "utf-8"

        with open(path, "a", encoding=encoding, newline=newline) as fp:
            _write_csv_rows(fp, rows)

        return len(rows)

    tmp = path.with_suffix(path.suffix + ".tmp")

    try:
        encoding = "utf-8-sig" if bom_utf8 else "utf-8"

        with open(tmp, "w", encoding=encoding, newline=newline) as fp:
            _write_csv_rows(fp, rows)

        os.replace(tmp, path)
    except Exception:
        try:
            if tmp.exists():
                tmp.unlink()
        except Exception:
            pass

        raise

    return len(rows)
