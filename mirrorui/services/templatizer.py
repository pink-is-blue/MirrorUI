from __future__ import annotations

from typing import Any, Dict, List

from mirrorui.schemas import Action, Section
from mirrorui.services.utils import pick_color_token, snap_spacing


class ActionTemplatizer:
    def to_actions(self, extracted: Dict[str, Any], sections: List[Section]) -> List[Action]:
        by_id = {node["node_id"]: node for node in extracted["nodes"]}
        actions: List[Action] = []

        for section in sections:
            actions.append(Action(action="SetLayoutMode", target=section.section_id, payload={"mode": self._infer_layout(section, by_id)}))
            actions.append(Action(action="SetAxis", target=section.section_id, payload={"axis": self._infer_axis(section, by_id)}))
            actions.append(Action(action="SetGap", target=section.section_id, payload={"gap": self._infer_gap(section, by_id)}))

            sample = by_id.get(section.node_ids[0]) if section.node_ids else None
            if sample:
                styles = sample.get("styles", {})
                actions.append(
                    Action(
                        action="SetTypography",
                        target=section.section_id,
                        payload={
                            "fontSize": styles.get("fontSize", "16px"),
                            "fontWeight": styles.get("fontWeight", "400"),
                        },
                    )
                )
                actions.append(
                    Action(
                        action="SetColorToken",
                        target=section.section_id,
                        payload={"color": pick_color_token(styles.get("color", ""))},
                    )
                )

            if section.repeated:
                actions.append(Action(action="RepeatPattern", target=section.section_id, payload={"repeated": True}))

        return actions

    def _infer_layout(self, section: Section, by_id: Dict[str, Dict[str, Any]]) -> str:
        displays = [by_id[nid]["layout"].get("display", "block") for nid in section.node_ids if nid in by_id]
        if any("grid" in d for d in displays):
            return "grid"
        if any("flex" in d for d in displays):
            return "flex"
        return "block"

    def _infer_axis(self, section: Section, by_id: Dict[str, Dict[str, Any]]) -> str:
        widths = [by_id[nid]["box"].get("width", 0) for nid in section.node_ids if nid in by_id]
        heights = [by_id[nid]["box"].get("height", 0) for nid in section.node_ids if nid in by_id]
        if sum(widths) > sum(heights):
            return "row"
        return "col"

    def _infer_gap(self, section: Section, by_id: Dict[str, Dict[str, Any]]) -> int:
        vals: List[int] = []
        for nid in section.node_ids:
            node = by_id.get(nid)
            if not node:
                continue
            raw = str(node["layout"].get("gap", "0px")).replace("px", "")
            try:
                vals.append(int(float(raw)))
            except ValueError:
                continue
        if not vals:
            return 4
        return snap_spacing(sum(vals) / len(vals))
