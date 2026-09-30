"""Deterministic grading: no LLM judge, so scores are reproducible and free to compute."""

from __future__ import annotations

from dataclasses import dataclass

from model_selection.config import Case
from model_selection.runner import Record


@dataclass(frozen=True)
class Grade:
    case_id: str
    expected_behavior: str
    failed: bool  # refusal or API error
    abstained: bool
    keyword_recall: float
    cited_expected_doc: bool
    passed: bool


def grade(record: Record, case: Case) -> Grade:
    failed = record.refused or record.error is not None
    answer = record.answer.lower()
    found = [kw for kw in case.expected_keywords if kw.lower() in answer]
    recall = len(found) / len(case.expected_keywords) if case.expected_keywords else 1.0
    cited_docs = {
        case.sources[i].doc_id for i in record.cited_sources if 0 <= i < len(case.sources)
    }
    cited_expected = case.expected_doc in cited_docs if case.expected_doc else False

    if failed:
        passed = False
    elif case.expected_behavior == "abstain":
        passed = record.abstained
    else:
        passed = not record.abstained and recall == 1.0 and cited_expected
    return Grade(
        case_id=case.id,
        expected_behavior=case.expected_behavior,
        failed=failed,
        abstained=record.abstained,
        keyword_recall=recall,
        cited_expected_doc=cited_expected,
        passed=passed,
    )
