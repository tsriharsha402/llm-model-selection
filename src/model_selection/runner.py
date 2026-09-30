"""Run every case against every candidate and append raw results to a JSONL file.

Runs are resumable: re-running with the same output file skips (candidate, case)
pairs that already succeeded and retries the ones that errored.
"""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import anthropic

from model_selection.config import Candidate, Case
from model_selection.prompt import ABSTAIN_MESSAGE, PROMPT_VERSION, build_request


@dataclass
class Record:
    candidate: str
    model: str
    case_id: str
    prompt_version: str
    answer: str = ""
    cited_sources: list[int] = field(default_factory=list)
    abstained: bool = False
    refused: bool = False
    error: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    latency_seconds: float = 0.0


def call_model(client: Any, candidate: Candidate, case: Case, clock: Callable[[], float]) -> Record:
    record = Record(
        candidate=candidate.name,
        model=candidate.model,
        case_id=case.id,
        prompt_version=PROMPT_VERSION,
    )
    started = clock()
    try:
        response = client.messages.create(**build_request(candidate, case))
    except anthropic.APIError as exc:
        # The SDK has already retried 429s, 5xx and connection errors with backoff.
        record.error = f"{type(exc).__name__}: {exc}"
        record.latency_seconds = clock() - started
        return record
    record.latency_seconds = clock() - started
    record.input_tokens = response.usage.input_tokens
    record.output_tokens = response.usage.output_tokens

    if response.stop_reason == "refusal":
        record.refused = True
        return record

    parts = []
    for block in response.content:
        if block.type != "text":
            continue
        parts.append(block.text)
        for citation in block.citations or []:
            if (
                citation.type == "search_result_location"
                and citation.search_result_index not in record.cited_sources
            ):
                record.cited_sources.append(citation.search_result_index)
    record.answer = "".join(parts).strip()
    record.abstained = record.answer.startswith(ABSTAIN_MESSAGE)
    return record


def load_records(path: Path) -> list[Record]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as handle:
        return [Record(**json.loads(line)) for line in handle if line.strip()]


def run_benchmark(
    client: Any,
    candidates: list[Candidate],
    cases: list[Case],
    out_path: Path,
    workers: int = 4,
    clock: Callable[[], float] = time.perf_counter,
    progress: Callable[[Record], None] | None = None,
) -> list[Record]:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    done = {(r.candidate, r.case_id) for r in load_records(out_path) if r.error is None}
    todo = [(c, case) for c in candidates for case in cases if (c.name, case.id) not in done]
    lock = threading.Lock()

    with ThreadPoolExecutor(max_workers=workers) as pool, out_path.open("a") as out:
        futures = [pool.submit(call_model, client, c, case, clock) for c, case in todo]
        for future in as_completed(futures):
            record = future.result()
            with lock:
                out.write(json.dumps(asdict(record)) + "\n")
                out.flush()
            if progress:
                progress(record)
    return latest_records(load_records(out_path))


def latest_records(records: list[Record]) -> list[Record]:
    """Keep one record per (candidate, case): a success wins over earlier errors."""
    latest: dict[tuple[str, str], Record] = {}
    for record in records:
        key = (record.candidate, record.case_id)
        if key not in latest or latest[key].error is not None:
            latest[key] = record
    return list(latest.values())
