import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pipeline.models import Edition  # noqa: E402


def validate_public(mode: str, root: Path = ROOT) -> Edition:
    path = root / "public/data" / ("demo.json" if mode == "demo" else "latest.json")
    edition = Edition.model_validate_json(path.read_text(encoding="utf-8"))
    if edition.mode != mode:
        raise ValueError("Refusing a mismatched data mode")
    if edition.publicationScope != "public":
        raise ValueError("Local private API evaluations cannot be publicly deployed")
    # Even a DEMO Vite build copies public/; private Live files must not travel with it.
    private_path = root / "public/data/latest.json"
    if mode == "demo" and private_path.exists():
        private_edition = Edition.model_validate_json(private_path.read_text(encoding="utf-8"))
        if private_edition.publicationScope != "public":
            raise ValueError("Private Live JSON would be included in the static build")
    return edition


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["demo", "live"], required=True)
    args = parser.parse_args()
    checked = validate_public(args.mode)
    print(f"Validated {checked.mode} edition with {len(checked.issues)} issues.")
