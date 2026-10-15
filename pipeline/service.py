"""Project-wide stop switch for collection and paid model requests."""
import json
from pathlib import Path

SERVICE_FILE = Path(__file__).resolve().parents[1] / "config/service.json"


class UpdatesDisabled(RuntimeError):
    pass


def require_updates_enabled() -> None:
    try:
        settings = json.loads(SERVICE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise UpdatesDisabled("Updates disabled: a valid service policy is required; existing edition preserved.") from exc
    if not isinstance(settings, dict) or settings.get("updates_enabled") is not True:
        raise UpdatesDisabled("Updates disabled: GPT and news collection are stopped; existing edition preserved.")
