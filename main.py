
import os, base64, pathlib, shutil
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from playwright_utils import capture
from openai_client import gpt_generate
from code_postprocess import split_files
from zipper import zip_bytes

ROOT = pathlib.Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"
WORK = ROOT / "workspace"; (WORK / "screens").mkdir(parents=True, exist_ok=True)

app = FastAPI(title="MirrorUI API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

class Req(BaseModel): url: str

@app.post("/api/generate")
async def generate(req: Req):
    url = req.url.strip()
    if not (url.startswith("http://") or url.startswith("https://")):
        return JSONResponse({"error":"Use full http(s):// URL"}, status_code=400)
    shot_path = str(WORK / "screens" / "page.png")
    html, shot, title = await capture(url, screenshot_path=shot_path)
    with open(shot, "rb") as f: b64 = base64.b64encode(f.read()).decode("utf-8")
    raw = gpt_generate(html, b64)
    files = split_files(raw)

    gen_root = FRONTEND / "src" / "components" / "generated"
    if gen_root.exists(): shutil.rmtree(gen_root)
    os.makedirs(gen_root, exist_ok=True)

    written = []
    for rel, code in files.items():
        relp = rel[4:] if rel.startswith("src/") else rel
        tgt = FRONTEND / "src" / relp
        os.makedirs(tgt.parent, exist_ok=True)
        with open(tgt, "w", encoding="utf-8") as f: f.write(code)
        written.append(str(tgt.relative_to(FRONTEND)))
    # simple barrel
    with open(gen_root / "index.js", "w", encoding="utf-8") as f:
        f.write("// generated components exported here dynamically
")
    return {"ok": True, "title": title, "written": written}

@app.get("/api/export")
async def export_zip():
    data = zip_bytes(str(FRONTEND), skip=["node_modules","dist"])
    return StreamingResponse(iter([data]), media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="MirrorUI-export.zip"'})
