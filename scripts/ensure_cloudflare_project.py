"""Create the selected Direct Upload Pages project once, using Actions Secrets."""
from __future__ import annotations

import os
import re
from pathlib import Path

import httpx


def ensure_project() -> str:
    account = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "").strip()
    token = os.environ.get("CLOUDFLARE_API_TOKEN", "").strip()
    project = os.environ.get("CLOUDFLARE_PROJECT_NAME", "today-issue-dlwo8520").strip()
    if not re.fullmatch(r"[a-fA-F0-9]{32}", account) or not token:
        raise ValueError("Set CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN in repository Actions Secrets")
    if not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,56}[a-z0-9])?", project):
        raise ValueError("Invalid Cloudflare Pages project name")
    endpoint = f"https://api.cloudflare.com/client/v4/accounts/{account}/pages/projects"
    with httpx.Client(timeout=30, follow_redirects=False,
                      headers={"Authorization": f"Bearer {token}"}) as client:
        response = client.get(f"{endpoint}/{project}")
        if response.status_code == 404:
            response = client.post(endpoint, json={"name": project, "production_branch": "main"})
        if not response.is_success:
            raise ValueError(f"Cloudflare project request failed (HTTP {response.status_code}); check account and Pages Edit permission")
        payload = response.json()
        if not payload.get("success") or not isinstance(payload.get("result"), dict):
            raise ValueError("Cloudflare did not confirm a valid Pages project")
        result = payload["result"]
        if result.get("name") != project or result.get("production_branch") != "main":
            raise ValueError("Existing Pages project must use the selected name and main production branch")
        if result.get("source"):
            raise ValueError("Use a Direct Upload Pages project; existing Git-integrated project requires review")
        subdomain = result.get("subdomain", "")
        if not isinstance(subdomain, str) or not re.fullmatch(r"[a-z0-9-]+\.pages\.dev", subdomain):
            raise ValueError("Cloudflare did not confirm a valid Pages subdomain")
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with Path(output).open("a", encoding="utf-8") as stream:
            stream.write(f"production_url=https://{subdomain}\n")
    print(f"Cloudflare Pages project ready: {project}")
    return project


if __name__ == "__main__":
    ensure_project()
