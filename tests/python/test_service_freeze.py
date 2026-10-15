import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from pipeline import api_pipeline, run, service, summarize
from pipeline.news_apis import GNewsAdapter, NewsDataAdapter
from pipeline.sources import fetch_feed
from tests.python.conftest import ROOT


@pytest.mark.parametrize("flags", [
    ["--stage", stage] for stage in ["probe", "collect", "select", "summarize", "live"]
] + [["--fresh"], ["--from-cache"], ["--collector", "rss"], ["--dry-run"]])
def test_live_cli_is_a_noop_without_clients_or_file_changes(tmp_path, monkeypatch, flags):
    output = tmp_path / "latest.json"
    output.write_bytes(b"saved edition")
    status = tmp_path / "status.json"
    status.write_bytes(b"saved status")
    client = Mock(side_effect=AssertionError("No HTTP or GPT client may be created"))
    monkeypatch.setattr(run, "httpx", SimpleNamespace(Client=client))
    monkeypatch.setattr(api_pipeline, "OpenAI", client)
    monkeypatch.setattr(run, "load_dotenv", lambda *args, **kwargs: None)
    monkeypatch.setattr("sys.argv", ["pipeline.run", "--mode", "live", "--output", str(output), *flags])
    assert run.main() == 0
    client.assert_not_called()
    assert output.read_bytes() == b"saved edition"
    assert status.read_bytes() == b"saved status"
    assert sorted(path.name for path in tmp_path.iterdir()) == ["latest.json", "status.json"]


def test_direct_entry_points_and_adapters_cannot_bypass_freeze(tmp_path, monkeypatch):
    client = Mock()
    monkeypatch.setattr(summarize, "OpenAI", client)
    with pytest.raises(service.UpdatesDisabled):
        api_pipeline.run_api_stage(SimpleNamespace())
    with pytest.raises(service.UpdatesDisabled):
        run.run_live(tmp_path / "latest.json", tmp_path / "sources.json", tmp_path / "config.json")
    with pytest.raises(service.UpdatesDisabled):
        summarize.GPTSummarizer(model="unused")
    # Also stop a previously created summarizer and direct adapter calls.
    with pytest.raises(service.UpdatesDisabled):
        object.__new__(summarize.GPTSummarizer).structured("unused", {}, object)
    for adapter in [GNewsAdapter, NewsDataAdapter]:
        with pytest.raises(service.UpdatesDisabled):
            object.__new__(adapter).fetch({})
    with pytest.raises(service.UpdatesDisabled):
        fetch_feed(client, "https://example.com/rss")
    client.assert_not_called()
    assert not client.mock_calls
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("content", [None, "invalid JSON", "[]", '{}', '{"updates_enabled": "true"}'])
def test_missing_or_invalid_policy_keeps_requests_disabled(tmp_path, monkeypatch, content):
    policy = tmp_path / "service.json"
    if content is not None:
        policy.write_text(content, encoding="utf-8")
    monkeypatch.setattr(service, "SERVICE_FILE", policy)
    with pytest.raises(service.UpdatesDisabled):
        service.require_updates_enabled()


def test_demo_still_runs_offline(tmp_path, monkeypatch):
    output = tmp_path / "demo.json"
    monkeypatch.setattr(run, "load_dotenv", lambda *args, **kwargs: None)
    monkeypatch.setattr("sys.argv", ["pipeline.run", "--mode", "demo", "--output", str(output)])
    assert run.main() == 0
    assert json.loads(output.read_text(encoding="utf-8"))["mode"] == "demo"


def test_workflow_only_checks_source_and_cannot_generate_or_deploy():
    workflow = (ROOT / ".github/workflows/daily.yml").read_text(encoding="utf-8")
    for disabled in ["schedule:", "cron:", "workflow_dispatch:", "pipeline.run", "secrets.", "wrangler", "prepare:", "deploy:"]:
        assert disabled not in workflow
