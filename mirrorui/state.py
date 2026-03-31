from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


class WorkspaceState:
    def __init__(self, root: Path):
        self.root = root
        self.work_dir = root / "workspace" / "generated"
        self.screens_dir = root / "workspace" / "screens"
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.screens_dir.mkdir(parents=True, exist_ok=True)

        self.layout_file = self.work_dir / "layout.json"
        self.meta_file = self.work_dir / "meta.json"

    def save_json(self, path: Path, payload: Dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")

    def load_json(self, path: Path) -> Dict[str, Any]:
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))

    def save_layout(self, payload: Dict[str, Any]) -> None:
        self.save_json(self.layout_file, payload)

    def load_layout(self) -> Dict[str, Any]:
        return self.load_json(self.layout_file)

    def save_meta(self, payload: Dict[str, Any]) -> None:
        self.save_json(self.meta_file, payload)

    def load_meta(self) -> Dict[str, Any]:
        return self.load_json(self.meta_file)
