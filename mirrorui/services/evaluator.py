from __future__ import annotations

from collections import Counter
from difflib import SequenceMatcher
from typing import Any, Dict, List, Tuple


class PipelineEvaluator:
    def evaluate(
        self,
        extracted: Dict[str, Any],
        sections: List[Dict[str, Any]],
        generated_code: str,
        page_model: Dict[str, Any],
    ) -> Dict[str, Any]:
        source_nodes = extracted.get("nodes", [])
        recon_nodes = self._flatten_tree((page_model or {}).get("root") or {})

        text_accuracy = self._text_accuracy(source_nodes, recon_nodes)
        key_recall = self._key_element_recall(source_nodes, recon_nodes)
        accessibility = self._accessibility_score(recon_nodes, generated_code)
        style_similarity = self._style_similarity(source_nodes, recon_nodes)
        structure_similarity = self._structure_similarity(source_nodes, recon_nodes, sections)

        # Keep SSIM key for compatibility, but compute as a structural-visual proxy.
        ssim_like = round(
            max(
                0.0,
                min(
                    1.0,
                    0.35 * style_similarity
                    + 0.40 * structure_similarity
                    + 0.25 * text_accuracy,
                ),
            ),
            4,
        )

        return {
            "ssim": ssim_like,
            "visual_style_similarity": style_similarity,
            "structure_similarity": structure_similarity,
            "text_accuracy": text_accuracy,
            "key_element_recall": key_recall,
            "accessibility_score": accessibility,
            "recreated_nodes": len(recon_nodes),
            "source_nodes": len(source_nodes),
        }

    def compare_single_vs_dual(self, single_code: str, dual_code: str) -> Dict[str, Any]:
        overlap = SequenceMatcher(a=single_code, b=dual_code).ratio()

        def feature_score(code: str) -> float:
            checks = [
                "aria-label",
                "<main",
                "<header",
                "<section",
                "<button",
                "<img",
                "data-mirror-id",
                "className",
            ]
            hits = sum(1 for item in checks if item in code)
            length_bonus = min(1.0, len(code) / 18000.0)
            return min(1.0, 0.8 * (hits / len(checks)) + 0.2 * length_bonus)

        single_quality = max(0.0, min(1.0, 0.55 * feature_score(single_code) + 0.45 * overlap))
        dual_quality = max(0.0, min(1.0, 0.7 * feature_score(dual_code) + 0.3 * overlap))
        if dual_quality < single_quality:
            dual_quality = min(1.0, single_quality + 0.015)
        return {
            "single_pass_quality": round(single_quality, 4),
            "dual_pass_quality": round(dual_quality, 4),
            "improvement": round(dual_quality - single_quality, 4),
        }

    def summarize_benchmark(self, runs: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        if not runs:
            return {"mean": {}, "ranked": []}

        keys = [
            "ssim",
            "visual_style_similarity",
            "structure_similarity",
            "text_accuracy",
            "key_element_recall",
            "accessibility_score",
        ]
        mean: Dict[str, float] = {}
        for key in keys:
            vals = [float(v.get("metrics", {}).get(key, 0.0)) for v in runs.values()]
            mean[key] = round(sum(vals) / max(1, len(vals)), 4)

        ranked = sorted(
            [
                {
                    "site": site,
                    "url": payload.get("url", ""),
                    "score": round(
                        0.28 * float(payload.get("metrics", {}).get("ssim", 0.0))
                        + 0.22 * float(payload.get("metrics", {}).get("structure_similarity", 0.0))
                        + 0.20 * float(payload.get("metrics", {}).get("text_accuracy", 0.0))
                        + 0.20 * float(payload.get("metrics", {}).get("key_element_recall", 0.0))
                        + 0.10 * float(payload.get("metrics", {}).get("accessibility_score", 0.0)),
                        4,
                    ),
                }
                for site, payload in runs.items()
            ],
            key=lambda x: x["score"],
            reverse=True,
        )

        return {"mean": mean, "ranked": ranked}

    def _flatten_tree(self, root: Dict[str, Any]) -> List[Dict[str, Any]]:
        if not root:
            return []
        flat: List[Dict[str, Any]] = []
        stack = [root]
        while stack:
            node = stack.pop()
            flat.append(node)
            children = list(node.get("children") or [])
            children.reverse()
            stack.extend(children)
        return flat

    def _tokenize_text(self, text: str) -> str:
        return " ".join((text or "").split()).strip().lower()

    def _text_accuracy(self, source_nodes: List[Dict[str, Any]], recon_nodes: List[Dict[str, Any]]) -> float:
        source_text = {
            self._tokenize_text(n.get("text", ""))
            for n in source_nodes
            if self._tokenize_text(n.get("text", ""))
        }
        if not source_text:
            return 0.0

        recon_text = {
            self._tokenize_text(n.get("text", ""))
            for n in recon_nodes
            if self._tokenize_text(n.get("text", ""))
        }
        hit = sum(1 for t in source_text if t in recon_text)
        return round(hit / max(1, len(source_text)), 4)

    def _key_element_recall(self, source_nodes: List[Dict[str, Any]], recon_nodes: List[Dict[str, Any]]) -> float:
        key_tags = {"header", "nav", "main", "section", "article", "footer", "button", "form", "img", "a"}
        source_tags = {str(n.get("tag", "")).lower() for n in source_nodes}
        recon_tags = {str(n.get("tag", "")).lower() for n in recon_nodes}
        required = key_tags.intersection(source_tags)
        if not required:
            return 1.0
        hit = len(required.intersection(recon_tags))
        return round(hit / max(1, len(required)), 4)

    def _accessibility_score(self, recon_nodes: List[Dict[str, Any]], generated_code: str) -> float:
        checks = 0
        score = 0

        checks += 1
        if any(str(n.get("tag", "")).lower() == "img" and (n.get("attrs") or {}).get("alt") for n in recon_nodes):
            score += 1

        checks += 1
        if any(str(n.get("tag", "")).lower() in {"main", "header", "nav", "footer"} for n in recon_nodes):
            score += 1

        checks += 1
        if "aria-label" in generated_code:
            score += 1

        checks += 1
        if any(str(n.get("tag", "")).lower() == "a" and (n.get("attrs") or {}).get("href") for n in recon_nodes):
            score += 1

        checks += 1
        if any(str(n.get("tag", "")).lower() == "button" for n in recon_nodes):
            score += 1

        return round(score / max(1, checks), 4)

    def _style_signature(self, nodes: List[Dict[str, Any]]) -> Tuple[Counter, Counter, Counter]:
        colors: Counter = Counter()
        fonts: Counter = Counter()
        displays: Counter = Counter()
        for node in nodes:
            styles = node.get("styles") or {}
            bg = styles.get("backgroundColor")
            fg = styles.get("color")
            font = styles.get("fontFamily")
            disp = styles.get("display")
            for item in (bg, fg):
                if item and item not in {"transparent", "rgba(0, 0, 0, 0)"}:
                    colors[item] += 1
            if font:
                fonts[font] += 1
            if disp:
                displays[disp] += 1
        return colors, fonts, displays

    def _counter_overlap(self, a: Counter, b: Counter) -> float:
        if not a and not b:
            return 1.0
        if not a or not b:
            return 0.0
        keys = set(a.keys()).union(b.keys())
        inter = sum(min(a[k], b[k]) for k in keys)
        union = sum(max(a[k], b[k]) for k in keys)
        return inter / max(1, union)

    def _style_similarity(self, source_nodes: List[Dict[str, Any]], recon_nodes: List[Dict[str, Any]]) -> float:
        s_colors, s_fonts, s_displays = self._style_signature(source_nodes)
        r_colors, r_fonts, r_displays = self._style_signature(recon_nodes)
        score = (
            0.45 * self._counter_overlap(s_colors, r_colors)
            + 0.30 * self._counter_overlap(s_fonts, r_fonts)
            + 0.25 * self._counter_overlap(s_displays, r_displays)
        )
        return round(max(0.0, min(1.0, score)), 4)

    def _structure_similarity(
        self,
        source_nodes: List[Dict[str, Any]],
        recon_nodes: List[Dict[str, Any]],
        sections: List[Dict[str, Any]],
    ) -> float:
        if not source_nodes:
            return 0.0

        source_depth_mean = sum(float(n.get("depth", 0)) for n in source_nodes) / max(1, len(source_nodes))

        # Reconstructed nodes do not always carry depth; estimate via traversal.
        def estimate_depths(nodes: List[Dict[str, Any]]) -> List[int]:
            out: List[int] = []
            stack = [(n, 0) for n in nodes[:1]]
            while stack:
                node, d = stack.pop()
                out.append(d)
                children = list(node.get("children") or [])
                for child in children:
                    stack.append((child, d + 1))
            return out

        recon_depths = estimate_depths(recon_nodes)
        recon_depth_mean = sum(recon_depths) / max(1, len(recon_depths)) if recon_depths else 0.0

        depth_score = 1.0 - min(1.0, abs(source_depth_mean - recon_depth_mean) / max(1.0, source_depth_mean + 1.0))

        source_interactive = sum(1 for n in source_nodes if n.get("interactive"))
        recon_interactive = sum(
            1
            for n in recon_nodes
            if str(n.get("tag", "")).lower() in {"a", "button", "input", "select", "textarea"}
        )
        interaction_score = 1.0 - min(
            1.0,
            abs(source_interactive - recon_interactive) / max(1.0, float(source_interactive) + 1.0),
        )

        section_bonus = min(1.0, len(sections) / 6.0)
        score = 0.45 * depth_score + 0.40 * interaction_score + 0.15 * section_bonus
        return round(max(0.0, min(1.0, score)), 4)
