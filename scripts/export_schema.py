"""Export the shared schema without rewriting any DEMO or Live data."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pipeline.models import Edition  # noqa: E402

target = ROOT / "data/edition.schema.json"
target.write_text(json.dumps(Edition.model_json_schema(), ensure_ascii=False, indent=2), encoding="utf-8")
print("Shared edition schema exported.")
