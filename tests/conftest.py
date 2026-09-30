from pathlib import Path
from types import SimpleNamespace

import pytest

from model_selection.config import Case, DecisionRule, Source, load_cases, load_config
from model_selection.prompt import ABSTAIN_MESSAGE

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def config():
    return load_config(ROOT / "candidates.toml")


@pytest.fixture
def cases():
    return load_cases(ROOT / "data" / "grounded_qa.jsonl")


@pytest.fixture
def rule() -> DecisionRule:
    return DecisionRule(bootstrap_resamples=500, baseline="big")


def make_case(case_id: str, behavior: str = "answer") -> Case:
    sources = [
        Source("pto#0", "pto", "Time Off", "PTO", "You get 25 days of PTO."),
        Source("exp#0", "expense", "Expenses", "Meals", "Meals are $75 per day."),
    ]
    if behavior == "answer":
        return Case(case_id, "How much PTO?", "answer", sources, "pto", ["25 days"])
    return Case(case_id, "Parental leave?", "abstain", sources)


def text_block(text, cited_index=None):
    citations = None
    if cited_index is not None:
        citations = [
            SimpleNamespace(
                type="search_result_location", search_result_index=cited_index, cited_text="x"
            )
        ]
    return SimpleNamespace(type="text", text=text, citations=citations)


def response(content, stop_reason="end_turn", input_tokens=500, output_tokens=100):
    return SimpleNamespace(
        content=content,
        stop_reason=stop_reason,
        usage=SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens),
    )


class FakeClient:
    """Answers correctly unless the model name is in `bad_models`."""

    def __init__(self, bad_models=()):
        self.bad_models = set(bad_models)
        self.calls = []
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **request):
        self.calls.append(request)
        question = request["messages"][0]["content"][-1]["text"]
        if request["model"] in self.bad_models:
            return response([text_block("Not sure.")])
        if question == "Parental leave?":
            return response([text_block(ABSTAIN_MESSAGE)])
        return response([text_block("You get 25 days", cited_index=0), text_block(".")])
