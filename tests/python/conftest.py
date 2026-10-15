import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from pipeline.models import Article, Engagement

NOW = datetime.fromisoformat("2026-10-13T07:00:00+09:00")
ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def offline_updates(tmp_path_factory, monkeypatch):
    """Permit only the existing mocked pipeline tests through a temporary policy."""
    from pipeline import service
    policy = tmp_path_factory.mktemp("mock-policy") / "service.json"
    policy.write_text('{"updates_enabled": true}', encoding="utf-8")
    monkeypatch.setattr(service, "SERVICE_FILE", policy)


@pytest.fixture
def config():
    return json.loads((ROOT / "config/pipeline.json").read_text(encoding="utf-8"))


@pytest.fixture
def article_factory():
    def make(title="한국은행 기준금리 동결 결정", publisher="A", index=1, age=1, excerpt=None, **extra):
        return Article(id=f"article-{publisher}-{index}", publisher=publisher, title=title,
                       url=f"https://example.com/{publisher}/{index}", published_at=NOW - timedelta(hours=age),
                       collected_at=NOW, excerpt=excerpt or f"{title}. 한국은행은 13일 기준금리를 동결했다고 발표했습니다.",
                       source_url=f"https://example.com/{publisher}/rss", independence_key=extra.pop("independence_key", publisher),
                       engagement=extra.pop("engagement", Engagement()), **extra)
    return make
