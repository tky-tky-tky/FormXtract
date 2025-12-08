# -*- coding: utf-8 -*-

from __future__ import annotations

import re
from typing import List

from core.app.constants import (
    PP_TRIM,
    PP_COMPRESS_SPACES,
    PP_ASCII_DIGIT_ZEN2HAN,
    PP_REMOVE_ZERO_WIDTH,
    PP_BY_COL,
)

_ZERO_WIDTH = re.compile(r"[\u200B-\u200D\uFEFF]")
_WS = re.compile(r"\s+")
_NON_DIGIT = re.compile(r"\D+")
_NON_NUMBER = re.compile(r"[^\d]")
_NUMBER_CHUNK = re.compile(r"(\d{1,4})")

# 日付抽出（年/月/日でバラバラでも3つ拾う）
_DATE_ANY = re.compile(
    r"(?P<a>\d{1,4})\D+(?P<b>\d{1,2})\D+(?P<c>\d{1,4})"
)

def _zen2han_ascii_digit(s: str) -> str:
    try:
        import jaconv
        return jaconv.z2h(s, ascii=True, digit=True, kana=False)
    except Exception:
        return s


def _safe_strip(s: str) -> str:
    if not PP_TRIM:
        return s
    return s.strip()


def _compress_spaces(s: str) -> str:
    if not PP_COMPRESS_SPACES:
        return s
    # 改行・タブ・全角空白を含む空白類を1スペースへ
    s = s.replace("\u3000", " ")
    return _WS.sub(" ", s)


def _remove_zero_width(s: str) -> str:
    if not PP_REMOVE_ZERO_WIDTH:
        return s
    return _ZERO_WIDTH.sub("", s)


def normalize_global(s: str) -> str:
    """
    すべてのフィールドに適用する安全な最小正規化。
    （壊しにくい順に適用）
    """
    if not s:
        return ""

    s = _remove_zero_width(s)

    if PP_ASCII_DIGIT_ZEN2HAN:
        s = _zen2han_ascii_digit(s)

    s = _compress_spaces(s)
    s = _safe_strip(s)
    return s


# -------- 列別ルール --------
def _rule_phone_digits(s: str) -> str:
    """
    電話番号向け：数字のみ抽出（10/11桁でなくても戻す）
    """
    return _NON_DIGIT.sub("", s)


def _rule_money_number(s: str) -> str:
    """
    金額向け：数字だけ抽出（カンマ・通貨記号を除去）
    """
    s = s.replace(",", "")
    s = s.replace("¥", "")
    s = s.replace("￥", "")
    s = s.replace("円", "")
    s = s.replace("$", "")
    s = s.replace("＄", "")
    return _NON_NUMBER.sub("", s)


def _rule_date_std(s: str) -> str:
    """
    多様な日付表記を YYYY-MM-DD にざっくり正規化（ヒューリスティック）。
    - 例: "2025年10月30日" → "2025-10-30"
         "10/30/2025" → "2025-10-30"
         "25-10-30" のような2桁年はそのまま失敗で原文返却（壊さない）
    """
    m = _DATE_ANY.search(s)
    if not m:
        return s

    a = m.group("a")
    b = m.group("b")
    c = m.group("c")

    try:
        ia = int(a)
        ib = int(b)
        ic = int(c)
    except Exception:
        return s

    # パターン1: aが4桁年
    if 1000 <= ia <= 2999:
        y = ia
        m_ = ib
        d_ = ic
    # パターン2: cが4桁年（MM/DD/YYYY想定）
    elif 1000 <= ic <= 2999:
        y = ic
        m_ = ia
        d_ = ib
    else:
        # 2桁年は壊しやすいので原文返却
        return s

    if not (1 <= m_ <= 12 and 1 <= d_ <= 31):
        return s

    return f"{y:04d}-{m_:02d}-{d_:02d}"


_RULES_MAP = {
    "phone_digits": _rule_phone_digits,
    "money_number": _rule_money_number,
    "date_std": _rule_date_std,
}


def apply_rules_to_row(row: List[str]) -> List[str]:
    """
    constants.PP_BY_COL に従って、列ごとに追加ルールを適用する。
    未設定列や未知ルールは無視。
    """
    if not row:
        return row

    out = list(row)

    if not PP_BY_COL:
        return out

    for col_idx, rules in PP_BY_COL.items():
        if not isinstance(col_idx, int):
            continue

        if col_idx < 0:
            continue

        if col_idx >= len(out):
            continue

        val = out[col_idx]

        for rname in rules:
            fn = _RULES_MAP.get(rname)
            if fn is None:
                continue

            try:
                val = fn(val)
            except Exception:
                # 個別ルール失敗は無視
                pass

        out[col_idx] = val

    return out
