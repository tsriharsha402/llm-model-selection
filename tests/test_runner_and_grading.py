import anthropic
import httpx2
from conftest import FakeClient, make_case, response, text_block

from model_selection.config import Candidate
from model_selection.grading import grade
from model_selection.runner import Record, call_model, load_records, run_benchmark

CANDIDATE = Candidate("big", "claude-opus-5-5", "medium")


def clock_factory():
    ticks = iter(range(1000))
    return lambda: float(next(ticks))


def test_call_model_records_answer_citations_and_usage():
    record = call_model(FakeClient(), CANDIDATE, make_case("a"), clock_factory())
    assert record.answer == "You get 25 days."
    assert record.cited_sources == [0]
    assert (record.input_tokens, record.output_tokens) == (500, 100)
    assert record.latency_seconds == 1.0
    assert not record.abstained


def test_refusal_is_recorded():
    class Refuser(FakeClient):
        def _create(self, **request):
            return response([], stop_reason="refusal")

    record = call_model(Refuser(), CANDIDATE, make_case("a"), clock_factory())
    assert record.refused
    assert not grade(record, make_case("a")).passed


def test_api_error_is_recorded_not_raised():
    class Broken(FakeClient):
        def _create(self, **request):
            req = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
            raise anthropic.InternalServerError(
                "boom", response=httpx2.Response(500, request=req), body=None
            )

    record = call_model(Broken(), CANDIDATE, make_case("a"), clock_factory())
    assert record.error and "InternalServerError" in record.error
    assert grade(record, make_case("a")).failed


def test_run_is_resumable(tmp_path):
    out = tmp_path / "raw.jsonl"
    cases = [make_case("a"), make_case("b", "abstain")]
    client = FakeClient()
    run_benchmark(client, [CANDIDATE], cases, out, workers=2)
    assert len(client.calls) == 2
    records = run_benchmark(client, [CANDIDATE], cases, out, workers=2)
    assert len(client.calls) == 2, "completed pairs are not re-run"
    assert len(records) == 2
    assert len(load_records(out)) == 2


def test_errored_pairs_are_retried_on_resume(tmp_path):
    out = tmp_path / "raw.jsonl"
    failed = Record("big", "claude-opus-5-5", "a", "v", error="APIConnectionError")
    out.write_text(__import__("json").dumps(failed.__dict__) + "\n")
    client = FakeClient()
    records = run_benchmark(client, [CANDIDATE], [make_case("a")], out)
    assert len(client.calls) == 1
    assert records[0].error is None


def test_grading_rules():
    answer_case = make_case("a")
    good = Record("big", "m", "a", "v", answer="You get 25 days.", cited_sources=[0])
    assert grade(good, answer_case).passed

    wrong_citation = Record("big", "m", "a", "v", answer="You get 25 days.", cited_sources=[1])
    assert not grade(wrong_citation, answer_case).passed

    missing_fact = Record("big", "m", "a", "v", answer="Some days.", cited_sources=[0])
    assert grade(missing_fact, answer_case).keyword_recall == 0.0

    abstain_case = make_case("b", "abstain")
    assert grade(Record("big", "m", "b", "v", abstained=True), abstain_case).passed
    assert not grade(Record("big", "m", "b", "v", answer="Yes."), abstain_case).passed


def test_text_block_helper_without_citations():
    assert text_block("x").citations is None
