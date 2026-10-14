"""Build only the selected, publication-approved edition in an isolated directory."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pipeline.api_pipeline import load_api_settings  # noqa: E402
from pipeline.models import Edition  # noqa: E402
from scripts.validate_public import validate_public  # noqa: E402


def check_live_permission(root: Path = ROOT) -> None:
    settings = load_api_settings(root / "config/news_apis.json")
    if settings["usage_scope"] != "public" or not settings["public_reuse_granted"] or not settings["permission_reference"]:
        raise ValueError("Public Live requires documented news and image publication permission")


def stage_public_assets(root: Path, staging: Path, mode: str) -> Edition:
    if mode not in {"demo", "live"}:
        raise ValueError("Unknown public data mode")
    if mode == "live":
        check_live_permission(root)
    filename = "demo.json" if mode == "demo" else "latest.json"
    source = root / "public/data" / filename
    edition = Edition.model_validate_json(source.read_text(encoding="utf-8"))
    if edition.mode != mode or edition.publicationScope != "public":
        raise ValueError("The selected edition is not approved for public deployment")
    public = staging / "public"
    data = public / "data"
    data.mkdir(parents=True, exist_ok=False)
    # Include explicit defaults such as publicationScope for deployment checks.
    (data / filename).write_text(edition.model_dump_json(indent=2), encoding="utf-8")
    favicon = root / "public/favicon.svg"
    if favicon.exists():
        shutil.copyfile(favicon, public / "favicon.svg")
    if mode == "live" and (root / "public/data/status.json").exists():
        status = json.loads((root / "public/data/status.json").read_text(encoding="utf-8"))
        datetime.fromisoformat(status["attemptedAt"])
        if status["state"] not in {"ok", "error"} or not isinstance(status["message"], str):
            raise ValueError("Invalid update status")
        shutil.copyfile(root / "public/data/status.json", data / "status.json")
    (public / "_headers").write_text(
        "/data/*\n  Cache-Control: no-store\n/assets/*\n  Cache-Control: public, max-age=31536000, immutable\n",
        encoding="utf-8",
    )
    validate_public(mode, staging)
    return edition


def build_public(mode: str, root: Path = ROOT) -> Path:
    work = (root / ".tools/public-deploy").resolve()
    if not work.is_relative_to(root.resolve()):
        raise ValueError("Public build must stay within the project")
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
            raise ValueError("Staging must stay within the public-build directory")
        edition = stage_public_assets(root, staging, mode)
        environment.update({"PUBLIC_ASSET_DIR": str(staging / "public"),
                            "VITE_DATA_MODE": mode, "VITE_BASE_PATH": "./"})
        subprocess.run([npm, "run", "build", "--", "--outDir", str(output)],
                       cwd=root, env=environment, check=True)
    delivered = Edition.model_validate_json((output / "data" / ("demo.json" if mode == "demo" else "latest.json")).read_text(encoding="utf-8"))
    if delivered != edition or (mode == "demo" and (output / "data/latest.json").exists()):
        raise ValueError("Public build data does not match the selected edition")
    print(f"Public {mode} build verified: {len(edition.issues)} issues; output=.tools/public-deploy/dist")
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["demo", "live"], default="demo")
    parser.add_argument("--check-live-permission", action="store_true")
    args = parser.parse_args()
    if args.check_live_permission:
        check_live_permission()
        print("Public Live permission configuration verified.")
    else:
        build_public(args.mode)
