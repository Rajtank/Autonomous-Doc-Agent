from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class AgentRequest(BaseModel):
    request: str = Field(..., min_length=5, max_length=2000)


class TableData(BaseModel):
    caption: Optional[str] = None
    headers: list[str]
    rows: list[list[str]]


class Section(BaseModel):
    heading: str
    content: str
    table: Optional[TableData] = None


class Plan(BaseModel):
    doc_type: str
    title: str
    assumptions: list[str] = Field(default_factory=list)
    outline: list[str]


class Critique(BaseModel):
    score: int = Field(..., ge=1, le=10)
    feedback: str
    sections_to_revise: list[str] = Field(default_factory=list)


class AgentResponse(BaseModel):
    message: str
    plan: Plan
    critique: Critique
    revised: bool
    download_url: str
