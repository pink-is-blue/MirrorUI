from __future__ import annotations

from typing import Dict


def snap_spacing(px: float) -> int:
    if px <= 0:
        return 0
    steps = [0, 1, 2, 3, 4, 5, 6, 8, 10, 12, 16, 20, 24, 28, 32, 36, 40, 44, 48, 56, 64, 72, 80, 96]
    rem_value = round(px / 4.0)
    nearest = min(steps, key=lambda x: abs(x - rem_value))
    return nearest


def sanitize_text(text: str) -> str:
    return " ".join((text or "").split())[:240]


def pick_color_token(rgb: str) -> str:
    token_map: Dict[str, str] = {
        "rgb(255, 255, 255)": "white",
        "rgb(0, 0, 0)": "black",
        "rgb(15, 23, 42)": "slate-900",
        "rgb(51, 65, 85)": "slate-700",
        "rgb(100, 116, 139)": "slate-500",
        "rgb(226, 232, 240)": "slate-200",
    }
    return token_map.get((rgb or "").strip(), "slate-700")


def to_js_string(text: str) -> str:
    value = (text or "").replace("\\", "\\\\").replace("`", "\\`")
    return value
