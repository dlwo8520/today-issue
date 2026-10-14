import json
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from scripts import ensure_cloudflare_project
from scripts.build_public import check_live_permission, stage_public_assets
from tests.python.conftest import ROOT


def make_project(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    (root / "public/data").mkdir(parents=True)
    (root / "config").mkdir()
    (root / "public/data/demo.json").write_bytes((ROOT / "public/data/demo.json").read_bytes())
    (root / "config/news_apis.json").write_bytes((ROOT / "config/news_apis.json").read_bytes())
    (root / "public/favicon.svg").write_text("<svg/>")
    return root


def live_payload():
    payload = json.loads((ROOT / "public/data/demo.json").read_text(encoding="utf-8"))
    payload.update(mode="live", rankingMethod="coverage_recency", publicationScope="public")
    for issue in payload["issues"]:
        issue["ranking"]["method"] = "coverage_recency"
        for source in issue["sources"]:
            source["method"] = "official_api"
    return payload


def test_demo_staging_does_not_publish_or_modify_private_live_files(tmp_path):
    root = make_project(tmp_path)
    private = root / "public/data/latest.json"
    private.write_text("private news text that must not be copied")
    (root / "public/data/status.json").write_text("private status")
    (root / "public/private-photo.png").write_bytes(b"private image")
    staging = tmp_path / "staging"
    edition = stage_public_assets(root, staging, "demo")
    assert edition.mode == "demo"
    delivered = sorted(path.relative_to(staging).as_posix() for path in staging.rglob("*") if path.is_file())
    assert delivered == ["public/_headers", "public/data/demo.json", "public/favicon.svg"]
    assert private.read_text() == "private news text that must not be copied"


def test_live_permission_is_checked_before_any_staging(tmp_path):
    root = make_project(tmp_path)
    (root / "public/data/latest.json").write_text(json.dumps(live_payload()), encoding="utf-8")
    staging = tmp_path / "staging"
    with pytest.raises(ValueError, match="permission"):
        stage_public_assets(root, staging, "live")
    assert not staging.exists()


def test_approved_live_staging_preserves_failure_status_without_demo(tmp_path):
    root = make_project(tmp_path)
    settings = json.loads((root / "config/news_apis.json").read_text(encoding="utf-8"))
    settings.update(usage_scope="public", public_reuse_granted=True, permission_reference="synthetic-test-permission")
    (root / "config/news_apis.json").write_text(json.dumps(settings))
    (root / "public/data/latest.json").write_text(json.dumps(live_payload()), encoding="utf-8")
    status = {"attemptedAt": "2026-10-14T07:00:00+09:00", "state": "error", "message": "Previous edition preserved"}
    (root / "public/data/status.json").write_text(json.dumps(status))
    staging = tmp_path / "staging"
    check_live_permission(root)
    stage_public_assets(root, staging, "live")
    assert json.loads((staging / "public/data/status.json").read_text()) == status
    assert not (staging / "public/data/demo.json").exists()


def test_public_config_does_not_allow_a_private_edition(tmp_path):
    root = make_project(tmp_path)
    settings = json.loads((root / "config/news_apis.json").read_text(encoding="utf-8"))
    settings.update(usage_scope="public", public_reuse_granted=True, permission_reference="synthetic-test-permission")
    (root / "config/news_apis.json").write_text(json.dumps(settings))
    payload = live_payload()
    payload["publicationScope"] = "local_private"
    (root / "public/data/latest.json").write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="not approved"):
        stage_public_assets(root, tmp_path / "staging", "live")


def mock_cloudflare(monkeypatch, handler):
    monkeypatch.delenv("GITHUB_OUTPUT", raising=False)
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "a" * 32)
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "synthetic-cloudflare-token")
    monkeypatch.setenv("CLOUDFLARE_PROJECT_NAME", "today-issue-test")
    monkeypatch.setattr(ensure_cloudflare_project, "httpx", SimpleNamespace(
        Client=lambda **kwargs: httpx.Client(transport=httpx.MockTransport(handler), **kwargs)))


@pytest.mark.parametrize("existing", [True, False])
def test_cloudflare_project_is_created_only_when_missing(monkeypatch, existing):
    calls = []
    def handler(request):
        calls.append(request)
        assert request.headers["Authorization"] == "Bearer synthetic-cloudflare-token"
        assert "synthetic-cloudflare-token" not in str(request.url)
        if request.method == "GET" and not existing:
            return httpx.Response(404)
        if request.method == "POST":
            assert json.loads(request.content) == {"name": "today-issue-test", "production_branch": "main"}
        return httpx.Response(200, json={"success": True, "result": {
            "name": "today-issue-test", "production_branch": "main", "subdomain": "today-issue-test.pages.dev"}})
    mock_cloudflare(monkeypatch, handler)
    assert ensure_cloudflare_project.ensure_project() == "today-issue-test"
    assert [request.method for request in calls] == (["GET"] if existing else ["GET", "POST"])


def test_cloudflare_auth_failure_does_not_create_project_or_expose_token(monkeypatch):
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(403, json={"errors": [{"message": "synthetic-cloudflare-token"}]})
    mock_cloudflare(monkeypatch, handler)
    with pytest.raises(ValueError, match="HTTP 403") as error:
        ensure_cloudflare_project.ensure_project()
    assert "synthetic-cloudflare-token" not in str(error.value)
    assert len(calls) == 1


def test_cloudflare_does_not_take_over_git_integrated_project(monkeypatch):
    mock_cloudflare(monkeypatch, lambda request: httpx.Response(200, json={"success": True, "result": {
        "name": "today-issue-test", "production_branch": "main", "source": {"type": "github"}}}))
    with pytest.raises(ValueError, match="Direct Upload"):
        ensure_cloudflare_project.ensure_project()
