from __future__ import annotations

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
        for node in payload.dom_nodes:
            box = node.box or {}
            if box.get("width", 0) < 2 or box.get("height", 0) < 2:
                continue
            if not node.visible:
                continue
            candidate = (
                {
                    "node_id": node.node_id,
                    "tag": node.tag,
                    "text": sanitize_text(node.text),
                    "classes": node.classes,
                    "attrs": node.attrs,
                    "styles": node.styles,
                    "box": box,
                    "children": node.children,
                    "parent_id": node.parent_id,
                    "layout": {
                        "display": node.styles.get("display", "block"),
                        "position": node.styles.get("position", "static"),
                        "grid": node.styles.get("gridTemplateColumns", "none"),
                        "gap": node.styles.get("gap", "0px"),
                    },
                }
            )
            ranked_nodes.append(candidate)

        ranked_nodes.sort(key=lambda n: float(n["box"].get("width", 0) * n["box"].get("height", 0)), reverse=True)
        nodes = ranked_nodes[:900]

        return {
            "url": payload.url,
            "title": payload.title,
            "screenshot_path": payload.screenshot_path,
            "viewport": payload.viewport,
            "semantic_counts": semantic_counts,
            "nodes": nodes,
        }
