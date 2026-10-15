import json
from unittest.mock import patch

import httpx
import pytest
from pydantic import ValidationError

from pipeline.models import Edition
from pipeline.sources import RSSAdapter, SourceConfig, collect_sources, fetch_feed
from pipeline.storage import atomic_json, pipeline_lock, save_edition
from tests.python.conftest import NOW, ROOT

pytestmark = pytest.mark.usefixtures("offline_updates")


def permitted_source():
    return SourceConfig(id="fixture", publisher="A", url="https://example.com/rss", policyUrl="https://example.com/policy",
                        enabled=True, reuseGranted=True, llmProcessingGranted=True, permissionReference="synthetic test only",
                        reviewedAt="2026-10-13", independenceKey="A", notes="test")


def test_permission_gate():
    data = permitted_source().model_dump()
    data["llmProcessingGranted"] = False
    with pytest.raises(ValidationError):
        SourceConfig.model_validate(data)


def test_feed_parsing_filters_bad_old_dates(config):
    rss = '''<rss version="2.0"><channel><title>Test</title>
    <item><title>한국은행 기준금리 동결</title><link>https://example.com/1</link><pubDate>Mon, 12 Oct 2026 22:00:00 GMT</pubDate><description>확인 가능한 문장</description></item>
    <item><title>오래된 기사</title><link>https://example.com/old</link><pubDate>Mon, 05 Oct 2026 22:00:00 GMT</pubDate></item>
    <item><title>잘못된 기사</title><link>javascript:alert(1)</link><pubDate>bad</pubDate></item></channel></rss>'''
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, text=rss))) as client:
        rows = RSSAdapter(client, config).collect(permitted_source(), NOW, NOW)
    assert len(rows) == 1
    assert rows[0].engagement.views is None
    assert rows[0].published_at == NOW


def test_transient_retry_and_no_access_bypass():
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(503 if len(calls) == 1 else 200, text="feed")
    with httpx.Client(transport=httpx.MockTransport(handler)) as client, patch("pipeline.sources.time.sleep"):
        assert fetch_feed(client, "https://example.com/rss") == b"feed"
    assert len(calls) == 2
    calls.clear()
    with httpx.Client(transport=httpx.MockTransport(lambda r: calls.append(r) or httpx.Response(403))) as client:
        with pytest.raises(httpx.HTTPStatusError):
            fetch_feed(client, "https://example.com/rss")
    assert len(calls) == 1


def test_size_limit():
    with httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, content=b"123456"))) as client:
        with pytest.raises(ValueError, match="size limit"):
            fetch_feed(client, "https://example.com/rss", max_bytes=5)


def test_partial_source_failure_isolated(article_factory):
    class Adapter:
        def collect(self, source, start, end):
            if source.id == "bad":
                raise ValueError("bad feed")
            return [article_factory()]
    first = permitted_source()
    second = first.model_copy(update={"id": "bad"})
    rows, errors, successes = collect_sources([second, first], {"rss": Adapter()}, NOW, NOW)
    assert len(rows) == 1 and errors == ["bad"] and successes == 1


def test_atomic_write_keeps_old_file_on_failure(tmp_path):
    path = tmp_path / "latest.json"
    path.write_text('{"old": true}')
    with patch("pipeline.storage.os.replace", side_effect=OSError("disk error")):
        with pytest.raises(OSError):
            atomic_json(path, {"new": True})
    assert json.loads(path.read_text()) == {"old": True}
    assert list(tmp_path.glob("*.tmp")) == []


def test_demo_schema_source_ids_and_live_mode(tmp_path):
    raw = json.loads((ROOT / "public/data/demo.json").read_text(encoding="utf-8"))
    edition = Edition.model_validate(raw)
    assert len(edition.issues) == 6
    save_edition(tmp_path / "demo.json", edition)
    raw["issues"][0]["currentSituation"][0]["sourceIds"] = ["nonexistent"]
    with pytest.raises(ValidationError, match="Unknown source"):
        Edition.model_validate(raw)
    raw = edition.model_dump(mode="json")
    raw["mode"] = "live"
    with pytest.raises(ValidationError, match="cannot contain demo"):
        Edition.model_validate(raw)


def test_lock_prevents_concurrent_write(tmp_path):
    lock = tmp_path / ".pipeline.lock"
    with pipeline_lock(lock):
        with pytest.raises(FileExistsError):
            with pipeline_lock(lock):
                pass
    assert not lock.exists()
