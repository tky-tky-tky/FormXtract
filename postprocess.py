# -*- coding: utf-8 -*-
import re

def normalize_zenhan(s: str) -> str:
    try:
        import jaconv
        return jaconv.z2h(s, ascii=True, digit=True, kana=False)
    except:
        return s

def normalize_phone(s: str) -> str:
    d = re.sub(r"[^\d]", "", s)
    if len(d)>=9:
        return d
    return s

# 必要に応じて拡張
