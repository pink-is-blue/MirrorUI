from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List

from mirrorui.schemas import Section


class ComponentSegmenter:
    def segment(self, extracted: Dict[str, Any]) -> List[Section]:
        nodes = extracted["nodes"]
        if not nodes:
            return []

        max_y = max(node["box"].get("y", 0) + node["box"].get("height", 0) for node in nodes)
        sections: List[Section] = []

        by_tag = Counter(node["tag"] for node in nodes)

        header_nodes = [n["node_id"] for n in nodes if n["box"].get("y", 0) < max_y * 0.15]
        if header_nodes:
            sections.append(Section(section_id="sec_header", role="header", node_ids=header_nodes))

        nav_nodes = [n["node_id"] for n in nodes if n["tag"] in {"nav", "a"} and n["box"].get("y", 0) < max_y * 0.25]
        if nav_nodes:
            sections.append(Section(section_id="sec_nav", role="navbar", node_ids=nav_nodes))

        hero_nodes = [n["node_id"] for n in nodes if n["tag"] in {"h1", "h2", "section"} and n["box"].get("y", 0) < max_y * 0.4]
        if hero_nodes:
            sections.append(Section(section_id="sec_hero", role="hero", node_ids=hero_nodes))

        card_nodes = [n["node_id"] for n in nodes if n["tag"] in {"article", "li", "div"} and n["box"].get("height", 0) > 60]
        if card_nodes and by_tag["article"] + by_tag["li"] >= 2:
            sections.append(Section(section_id="sec_cards", role="cards", node_ids=card_nodes, repeated=True))

        form_nodes = [n["node_id"] for n in nodes if n["tag"] in {"form", "input", "button", "label", "select", "textarea"}]
        if form_nodes:
            sections.append(Section(section_id="sec_form", role="form", node_ids=form_nodes))

        footer_nodes = [n["node_id"] for n in nodes if n["box"].get("y", 0) > max_y * 0.82]
        if footer_nodes:
            sections.append(Section(section_id="sec_footer", role="footer", node_ids=footer_nodes))

        if not sections:
            sections.append(Section(section_id="sec_content", role="content", node_ids=[n["node_id"] for n in nodes]))

        return sections
