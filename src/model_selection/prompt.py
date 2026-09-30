"""The request under test.

Mirrors production-rag-service's system prompt and message layout, so the benchmark
measures what production would actually send. PROMPT_VERSION is recorded with every
result; results from different prompt versions must not be compared.
"""

from __future__ import annotations

import hashlib
from typing import Any

from model_selection.config import Candidate, Case

ABSTAIN_MESSAGE = "I don't know based on the available documents."

SYSTEM_PROMPT = f"""You are an internal knowledge assistant. Employees ask questions and you \
answer using only the search results attached to their message.

- Ground every statement in the search results and cite them. Do not use outside knowledge.
- If the search results do not answer the question, reply with exactly "{ABSTAIN_MESSAGE}" \
followed by one sentence on what information is missing.
- Lead with the direct answer, then add only the details the employee needs to act on it.
- Keep answers under 120 words. Use plain sentences; no headings."""

PROMPT_VERSION = hashlib.sha256(SYSTEM_PROMPT.encode()).hexdigest()[:8]
MAX_OUTPUT_TOKENS = 16000


def build_request(candidate: Candidate, case: Case) -> dict[str, Any]:
    content: list[dict[str, Any]] = [
        {
            "type": "search_result",
            "source": source.chunk_id,
            "title": f"{source.title} > {source.section}",
            "content": [{"type": "text", "text": source.text}],
            "citations": {"enabled": True},
        }
        for source in case.sources
    ]
    content.append({"type": "text", "text": case.question})
    request: dict[str, Any] = {
        "model": candidate.model,
        "max_tokens": MAX_OUTPUT_TOKENS,
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": content}],
    }
    if candidate.effort:
        request["output_config"] = {"effort": candidate.effort}
    return request
