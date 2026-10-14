"""Package reviewable source; include a static build only without private news."""
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
archive = ROOT.parent / "today-issue-delivery.zip"
excluded = {"node_modules", ".tools", ".venv", "__pycache__", ".pytest_cache", ".ruff_cache",
            "test-results", "playwright-report", ".git", "raw", "debug", "cache", "reports"}
private_data = False
live_path = ROOT / "public/data/latest.json"
if live_path.exists():
    private_data = json.loads(live_path.read_text(encoding="utf-8")).get("publicationScope") == "local_private"
files = []
for path in ROOT.rglob("*"):
    if not path.is_file():
        continue
    relative = path.relative_to(ROOT)
    if any(part in excluded for part in relative.parts):
        continue
    if relative.as_posix() == "docs/API_LIVE_REPORT.md":
        continue
    if private_data and (relative.parts[0] == "dist" or relative.as_posix() in {"public/data/latest.json", "public/data/status.json"}):
        continue
    if path.name.startswith(".env") and path.name != ".env.example":
        continue
    if path.suffix in {".log", ".pyc", ".tsbuildinfo", ".zip", ".tmp"} or path.name in {".pipeline.lock", "demo-output.json"}:
        continue
    files.append(path)
with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
    for path in files:
        bundle.write(path, "today-issue/" + path.relative_to(ROOT).as_posix())
with zipfile.ZipFile(archive) as bundle:
    if bundle.testzip() is not None:
        raise RuntimeError("Delivery archive integrity failed")
    if any("/.env" in name and not name.endswith("/.env.example") for name in bundle.namelist()):
        raise RuntimeError("Environment file included in archive")
print(f"Packaged {len(files)} files: {archive} ({archive.stat().st_size:,} bytes); private Live data/build excluded={private_data}")
