"""FastAPI app. One POST endpoint, one GET for downloading the output docx."""
from __future__ import annotations

import logging
import os
import uuid
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, RedirectResponse

load_dotenv()

from .agent import run_agent
from .docgen import build_docx
from .schemas import AgentRequest, AgentResponse

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)
log = logging.getLogger(__name__)

DOCS_DIR = Path(os.getenv("DOCS_DIR", "generated_docs"))
DOCS_DIR.mkdir(exist_ok=True)

app = FastAPI(
    title="Autonomous Document Agent",
    version="1.0.0",
    description="plan -> execute -> reflect -> revise -> .docx",
)


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse(url="/docs")


@app.get("/healthz")
def health() -> dict:
    return {"status": "ok"}


@app.post("/agent", response_model=AgentResponse)
def agent_endpoint(req: AgentRequest) -> AgentResponse:
    log.info("request: %s", req.request[:160])

    try:
        result = run_agent(req.request)
        docx_bytes = build_docx(result["plan"], result["sections"])
    except Exception as e:
        log.exception("pipeline failed")
        raise HTTPException(status_code=500, detail=str(e)) from e

    plan = result["plan"]
    critique = result["critique"]

    doc_id = uuid.uuid4().hex[:12]
    (DOCS_DIR / f"{plan.doc_type}_{doc_id}.docx").write_bytes(docx_bytes)

    if result["revised"]:
        message = (
            f"Produced '{plan.title}'. Reflection scored {critique.score}/10 "
            f"and revised {len(critique.sections_to_revise)} section(s)."
        )
    else:
        message = f"Produced '{plan.title}'. Reflection passed with score {critique.score}/10."

    return AgentResponse(
        message=message,
        plan=plan,
        critique=critique,
        revised=result["revised"],
        download_url=f"/download/{doc_id}",
    )


@app.get("/download/{doc_id}")
def download(doc_id: str) -> FileResponse:
    matches = list(DOCS_DIR.glob(f"*_{doc_id}.docx"))
    if not matches:
        raise HTTPException(status_code=404, detail="document not found")
    return FileResponse(
        matches[0],
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=matches[0].name,
    )
