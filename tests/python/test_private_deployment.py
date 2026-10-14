import json
import shutil
import zipfile
from types import SimpleNamespace

import httpx
import pytest

from scripts import build_private
from scripts.build_private import check_access, stage_private_assets
from scripts.restore_state import restore_state
from tests.python.conftest import ROOT
from tests.python.test_public_deployment import live_payload, make_project


def mock_private_access(monkeypatch, mutation=None, denied=False):
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "a" * 32)
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "synthetic-private-token")
    monkeypatch.setenv("CLOUDFLARE_PROJECT_NAME", "today-issue-test")
    monkeypatch.setenv("CLOUDFLARE_ACCESS_EMAIL", "owner@example.com")
    host = "today-issue-test.pages.dev"
    applications = [dict(id=name, type="self_hosted", domain=domain, allowed_idps=["otp"])
                    for name, domain in [("production", host), ("preview", "*." + host)]]
    policy = {"decision": "allow", "include": [{"email": {"email": "owner@example.com"}}]}
    policies = {app["id"]: [dict(policy)] for app in applications}
    if mutation:
        mutation(applications, policies)

    def handler(request):
        if request.url.host == "api.cloudflare.com":
            if denied:
                return httpx.Response(403, json={"errors": [{"message": "synthetic-private-token"}]})
            assert request.headers["Authorization"] == "Bearer synthetic-private-token"
            path = request.url.path
            if "/pages/projects/" in path:
                result = {"name": "today-issue-test", "subdomain": host, "domains": [host], "deployment_configs": {"production": {"env_vars": {
                    "PERSONAL_EMAIL": {"type": "plain_text", "value": "owner@example.com"},
                    "PERSONAL_SESSION_SECRET": {"type": "secret_text"}}}}}
            elif path.endswith("/organizations"):
                result = {"auth_domain": "test.cloudflareaccess.com"}
            elif path.endswith("/identity_providers"):
                result = [{"id": "otp", "type": "onetimepin"}]
            elif path.endswith("/apps"):
                result = applications
            elif path.endswith("/policies"):
                result = policies[path.split("/")[-2]]
            else:
                raise AssertionError("Unexpected API request")
            return httpx.Response(200, json={"success": True, "result": result})
        assert "Authorization" not in request.headers
        if request.url.path == "/login":
            return httpx.Response(200, text='<main data-personal-entry="email">')
        return httpx.Response(302, headers={"Location": "/login?next=/"})

    monkeypatch.setattr(build_private, "httpx", SimpleNamespace(
        Client=lambda **kwargs: httpx.Client(transport=httpx.MockTransport(handler), **kwargs)))


def test_private_access_requires_root_and_wildcard_email_otp(monkeypatch):
    mock_private_access(monkeypatch)
    assert check_access().hostname == "today-issue-test.pages.dev"


@pytest.mark.parametrize("weakness", ["missing-preview", "bypass", "other-email", "other-idp", "path-bypass"])
def test_weaker_access_configuration_blocks_private_build(monkeypatch, weakness):
    def change(apps, policies):
        if weakness == "missing-preview":
            apps.pop()
        elif weakness == "bypass":
            policies["production"] = [{"decision": "bypass", "include": [{"everyone": {}}]}]
        elif weakness == "other-email":
            policies["production"] = [{"decision": "allow", "include": [{"email": {"email": "other@example.com"}}]}]
        elif weakness == "other-idp":
            apps[0]["allowed_idps"] = ["unreviewed"]
        else:
            apps.append(dict(id="path", type="self_hosted", domain="today-issue-test.pages.dev/data", allowed_idps=["otp"]))
            policies["path"] = [{"decision": "bypass", "include": [{"everyone": {}}]}]
    mock_private_access(monkeypatch, change)
    with pytest.raises(ValueError):
        check_access()


def test_private_access_auth_failure_does_not_expose_credentials(monkeypatch):
    mock_private_access(monkeypatch, denied=True)
    with pytest.raises(ValueError, match="HTTP 403") as error:
        check_access()
    assert "synthetic-private-token" not in str(error.value)


def test_private_staging_preserves_photos_scope_and_original(tmp_path):
    root = make_project(tmp_path)
    payload = live_payload()
    payload["publicationScope"] = "local_private"
    payload["issues"][0]["sources"][0]["imageUrl"] = "https://example.com/photo.jpg"
    private_path = root / "public/data/latest.json"
    private_path.write_text(json.dumps(payload), encoding="utf-8")
    original = private_path.read_bytes()
    (root / "public/unselected-photo.jpg").write_bytes(b"must not be copied")
    (root / ".env").write_text("SECRET=synthetic-must-not-ship")
    (root / "server").mkdir()
    shutil.copyfile(ROOT / "server/email-gate.mjs", root / "server/email-gate.mjs")
    staging = tmp_path / "staging"
    edition = stage_private_assets(root, staging)
    assert edition.publicationScope == "local_private"
    assert edition.issues[0].sources[0].imageUrl == "https://example.com/photo.jpg"
    assert private_path.read_bytes() == original
    files = sorted(p.relative_to(staging).as_posix() for p in staging.rglob("*") if p.is_file())
    assert files == ["public/_headers", "public/_routes.json", "public/_worker.js", "public/data/latest.json", "public/favicon.svg"]
    assert "private, no-store" in (staging / "public/_headers").read_text()


def test_reachable_private_json_prevents_deployment(monkeypatch):
    monkeypatch.setattr(build_private, "httpx", SimpleNamespace(
        Client=lambda **kwargs: httpx.Client(transport=httpx.MockTransport(
            lambda request: httpx.Response(200, text="private news")), **kwargs)))
    with pytest.raises(ValueError, match="accessible without"):
        build_private.verify_anonymous_access(build_private.AccessProof("example.pages.dev", "team.cloudflareaccess.com"))


def test_build_does_not_stage_when_access_is_unverified(tmp_path, monkeypatch):
    root = make_project(tmp_path)
    def reject():
        raise ValueError("Access not verified")
    monkeypatch.setattr(build_private, "check_access", reject)
    with pytest.raises(ValueError, match="not verified"):
        build_private.build_private(root)
    assert not (root / ".tools/private-deploy").exists()


@pytest.mark.parametrize("requested_scope", ["public", "local_private"])
def test_private_state_is_never_restored_into_public_mode(tmp_path, requested_scope):
    payload = live_payload()
    payload["publicationScope"] = "local_private"
    archive = tmp_path / "prior.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("latest.json", json.dumps(payload))
    root = tmp_path / "restore"
    if requested_scope == "public":
        with pytest.raises(ValueError, match="different publication scope"):
            restore_state(archive, root=root)
        assert not root.exists()
    else:
        restore_state(archive, requested_scope, root)
        restored = json.loads((root / "public/data/latest.json").read_text(encoding="utf-8"))
        assert restored["publicationScope"] == "local_private"
