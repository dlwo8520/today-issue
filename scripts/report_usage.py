"""Aggregate recorded request events once, including failed validation runs."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pipeline.storage import atomic_json  # noqa: E402

events = {}
for path in (ROOT / "data/reports").rglob("*.json"):
    if path.name == "usage-total.json":
        continue
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
        for event in report.get("usage", {}).get("events", []):
            identity = (event.get("at"), event.get("provider"), event.get("stage"), event.get("state"))
            events[identity] = event
    except (OSError, ValueError, TypeError):
        continue
network = [e for e in events.values() if e.get("provider") in {"gnews", "newsdata"} and e.get("state") in {"success", "error"}]
gpt = [e for e in events.values() if e.get("provider") == "openai" and e.get("state") in {"success", "error"}]
models = {}
for event in gpt:
    model = event.get("model", "unknown")
    totals = models.setdefault(model, {"requestAttempts": 0, "inputTokens": 0, "outputTokens": 0, "knownEstimatedUsd": 0.0, "unknownCostRequests": 0})
    totals["requestAttempts"] += 1
    totals["inputTokens"] += event.get("inputTokens") or 0
    totals["outputTokens"] += event.get("outputTokens") or 0
    if event.get("estimatedUsd") is None:
        totals["unknownCostRequests"] += 1
    else:
        totals["knownEstimatedUsd"] += event["estimatedUsd"]
for totals in models.values():
    totals["knownEstimatedUsd"] = round(totals["knownEstimatedUsd"], 8)
result = {"newsRequestAttempts": {p: sum(e["provider"] == p for e in network) for p in ["gnews", "newsdata"]},
          "models": models, "gptRequestAttempts": len(gpt),
          "knownEstimatedUsd": round(sum(e.get("estimatedUsd") or 0 for e in gpt), 8),
          "unknownCostRequests": sum(e.get("estimatedUsd") is None for e in gpt),
          "costBasis": "Observed token usage and recorded published rates; not an invoice",
          "newsApiMonetaryCost": None}
atomic_json(ROOT / "data/reports/usage-total.json", result)
print(json.dumps(result, ensure_ascii=True, indent=2))
