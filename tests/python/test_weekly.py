"""Rolling-week collection, independent overlap, and honest interest cutoffs."""
import json
from datetime import timedelta, timezone

import httpx
import pytest

from pipeline.api_pipeline import (
    effective_ranking_config,
    inspect_candidates,
    load_api_settings,
    load_snapshot,
)
from pipeline.grouping import group_articles
from pipeline.models import Engagement
from pipeline.news_apis import GNewsAdapter, NewsDataAdapter, collect_api_news
from pipeline.ranking import rank_groups
from pipeline.usage import LocalCache, UsageLedger
from tests.python.conftest import NOW, ROOT
from tests.python.test_news_apis import gnews_payload


@pytest.fixture
def weekly_settings():
    settings = load_api_settings(ROOT / "config/news_apis.json")
    settings["request_interval_seconds"] = {}
    settings["gnews_extra_page_windows"] = 0
    settings["selection_strategy"] = "overlap_then_engagement"
    return settings


@pytest.fixture
def config():
    settings = json.loads((ROOT / "config/pipeline.json").read_text(encoding="utf-8"))
    settings.update(hours=168, max_cluster_hours=168)
    return settings


def test_seven_date_windows_cover_the_full_rolling_week(tmp_path, monkeypatch, config, weekly_settings):
    monkeypatch.setenv("GNEWS_API_KEY", "synthetic-week-key")
    requests = []
    def handler(request):
        requests.append(request)
        response = gnews_payload()
        response["articles"][0]["publishedAt"] = request.url.params["to"]
        response["articles"][0]["url"] = "https://media-a.example/article?day=" + str(len(requests))
        return httpx.Response(200, json=response)
    weekly_settings.update(max_related_queries=0, max_gnews_related_queries=0)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        ledger = UsageLedger(max_news_requests=7, provider_limits={"gnews": 7})
        cache = LocalCache(tmp_path)
        result = collect_api_news(GNewsAdapter(client, weekly_settings, ledger, cache),
                                  NewsDataAdapter(client, weekly_settings, ledger, cache),
                                  NOW - timedelta(days=7), NOW, config, weekly_settings)
    assert len(requests) == 7 and len(result.articles) == 7
    assert all(r.url.params["max"] == "10" and r.url.params["country"] == "kr" for r in requests)
    dates = [(r.url.params["from"], r.url.params["to"]) for r in requests]
    assert dates[0][1] == NOW.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    assert all(dates[i][0] == dates[i + 1][1] for i in range(6))
    assert ledger.news_calls == {"gnews": 7}


def test_related_gnews_search_has_dates_and_is_not_headline_signal(tmp_path, monkeypatch, weekly_settings):
    monkeypatch.setenv("GNEWS_API_KEY", "synthetic-week-key")
    requests = []
    def handler(request):
        requests.append(request)
        return httpx.Response(200, json=gnews_payload())
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        adapter = GNewsAdapter(client, weekly_settings, UsageLedger(), LocalCache(tmp_path))
        rows, _ = adapter.collect(NOW - timedelta(days=7), NOW, "한국은행 기준금리")
    assert requests[0].url.path == "/api/v4/search"
    assert "from" in requests[0].url.params and "to" in requests[0].url.params
    assert requests[0].url.params["sortby"] == "relevance"
    assert rows[0].discovery_signals == ["gnews_search"]
    params = NewsDataAdapter.parameters(type("Adapter", (), {"config": weekly_settings})(), "한국은행", NOW - timedelta(days=7), NOW)
    assert params["size"] == 10 and "from_date" not in params and "timeframe" not in params


def test_same_event_followups_across_days_but_not_explicit_different_dates(article_factory, config):
    a = article_factory("한국은행 기준금리 동결 결정")
    b = article_factory("한국은행 기준금리 동결 결정 배경은", "B", age=120)
    assert len(group_articles([a, b], config)) == 1
    a = article_factory("한국은행 10월12일 기준금리 동결 결정")
    b = article_factory("한국은행 10월13일 기준금리 동결 결정", "B")
    assert len(group_articles([a, b], config)) == 2


def test_overlap_does_not_require_gnews_and_excludes_single_publisher(article_factory, config, weekly_settings):
    settings = effective_ranking_config(config, weekly_settings)
    group = [article_factory(publisher=p, providers=["newsdata"], excerpt="제공된 기사 설명의 직접 근거입니다. " * 5) for p in ["A", "B"]]
    assert len(rank_groups([group], NOW, settings)) == 1
    repeated = [a.model_copy(update={"publisher_key": "media:same.example"}) for a in group]
    assert rank_groups([repeated], NOW, settings) == []
    wire = [a.model_copy(update={"independence_key": "wire:common"}) for a in group]
    assert rank_groups([wire], NOW, settings) == []


def interest_groups(article_factory):
    return [[article_factory(title=f"한국은행 10월{i + 7}일 기준금리 동결 결정", publisher=p, index=i,
               excerpt="제공된 기사 설명의 직접 근거입니다. " * 5, engagement=Engagement(views=10 * (i + 1), comments=i,
               observed_at=NOW, provenance="Synthetic test measurement")) for p in ["A", "B"]] for i in range(7)]


def test_over_six_uses_comparable_observed_views_and_comments(article_factory, config, weekly_settings):
    groups = interest_groups(article_factory)
    ranked = rank_groups(groups, NOW, effective_ranking_config(config, weekly_settings))
    assert ranked[0][0][0].engagement.views == 70
    assert ranked[5][0][0].engagement.views == 20
    assert all(ranking.method == "engagement" for _, ranking in ranked)
    assert ranked[0][1].score == 1


def test_partial_interest_does_not_treat_missing_as_zero(article_factory, config, weekly_settings):
    groups = interest_groups(article_factory)
    groups[0] = [a.model_copy(update={"engagement": Engagement()}) for a in groups[0]]
    groups[0].append(article_factory(publisher="C", index=20, excerpt="제공된 기사 설명의 직접 근거입니다. " * 5))
    ranked = rank_groups(groups, NOW, effective_ranking_config(config, weekly_settings))
    assert len(ranked[0][0]) == 3 and ranked[0][1].components["engagement"] is None
    assert all(ranking.method == "coverage_recency" for _, ranking in ranked)


def test_weekly_filter_and_six_candidate_cutoff(article_factory, config, weekly_settings):
    rows = [a for group in interest_groups(article_factory) for a in group]
    rows.append(article_factory(publisher="old", age=169))
    rows.append(article_factory(title="가온학교 도서관 개관", publisher="inside", age=167))
    _, inspection = inspect_candidates(rows, NOW, effective_ranking_config(config, weekly_settings))
    assert inspection["outsideWindow"] == 1
    assert inspection["eligibleIssueCount"] == 7 and inspection["selectedIssueCount"] == 6


def test_short_period_snapshot_cannot_pretend_to_be_weekly(tmp_path):
    from datetime import datetime

    from pipeline.normalize import KST
    path = tmp_path / "snapshot.json"
    path.write_text(json.dumps({"kind": "api_collection", "mode": "live", "windowEnd": datetime.now(KST).isoformat(),
                                 "windowHours": 24, "articles": []}), encoding="utf-8")
    with pytest.raises(ValueError, match="window changed"):
        load_snapshot(path, 6, 168)


def test_history_retains_valid_weekly_articles_only(tmp_path, monkeypatch, article_factory):
    from datetime import datetime

    from pipeline import api_pipeline
    from pipeline.normalize import KST
    from tests.python.test_api_pipeline import args_for, mock_pipeline
    mock_pipeline(tmp_path, monkeypatch)
    end = datetime.now(KST)
    prior = [article_factory(publisher="history", index=i, method="official_api", providers=["newsdata"]).model_copy(
                   update={"published_at": end - timedelta(days=days)}) for i, days in [(1, 4), (2, 15)]]
    path = tmp_path / "data/raw/api-history.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"usageScope": "local_private", "articles": [a.model_dump(mode="json") for a in prior]}), encoding="utf-8")
    assert api_pipeline.run_api_stage(args_for(tmp_path, stage="collect")) == 0
    history = json.loads(path.read_text(encoding="utf-8"))
    urls = {a["url"] for a in history["articles"]}
    assert prior[0].url in urls and prior[1].url not in urls
    report = json.loads((tmp_path / "data/reports/collect.json").read_text(encoding="utf-8"))
    assert report["historyArticlesReused"] == 1


def test_unidentified_portal_mirror_does_not_count_as_an_independent_publisher(article_factory, config, weekly_settings):
    first = article_factory(publisher="원문 매체", excerpt="직접 원문 보도에서 제공된 근거입니다. " * 5)
    mirror = article_factory(publisher="Daum", publisher_key="name:daum", excerpt=first.excerpt)
    cleaned, inspection = inspect_candidates([first, mirror], NOW, effective_ranking_config(config, weekly_settings))
    assert len(cleaned) == 1 and inspection["unknownPublisherExcluded"] == 1
    assert inspection["eligibleIssueCount"] == 0


def test_provider_calls_are_spaced_after_response_completion(tmp_path, monkeypatch, weekly_settings):
    from types import SimpleNamespace

    from pipeline import news_apis
    monkeypatch.setenv("GNEWS_API_KEY", "synthetic-week-key")
    fake_clock = [0.0]
    def sleep(seconds):
        fake_clock[0] += seconds
    monkeypatch.setattr(news_apis, "time", SimpleNamespace(monotonic=lambda: fake_clock[0], sleep=sleep))
    starts = []
    def handler(request):
        starts.append(fake_clock[0])
        fake_clock[0] += 0.9  # Provider spends time processing the response.
        return httpx.Response(200, json=gnews_payload())
    weekly_settings["request_interval_seconds"] = {"gnews": 1.25}
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        adapter = GNewsAdapter(client, weekly_settings, UsageLedger(provider_limits={"gnews": 2}), LocalCache(tmp_path))
        adapter.collect(NOW - timedelta(days=7), NOW, "one")
        adapter.collect(NOW - timedelta(days=7), NOW, "two")
    assert starts[1] - starts[0] >= 2.15
