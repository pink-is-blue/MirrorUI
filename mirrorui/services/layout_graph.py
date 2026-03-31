from __future__ import annotations

from typing import Any, Dict, List

from mirrorui.schemas import LayoutGraph, VisualRegion


class LayoutGraphBuilder:
    def build(self, extracted: Dict[str, Any], visual_regions: List[VisualRegion]) -> LayoutGraph:
        nodes: List[Dict[str, Any]] = []
        edges: List[Dict[str, Any]] = []

        for node in extracted["nodes"]:
            nodes.append(
                {
                    "id": node["node_id"],
                    "type": "dom",
                    "tag": node["tag"],
                    "text": node["text"],
                    "box": node["box"],
                    "styles": node["styles"],
                }
            )
            if node.get("parent_id"):
                edges.append({"src": node["parent_id"], "dst": node["node_id"], "type": "dom-child"})

        for region in visual_regions:
            rid = f"region::{region.region_id}"
            nodes.append({
                "id": rid,
                "type": "visual",
                "role": region.role,
                "box": {"x": region.x, "y": region.y, "width": region.w, "height": region.h},
                "score": region.score,
            })

        for node in extracted["nodes"]:
            box = node["box"]
            cx = box["x"] + (box["width"] / 2)
            cy = box["y"] + (box["height"] / 2)
            best = None
            best_score = -1.0
            for region in visual_regions:
                inside = region.x <= cx <= region.x + region.w and region.y <= cy <= region.y + region.h
                if not inside:
                    continue
                area = max(1.0, region.w * region.h)
                score = 1.0 / area
                if score > best_score:
                    best_score = score
                    best = region
            if best:
                edges.append({"src": node["node_id"], "dst": f"region::{best.region_id}", "type": "maps-to"})

        return LayoutGraph(nodes=nodes, edges=edges)
