from datetime import timedelta

import pytest

from pipeline.api_pipeline import effective_ranking_config, inspect_candidates, load_api_settings
from pipeline.images import ImageMetadata, public_image_url
from pipeline.models import Engagement
from pipeline.news_apis import normalize_api_articles
from pipeline.normalize import deduplicate
from pipeline.ranking import balanced_sources, rank_groups
from tests.python.conftest import NOW, ROOT
from tests.python.test_news_apis import gnews_payload, newsdata_payload


def test_two_week_boundary_and_latest_order_ignore_popularity(article_factory, config):
    settings = effective_ranking_config(config, load_api_settings(ROOT / "config/news_apis.json"))
    older = [article_factory("한국은행 10월1일 기준금리 동결", publisher=str(p), age=200,
              excerpt="충분한 기사 본문 근거입니다. " * 8,
              engagement=Engagement(views=100000, observed_at=NOW, provenance="synthetic test")) for p in range(3)]
    recent = [article_factory("한국은행 10월13일 기준금리 동결", publisher=str(p), index=2, age=1,
               excerpt="충분한 기사 본문 근거입니다. " * 8) for p in range(2)]
    too_old = article_factory("별도 사건", publisher="old", age=337)
    _, report = inspect_candidates(older + recent + [too_old], NOW, settings)
    assert report["outsideWindow"] == 1 and report["eligibleIssueCount"] == 2
    ranked = rank_groups([older, recent], NOW, settings)
    assert ranked[0][0][0].published_at == NOW - timedelta(hours=1)
    assert ranked[0][1].method == "coverage_recency"
    assert balanced_sources(older + recent, 8, prefer_latest=True)[0].published_at == NOW - timedelta(hours=1)


def test_api_image_mapping_and_duplicate_metadata_survive(config):
    settings = load_api_settings(ROOT / "config/news_apis.json")
    gnews = gnews_payload()
    gnews["articles"][0]["image"] = "https://cdn.example.com/first.jpg"
    first = normalize_api_articles("gnews", gnews, NOW, settings)[0][0]
    assert first.image_url == "https://cdn.example.com/first.jpg"
    without = first.model_copy(update={"image_url": None, "excerpt": "더 풍부한 근거 문장입니다. " * 20})
    assert deduplicate([first, without])[0].image_url == first.image_url
    newsdata = newsdata_payload()
    newsdata["results"][0]["image_url"] = "https://cdn.example.com/second.jpg"
    assert normalize_api_articles("newsdata", newsdata, NOW, settings)[0][0].image_url.endswith("second.jpg")
    gnews["articles"][0]["image"] = "javascript:alert(1)"
    assert normalize_api_articles("gnews", gnews, NOW, settings)[0][0].image_url is None


def test_original_image_metadata_relative_url_empty_and_invalid():
    parser = ImageMetadata("https://news.example.com/article/one")
    parser.feed('<meta property="og:image" content=""><meta property="og:image" content="javascript:bad"><meta property="og:image" content="/images/original.jpg">')
    assert parser.images == ["https://news.example.com/images/original.jpg"]


@pytest.mark.parametrize("url", ["http://127.0.0.1/a.jpg", "http://localhost/a.jpg", "http://192.168.0.1/a.jpg", "https://u:p@news.example/a.jpg"])
def test_local_or_authenticated_image_metadata_rejected(url):
    with pytest.raises(ValueError):
        public_image_url(url)
