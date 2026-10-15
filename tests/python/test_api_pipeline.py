import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import httpx
import pytest
from openai import OpenAI

from pipeline import api_pipeline
from pipeline.models import Edition
from pipeline.normalize import KST
from pipeline.summarize import ReferencedExtraction, SummaryRejected, resolve_evidence
from scripts.validate_public import validate_public
from tests.python.conftest import ROOT
from tests.python.test_news_apis import gnews_payload, newsdata_payload
from tests.python.test_summary_pipeline import payloads

pytestmark = pytest.mark.usefixtures("offline_updates")


def args_for(tmp_path, **overrides):
    values = dict(config=ROOT / "config/pipeline.json", api_config=ROOT / "config/news_apis.json",
                  output=tmp_path / "public/data/latest.json", stage="live", providers="both", query=None,
                  max_news_requests=None, max_related_queries=None, max_gpt_requests=None,
                  max_issues=None, from_cache=False, fresh=False, dry_run=False)
    return SimpleNamespace(**{**values, **overrides})


def mock_pipeline(tmp_path, monkeypatch):
    monkeypatch.setattr(api_pipeline, "ROOT", tmp_path)
    original_settings = api_pipeline.load_api_settings
    def small_test_settings(path):
        settings = original_settings(path)
        settings.update(gnews_discovery_windows=1, gnews_extra_page_windows=0, max_gnews_related_queries=0, max_related_queries=3,
                        max_news_requests=4, max_gnews_requests=1, max_newsdata_requests=3,
                        max_gpt_issues=1, max_gpt_requests=3, request_interval_seconds={}, fetch_missing_images=False)
        return settings
    monkeypatch.setattr(api_pipeline, "load_api_settings", small_test_settings)
    for name in ("GNEWS_API_KEY", "NEWSDATA_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.setenv(name, "synthetic-" + name)
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4o-mini")
    calls = {"news": [], "gpt": []}
    def news_handler(request):
        calls["news"].append(request)
        response = gnews_payload() if request.url.host == "gnews.io" else newsdata_payload()
        published = datetime.now(KST) - timedelta(hours=1)
        if request.url.host == "gnews.io":
            response["articles"][0]["publishedAt"] = published.isoformat()
        else:
            response["results"][0]["pubDate"] = published.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        return httpx.Response(200, json=response)
    monkeypatch.setattr(api_pipeline, "httpx", SimpleNamespace(Client=lambda **kwargs: httpx.Client(transport=httpx.MockTransport(news_handler)), HTTPError=httpx.HTTPError))
    def gpt_handler(request):
        body = json.loads(request.content)
        calls["gpt"].append(body)
        source = json.loads(body["input"][1]["content"])["articles"]
        articles = [SimpleNamespace(id=a["id"], title=a["title"]) for a in source]
        extraction, summary, verification = payloads(articles)
        referenced = ReferencedExtraction.model_validate({"findings": [
            {**f.model_dump(), "evidence": [{"sourceId": e.sourceId, "spanId": "span-000"} for e in f.evidence]}
            for f in extraction.findings]})
        name = body["text"]["format"]["schema"]["title"]
        output = {"ReferencedExtraction": referenced, "Summary": summary, "Verification": verification}[name]
        return httpx.Response(200, json={"id": f"resp_mock_{len(calls['gpt'])}", "object": "response", "created_at": 1,
            "status": "completed", "model": "gpt-4o-mini", "usage": {"input_tokens": 600, "output_tokens": 200, "total_tokens": 800},
            "output": [{"id": "msg_mock", "type": "message", "role": "assistant", "status": "completed",
                        "content": [{"type": "output_text", "text": output.model_dump_json(), "annotations": []}]}]})
    monkeypatch.setattr(api_pipeline, "OpenAI", lambda **kwargs: OpenAI(api_key="synthetic-openai", max_retries=0,
                          http_client=httpx.Client(transport=httpx.MockTransport(gpt_handler))))
    return calls


def test_complete_two_api_gpt_pipeline_and_cache_without_network(tmp_path, monkeypatch):
    calls = mock_pipeline(tmp_path, monkeypatch)
    assert api_pipeline.run_api_stage(args_for(tmp_path)) == 0
    edition = Edition.model_validate_json((tmp_path / "public/data/latest.json").read_text(encoding="utf-8"))
    assert len(edition.issues) == 1 and edition.publicationScope == "local_private"
    assert edition.issues[0].ranking.method == "coverage_recency"
    assert (edition.windowEnd - edition.windowStart).total_seconds() == 336 * 3600
    assert {p for s in edition.issues[0].sources for p in s.providers} == {"gnews", "newsdata"}
    assert len(calls["news"]) == 2 and len(calls["gpt"]) == 3
    report = json.loads((tmp_path / "data/reports/live.json").read_text(encoding="utf-8"))
    assert report["usage"]["totalEstimatedUsd"] == .00063
    assert api_pipeline.run_api_stage(args_for(tmp_path, from_cache=True)) == 0
    assert len(calls["news"]) == 2 and len(calls["gpt"]) == 3
    assert len(list((tmp_path / "data/reports/history").glob("live-*.json"))) == 2
    assert all("synthetic-OPENAI_API_KEY" not in p.read_text(encoding="utf-8") for p in tmp_path.rglob("*.json"))


def test_stages_do_not_generate_live_until_requested(tmp_path, monkeypatch):
    calls = mock_pipeline(tmp_path, monkeypatch)
    assert api_pipeline.run_api_stage(args_for(tmp_path, stage="collect")) == 0
    assert not (tmp_path / "public/data/latest.json").exists() and not calls["gpt"]
    assert api_pipeline.run_api_stage(args_for(tmp_path, stage="select", from_cache=True)) == 0
    assert not calls["gpt"]
    assert api_pipeline.run_api_stage(args_for(tmp_path, stage="summarize", from_cache=True)) == 0
    assert (tmp_path / "data/raw/summary-preview.json").exists()
    assert not (tmp_path / "public/data/latest.json").exists()


def test_missing_key_preserves_last_edition(tmp_path, monkeypatch):
    calls = mock_pipeline(tmp_path, monkeypatch)
    monkeypatch.delenv("GNEWS_API_KEY")
    target = tmp_path / "public/data/latest.json"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"previous verified edition bytes")
    assert api_pipeline.run_api_stage(args_for(tmp_path)) == 1
    assert target.read_bytes() == b"previous verified edition bytes"
    assert calls == {"news": [], "gpt": []}
    assert json.loads((target.parent / "status.json").read_text(encoding="utf-8"))["state"] == "error"


def test_dry_run_has_no_side_effects(tmp_path, monkeypatch, capsys):
    calls = mock_pipeline(tmp_path, monkeypatch)
    assert api_pipeline.run_api_stage(args_for(tmp_path, dry_run=True)) == 0
    plan = json.loads(capsys.readouterr().out)
    assert plan["generatedSummary"] is False and plan["maximumGPTLogicalRequests"] == 3
    assert calls == {"news": [], "gpt": []} and not list(tmp_path.iterdir())


def test_request_plan_includes_rejected_candidates_and_bounded_retries(tmp_path):
    settings = api_pipeline.load_api_settings(ROOT / "config/news_apis.json")
    settings.update(max_gpt_requests=60, max_news_requests=20, max_newsdata_requests=10,
                    max_gnews_requests=2, news_retries=2, max_related_queries=3,
                    gnews_discovery_windows=1, gnews_extra_page_windows=0, max_gnews_related_queries=0, selection_strategy="headline_coverage")
    plan = api_pipeline.request_plan(args_for(tmp_path, max_issues=1), {"hours": 24, "max_candidates": 12}, settings)
    assert plan["maximumGPTLogicalRequests"] == 36
    assert plan["maximumNewsRequestAttempts"] == 11
    plan = api_pipeline.request_plan(args_for(tmp_path, stage="summarize", from_cache=True), {"hours": 24}, settings)
    assert plan["maximumGPTLogicalRequests"] == 3 and plan["maximumNewsRequestAttempts"] == 0


def test_private_live_data_cannot_be_uploaded_with_live_or_demo(tmp_path, monkeypatch):
    mock_pipeline(tmp_path, monkeypatch)
    assert api_pipeline.run_api_stage(args_for(tmp_path)) == 0
    with pytest.raises(ValueError, match="private"):
        validate_public("live", tmp_path)
    (tmp_path / "public/data/demo.json").write_bytes((ROOT / "public/data/demo.json").read_bytes())
    with pytest.raises(ValueError, match="Private Live"):
        validate_public("demo", tmp_path)


def test_span_ids_link_exact_input_and_reject_unknown(article_factory):
    articles = [article_factory()]
    extraction, _, _ = payloads(articles)
    references = ReferencedExtraction.model_validate({"findings": [{**extraction.findings[0].model_dump(),
        "evidence": [{"sourceId": articles[0].id, "spanId": "span-000"}]}]})
    assert resolve_evidence(references, articles).findings[0].evidence[0].quote == articles[0].title
    references.findings[0].evidence[0].spanId = "invented-span"
    with pytest.raises(SummaryRejected, match="span ID"):
        resolve_evidence(references, articles)


def test_quote_match_does_not_merge_other_action_or_date(article_factory, config):
    from pipeline.grouping import group_articles
    special = {**config, "quoted_event_terms": ["휴전"], "context_entities": ["정부", "러시아", "우크라이나"]}
    a = article_factory("정부 '에너지 휴전' 승인", excerpt="러시아 우크라이나가 '에너지 휴전'에 관해 논의했습니다.")
    b = article_factory("정부 '에너지 휴전' 거부", "B", excerpt=a.excerpt)
    assert len(group_articles([a, b], special)) == 2
    b = article_factory(a.title, "B", age=338, excerpt=a.excerpt)
    assert len(group_articles([a, b], special)) == 2


def test_selection_without_collection_snapshot_errors(tmp_path, monkeypatch):
    calls = mock_pipeline(tmp_path, monkeypatch)
    assert api_pipeline.run_api_stage(args_for(tmp_path, stage="select", from_cache=True)) == 1
    assert calls == {"news": [], "gpt": []}


def test_verifier_extra_valid_source_is_allowed_but_all_citations_must_be_supported(article_factory):
    from pipeline.summarize import validate_summary
    articles = [article_factory(), article_factory(publisher="B")]
    extracted, summary, verified = payloads(articles)
    summary.currentSituation[0].sourceIds = [articles[0].id]
    validate_summary(summary, articles, extracted, verified)
    summary.currentSituation[0].sourceIds = [a.id for a in articles]
    next(v for v in verified.segments if v.id == "current-1").sourceIds = [articles[0].id]
    with pytest.raises(SummaryRejected, match="cited sources"):
        validate_summary(summary, articles, extracted, verified)
