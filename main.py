
import os
import uuid
import pathlib
import shutil
import asyncio
import traceback
from typing import Any, Dict

from fastapi import BackgroundTasks, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from mirrorui.pipeline import MirrorPipeline
from mirrorui.schemas import BenchmarkRequest, EditorUpdateRequest, GenerateRequest
from zipper import zip_bytes

ROOT = pathlib.Path(__file__).resolve().parent
FRONTEND = ROOT
WORK = ROOT / "workspace"
(WORK / "screens").mkdir(parents=True, exist_ok=True)
(WORK / "generated").mkdir(parents=True, exist_ok=True)

pipeline = MirrorPipeline(ROOT)

# In-memory job store: job_id -> {status, result, error}
_JOBS: Dict[str, Dict[str, Any]] = {}

app = FastAPI(title="MirrorUI API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


async def _run_generation_job(job_id: str, url: str) -> None:
    """Background task: run pipeline and write files, then update job store."""
    try:
        result = await asyncio.wait_for(pipeline.run(url), timeout=120)

        written = []
        for rel, code in result.files.items():
            if rel.startswith("src/"):
                tgt = FRONTEND / rel
            elif rel.startswith("workspace/"):
                tgt = ROOT / rel
            else:
                tgt = ROOT / rel
            os.makedirs(tgt.parent, exist_ok=True)
            with open(tgt, "w", encoding="utf-8") as f:
                f.write(code)
            written.append(str(tgt.relative_to(FRONTEND)))

        gen_root = FRONTEND / "src" / "components" / "generated"
        with open(gen_root / "index.js", "w", encoding="utf-8") as f:
            f.write("export { default as AppBody } from './AppBody.jsx'\n")

        _JOBS[job_id] = {
            "status": "done",
            "ok": True,
            "title": result.title,
            "written": written,
            "screenshot": result.screenshot_path,
            "metrics": result.metrics,
            "comparison": result.comparison,
            "actions": [action.model_dump() for action in result.actions],
            "warnings": result.warnings,
            "challenge_detected": result.challenge_detected,
            "challenge_reason": result.challenge_reason,
        }
    except asyncio.TimeoutError:
        _JOBS[job_id] = {
            "status": "error",
            "error": "Capture timed out. The site may be blocking headless browsers or is too slow. Try a simpler URL.",
        }
    except Exception as exc:
        _JOBS[job_id] = {
            "status": "error",
            "error": str(exc),
            "trace": traceback.format_exc()[-800:],
        }


@app.get("/api/health")
async def health():
    return {"ok": True, "mode": "hybrid-vision-ai", "project": "MIRRORUI"}


@app.post("/api/generate")
async def generate(req: GenerateRequest, background_tasks: BackgroundTasks):
    url = req.url.strip()
    if not (url.startswith("http://") or url.startswith("https://")):
        return JSONResponse({"error": "Use full http(s):// URL"}, status_code=400)

    job_id = str(uuid.uuid4())
    _JOBS[job_id] = {"status": "running"}
    background_tasks.add_task(_run_generation_job, job_id, url)
    return {"ok": True, "job_id": job_id, "status": "running"}


@app.get("/api/job/{job_id}")
async def get_job(job_id: str):
    job = _JOBS.get(job_id)
    if job is None:
        return JSONResponse({"error": "Unknown job ID"}, status_code=404)
    return job


@app.get("/api/layout")
async def get_layout() -> Dict[str, Any]:
    payload = pipeline.state.load_layout()
    if not payload:
        return JSONResponse({"error": "No generated layout yet."}, status_code=404)
    return {"ok": True, "layout": payload}


@app.get("/api/page-data")
async def get_page_data() -> Dict[str, Any]:
    """Return the full pageData tree used by MirrorRenderer (width, height, root, etc.)."""
    path = pipeline.state.work_dir / "page_data.json"
    if not path.exists():
        return JSONResponse({"error": "No generated page data yet."}, status_code=404)
    import json as _json
    return {"ok": True, "pageData": _json.loads(path.read_text(encoding="utf-8"))}


@app.get("/api/code")
async def get_generated_code() -> Dict[str, Any]:
    generated_root = FRONTEND / "src" / "components" / "generated"
    files: Dict[str, str] = {}
    for name in ["AppBody.jsx", "SectionList.jsx", "generation.meta.js", "index.js"]:
        path = generated_root / name
        if path.exists():
            files[str(path.relative_to(FRONTEND))] = path.read_text(encoding="utf-8")
    runtime_path = FRONTEND / "src" / "components" / "runtime" / "MirrorRenderer.jsx"
    if runtime_path.exists():
        files[str(runtime_path.relative_to(FRONTEND))] = runtime_path.read_text(encoding="utf-8")
    return {"ok": True, "files": files}


@app.post("/api/editor/update-node")
async def update_node(req: EditorUpdateRequest):
    try:
        result = pipeline.apply_editor_update(req)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)

    written = []
    for rel, code in result["files"].items():
        if not rel.startswith("src/"):
            continue
        tgt = FRONTEND / rel
        os.makedirs(tgt.parent, exist_ok=True)
        with open(tgt, "w", encoding="utf-8") as f:
            f.write(code)
        written.append(str(tgt.relative_to(FRONTEND)))

    return {
        "ok": True,
        "updated_node": result["updated_node"],
        "written": written,
    }


@app.get("/api/evaluate")
async def evaluate_latest() -> Dict[str, Any]:
    meta = pipeline.state.load_meta()
    if not meta:
        return JSONResponse({"error": "No evaluation found. Generate first."}, status_code=404)
    return {"ok": True, "metrics": meta.get("metrics", {}), "comparison": meta.get("comparison", {})}


@app.post("/api/benchmark")
async def benchmark(req: BenchmarkRequest):
    # 3-tier suite requested by user: simple, medium, complex.
    defaults = {
        "simple_stripe": "https://stripe.com",
        "simple_notion": "https://www.notion.so",
        "medium_amazon": "https://www.amazon.com",
        "medium_bbc": "https://www.bbc.com",
        "complex_apple": "https://www.apple.com",
        "complex_airbnb": "https://www.airbnb.com",
    }
    sites = req.urls or defaults
    payload = await pipeline.run_benchmark(sites)
    return {"ok": True, **payload}


@app.get("/api/screenshot")
async def latest_screenshot():
    shot_path = WORK / "screens" / "page.png"
    if not shot_path.exists():
        return JSONResponse({"error": "No screenshot found. Generate first."}, status_code=404)
    return FileResponse(shot_path)

@app.get("/api/export")
async def export_zip():
    data = zip_bytes(str(FRONTEND), skip=["node_modules", "dist", "__pycache__"])
    return StreamingResponse(iter([data]), media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="MirrorUI-export.zip"'})
