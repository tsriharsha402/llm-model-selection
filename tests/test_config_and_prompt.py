from model_selection.config import Candidate
from model_selection.estimate import estimate, render_estimate
from model_selection.pricing import PRICES_PER_MTOK
from model_selection.prompt import build_request


def test_candidates_are_priced_and_baseline_exists(config):
    candidates, rule = config
    assert {c.model for c in candidates} <= set(PRICES_PER_MTOK)
    assert rule.baseline in {c.name for c in candidates}


def test_dataset_is_consistent(cases):
    assert len(cases) >= 40
    assert len({c.id for c in cases}) == len(cases)
    for case in cases:
        assert case.sources, case.id
        if case.expected_behavior == "answer":
            assert case.expected_doc in {s.doc_id for s in case.sources}, case.id
            assert case.expected_keywords, case.id
            # The required facts must be in the context the model sees; otherwise the
            # correct behavior is to abstain and the case is mislabeled.
            context = " ".join(s.text for s in case.sources).lower()
            for keyword in case.expected_keywords:
                assert keyword.lower() in context, f"{case.id}: {keyword!r} not in context"
        else:
            assert case.expected_behavior == "abstain"


def test_request_matches_production_layout(cases):
    request = build_request(Candidate("x", "claude-opus-5-5", "low"), cases[0])
    blocks = request["messages"][0]["content"]
    assert blocks[-1] == {"type": "text", "text": cases[0].question}
    assert all(b["type"] == "search_result" for b in blocks[:-1])
    assert all(b["citations"] == {"enabled": True} for b in blocks[:-1])
    assert request["output_config"] == {"effort": "low"}
    assert "fallbacks" not in request, "the benchmark measures each model on its own"


def test_haiku_request_has_no_effort(cases):
    request = build_request(Candidate("h", "claude-haiku-4-5"), cases[0])
    assert "output_config" not in request


def test_estimate_scales_with_price(config, cases):
    candidates, _ = config
    estimates = {e.candidate.model: e for e in estimate(candidates, cases)}
    assert estimates["claude-opus-5-5"].high_usd > estimates["claude-haiku-4-5"].high_usd
    assert "Total" in render_estimate(list(estimates.values()), len(cases))
