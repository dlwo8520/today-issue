"""Build personal Live with a server-side email gate and protected legacy URLs."""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pipeline.api_pipeline import load_api_settings  # noqa: E402
from pipeline.models import Edition  # noqa: E402


@dataclass(frozen=True)
class AccessProof:
    hostname: str
    auth_domain: str


def access_settings() -> tuple[str, str, str, str]:
    account = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "").strip()
    token = os.environ.get("CLOUDFLARE_API_TOKEN", "").strip()
    project = os.environ.get("CLOUDFLARE_PROJECT_NAME", "today-issue-dlwo8520").strip()
    email = os.environ.get("CLOUDFLARE_ACCESS_EMAIL", "").strip().lower()
    if not re.fullmatch(r"[a-fA-F0-9]{32}", account) or not token:
        raise ValueError("Cloudflare account and token are required for the private build")
    if not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,56}[a-z0-9])?", project):
        raise ValueError("Invalid private project name")
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise ValueError("Set CLOUDFLARE_ACCESS_EMAIL to the permitted personal email")
    return account, token, project, email


def api_get(client: httpx.Client, url: str) -> object:
    response = client.get(url)
    if not response.is_success:
        raise ValueError(f"Cloudflare Access check failed (HTTP {response.status_code}); check Access permissions")
    payload = response.json()
    if not payload.get("success") or "result" not in payload:
        raise ValueError("Cloudflare did not confirm Access configuration")
    if payload.get("result_info", {}).get("total_pages", 1) > 1:
        raise ValueError("Access inventory is paginated; a full review is required")
    return payload["result"]


def check_access() -> AccessProof:
    account, token, project, email = access_settings()
    base = f"https://api.cloudflare.com/client/v4/accounts/{account}"
    with httpx.Client(timeout=30, follow_redirects=False,
                      headers={"Authorization": f"Bearer {token}"}) as client:
        page = api_get(client, f"{base}/pages/projects/{project}")
        if not isinstance(page, dict) or page.get("name") != project:
            raise ValueError("Cloudflare did not confirm the selected Pages project")
        hostname = page.get("subdomain", "")
        if not re.fullmatch(r"[a-z0-9-]+\.pages\.dev", hostname):
            raise ValueError("Invalid Pages hostname")
        if any(domain != hostname for domain in page.get("domains", [])):
            raise ValueError("Custom domains require a separate private access review")
        bindings = page.get("deployment_configs", {}).get("production", {}).get("env_vars", {})
        if bindings.get("PERSONAL_EMAIL", {}).get("value", "").strip().lower() != email:
            raise ValueError("Configure PERSONAL_EMAIL on the Pages production server")
        if bindings.get("PERSONAL_SESSION_SECRET", {}).get("type") != "secret_text":
            raise ValueError("Configure PERSONAL_SESSION_SECRET as a server secret")
        org = api_get(client, f"{base}/access/organizations")
        auth_domain = org.get("auth_domain", "") if isinstance(org, dict) else ""
        if not re.fullmatch(r"[a-z0-9-]+\.cloudflareaccess\.com", auth_domain):
            raise ValueError("A Cloudflare Zero Trust organization is required")
        idps = api_get(client, f"{base}/access/identity_providers")
        if not isinstance(idps, list):
            raise ValueError("Invalid Access identity provider response")
        otp_ids = {x["id"] for x in idps if x.get("type") == "onetimepin" and x.get("id")}
        apps = api_get(client, f"{base}/access/apps?per_page=100")
        if not isinstance(apps, list):
            raise ValueError("Invalid Access application response")
        covered = set()
        for app in apps:
            domains = set(app.get("self_hosted_domains") or [])
            if app.get("domain"):
                domains.add(app["domain"])
            relevant = {d for d in domains if d.partition("/")[0] == hostname
                        or d.partition("/")[0].endswith("." + hostname)}
            if not relevant:
                continue
            # A more specific path application can override the root application's policy.
            idp_ids = set(app.get("allowed_idps") or [])
            if (app.get("type") != "self_hosted" or not idp_ids or not idp_ids <= otp_ids
                    or app.get("allow_authenticate_via_warp")):
                raise ValueError("Every matching Access application must use only email OTP")
            policies = api_get(client, f"{base}/access/apps/{app['id']}/policies")
            if not isinstance(policies, list):
                raise ValueError("Invalid Access policy response")
            allows = 0
            for policy in policies:
                if policy.get("decision") == "deny":
                    continue
                if (policy.get("decision") != "allow"
                        or policy.get("include") != [{"email": {"email": email}}]):
                    raise ValueError("Access policies must allow only the configured email; bypass is forbidden")
                allows += 1
            if not allows:
                raise ValueError("An email-only Allow policy is required")
            covered.update(relevant)
        if "*." + hostname not in covered:
            raise ValueError("Access must protect legacy deployment and preview hostnames")
    proof = AccessProof(hostname, auth_domain)
    verify_anonymous_access(proof)
    return proof


def verify_anonymous_access(proof: AccessProof, extra_hosts: tuple[str, ...] = ()) -> None:
    with httpx.Client(timeout=20, follow_redirects=False) as client:
        for host in (proof.hostname,) + extra_hosts:
            if host != proof.hostname and not host.endswith("." + proof.hostname):
                raise ValueError("Unexpected private deployment hostname")
            for path in ("/", "/data/latest.json", "/data/status.json"):
                response = client.get(f"https://{host}{path}")
                if response.status_code in {401, 403}:
                    continue
                target = urlparse(response.headers.get("location", ""))
                email_entry = (host == proof.hostname and target.hostname in {None, proof.hostname}
                               and target.path == "/login")
                legacy_login = (host != proof.hostname and target.hostname == proof.auth_domain
                                and target.path.startswith("/cdn-cgi/access/login"))
                login_redirect = response.status_code in {302, 303, 307} and (email_entry or legacy_login)
                if not login_redirect:
                    raise ValueError("A private route is accessible without its entry restriction; deployment is blocked")
        entry = client.get(f"https://{proof.hostname}/login")
        if entry.status_code != 200 or 'data-personal-entry="email"' not in entry.text:
            raise ValueError("The production email entry form is unavailable")


def check_private_configuration(root: Path = ROOT) -> None:
    settings = load_api_settings(root / "config/news_apis.json")
    if settings["usage_scope"] != "local_private":
        raise ValueError("Personal Live requires local_private collection settings")


def load_private_edition(root: Path = ROOT) -> Edition:
    check_private_configuration(root)
    edition = Edition.model_validate_json((root / "public/data/latest.json").read_text(encoding="utf-8"))
    if edition.mode != "live" or edition.publicationScope != "local_private" or not edition.issues:
        raise ValueError("A nonempty validated private Live edition is required")
    return edition


def stage_private_assets(root: Path, staging: Path) -> Edition:
    edition = load_private_edition(root)
    public = staging / "public"
    data = public / "data"
    data.mkdir(parents=True, exist_ok=False)
    (data / "latest.json").write_text(edition.model_dump_json(indent=2), encoding="utf-8")
    if (root / "public/favicon.svg").exists():
        shutil.copyfile(root / "public/favicon.svg", public / "favicon.svg")
    status_path = root / "public/data/status.json"
    if status_path.exists():
        status = json.loads(status_path.read_text(encoding="utf-8"))
        if status.get("state") not in {"ok", "error"} or not isinstance(status.get("message"), str):
            raise ValueError("Invalid private update status")
        shutil.copyfile(status_path, data / "status.json")
    (public / "_headers").write_text(
        "/*\n  Cache-Control: private, no-store\n  X-Robots-Tag: noindex, nofollow\n",
        encoding="utf-8",
    )
    shutil.copyfile(root / "server/email-gate.mjs", public / "_worker.js")
    (public / "_routes.json").write_text(json.dumps({"version": 1, "include": ["/*"], "exclude": []}), encoding="utf-8")
    return edition


def build_private(root: Path = ROOT) -> Path:
    # This guard runs before staging or including any real news in the remote build.
    check_private_configuration(root)
    proof = check_access()
    work = (root / ".tools/private-deploy").resolve()
    if not work.is_relative_to(root.resolve()):
        raise ValueError("Private build must stay within the project")
    work.mkdir(parents=True, exist_ok=True)
    output = work / "dist"
    environment = os.environ.copy()
    npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
    if npm is None and os.name == "nt":
        nodes = sorted((root / ".tools").glob("node-*-win-x64"), reverse=True)
        if nodes:
            environment["PATH"] = str(nodes[0]) + os.pathsep + environment.get("PATH", "")
            npm = str(nodes[0] / "npm.cmd")
    if npm is None:
        raise ValueError("Install Node and run npm ci before building")
    with tempfile.TemporaryDirectory(prefix="stage-", dir=work) as directory:
        staging = Path(directory).resolve()
        if not staging.is_relative_to(work):
            raise ValueError("Invalid private staging path")
        edition = stage_private_assets(root, staging)
        environment.update({"PUBLIC_ASSET_DIR": str(staging / "public"),
                            "VITE_DATA_MODE": "live", "VITE_BASE_PATH": "./"})
        subprocess.run([npm, "run", "build", "--", "--outDir", str(output)],
                       cwd=root, env=environment, check=True)
    delivered = Edition.model_validate_json((output / "data/latest.json").read_text(encoding="utf-8"))
    if delivered != edition or (output / "data/demo.json").exists():
        raise ValueError("Private output differs from the selected Live edition")
    verify_anonymous_access(proof)
    print(f"Private Live build verified: {len(edition.issues)} issues; output=.tools/private-deploy/dist")
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    checks = parser.add_mutually_exclusive_group()
    checks.add_argument("--check-access", action="store_true")
    checks.add_argument("--check-edition", action="store_true")
    args = parser.parse_args()
    if args.check_access:
        check_private_configuration()
        check_access()
        print("Production email gate and legacy URL protection verified.")
    elif args.check_edition:
        load_private_edition()
        print("Private Live edition and collection scope verified.")
    else:
        build_private()
