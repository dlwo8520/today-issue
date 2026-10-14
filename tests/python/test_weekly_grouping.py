from pipeline.api_pipeline import effective_ranking_config, load_api_settings
from pipeline.grouping import group_articles
from tests.python.conftest import ROOT


def test_korean_abbreviations_and_same_prisoner_case_merge_without_an_extra_card(article_factory, config):
    settings = effective_ranking_config(config, load_api_settings(ROOT / "config/news_apis.json"))
    excerpt = "우크라이나 외무장관이 북한군 포로의 한국 송환을 둘러싼 갈등에 관해 입장을 밝혔다. " * 3
    titles = ["우크라 외무, 북 포로 한국행 공개 논란에 종결된 사안",
              "우크라 北포로 송환 갈등 종결된 문제 사과 거부 시사",
              "우크라 외무장관 北포로 한국행 공개 논란에 종결된 사안"]
    articles = [article_factory(title, publisher=str(i), excerpt=excerpt) for i, title in enumerate(titles)]
    assert len(group_articles(articles, settings)) == 1
    other_day = article_factory("우크라 10월10일 北포로 송환 논란", "D", excerpt=excerpt)
    another_day = article_factory("우크라 10월11일 北포로 송환 논란", "E", excerpt=excerpt)
    assert len(group_articles([other_day, another_day], settings)) == 2
