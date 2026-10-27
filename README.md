# Autonomous Document Agent

A FastAPI service that takes a natural-language business request and
produces a Microsoft Word (`.docx`) document end-to-end.

Pipeline: **plan -> execute -> reflect -> (revise) -> .docx**

The mandatory engineering improvement is **reflection / self-check**:
after the first draft is assembled, a reviewer LLM scores it against
the original request and triggers a targeted re-draft of weak sections.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
# edit .env and paste your GROQ_API_KEY
```

## Run

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

Open `http://localhost:8000/docs` for Swagger UI.

## Test cases

**Simple:**
```json
{"request": "Create an SOP for onboarding new software engineers."}
```

**Ambiguous:**
```json
{"request": "Write a proposal for an AI chatbot project."}
```

The response includes `plan`, `critique`, `revised`, and a
`download_url` pointing to the generated `.docx`.

## Project layout

```
app/
  main.py       FastAPI app, /agent and /download routes
  agent.py      plan -> execute -> reflect -> revise
  llm.py        Groq client, retry, model fallback
  docgen.py    python-docx builder
  schemas.py    Pydantic models
project_notes.md  architecture, decisions, demo script, tradeoffs
```

Author: Raj Tank (`rajtank2207@gmail.com`)
