
# Backend
- FastAPI + Playwright
- OpenAI GPT-4 Vision via `openai` SDK
## Setup
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install
cp .env.example .env  # put your key
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```
