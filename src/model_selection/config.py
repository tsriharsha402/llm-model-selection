"""Candidates, decision rule and benchmark cases."""

from __future__ import annotations

import json
import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Candidate:
    name: str
    model: str
    effort: str | None = None
    note: str = ""


@dataclass(frozen=True)
class DecisionRule:
    min_abstention_accuracy: float = 0.80
    min_citation_accuracy: float = 0.90
    max_failure_rate: float = 0.02
    max_p95_latency_seconds: float = 10.0
    non_inferiority_margin: float = 0.05
    bootstrap_resamples: int = 2000
    seed: int = 7
    baseline: str = ""  # the configuration production runs today


@dataclass(frozen=True)
class Source:
    chunk_id: str
    doc_id: str
    title: str
    section: str
    text: str


@dataclass(frozen=True)
class Case:
    id: str
    question: str
    expected_behavior: str  # "answer" | "abstain"
    sources: list[Source]
    expected_doc: str | None = None
    expected_keywords: list[str] = field(default_factory=list)


def load_config(path: Path) -> tuple[list[Candidate], DecisionRule]:
    data = tomllib.loads(path.read_text())
    candidates = [Candidate(**entry) for entry in data["candidate"]]
    names = [c.name for c in candidates]
    if len(set(names)) != len(names):
        raise ValueError("Candidate names must be unique")
    return candidates, DecisionRule(**data.get("decision", {}))


def load_cases(path: Path) -> list[Case]:
    cases = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                raw = json.loads(line)
                raw["sources"] = [Source(**s) for s in raw["sources"]]
                cases.append(Case(**raw))
    return cases
