# -*- coding: utf-8 -*-
import os, json, dataclasses
from typing import List

PRESET_DIR = os.path.join("assets", "presets")
os.makedirs(PRESET_DIR, exist_ok=True)

@dataclasses.dataclass
class ROI:
    x: int; y: int; w: int; h: int
    orientation: str = "auto"  # "auto" / "0" / "90" / "180" / "270"

@dataclasses.dataclass
class Preset:
    name: str
    image_w: int = 0
    image_h: int = 0
    rois: List[ROI] = dataclasses.field(default_factory=list)
    layout_text: str = "(1){1}{2}{3}"

    def to_dict(self):
        return {
            "name": self.name,
            "image_w": self.image_w, "image_h": self.image_h,
            "rois": [dataclasses.asdict(r) for r in self.rois],
            "layout_text": self.layout_text
        }

    @staticmethod
    def from_dict(d: dict) -> "Preset":
        rois = [ROI(**r) for r in d.get("rois", [])]
        return Preset(
            name=d.get("name","preset"),
            image_w=d.get("image_w",0),
            image_h=d.get("image_h",0),
            rois=rois,
            layout_text=d.get("layout_text","")
        )

    def path(self):
        return os.path.join(PRESET_DIR, f"{self.name}.json")

    def delete_file_if_exists(self):
        p = self.path()
        if os.path.exists(p):
            os.remove(p)

    def copy(self):
        return Preset.from_dict(self.to_dict())

    def copy_with_new_name(self, newname: str):
        d = self.to_dict(); d["name"] = newname
        return Preset.from_dict(d)

def load_presets() -> List[Preset]:
    out = []
    for fn in os.listdir(PRESET_DIR):
        if not fn.endswith(".json"): continue
        with open(os.path.join(PRESET_DIR, fn), "r", encoding="utf-8") as f:
            out.append(Preset.from_dict(json.load(f)))
    return out

def save_preset(p: Preset):
    with open(p.path(), "w", encoding="utf-8") as f:
        json.dump(p.to_dict(), f, ensure_ascii=False, indent=2)
