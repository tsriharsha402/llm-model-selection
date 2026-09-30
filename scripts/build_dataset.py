"""Freeze the benchmark dataset from production-rag-service.

Runs the service's own retrieval for every question in its evaluation set and stores
the retrieved chunks with the question. Every candidate model then sees exactly the
same context, so the benchmark measures generation only.

Usage:
    python scripts/build_dataset.py --rag-repo ../production-rag-service
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--rag-repo", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=ROOT / "data" / "grounded_qa.jsonl")
    args = parser.parse_args()

    rag_repo = args.rag_repo.resolve()
    sys.path.insert(0, str(rag_repo / "src"))
    from rag_service.api import build_pipeline  # noqa: E402
    from rag_service.config import Settings  # noqa: E402

    settings = Settings(llm_provider="offline", corpus_dir=rag_repo / "data" / "handbook")
    pipeline = build_pipeline(settings)

    written = skipped = 0
    with (rag_repo / "evals" / "dataset.jsonl").open() as source, args.out.open("w") as out:
        for line in source:
            case = json.loads(line)
            hits = [
                hit
                for hit in pipeline.index.search(case["question"], pipeline.top_k)
                if hit.score >= pipeline.min_retrieval_score
            ]
            if not hits:
                # Production abstains without calling a model, so there is nothing to compare.
                skipped += 1
                continue
            sources = [
                {
                    "chunk_id": hit.chunk.chunk_id,
                    "doc_id": hit.chunk.doc_id,
                    "title": hit.chunk.title,
                    "section": hit.chunk.section,
                    "text": hit.chunk.text,
                }
                for hit in hits
            ]
            answer_in_context = case["answerable"] and any(
                s["doc_id"] == case.get("expected_doc") for s in sources
            )
            record = {
                "id": case["id"],
                "question": case["question"],
                "expected_behavior": "answer" if answer_in_context else "abstain",
                "expected_doc": case.get("expected_doc") if answer_in_context else None,
                "expected_keywords": case.get("expected_keywords", []) if answer_in_context else [],
                "sources": sources,
            }
            out.write(json.dumps(record) + "\n")
            written += 1

    print(f"Wrote {written} cases to {args.out} ({skipped} skipped: nothing retrieved)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
