from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List
from bs4 import BeautifulSoup

from mirrorui.schemas import CapturePayload
from mirrorui.services.utils import sanitize_text


class DomCssExtractor:
    def extract(self, payload: CapturePayload) -> Dict[str, Any]:
        soup = BeautifulSoup(payload.html, "html.parser")
        semantic_counts = {
            "header": len(soup.find_all("header")),
            "nav": len(soup.find_all("nav")),
            "main": len(soup.find_all("main")),
            "section": len(soup.find_all("section")),
            "article": len(soup.find_all("article")),
            "footer": len(soup.find_all("footer")),
            "form": len(soup.find_all("form")),
        }

        ranked_nodes: List[Dict[str, Any]] = []
        node_lookup: Dict[str, Dict[str, Any]] = {}
        children_by_parent: Dict[str, List[str]] = defaultdict(list)

        for node in payload.dom_nodes:
            box = node.box or {}
            if box.get("width", 0) < 2 or box.get("height", 0) < 2:
                continue
            if not node.visible:
                continue
            text = sanitize_text(node.text)
            background = node.styles.get("backgroundColor", "")
            candidate = {
                "node_id": node.node_id,
                "tag": node.tag,
                "text": text,
                "classes": node.classes,
                "attrs": node.attrs,
                "styles": node.styles,
                "box": box,
                "children": node.children,
                "parent_id": node.parent_id,
                "depth": node.depth,
                "order": node.order,
                "interactive": node.interactive,
                "role_hint": node.role_hint,
                "layout": {
                    "display": node.styles.get("display", "block"),
                    "position": node.styles.get("position", "static"),
                    "grid": node.styles.get("gridTemplateColumns", "none"),
                    "gap": node.styles.get("gap", "0px"),
                },
                "importance": self._importance_score(
                    tag=node.tag,
                    text=text,
                    box=box,
                    attrs=node.attrs,
                    styles=node.styles,
                    interactive=node.interactive,
                    role_hint=node.role_hint,
                ),
                "has_visual_fill": background not in {"", "rgba(0, 0, 0, 0)", "transparent"}
                or node.styles.get("backgroundImage", "") not in {"", "none"},
            }
            node_lookup[candidate["node_id"]] = candidate
            children_by_parent[candidate.get("parent_id") or ""].append(candidate["node_id"])
            ranked_nodes.append(candidate)

        ranked_nodes.sort(
            key=lambda n: (
                -float(n.get("importance", 0.0)),
                n.get("depth", 0),
                n.get("order", 0),
            )
        )

        kept_ids = set()
        for node in ranked_nodes[:540]:
            current = node
            while current:
                node_id = current.get("node_id")
                if node_id in kept_ids:
                    break
                kept_ids.add(node_id)
                parent_id = current.get("parent_id")
                current = node_lookup.get(parent_id) if parent_id else None

        # Pull in structural children to avoid collapsing into root-only reconstruction.
        frontier = list(kept_ids)
        cursor = 0
        while cursor < len(frontier):
            parent_id = frontier[cursor]
            cursor += 1
            children = children_by_parent.get(parent_id, [])
            if not children:
                continue

            ranked_children = sorted(
                (node_lookup.get(child_id) for child_id in children if child_id in node_lookup),
                key=lambda n: (
                    -float((n or {}).get("importance", 0.0)),
                    (n or {}).get("order", 0),
                ),
            )

            # Keep top structural children even when they are not text-heavy.
            for idx, child in enumerate(ranked_children[:18]):
                if not child:
                    continue
                keep = False
                parent = node_lookup.get(parent_id, {})
                parent_box = parent.get("box", {})
                parent_area = float(parent_box.get("width", 0.0)) * float(parent_box.get("height", 0.0))
                if parent_area > 220000 and idx < 10:
                    keep = True
                if child.get("importance", 0.0) >= 0.75:
                    keep = True
                if child.get("interactive"):
                    keep = True
                if child.get("text"):
                    keep = True
                if child.get("tag") in {"img", "picture", "video", "section", "article", "main", "nav", "header", "footer", "form", "ul", "ol", "li"}:
                    keep = True
                if child.get("attrs", {}).get("src"):
                    keep = True
                if keep:
                    child_id = child["node_id"]
                    if child_id not in kept_ids:
                        kept_ids.add(child_id)
                        frontier.append(child_id)

        nodes = [node_lookup[node_id] for node_id in kept_ids if node_id in node_lookup]
        nodes.sort(key=lambda n: (n.get("depth", 0), n["box"].get("y", 0), n["box"].get("x", 0), n.get("order", 0)))

        text_nodes = sum(1 for node in nodes if node.get("text"))
        interactive_nodes = sum(1 for node in nodes if node.get("interactive"))
        image_nodes = sum(1 for node in nodes if node.get("tag") == "img" or node.get("attrs", {}).get("src"))

        return {
            "url": payload.url,
            "title": payload.title,
            "screenshot_path": payload.screenshot_path,
            "viewport": payload.viewport,
            "semantic_counts": semantic_counts,
            "challenge_detected": payload.challenge_detected,
            "challenge_reason": payload.challenge_reason,
            "summary": {
                "node_count": len(nodes),
                "text_nodes": text_nodes,
                "interactive_nodes": interactive_nodes,
                "image_nodes": image_nodes,
            },
            "nodes": nodes,
        }

    def _importance_score(
        self,
        tag: str,
        text: str,
        box: Dict[str, Any],
        attrs: Dict[str, Any],
        styles: Dict[str, Any],
        interactive: bool,
        role_hint: str,
    ) -> float:
        area = float(box.get("width", 0.0)) * float(box.get("height", 0.0))
        score = 0.0

        if text:
            score += min(3.2, 0.45 + len(text) / 70.0)
        if interactive:
            score += 2.6
        if tag in {"img", "video", "picture"} or attrs.get("src"):
            score += 2.2
        if tag in {"header", "nav", "main", "section", "article", "footer", "form"}:
            score += 1.8
        if role_hint:
            score += 0.9
        if styles.get("display") in {"flex", "grid", "inline-flex", "inline-grid"}:
            score += 1.0
        if styles.get("backgroundImage") not in {None, "", "none"}:
            score += 1.4
        if styles.get("backgroundColor") not in {None, "", "rgba(0, 0, 0, 0)", "transparent"}:
            score += 0.6
        if styles.get("boxShadow") not in {None, "", "none"}:
            score += 0.4
        if styles.get("borderWidth") not in {None, "", "0px"}:
            score += 0.3

        if area > 0:
            score += min(2.8, area / 260000.0)
        if area > 800000 and not text and not interactive and tag == "div":
            score -= 1.2

        if text and len(text) > 180 and tag in {"div", "section", "article", "main"}:
            score -= 0.6

        return round(score, 4)
