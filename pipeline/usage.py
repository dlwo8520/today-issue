from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from .normalize import KST
from .storage import atomic_json

SECRET_NAMES = ("GNEWS_API_KEY", "NEWSDATA_API_KEY", "OPENAI_API_KEY")


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: "[REDACTED]" if k.lower() in {"apikey", "api_key", "authorization"} else redact(v)
                for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(v) for v in value]
    if isinstance(value, str):
        for name in SECRET_NAMES:
            secret = os.environ.get(name, "").strip()
            if secret:
                value = value.replace(secret, "[REDACTED]")
        return re.sub(r"(?i)(api[_-]?key=)[^&\s]+", r"\1[REDACTED]", value)
    return value


class BudgetExceeded(ValueError):
    pass


@dataclass
class UsageLedger:
    max_news_requests: int = 4
    provider_limits: dict[str, int] = field(default_factory=lambda: {"gnews": 1, "newsdata": 3})
    max_gpt_requests: int = 3
    pricing: dict = field(default_factory=dict)
    events: list[dict] = field(default_factory=list)
    news_calls: dict[str, int] = field(default_factory=dict)
    gpt_calls: int = 0

    def reserve_news(self, provider: str) -> None:
        if sum(self.news_calls.values()) >= self.max_news_requests or self.news_calls.get(provider, 0) >= self.provider_limits.get(provider, 0):
            raise BudgetExceeded(f"{provider}: configured request budget exhausted")
        self.news_calls[provider] = self.news_calls.get(provider, 0) + 1

    def reserve_gpt(self) -> None:
        if self.gpt_calls >= self.max_gpt_requests:
            raise BudgetExceeded("Configured GPT request budget exhausted")
        self.gpt_calls += 1

    def record(self, provider: str, stage: str, state: str, **details: Any) -> None:
        self.events.append(redact({"at": datetime.now(KST).isoformat(), "provider": provider,
                                  "stage": stage, "state": state, **details}))

    def record_gpt(self, stage: str, model: str, usage: Any, *, response_model: str | None = None, response_id: str | None = None) -> None:
        raw = usage.model_dump() if hasattr(usage, "model_dump") else usage
        input_tokens = raw.get("input_tokens") if isinstance(raw, dict) else None
        output_tokens = raw.get("output_tokens") if isinstance(raw, dict) else None
        cached = ((raw.get("input_tokens_details") or {}).get("cached_tokens", 0)) if isinstance(raw, dict) else None
        rates = self.pricing.get("models", {}).get(model)
        cost = None
        if rates and input_tokens is not None and output_tokens is not None:
            cached = min(cached or 0, input_tokens)
            cost = ((input_tokens - cached) * rates["input_per_million_usd"] + cached * rates.get("cached_input_per_million_usd", rates["input_per_million_usd"]) + output_tokens * rates["output_per_million_usd"]) / 1_000_000
        self.record("openai", stage, "success", model=model, inputTokens=input_tokens,
                    cachedInputTokens=cached, outputTokens=output_tokens, estimatedUsd=cost,
                    responseModel=response_model, responseId=response_id,
                    pricingSource=rates.get("source", self.pricing.get("source")) if rates else None,
                    costBasis="published token rates; not a billing invoice" if cost is not None else "usage or model rate unavailable")

    def report(self) -> dict:
        calls = [e for e in self.events if e["provider"] == "openai" and e["state"] in {"success", "error"}]
        costs = [e.get("estimatedUsd") for e in calls]
        known = [c for c in costs if c is not None]
        return {"newsRequestAttempts": dict(self.news_calls), "gptRequestAttempts": self.gpt_calls,
                "knownEstimatedUsd": round(sum(known), 8),
                "totalEstimatedUsd": round(sum(known), 8) if costs and all(c is not None for c in costs) else None,
                "pricingCheckedAt": self.pricing.get("checked_at"),
                "pricingSources": sorted({e["pricingSource"] for e in calls if e.get("pricingSource")}),
                "newsApiMonetaryCost": None, "events": redact(self.events)}


class LocalCache:
    def __init__(self, root: Path, ttl_hours: float = 6):
        self.root, self.ttl_hours = root, ttl_hours

    @staticmethod
    def fingerprint(value: Any) -> str:
        return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()

    def get(self, namespace: str, key: Any, *, permanent: bool = False) -> dict | None:
        path = self.root / namespace / (self.fingerprint(key) + ".json")
        try:
            result = json.loads(path.read_text(encoding="utf-8"))
            saved = datetime.fromisoformat(result["savedAt"])
            age = (datetime.now(KST) - saved).total_seconds()
            if not permanent and not 0 <= age <= self.ttl_hours * 3600:
                return None
            return result
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def put(self, namespace: str, key: Any, value: Any) -> None:
        path = self.root / namespace / (self.fingerprint(key) + ".json")
        atomic_json(path, redact({"savedAt": datetime.now(KST).isoformat(), "value": value}))
