from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from mirrorui.models.transformer import HybridVisionDomTransformer
from mirrorui.models.layout_gnn import LayoutGraphEncoder
from mirrorui.schemas import EditorUpdateRequest, GenerationResult
from mirrorui.services.editor import LayoutEditor
from mirrorui.services.evaluator import PipelineEvaluator
from mirrorui.services.extractor import DomCssExtractor
from mirrorui.services.generator import ProposerVerifierGenerator
from mirrorui.services.layout_graph import LayoutGraphBuilder
from mirrorui.services.renderer import PlaywrightRenderer
from mirrorui.services.segmenter import ComponentSegmenter
from mirrorui.services.templatizer import ActionTemplatizer
from mirrorui.services.vision import VisionProcessor
from mirrorui.state import WorkspaceState


class MirrorPipeline:
    def __init__(self, root: Path):
        self.root = root
        self.state = WorkspaceState(root)

        self.renderer = PlaywrightRenderer()
        self.extractor = DomCssExtractor()
        self.vision = VisionProcessor()
        self.graph_builder = LayoutGraphBuilder()
        self.segmenter = ComponentSegmenter()
        self.templatizer = ActionTemplatizer()
        self.generator = ProposerVerifierGenerator()
        self.evaluator = PipelineEvaluator()
        self.transformer = HybridVisionDomTransformer(in_dim=64)
        self.gnn = LayoutGraphEncoder(in_dim=32, hidden_dim=64)
        self.editor = LayoutEditor(self.generator)

    async def run(self, url: str) -> GenerationResult:
        shot_path = self.state.screens_dir / "page.png"
        capture = await self.renderer.capture(url=url, screenshot_path=shot_path)
        extracted = self.extractor.extract(capture)

        visual_regions = self.vision.segment(extracted["screenshot_path"])
        patch_features = self.vision.extract_patch_features(extracted["screenshot_path"], visual_regions)

        graph = self.graph_builder.build(extracted, visual_regions)
        sections = self.segmenter.segment(extracted)
        actions = self.templatizer.to_actions(extracted, sections)

        # Build fused feature vectors for the transformer latent summary.
        fused = []
        for region in visual_regions[:32]:
            vector = patch_features.get(region.region_id, [0.0] * 9)
            while len(vector) < 64:
                vector.append(0.0)
            fused.append(vector[:64])
        latent = self.transformer.infer_action_latent(fused)

        graph_vectors = []
        for node in graph.nodes[:128]:
            box = node.get("box", {})
            graph_vectors.append([
                float(len(node.get("id", ""))),
                float(len(node.get("type", ""))),
                float(len(node.get("tag", ""))),
                float(box.get("x", 0.0)),
                float(box.get("y", 0.0)),
                float(box.get("width", 0.0)),
                float(box.get("height", 0.0)),
            ])
        gnn_rows = [row + ([0.0] * (32 - len(row))) for row in graph_vectors]
        graph_latent = self.gnn.encode(gnn_rows)

        candidates = self.generator.generate_candidates(extracted, sections, actions)
        verified = self.generator.verify_and_select(candidates, extracted, sections)

        single_code = candidates[0].files.get("src/components/generated/AppBody.jsx", "")
        dual_code = verified["files"].get("src/components/generated/AppBody.jsx", "")

        selected_meta = verified["files"].get("src/components/generated/generation.meta.js", "")
        page_model = self._extract_page_model(selected_meta)

        metrics = self.evaluator.evaluate(
            extracted=extracted,
            sections=[section.model_dump() for section in sections],
            generated_code=dual_code,
            page_model=page_model,
        )
        comparison = self.evaluator.compare_single_vs_dual(single_code=single_code, dual_code=dual_code)

        warnings = []
        if extracted.get("challenge_detected"):
            warnings.append("Potential bot challenge detected. Reconstruction may be partial.")
        if metrics.get("ssim", 0.0) < 0.45:
            warnings.append("Low visual similarity. Try regenerating or using a less protected URL path.")

        layout_payload: Dict[str, Any] = {
            "title": extracted.get("title", ""),
            "url": url,
            "nodes": extracted.get("nodes", []),
            "sections": [section.model_dump() for section in sections],
            "actions": [action.model_dump() for action in actions],
            "layout_graph": graph.model_dump(),
            "visual_regions": [region.model_dump() for region in visual_regions],
            "latent": latent,
            "graph_latent": graph_latent,
        }

        self.state.save_layout(layout_payload)
        self.state.save_meta({"title": extracted.get("title", ""), "url": url, "metrics": metrics, "comparison": comparison})

        return GenerationResult(
            title=extracted.get("title", ""),
            screenshot_path=extracted["screenshot_path"],
            files=verified["files"],
            layout=layout_payload,
            actions=actions,
            comparison=comparison,
            metrics=metrics,
            warnings=warnings,
            challenge_detected=bool(extracted.get("challenge_detected")),
            challenge_reason=str(extracted.get("challenge_reason", "")),
        )

    async def run_benchmark(self, sites: Dict[str, str]) -> Dict[str, Any]:
        runs: Dict[str, Dict[str, Any]] = {}
        for site_name, site_url in sites.items():
            try:
                result = await self.run(site_url)
                runs[site_name] = {
                    "url": site_url,
                    "ok": True,
                    "title": result.title,
                    "metrics": result.metrics,
                    "comparison": result.comparison,
                    "warnings": result.warnings,
                    "challenge_detected": result.challenge_detected,
                }
            except Exception as exc:
                runs[site_name] = {
                    "url": site_url,
                    "ok": False,
                    "error": str(exc),
                    "metrics": {},
                    "comparison": {},
                    "warnings": ["Benchmark run failed."],
                    "challenge_detected": False,
                }

        summary = self.evaluator.summarize_benchmark(runs)
        return {"runs": runs, "summary": summary}

    def apply_editor_update(self, req: EditorUpdateRequest) -> Dict[str, Any]:
        layout_payload = self.state.load_layout()
        if not layout_payload:
            raise ValueError("No generated layout found")

        result = self.editor.update_node(
            layout_payload=layout_payload,
            node_id=req.node_id,
            text=req.text,
            href=req.href,
            image_src=req.image_src,
            class_name=req.class_name,
        )
        self.state.save_layout(layout_payload)
        return result

    def _extract_page_model(self, generation_meta_code: str) -> Dict[str, Any]:
        marker = "export const pageData = "
        idx = generation_meta_code.find(marker)
        if idx < 0:
            return {}
        content = generation_meta_code[idx + len(marker):].strip()
        if content.endswith(";"):
            content = content[:-1]
        try:
            import json

            return json.loads(content)
        except Exception:
            return {}
