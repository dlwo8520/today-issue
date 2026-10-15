import json
from types import SimpleNamespace

import httpx
import pytest
from openai import OpenAI
from pydantic import ValidationError

from pipeline.models import Edition, Summary
from pipeline.run import build_edition, run_live
from pipeline.summarize import (
    Extraction,
    GPTSummarizer,
    ReferencedExtraction,
    SummaryRejected,
    Verification,
    summary_segments,
    validate_extraction,
    validate_summary,
)
from tests.python.conftest import NOW, ROOT

pytestmark = pytest.mark.usefixtures("offline_updates")


def payloads(articles):
    ids = [a.id for a in articles]
    text = "한국은행 기준금리 동결 결정"
    summary = Summary(title=text, oneLineSummary="한국은행은 기준금리를 동결했다고 발표했습니다.",
                      titleSourceIds=ids, summarySourceIds=ids, background=[], response=[], terminology=[],
                      currentSituation=[{"id": "current-1", "text": text, "kind": "fact", "attribution": None, "sourceIds": ids}])
    extraction = Extraction.model_validate({"findings": [{"id": "finding-1", "text": text, "kind": "fact",
        "attribution": None, "sourceIds": ids, "conflictingWith": [],
        "evidence": [{"sourceId": a.id, "quote": a.title} for a in articles]}]})
    verification = Verification.model_validate({"conflictsHandled": True, "segments": [
        {"id": key, "supported": True, "sourceIds": ids, "reason": "제공된 원문에 명시됨"} for key in summary_segments(summary)]})
    return extraction, summary, verification


def test_actual_sdk_structured_responses_with_mock_http(article_factory):
    articles = [article_factory(), article_factory(publisher="B")]
    extracted, summary, verified = payloads(articles)
    referenced = ReferencedExtraction.model_validate({"findings": [
        {**f.model_dump(), "evidence": [{"sourceId": e.sourceId, "spanId": "span-000"} for e in f.evidence]}
        for f in extracted.findings]})
    outputs = [referenced, summary, verified]
    requests = []
    def handler(request):
        requests.append(json.loads(request.content))
        value = outputs[len(requests) - 1]
        return httpx.Response(200, json={"id": "resp_fixture", "object": "response", "created_at": 1,
             "status": "completed", "model": "fixture-model", "output": [{"type": "message", "id": "msg_fixture",
             "role": "assistant", "status": "completed", "content": [{"type": "output_text", "text": value.model_dump_json(), "annotations": []}]}]})
    with httpx.Client(transport=httpx.MockTransport(handler)) as transport:
        client = OpenAI(api_key="synthetic-test-key", http_client=transport, max_retries=0)
        result = GPTSummarizer(client=client, model="fixture-model").summarize(articles)
    assert result == summary
    assert len(requests) == 3
    assert all(r["text"]["format"]["type"] == "json_schema" and r["text"]["format"]["strict"] for r in requests)
    assert all(r["store"] is False and r["model"] == "fixture-model" for r in requests)


@pytest.mark.parametrize("mutate", ["unknown_source", "bad_quote", "conflict"])
def test_extraction_rejections(article_factory, mutate):
    articles = [article_factory()]
    extraction, _, _ = payloads(articles)
    raw = extraction.model_dump()
    if mutate == "unknown_source":
        raw["findings"][0]["sourceIds"] = ["invented"]
    elif mutate == "bad_quote":
        raw["findings"][0]["evidence"][0]["quote"] = "원문에는 없는 새로운 문장"
    else:
        raw["findings"][0]["conflictingWith"] = ["invented"]
    with pytest.raises(SummaryRejected):
        validate_extraction(Extraction.model_validate(raw), articles)


@pytest.mark.parametrize("mutate", ["unsupported", "missing_verdict", "conflict", "invented_number", "unknown_reference"])
def test_summary_rejections(article_factory, mutate):
    articles = [article_factory()]
    extraction, summary, verification = payloads(articles)
    if mutate == "unsupported":
        verification.segments[0].supported = False
    elif mutate == "missing_verdict":
        verification.segments.pop()
    elif mutate == "conflict":
        verification.conflictsHandled = False
    elif mutate == "invented_number":
        summary.oneLineSummary = "한국은행이 기준금리를 99%로 정했습니다."
    else:
        summary.summarySourceIds = ["invented"]
    with pytest.raises(SummaryRejected):
        validate_summary(summary, articles, extraction, verification)


def test_claim_without_speaker_is_rejected():
    from pipeline.models import Statement
    with pytest.raises(ValidationError):
        Statement(id="x", text="금리를 바꿔야 한다.", kind="claim", attribution=None, sourceIds=["s"])


def test_refusal_never_publishes(article_factory):
    client = SimpleNamespace(responses=SimpleNamespace(parse=lambda **kwargs: SimpleNamespace(output_parsed=None)))
    with pytest.raises(SummaryRejected):
        GPTSummarizer(client=client, model="fixture-model").summarize([article_factory()])


def test_no_key_or_model_not_assumed(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    with pytest.raises(ValueError):
        GPTSummarizer()


def test_full_pipeline_generates_fewer_than_six_without_padding(article_factory, config):
    articles = [article_factory(), article_factory(publisher="B")]
    class TestSummarizer:
        def summarize(self, rows):
            return payloads(rows)[1]
    edition, debug = build_edition(articles, NOW, config, TestSummarizer())
    assert edition.mode == "live" and len(edition.issues) == 1
    assert edition.issues[0].rank == 1
    assert debug["articleCount"] == 2 and len(debug["ranking"]) == 1
    Edition.model_validate_json(edition.model_dump_json())


def test_no_verified_results_keeps_existing_live_file(tmp_path, monkeypatch):
    # No network or credentials; disabled sources cause controlled failure.
    path = tmp_path / "latest.json"
    path.write_text('{"previous": "must remain byte-identical"}', encoding="utf-8")
    previous = path.read_bytes()
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    result = run_live(path, ROOT / "config/sources.json", ROOT / "config/pipeline.json")
    assert result == 1 and path.read_bytes() == previous
    assert json.loads((tmp_path / "status.json").read_text(encoding="utf-8"))["state"] == "error"


def test_no_eligible_results_rejected(article_factory, config):
    class NeverCalled:
        def summarize(self, rows):
            pytest.fail("Single-source issue should not be summarized")
    with pytest.raises(ValueError, match="No verified"):
        build_edition([article_factory()], NOW, config, NeverCalled())
