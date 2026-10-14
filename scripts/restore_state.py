"""Restore only validated public news state from a trusted Actions artifact."""
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pipeline.models import Edition  # noqa: E402
from pipeline.storage import atomic_json, save_edition  # noqa: E402

archive = Path(sys.argv[1])
if not archive.exists():
    print("No prior news-state artifact; first Live update must succeed.")
    raise SystemExit(0)
with zipfile.ZipFile(archive) as bundle:
    names = {Path(name).name: name for name in bundle.namelist()}
    if "latest.json" in names:
        edition = Edition.model_validate_json(bundle.read(names["latest.json"]))
        if edition.mode != "live":
            raise ValueError("Prior artifact is not a Live edition")
        save_edition(ROOT / "public/data/latest.json", edition)
    if "status.json" in names:
        status = json.loads(bundle.read(names["status.json"]))
        if status.get("state") in ["ok", "error"] and isinstance(status.get("message"), str):
            atomic_json(ROOT / "public/data/status.json", status)
print("Prior validated Live edition restored.")
