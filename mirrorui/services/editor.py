from __future__ import annotations

from typing import Any, Dict, Optional

from mirrorui.schemas import Action, Section
from mirrorui.services.generator import ProposerVerifierGenerator


class LayoutEditor:
    def __init__(self, generator: ProposerVerifierGenerator):
        self.generator = generator

    def update_node(
        self,
        layout_payload: Dict[str, Any],
        node_id: str,
        text: Optional[str] = None,
        href: Optional[str] = None,
        image_src: Optional[str] = None,
        class_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        nodes = layout_payload.get("nodes", [])
        updated = None

        for node in nodes:
            if node.get("node_id") != node_id:
                continue
            if text is not None:
                node["text"] = text
            if href is not None:
                node.setdefault("attrs", {})["href"] = href
            if image_src is not None:
                node.setdefault("attrs", {})["src"] = image_src
            if class_name is not None:
                node["classes"] = [part for part in class_name.split() if part]
            updated = node
            break

        if updated is None:
            raise ValueError("node_id not found")

        regen_sections = [Section(**section) for section in layout_payload.get("sections", [])]
        regen_actions = [Action(**action) for action in layout_payload.get("actions", [])]

        regenerated = self.generator._build_files(layout_payload, regen_sections, regen_actions, dense=False)
        return {"updated_node": updated, "files": regenerated}
