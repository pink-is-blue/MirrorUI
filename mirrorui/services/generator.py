from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from mirrorui.schemas import Action, GenerationCandidate, Section


class ProposerVerifierGenerator:
    def generate_candidates(self, extracted: Dict[str, Any], sections: List[Section], actions: List[Action]) -> List[GenerationCandidate]:
        candidate_a = GenerationCandidate(
            candidate_id="cand_a",
            rationale="Prioritize direct DOM and style preservation.",
            files=self._build_files(extracted, sections, actions, dense=False),
        )
        candidate_b = GenerationCandidate(
            candidate_id="cand_b",
            rationale="Prioritize denser retention of decorative containers.",
            files=self._build_files(extracted, sections, actions, dense=True),
        )
        return [candidate_a, candidate_b]

    def verify_and_select(self, candidates: List[GenerationCandidate], extracted: Dict[str, Any], sections: List[Section]) -> Dict[str, Any]:
        scored: List[Dict[str, Any]] = []
        for candidate in candidates:
            score = 0
            files = {k: self._verify_tailwind(v) for k, v in candidate.files.items()}
            app_body = files.get("src/components/generated/AppBody.jsx", "")
            metadata = files.get("src/components/generated/generation.meta.js", "")
            if "MirrorRenderer" in app_body:
                score += 3
            if "selectedNodeId" in app_body:
                score += 1
            if "pageData" in metadata:
                score += 2
            if "node_id" in metadata:
                score += 2
            scored.append({"candidate_id": candidate.candidate_id, "score": score, "files": files})

        best = sorted(scored, key=lambda x: x["score"], reverse=True)[0]
        return {
            "selected_candidate": best["candidate_id"],
            "scores": scored,
            "files": best["files"],
        }

    def _verify_tailwind(self, code: str) -> str:
        fixed = code.replace("  ", " ")
        fixed = fixed.replace("text-\"", "text-")
        fixed = fixed.replace("className=\"\"", "className=\"text-slate-700\"")
        return fixed

    def _build_files(self, extracted: Dict[str, Any], sections: List[Section], actions: List[Action], dense: bool) -> Dict[str, str]:
        nodes = extracted["nodes"]
        title = extracted.get("title") or "MirrorUI Output"
        page_model = self._build_page_model(extracted, dense=dense)

        actions_json = json.dumps([action.model_dump() for action in actions], ensure_ascii=True, indent=2)
        page_json = json.dumps(page_model, ensure_ascii=True, indent=2)

        app_body = """import React from 'react'
import MirrorRenderer from '../runtime/MirrorRenderer.jsx'
import { pageData } from './generation.meta.js'

export default function AppBody({ selectedNodeId = '' }) {
  return <MirrorRenderer pageData={pageData} selectedNodeId={selectedNodeId} />
}
"""

        section_list = """import React from 'react'

export default function SectionList() {
  return null
}
"""

        layout_json = json.dumps(
            {
                "title": title,
                "actions": [action.model_dump() for action in actions],
                "sections": [section.model_dump() for section in sections],
                "nodes": nodes,
            },
            ensure_ascii=True,
            indent=2,
        )

        metadata = (
            f"export const generationActions = {actions_json}\n\n"
            f"export const pageData = {page_json}\n"
        )

        return {
            "src/components/generated/AppBody.jsx": app_body,
            "src/components/generated/SectionList.jsx": section_list,
            "src/components/generated/generation.meta.js": metadata,
            "workspace/generated/layout.json": layout_json,
        }

    def _build_page_model(self, extracted: Dict[str, Any], dense: bool) -> Dict[str, Any]:
        nodes = extracted.get("nodes", [])
        viewport = extracted.get("viewport", {})
        root = self._pick_root(nodes, viewport)
        root_box = root.get("box", {}) if root else {}
        root_x = float(root_box.get("x", 0.0))
        root_y = float(root_box.get("y", 0.0))
        page_width = max(float(root_box.get("width", 0.0)), float(viewport.get("width", 1440)), 320.0)
        page_height = max(float(viewport.get("height", 1024)), 320.0)

        children_by_parent: Dict[str, List[str]] = {}
        node_by_id: Dict[str, Dict[str, Any]] = {}
        for node in nodes:
            parent_id = node.get("parent_id") or ""
            children_by_parent.setdefault(parent_id, []).append(node.get("node_id", ""))
            node_by_id[node.get("node_id", "")] = node

        budget = 650 if dense else 420
        rendered = 0

        root_id = root.get("node_id", "")

        def build_tree(node_id: str, depth: int) -> Optional[Dict[str, Any]]:
            nonlocal rendered
            if rendered >= budget:
                return None
            node = node_by_id.get(node_id)
            if not node:
                return None

            keep_self = self._should_keep(node, dense=dense)
            child_nodes: List[Dict[str, Any]] = []
            for child_id in children_by_parent.get(node_id, []):
                child = build_tree(child_id, depth + 1)
                if child:
                    child_nodes.append(child)

            if not keep_self and not child_nodes:
                return None

            rendered += 1
            tag = self._normalize_tag(node.get("tag", "div"))
            text_value = (node.get("text") or "").strip()
            if child_nodes and tag in {"div", "section", "article", "main", "header", "footer", "nav", "aside", "ul", "ol", "form"}:
                text_value = ""

            styles = self._pick_styles(node.get("styles", {}))
            box = node.get("box", {})
            if styles.get("position") in {"absolute", "fixed", "sticky"}:
                left_px = max(0.0, float(box.get("x", 0.0)) - root_x)
                top_px = max(0.0, float(box.get("y", 0.0)) - root_y)
                width_px = max(0.0, float(box.get("width", 0.0)))
                height_px = max(0.0, float(box.get("height", 0.0)))
                styles["left"] = styles.get("left") or f"{left_px:.2f}px"
                styles["top"] = styles.get("top") or f"{top_px:.2f}px"
                if width_px > 0:
                    styles["width"] = styles.get("width") or f"{width_px:.2f}px"
                if height_px > 0:
                    styles["height"] = styles.get("height") or f"{height_px:.2f}px"

            if node_id == root_id:
                styles["position"] = "relative"
                styles["marginTop"] = "0px"
                styles["marginRight"] = "0px"
                styles["marginBottom"] = "0px"
                styles["marginLeft"] = "0px"
                styles["width"] = "100%"
                styles["height"] = "auto"

            return {
                "node_id": node.get("node_id", ""),
                "tag": tag,
                "text": text_value,
                "attrs": self._pick_attrs(node.get("attrs", {})),
                "styles": styles,
                "classes": node.get("classes", []),
                "children": child_nodes,
            }

        tree_root = build_tree(root_id, 0) if root_id else None
        if not tree_root:
            synthetic_children = []
            for node in nodes:
                if not node.get("parent_id"):
                    branch = build_tree(node.get("node_id", ""), 0)
                    if branch:
                        synthetic_children.append(branch)
            tree_root = {
                "node_id": "root",
                "tag": "main",
                "text": "",
                "attrs": {},
                "styles": {},
                "classes": [],
                "children": synthetic_children,
            }

        return {
            "title": extracted.get("title") or "MirrorUI Output",
            "width": int(page_width),
            "height": int(page_height),
            "backgroundColor": self._pick_root_background(root, nodes),
            "screenshotUrl": "/api/screenshot",
            "root": tree_root,
        }

    def _pick_root(self, nodes: List[Dict[str, Any]], viewport: Dict[str, Any]) -> Dict[str, Any]:
        for tag in ("body", "main", "html"):
            for node in nodes:
                if node.get("tag") == tag:
                    return node
        return {
            "box": {
                "x": 0.0,
                "y": 0.0,
                "width": float(viewport.get("width", 1440)),
                "height": float(viewport.get("height", 1024)),
            },
            "styles": {"backgroundColor": "rgb(255, 255, 255)"},
        }

    def _estimate_page_height(self, nodes: List[Dict[str, Any]], root_y: float) -> float:
        max_bottom = 0.0
        for node in nodes:
            box = node.get("box", {})
            bottom = float(box.get("y", 0.0)) - root_y + float(box.get("height", 0.0))
            if bottom > max_bottom:
                max_bottom = bottom
        return max_bottom

    def _should_keep(self, node: Dict[str, Any], dense: bool) -> bool:
        tag = (node.get("tag") or "").lower()
        if tag in {"html", "body", "head", "script", "style", "meta", "link", "noscript", "path", "svg"}:
            return False

        box = node.get("box", {})
        width = float(box.get("width", 0.0))
        height = float(box.get("height", 0.0))
        if width < 4 or height < 4:
            return False

        styles = node.get("styles", {})
        attrs = node.get("attrs", {})
        text = (node.get("text") or "").strip()
        display = styles.get("display", "")
        visibility = styles.get("visibility", "visible")
        opacity = styles.get("opacity", "1")
        background = styles.get("backgroundColor", "")
        background_image = styles.get("backgroundImage", "")
        border_width = styles.get("borderWidth", "0px")
        box_shadow = styles.get("boxShadow", "none")

        if display == "none" or visibility == "hidden":
            return False
        try:
            if float(opacity) <= 0.0:
                return False
        except ValueError:
            pass

        if tag in {"img", "a", "button", "input", "textarea", "select", "label"}:
            return True
        if text and len(text) > 120 and tag in {"div", "section", "article", "main", "header", "footer", "nav"}:
            return False
        if tag.startswith("h") and len(tag) == 2 and tag[1].isdigit():
            return True
        if text:
            return True
        if attrs.get("src") or attrs.get("placeholder"):
            return True
        if display in {"flex", "grid", "inline-flex", "inline-grid"}:
            return True
        if background not in {"", "rgba(0, 0, 0, 0)", "transparent"}:
            return True
        if background_image and background_image != "none":
            return True
        if border_width not in {"", "0px"}:
            return True
        if box_shadow and box_shadow != "none":
            return True
        if dense:
            return tag in {"div", "section", "article", "main", "header", "footer", "nav", "aside", "ul", "ol", "li", "form"}
        return False

    def _normalize_tag(self, tag: str) -> str:
        allowed = {
            "div", "section", "article", "main", "header", "footer", "nav", "aside", "p", "span", "a", "button",
            "img", "ul", "ol", "li", "form", "input", "textarea", "label", "select", "option", "h1", "h2", "h3",
            "h4", "h5", "h6"
        }
        return tag if tag in allowed else "div"

    def _pick_attrs(self, attrs: Dict[str, Any]) -> Dict[str, str]:
        allowed = ["href", "src", "alt", "placeholder", "type", "value", "aria-label"]
        result: Dict[str, str] = {}
        for key in allowed:
            value = attrs.get(key)
            if isinstance(value, str) and value:
                result[key] = value
        return result

    def _pick_styles(self, styles: Dict[str, Any]) -> Dict[str, str]:
        allowed = [
            "display", "position", "visibility", "pointerEvents", "flexDirection", "flexWrap", "flexGrow", "flexShrink", "flexBasis",
            "fontSize", "fontWeight", "fontFamily", "color", "backgroundColor",
            "backgroundImage", "backgroundPosition", "backgroundSize", "backgroundRepeat", "paddingTop", "paddingBottom",
            "paddingLeft", "paddingRight", "marginTop", "marginBottom", "marginLeft", "marginRight", "width", "height",
            "minWidth", "minHeight", "maxWidth", "maxHeight", "gap", "rowGap", "columnGap", "justifyContent", "alignItems", "alignSelf", "gridTemplateColumns", "gridTemplateRows", "gridColumn", "gridRow",
            "borderRadius", "borderWidth", "borderStyle", "borderColor", "boxShadow", "lineHeight", "letterSpacing",
            "textAlign", "textDecoration", "textTransform", "opacity", "overflow", "overflowX", "overflowY", "objectFit", "left", "top", "right", "bottom", "zIndex"
        ]
        return {key: str(styles.get(key, "")) for key in allowed if styles.get(key) not in {None, ""}}

    def _pick_root_background(self, root: Dict[str, Any], nodes: List[Dict[str, Any]]) -> str:
        root_styles = (root or {}).get("styles", {})
        background = root_styles.get("backgroundColor") if isinstance(root_styles, dict) else None
        if background and background not in {"rgba(0, 0, 0, 0)", "transparent"}:
            return background
        for node in nodes:
            styles = node.get("styles", {})
            bg = styles.get("backgroundColor")
            if bg and bg not in {"rgba(0, 0, 0, 0)", "transparent"}:
                return bg
        return "rgb(255, 255, 255)"
