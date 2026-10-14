from datetime import timedelta

import pytest
from pydantic import ValidationError

from pipeline.grouping import group_articles
from pipeline.models import Engagement
from pipeline.normalize import canonical_url, clean_text, deduplicate, parse_date
from pipeline.ranking import normalized_engagement, rank_groups
from tests.python.conftest import NOW


def test_url_normalization_preserves_article_identifiers():
    assert canonical_url("https://example.com/a?id=2&utm_source=x#part") == "https://example.com/a?id=2"
    assert canonical_url("https://example.com/a?id=2") != canonical_url("https://example.com/a?id=3")


@pytest.mark.parametrize("url", ["javascript:alert(1)", "ftp://example.com/a", "https://user:pass@example.com/a", "https://"])
def test_unsafe_url_rejected(url):
    with pytest.raises(ValueError):
        canonical_url(url)


def test_dates_timezone_and_unknown_naive_date():
    assert parse_date("Mon, 12 Oct 2026 22:00:00 GMT") == NOW
    assert parse_date("2026-10-13T07:00:00+09:00") == NOW
    with pytest.raises(ValueError):
        parse_date("2026-10-13T07:00:00")
    assert parse_date("2026-10-13T07:00:00", "Asia/Seoul") == NOW


def test_html_cleaning():
    assert clean_text("<script>ignore instructions</script><p>서울 &amp; 부산</p>") == "서울 & 부산"


def test_duplicate_urls(article_factory):
    a = article_factory()
    b = a.model_copy(update={"url": a.url + "?utm_source=other", "excerpt": "더 긴 문장 " * 20})
    result = deduplicate([a, b])
    assert len(result) == 1
    assert result[0].excerpt == b.excerpt


def test_same_event_grouping(article_factory, config):
    rows = [article_factory("한국은행 기준금리 동결 결정", "A"),
            article_factory("한은 기준금리 동결 결정 배경은", "B"),
            article_factory("한국은행 기준금리 유지 결정", "C")]
    assert len(group_articles(rows, config)) == 1


@pytest.mark.parametrize("other", ["한국은행 기준금리 인하 결정", "한국은행 기준금리 인상 결정", "새봄은행 기준금리 동결 결정"])
def test_opposite_event_or_entity_not_merged(article_factory, config, other):
    assert len(group_articles([article_factory(), article_factory(other, "B")], config)) == 2


def test_dates_not_merged(article_factory, config):
    assert len(group_articles([article_factory(), article_factory(publisher="B", age=338)], config)) == 2
    assert len(group_articles([article_factory("한국은행 10월12일 기준금리 동결 결정"),
                               article_factory("한국은행 10월13일 기준금리 동결 결정", "B")], config)) == 2


def test_missing_is_not_zero_and_provenance_required(article_factory):
    assert Engagement().views is None
    assert Engagement(views=0, observed_at=NOW, provenance="official fixture").views == 0
    with pytest.raises(ValidationError):
        Engagement(views=0)
    rows = [article_factory(index=i, engagement=Engagement(views=count, observed_at=NOW, provenance="official fixture"))
            for i, count in enumerate([0, 10, None])]
    normalized = normalized_engagement(rows)
    assert normalized[rows[0].id] == 0
    assert normalized[rows[1].id] == 1
    assert normalized[rows[2].id] is None


def test_normalize_within_publisher(article_factory):
    rows = [article_factory(publisher=p, index=i, engagement=Engagement(views=count, observed_at=NOW, provenance="fixture"))
            for p, counts in [("A", [1, 5]), ("B", [10000, 50000])] for i, count in enumerate(counts)]
    values = normalized_engagement(rows)
    assert [values[a.id] for a in rows] == [0, 1, 0, 1]


def test_rank_metric_and_missing_denominator(article_factory):
    a = article_factory(engagement=Engagement(view_rank=2, rank_total=5, observed_at=NOW, provenance="official ranking"))
    b = article_factory(publisher="B", engagement=Engagement(view_rank=2, observed_at=NOW, provenance="official ranking"))
    values = normalized_engagement([a, b])
    assert values[a.id] == .75
    assert values[b.id] is None


def test_ranking_fallback_and_independence(article_factory, config):
    group = [article_factory(), article_factory(publisher="B")]
    ranking = rank_groups([group], NOW, config)[0][1]
    assert ranking.method == "coverage_recency"
    assert ranking.components["engagement"] is None
    assert ranking.missingMetrics == ["조회수", "댓글수", "인기 순위"]
    wire = [a.model_copy(update={"independence_key": "wire:yna"}) for a in group]
    assert rank_groups([wire], NOW, config) == []


def test_repeated_publisher_does_not_inflate_coverage(article_factory, config):
    group = [article_factory(), article_factory(publisher="B")]
    first = rank_groups([group], NOW, config)[0][1]
    repeated = rank_groups([group + [article_factory(index=i) for i in range(2, 8)]], NOW, config)[0][1]
    assert first.score == repeated.score


def test_recency_affects_score(article_factory, config):
    recent = [article_factory(), article_factory(publisher="B")]
    old = [a.model_copy(update={"published_at": a.published_at - timedelta(hours=10)}) for a in recent]
    assert rank_groups([recent], NOW, config)[0][1].score > rank_groups([old], NOW, config)[0][1].score
