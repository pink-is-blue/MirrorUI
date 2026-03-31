from __future__ import annotations

from typing import Any, Dict, List

import cv2
import numpy as np

from mirrorui.schemas import VisualRegion


class VisionProcessor:
    def segment(self, screenshot_path: str) -> List[VisualRegion]:
        image = cv2.imread(screenshot_path)
        if image is None:
            return []

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blur, 40, 140)
        kernel = np.ones((5, 5), np.uint8)
        closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel, iterations=2)
        contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        h, w = image.shape[:2]
        regions: List[VisualRegion] = []
        for idx, contour in enumerate(contours[:200]):
            x, y, cw, ch = cv2.boundingRect(contour)
            area_ratio = (cw * ch) / max(1, w * h)
            if area_ratio < 0.002:
                continue
            role = "content"
            if y < h * 0.18:
                role = "header"
            elif y + ch > h * 0.86:
                role = "footer"
            elif cw > w * 0.75 and ch > h * 0.18:
                role = "hero"
            regions.append(
                VisualRegion(
                    region_id=f"vr_{idx}",
                    role=role,
                    x=x,
                    y=y,
                    w=cw,
                    h=ch,
                    score=float(area_ratio),
                )
            )

        if not regions:
            regions.append(VisualRegion(region_id="vr_0", role="content", x=0, y=0, w=w, h=h, score=1.0))
        return regions

    def extract_patch_features(self, screenshot_path: str, regions: List[VisualRegion]) -> Dict[str, List[float]]:
        image = cv2.imread(screenshot_path)
        if image is None:
            return {}
        features: Dict[str, List[float]] = {}
        for region in regions:
            patch = image[region.y : region.y + region.h, region.x : region.x + region.w]
            if patch.size == 0:
                continue
            mean = patch.mean(axis=(0, 1))
            std = patch.std(axis=(0, 1))
            features[region.region_id] = [
                float(region.w),
                float(region.h),
                float(region.score),
                float(mean[0]),
                float(mean[1]),
                float(mean[2]),
                float(std[0]),
                float(std[1]),
                float(std[2]),
            ]
        return features
