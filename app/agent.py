"""Autonomous document agent.

Pipeline:
    plan     -> pick doc_type, title, assumptions, outline
    execute  -> draft each section (one LLM call per heading)
    reflect  -> score the draft 1-10 against the request
    revise   -> re-draft only the sections the reviewer flagged
"""
from __future__ import annotations

import logging

from .llm import ask_json
from .schemas import Critique, Plan, Section, TableData

log = logging.getLogger(__name__)

REFLECTION_THRESHOLD = 8  # revise if the reviewer scores below this


PLAN_PROMPT = """You plan business documents.

Pick a doc_type (proposal, project_plan, sop, business_report,
technical_design, product_spec, or meeting_minutes), a specific title,
any assumptions you need to make (budget, timeline, team size, client
name if missing), and an outline of 3-5 section headings.

Return a JSON object only. No prose, no markdown.

Schema:
{
  "doc_type": "...",
  "title": "...",
  "assumptions": ["..."],
  "outline": ["Heading 1", "Heading 2", ...]
}
"""


SECTION_PROMPT = """You write one section of a {doc_type}.

Produce 150-300 words of concrete prose with specific names, dates,
dollar amounts, or metrics. If a table fits (timeline, budget, roles,
risks), include one.

Return a JSON object only.

Schema:
{{
  "content": "...",
  "table": null OR {{"caption": "...", "headers": ["..."], "rows": [["..."]]}}
}}
"""


REFLECT_PROMPT = """You review a draft against the original request.

Score 1-10 (10 = specific and complete, 1 = off-topic). Flag any
section that is vague, misses a request detail, or lacks concrete data.

Return a JSON object only.

Schema:
{
  "score": 1-10,
  "feedback": "one paragraph",
  "sections_to_revise": ["Exact Heading", ...]
}
"""


def plan(request: str) -> Plan:
    data = ask_json(PLAN_PROMPT, f"REQUEST:\n{request}", temperature=0.4)
    p = Plan(**data)
    log.info("plan: %s | %d sections", p.doc_type, len(p.outline))
    return p


def draft_section(request: str, p: Plan, heading: str, feedback: str = "") -> Section:
    """Draft one section. If feedback is given, use it to improve the rewrite."""
    assumptions = "\n- ".join(p.assumptions) if p.assumptions else "(none)"
    user = (
        f"REQUEST:\n{request}\n\n"
        f"ASSUMPTIONS:\n- {assumptions}\n\n"
        f"HEADING: {heading}"
    )
    if feedback:
        user += f"\n\nREVIEWER FEEDBACK (address this):\n{feedback}"

    data = ask_json(SECTION_PROMPT.format(doc_type=p.doc_type), user, temperature=0.4)

    table = None
    if data.get("table"):
        try:
            table = TableData(**data["table"])
        except Exception:
            log.warning("dropping malformed table for '%s'", heading)

    return Section(
        heading=heading,
        content=data.get("content", "").strip(),
        table=table,
    )


def execute(request: str, p: Plan) -> list[Section]:
    """Draft every section in the outline, one at a time."""
    sections: list[Section] = []
    for heading in p.outline:
        try:
            s = draft_section(request, p, heading)
            log.info("draft: %s (%d words)", heading, len(s.content.split()))
        except Exception:
            log.exception("draft failed for %s", heading)
            s = Section(heading=heading, content="[section unavailable]")
        sections.append(s)
    return sections


def reflect(request: str, sections: list[Section]) -> Critique:
    """Score the assembled draft against the original request."""
    draft = "\n\n".join(f"## {s.heading}\n{s.content}" for s in sections)
    data = ask_json(
        REFLECT_PROMPT,
        f"ORIGINAL REQUEST:\n{request}\n\nDRAFT:\n{draft}",
        temperature=0.2,
    )
    c = Critique(**data)
    log.info("reflect: score=%d | revise=%d", c.score, len(c.sections_to_revise))
    return c


def revise(request: str, p: Plan, sections: list[Section], c: Critique) -> list[Section]:
    """Re-draft only the sections the reviewer flagged."""
    flagged = {h.strip().lower() for h in c.sections_to_revise}
    result: list[Section] = []
    for s in sections:
        if s.heading.strip().lower() in flagged:
            try:
                log.info("revise: %s", s.heading)
                result.append(draft_section(request, p, s.heading, feedback=c.feedback))
                continue
            except Exception:
                log.exception("revise failed for %s", s.heading)
        result.append(s)
    return result


def run_agent(request: str) -> dict:
    """Full pipeline: plan -> execute -> reflect -> maybe revise."""
    p = plan(request)
    sections = execute(request, p)
    critique = reflect(request, sections)

    revised = critique.score < REFLECTION_THRESHOLD or bool(critique.sections_to_revise)
    if revised:
        sections = revise(request, p, sections, critique)

    return {
        "plan": p,
        "sections": sections,
        "critique": critique,
        "revised": revised,
    }
