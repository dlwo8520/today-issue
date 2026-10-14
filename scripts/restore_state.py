"""Restore validated news state with the requested scope from a trusted artifact."""
import argparse
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pipeline.models import Edition  # noqa: E402
from pipeline.storage import atomic_json, save_edition  # noqa: E402


def restore_state(archive: Path, scope: str = "public", root: Path = ROOT) -> None:
    if scope not in {"public", "local_private"}:
        raise ValueError("Unknown prior state scope")
    if not archive.exists():
        print("No prior news-state artifact; first Live update must succeed.")
        return
    with zipfile.ZipFile(archive) as bundle:
        names = {Path(name).name: name for name in bundle.namelist()}
        if "latest.json" in names:
            edition = Edition.model_validate_json(bundle.read(names["latest.json"]))
            if edition.mode != "live":
                raise ValueError("Prior artifact is not a Live edition")
            if edition.publicationScope != scope:
                raise ValueError("Prior artifact has a different publication scope")
            save_edition(root / "public/data/latest.json", edition)
        if "status.json" in names:
            status = json.loads(bundle.read(names["status.json"]))
            if status.get("state") in ["ok", "error"] and isinstance(status.get("message"), str):
                atomic_json(root / "public/data/status.json", status)
    print("Prior validated Live edition restored.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", type=Path)
    parser.add_argument("--scope", choices=["public", "local_private"], default="public")
    args = parser.parse_args()
    restore_state(args.archive, args.scope)
