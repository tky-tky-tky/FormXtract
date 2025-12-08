# -*- coding: utf-8 -*-

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any


@dataclass
class ROI:
    x: int
    y: int
    w: int
    h: int
    orientation: str = "auto"   # "auto" | "0" | "90" | "180" | "270"


@dataclass
class Preset:
    # 注意：プリセットの正しい“名称”はファイル名（拡張子抜き）
    # ここでは読みやすさのため name を参考値として保持してもよいが、
    # I/O 層ではファイル名を真とする。
    name: str = ""
    image_w: int = 0
    image_h: int = 0
    rois: List[ROI] = field(default_factory=list)
    layout_text: str = "{1}{2}{3}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "image_w": self.image_w,
            "image_h": self.image_h,
            "rois": [asdict(r) for r in self.rois],
            "layout_text": self.layout_text,
        }

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "Preset":
        rois_data = d.get("rois", [])
        rois = [ROI(**r) for r in rois_data]
        return Preset(
            name=d.get("name", ""),
            image_w=int(d.get("image_w", 0) or 0),
            image_h=int(d.get("image_h", 0) or 0),
            rois=rois,
            layout_text=str(d.get("layout_text", "{1}{2}{3}")),
        )
