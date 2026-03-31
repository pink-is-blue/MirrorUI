# MIRRORUI: Hybrid Vision-AI for Editable Website Interface Reconstruction

## Stack
- Backend: FastAPI, Python, Playwright, BeautifulSoup, OpenCV, PyTorch
- Frontend: React, Tailwind CSS, Vite
- AI pipeline: visual + DOM fusion, layout graph, transformer latent encoder, proposer-verifier dual pass

## Project Structure
```text
mirrorui/
	models/
		transformer.py
	services/
		renderer.py
		extractor.py
		vision.py
		layout_graph.py
		segmenter.py
		templatizer.py
		generator.py
		evaluator.py
		editor.py
	pipeline.py
	schemas.py
	state.py
main.py
run_pipeline_example.py
src/
	main.jsx
	index.css
	components/generated/
workspace/
	screens/
	generated/
```

## Install
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
npm install
```

## Run
```bash
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
npm run dev -- --host 0.0.0.0 --port 5173
```

## API
- `POST /api/generate` body: `{ "url": "https://example.com" }`
- `GET /api/layout`
- `GET /api/code`
- `POST /api/editor/update-node`
- `GET /api/evaluate`
- `GET /api/export`

## Example Pipeline Run
```bash
python run_pipeline_example.py https://example.com
```

## Editable Interface Workflow
1. Open `http://localhost:5173`
2. Generate from URL
3. Click element in preview (`data-mirror-id`)
4. Edit text/link/image/classes in editor panel
5. Apply edit to regenerate React + Tailwind code
6. Inspect updated output in code panel and files under `src/components/generated`

## Output
- Pixel-close reconstruction workflow with DOM + screenshot alignment
- Reusable generated React components and Tailwind classes
- Dual-pass proposer-verifier refinement
- Evaluation metrics: SSIM, text accuracy, key-element recall, accessibility score
- Single-pass vs dual-pass quality comparison
