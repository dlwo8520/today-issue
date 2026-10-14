import copy
import json
import logging
from datetime import timedelta, timezone

import httpx
import pytest

from pipeline.api_pipeline import effective_ranking_config, inspect_candidates, load_api_settings
from pipeline.models import Engagement
from pipeline.news_apis import (
    GNewsAdapter,
    NewsAPIError,
    NewsDataAdapter,
    collect_api_news,
    newsdata_date,
    normalize_api_articles,
    related_query,
)
from pipeline.normalize import deduplicate
from pipeline.ranking import rank_groups
from pipeline.usage import BudgetExceeded, LocalCache, UsageLedger, redact
from tests.python.conftest import NOW, ROOT


@pytest.fixture
def api_config():
    settings = load_api_settings(ROOT / "config/news_apis.json")
    # Preserve explicit tests for the original headline-discovery strategy.
    settings.update(gnews_discovery_windows=1, gnews_extra_page_windows=0, max_gnews_related_queries=0,
                    selection_strategy="headline_coverage", require_gnews_candidate=True, request_interval_seconds={})
    return settings


def gnews_payload():
    return {"totalArticles": 1, "articles": [{"title": "한국은행 기준금리 동결 결정", "description": "한국은행은 기준금리를 동결했다고 발표했습니다. 다음 회의 일정은 추후 안내할 예정입니다.",
        "content": "한국은행은 기준금리를 동결했습니다. [+1234 chars]", "url": "https://media-a.example/article?id=1&utm_source=gnews",
        "publishedAt": NOW.isoformat(), "source": {"name": "가상 매체 A", "url": "https://media-a.example"}}]}


def newsdata_payload():
    return {"status": "success", "totalResults": 1, "results": [{"title": "한국은행 기준금리 동결 결정 배경은", "description": "한국은행은 기준금리를 동결했다고 발표했습니다. 다음 회의 일정은 추후 안내할 예정입니다. 발표 자료는 홈페이지에서 확인할 수 있습니다.",
        "content": "ONLY AVAILABLE IN PAID PLANS", "link": "https://media-b.example/article/2", "source_name": "가상 매체 B",
        "source_id": "test-b", "source_url": "https://media-b.example", "pubDate": NOW.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        "pubDateTZ": "UTC", "source_priority": 1}], "nextPage": "unused"}


def adapters(tmp_path, monkeypatch, api_config, handler, **limits):
    monkeypatch.setenv("GNEWS_API_KEY", "synthetic-gnews-secret")
    monkeypatch.setenv("NEWSDATA_API_KEY", "synthetic-newsdata-secret")
    client = httpx.Client(transport=httpx.MockTransport(handler))
    ledger = UsageLedger(**limits)
    cache = LocalCache(tmp_path / "cache")
    return client, ledger, GNewsAdapter(client, api_config, ledger, cache), NewsDataAdapter(client, api_config, ledger, cache)


def test_gnews_fields_and_truncated_content(api_config):
    rows, info = normalize_api_articles("gnews", gnews_payload(), NOW, api_config)
    article = rows[0]
    assert article.url == "https://media-a.example/article?id=1"
    assert article.providers == ["gnews"] and article.discovery_signals == ["gnews_top_headlines"]
    assert article.content_truncated is True and "chars" not in article.excerpt
    assert article.engagement == Engagement()
    assert article.published_at == NOW
    assert info["parsedCount"] == 1 and "source" in info["actualFields"]


def test_newsdata_fields_utc_and_subscription_placeholder(api_config):
    rows, info = normalize_api_articles("newsdata", newsdata_payload(), NOW, api_config)
    article = rows[0]
    assert article.published_at == NOW and article.content == ""
    assert article.providers == ["newsdata"] and article.engagement.view_rank is None
    assert article.independence_key == "media:media-b.example"
    assert info["descriptionLengths"][0] > 50


def test_unknown_dates_unsafe_urls_and_missing_fields_filtered(api_config):
    raw = newsdata_payload()
    raw["results"] = [copy.deepcopy(raw["results"][0]) for _ in range(3)]
    raw["results"][0]["link"] = "javascript:alert(1)"
    raw["results"][1]["pubDateTZ"] = "Unknown/Timezone"
    raw["results"][2]["source_name"] = ""
    raw["results"][2]["source_id"] = ""
    rows, info = normalize_api_articles("newsdata", raw, NOW, api_config)
    assert rows == [] and info["invalidCount"] == 3


def test_offset_dates_and_unknown_timezone():
    assert newsdata_date("2026-10-13 07:00:00", "+0900") == NOW
    assert newsdata_date(NOW.isoformat(), "+09:00") == NOW
    with pytest.raises(ValueError):
        newsdata_date("2026-10-13 07:00:00", None)


@pytest.mark.parametrize("status,category", [(401, "authentication"), (403, "quota"), (429, "rate_limit"), (500, "transient")])
def test_api_errors_are_bounded_and_secret_free(tmp_path, monkeypatch, api_config, status, category, caplog):
    client, ledger, gnews, _ = adapters(tmp_path, monkeypatch, api_config, lambda r: httpx.Response(status, json={"errors": [str(r.url)]}))
    with client, caplog.at_level(logging.INFO):
        with pytest.raises(NewsAPIError) as error:
            gnews.collect(NOW - timedelta(days=1), NOW)
    assert error.value.category == category
    assert ledger.news_calls == {"gnews": 1}
    assert "synthetic-gnews-secret" not in str(error.value)
    assert "synthetic-gnews-secret" not in caplog.text
    assert "synthetic-gnews-secret" not in json.dumps(ledger.report())


def test_timeout(tmp_path, monkeypatch, api_config):
    def handler(request):
        raise httpx.ReadTimeout("secret URL must not escape", request=request)
    client, ledger, gnews, _ = adapters(tmp_path, monkeypatch, api_config, handler)
    with client, pytest.raises(NewsAPIError, match="timeout"):
        gnews.collect(NOW - timedelta(days=1), NOW)
    assert ledger.news_calls["gnews"] == 1


def test_provider_body_error_and_invalid_json(tmp_path, monkeypatch, api_config):
    client, _, _, newsdata = adapters(tmp_path, monkeypatch, api_config, lambda r: httpx.Response(200, json={"status": "error", "results": {"message": "private"}}))
    with client, pytest.raises(NewsAPIError, match="provider_error"):
        newsdata.collect(NOW - timedelta(days=1), NOW)
    client, _, gnews, _ = adapters(tmp_path / "two", monkeypatch, api_config, lambda r: httpx.Response(200, text="not JSON"))
    with client, pytest.raises(NewsAPIError, match="invalid_json"):
        gnews.collect(NOW - timedelta(days=1), NOW)


def test_request_budget_includes_retries(tmp_path, monkeypatch, api_config):
    api_config["news_retries"] = 1
    client, ledger, gnews, _ = adapters(tmp_path, monkeypatch, api_config, lambda r: httpx.Response(503))
    with client, pytest.raises(BudgetExceeded):
        gnews.collect(NOW - timedelta(days=1), NOW)
    assert ledger.news_calls == {"gnews": 1}


def test_success_cache_no_second_http_call(tmp_path, monkeypatch, api_config):
    requests = []
    def handler(request):
        requests.append(request)
        return httpx.Response(200, json=gnews_payload())
    client, ledger, gnews, _ = adapters(tmp_path, monkeypatch, api_config, handler)
    with client:
        first, _ = gnews.collect(NOW - timedelta(days=1), NOW)
        second, info = gnews.collect(NOW - timedelta(days=1), NOW)
    assert len(requests) == 1 and ledger.news_calls == {"gnews": 1}
    assert first[0].title == second[0].title and info["state"] == "cached"
    assert all("synthetic-gnews-secret" not in p.read_text(encoding="utf-8") for p in tmp_path.rglob("*.json"))


def test_two_api_same_url_merges_provenance_and_seed_signal(api_config):
    first = normalize_api_articles("gnews", gnews_payload(), NOW, api_config)[0][0]
    raw = newsdata_payload()
    raw["results"][0].update({"link": first.url, "source_name": first.publisher, "source_url": "https://media-a.example", "description": first.excerpt + "  추가 확인 문장이 있습니다."})
    second = normalize_api_articles("newsdata", raw, NOW, api_config)[0][0]
    rows = deduplicate([first, second])
    assert len(rows) == 1 and rows[0].providers == ["gnews", "newsdata"]
    assert rows[0].discovery_signals == ["gnews_top_headlines"]


def test_same_publisher_alias_different_urls_not_independent(api_config):
    raw = gnews_payload()
    raw["articles"][0]["source"] = {"name": "Yonhap", "url": "https://www.yna.co.kr"}
    first = normalize_api_articles("gnews", raw, NOW, api_config)[0][0]
    raw = newsdata_payload()
    raw["results"][0].update({"source_name": "연합뉴스", "source_url": "https://www.yna.co.kr", "title": first.title})
    second = normalize_api_articles("newsdata", raw, NOW, api_config)[0][0]
    assert first.independence_key == second.independence_key == "wire:yna"
    assert first.publisher == second.publisher == "연합뉴스"
    assert len(deduplicate([first, second])) == 1


def test_follow_up_different_time_not_removed(api_config):
    first = normalize_api_articles("gnews", gnews_payload(), NOW, api_config)[0][0]
    second = first.model_copy(update={"url": "https://media-a.example/new-update", "published_at": NOW + timedelta(hours=3)})
    assert len(deduplicate([first, second])) == 2


def test_queries_extract_core_keywords(api_config, config):
    row = normalize_api_articles("gnews", gnews_payload(), NOW, api_config)[0][0]
    query = related_query([row], config, api_config)
    assert "한국은행" in query and "기준금리" in query
    assert query != row.title and len(query.split()) <= 3


def test_combined_collection_selects_supported_seed_groups(tmp_path, monkeypatch, api_config, config):
    requests = []
    def handler(request):
        requests.append(request)
        return httpx.Response(200, json=gnews_payload() if "gnews.io" in request.url.host else newsdata_payload())
    client, ledger, gnews, newsdata = adapters(tmp_path, monkeypatch, api_config, handler)
    with client:
        collected = collect_api_news(gnews, newsdata, NOW - timedelta(days=1), NOW, config, api_config)
    cleaned, info = inspect_candidates(collected.articles, NOW, effective_ranking_config(config, api_config))
    assert len(requests) == 2 and len(cleaned) == 2 and info["eligibleIssueCount"] == 1
    ranking = rank_groups([cleaned], NOW, effective_ranking_config(config, api_config))[0][1]
    assert ranking.method == "headline_coverage" and ranking.components["headline"] == 1
    assert ranking.components["engagement"] is None


def test_insufficient_excerpts_and_unrelated_newsdata_rejected(api_config, config):
    a = normalize_api_articles("gnews", gnews_payload(), NOW, api_config)[0][0]
    b = normalize_api_articles("newsdata", newsdata_payload(), NOW, api_config)[0][0]
    ranking_config = effective_ranking_config(config, api_config)
    assert rank_groups([[a.model_copy(update={"excerpt": "짧음"}), b]], NOW, ranking_config) == []
    assert rank_groups([[b, b.model_copy(update={"id": "other", "independence_key": "other"})]], NOW, ranking_config) == []


def test_array_order_never_generates_popularity(api_config, config):
    rows = normalize_api_articles("gnews", gnews_payload(), NOW, api_config)[0]
    b = normalize_api_articles("newsdata", newsdata_payload(), NOW, api_config)[0][0]
    forward = rank_groups([rows + [b]], NOW, effective_ranking_config(config, api_config))[0][1]
    reverse = rank_groups([[b] + rows], NOW, effective_ranking_config(config, api_config))[0][1]
    assert forward.score == reverse.score
    assert all(a.engagement.view_rank is None for a in rows)


def test_redaction_and_unknown_model_cost(monkeypatch):
    monkeypatch.setenv("GNEWS_API_KEY", "synthetic-secret")
    assert "synthetic-secret" not in json.dumps(redact({"apikey": "synthetic-secret", "message": "https://api?a=1&apikey=synthetic-secret"}))
    ledger = UsageLedger()
    ledger.reserve_gpt()
    ledger.record_gpt("Summary", "unknown-model", {"input_tokens": 100, "output_tokens": 50})
    assert ledger.report()["totalEstimatedUsd"] is None


def test_known_model_estimate_and_budget(api_config):
    ledger = UsageLedger(max_gpt_requests=1, pricing=api_config["pricing"])
    ledger.reserve_gpt()
    ledger.record_gpt("Summary", "gpt-4o-mini", {"input_tokens": 1_000_000, "output_tokens": 1_000_000, "input_tokens_details": {"cached_tokens": 0}})
    assert ledger.report()["totalEstimatedUsd"] == .75
    with pytest.raises(BudgetExceeded):
        ledger.reserve_gpt()
