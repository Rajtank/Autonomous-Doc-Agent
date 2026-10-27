"""Groq LLM client. One function: ask_json(system, user) -> dict.

Tries the primary model first. If it fails or returns unparseable
output, falls back to the bigger model.
"""
from __future__ import annotations

import json
import logging
import os
import re

from groq import Groq
from tenacity import retry, stop_after_attempt, wait_exponential

log = logging.getLogger(__name__)

PRIMARY_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
FALLBACK_MODEL = os.getenv("GROQ_FALLBACK_MODEL", "openai/gpt-oss-120b")

_client: Groq | None = None


def _groq() -> Groq:
    global _client
    if _client is None:
        key = os.getenv("GROQ_API_KEY")
        if not key:
            raise RuntimeError("GROQ_API_KEY is not set")
        _client = Groq(api_key=key)
    return _client


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10))
def _call(model: str, system: str, user: str, temperature: float) -> str:
    """Single Groq call. Tenacity retries on transient errors."""
    resp = _groq().chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=temperature,
        max_tokens=2000,
    )
    content = (resp.choices[0].message.content or "").strip()
    if not content:
        raise RuntimeError(f"{model} returned empty content")
    return content


def _parse(text: str) -> dict:
    """Parse JSON. Fall back to regex if the model wrapped it in prose."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise ValueError(f"no JSON object in: {text[:200]}")


def ask_json(system: str, user: str, temperature: float = 0.3) -> dict:
    """Ask the LLM for a JSON object. Primary model first, fallback on failure."""
    for model in (PRIMARY_MODEL, FALLBACK_MODEL):
        try:
            return _parse(_call(model, system, user, temperature))
        except Exception as e:
            log.warning("model=%s failed: %s", model, e)
    raise RuntimeError("all models failed to return parseable JSON")
