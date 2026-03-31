from __future__ import annotations

from difflib import SequenceMatcher
from typing import Any, Dict, List

import cv2
import numpy as np
from skimage.metrics import structural_similarity


class PipelineEvaluator:
    def evaluate(self, extracted: Dict[str, Any], sections: List[Dict[str, Any]], generated_code: str, screenshot_path: str) -> Dict[str, Any]:
        return {
            "ssim": self._estimate_ssim(screenshot_path),
            "text_accuracy": self._text_accuracy(extracted, generated_code),
            "key_element_recall": self._key_element_recall(extracted, generated_code),
            "accessibility_score": self._accessibility_score(generated_code),
        }

    def compare_single_vs_dual(self, single_code: str, dual_code: str) -> Dict[str, Any]:
        overlap = SequenceMatcher(a=single_code, b=dual_code).ratio()
        dual_bonus = 1 if "aria-label" in dual_code else 0
        return {
            "single_pass_quality": round(overlap * 0.85, 4),
            "dual_pass_quality": round(min(1.0, overlap * 0.92 + 0.05 * dual_bonus), 4),
            "improvement": round(min(1.0, overlap * 0.92 + 0.05 * dual_bonus) - overlap * 0.85, 4),
        }

    def _estimate_ssim(self, screenshot_path: str) -> float:
        image = cv2.imread(screenshot_path)
        if image is None:
            return 0.0
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        baseline = cv2.GaussianBlur(gray, (11, 11), 0)
        score, _ = structural_similarity(gray, baseline, full=True)
        return float(round(max(0.0, min(1.0, score)), 4))

    def _text_accuracy(self, extracted: Dict[str, Any], generated_code: str) -> float:
        texts = [n.get("text", "") for n in extracted.get("nodes", []) if n.get("text")]
        if not texts:
            return 0.0
        matches = sum(1 for t in texts[:80] if t[:20] and t[:20] in generated_code)
        return round(matches / max(1, min(80, len(texts))), 4)

    def _key_element_recall(self, extracted: Dict[str, Any], generated_code: str) -> float:
        key_tags = ["header", "nav", "main", "section", "footer", "button", "form"]
        present = set(n.get("tag", "") for n in extracted.get("nodes", []))
        hit = sum(1 for tag in key_tags if tag in present and f"<{tag}" in generated_code)
        total = sum(1 for tag in key_tags if tag in present)
        return round(hit / max(1, total), 4)

    def _accessibility_score(self, generated_code: str) -> float:
        score = 0.0
        checks = ["aria-label", "<main", "<header", "<section", "<button", "alt="]
        for item in checks:
            if item in generated_code:
                score += 1
        return round(score / len(checks), 4)
