from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
from openai import OpenAI, OpenAIError

from .grouping import group_articles
from .models import Article, Edition
from .news_apis import GNewsAdapter, NewsAPIError, NewsDataAdapter, collect_api_news, known_publisher
from .normalize import KST, deduplicate
from .ranking import rank_groups
from .storage import atomic_json, pipeline_lock, save_edition
from .summarize import GPTSummarizer
from .usage import BudgetExceeded, LocalCache, UsageLedger, redact

ROOT = Path(__file__).resolve().parents[1]
LOG = logging.getLogger(__name__)


def load_api_settings(path: Path) -> dict:
    config = json.loads(path.read_text(encoding="utf-8"))
    limits = {"max_news_requests": (0, 50), "max_gnews_requests": (0, 30), "max_newsdata_requests": (0, 20),
              "max_related_queries": (0, 10), "articles_per_request": (1, 10), "news_retries": (0, 2),
              "max_gpt_issues": (1, 6), "max_gpt_requests": (0, 60), "min_excerpt_chars": (1, 2000),
              "max_excerpt_chars": (50, 10000), "timeout_seconds": (1, 120), "max_response_bytes": (1024, 10_485_760)}
    for name, (lower, upper) in limits.items():
        if not isinstance(config.get(name), int) or not lower <= config[name] <= upper:
            raise ValueError(f"Invalid API setting: {name}")
    for name, lower, upper in [("gnews_discovery_windows", 1, 14), ("max_gnews_related_queries", 0, 10), ("gnews_extra_page_windows", 0, 6)]:
        value = config.get(name, 1 if name == "gnews_discovery_windows" else 0)
        if not isinstance(value, int) or not lower <= value <= upper:
            raise ValueError(f"Invalid API setting: {name}")
    if config.get("selection_strategy", "headline_coverage") not in {"headline_coverage", "overlap_then_engagement", "latest"}:
        raise ValueError("Unknown selection_strategy")
    if any(not isinstance(v, (int, float)) or not 0 <= v <= 10 for v in config.get("request_interval_seconds", {}).values()):
        raise ValueError("Invalid provider request interval")
    if not 1 <= config.get("query_keyword_limit", 3) <= 3:
        raise ValueError("Invalid keyword limit")
    if not 0 < config["cache_ttl_hours"] <= 24:
        raise ValueError("cache_ttl_hours must be between 0 and 24")
    if config["usage_scope"] not in {"local_private", "public"}:
        raise ValueError("Unknown usage_scope")
    if config["usage_scope"] == "public" and not (config["public_reuse_granted"] and config["permission_reference"]):
        raise ValueError("Public API publication requires a verified permission reference")
    return config


def effective_ranking_config(config: dict, api_config: dict) -> dict:
    return {**config, "weights": api_config["ranking_weights"],
            "min_excerpt_chars": api_config["min_excerpt_chars"],
            "require_gnews_candidate": api_config["require_gnews_candidate"],
            "selection_strategy": api_config.get("selection_strategy", "headline_coverage"),
            "max_issues": api_config["max_gpt_issues"],
            "quoted_event_terms": api_config.get("quoted_event_terms", []),
            "specific_event_anchors": api_config.get("specific_event_anchors", []),
            "context_entities": api_config.get("context_entities", [])}


def inspect_candidates(articles: list[Article], end: datetime, config: dict) -> tuple[list[Article], dict]:
    filtered = [a for a in articles if end - timedelta(hours=config["hours"]) <= a.published_at <= end]
    recognized = [a for a in filtered if known_publisher(a)]
    cleaned = deduplicate(recognized)
    groups = group_articles(cleaned, config)
    candidates = rank_groups(groups, end, config)
    return cleaned, {
        "beforeDeduplication": len(filtered), "afterDeduplication": len(cleaned), "outsideWindow": len(articles) - len(filtered),
        "unknownPublisherExcluded": len(filtered) - len(recognized),
        "groupCount": len(groups), "eligibleIssueCount": len(candidates),
        "selectedIssueCount": min(len(candidates), config["max_issues"]),
        "groups": [{"articleIds": [a.id for a in group], "titles": [a.title for a in group],
                    "publishers": sorted({a.publisher for a in group}),
                    "independentSourceCount": len({a.independence_key for a in group}),
                    "providers": sorted({p for a in group for p in a.providers})} for group in groups],
        "candidates": [{"articleIds": [a.id for a in group], "ranking": ranking.model_dump()} for group, ranking in candidates],
    }


def load_snapshot(path: Path, ttl_hours: float, window_hours: int | None = None) -> tuple[list[Article], datetime, list[str]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("kind") != "api_collection" or payload.get("mode") != "live":
        raise ValueError("Not a real API collection snapshot")
    if window_hours is not None and payload.get("windowHours", 24) != window_hours:
        raise ValueError("Collection window changed; collect articles for the new period first")
    end = datetime.fromisoformat(payload["windowEnd"])
    if end.tzinfo is None or not 0 <= (datetime.now(KST) - end).total_seconds() <= ttl_hours * 3600:
        raise ValueError("Collection snapshot expired; collect fresh API data")
    articles = [Article.model_validate(row) for row in payload["articles"]]
    if any(a.method != "official_api" or not a.providers for a in articles):
        raise ValueError("API snapshot contains unexpected non-API data")
    return articles, end, payload.get("errors", [])


def request_plan(args: Any, config: dict, api_config: dict) -> dict:
    attempts = 1 + api_config["news_retries"]
    windows = min(api_config.get("gnews_discovery_windows", 1), (config["hours"] + 23) // 24)
    gnews_queries = 1 if args.stage == "probe" else windows + min(windows, api_config.get("gnews_extra_page_windows", 0)) + min(api_config.get("max_gnews_related_queries", 0), api_config["max_related_queries"])
    gnews = min(gnews_queries * attempts, api_config["max_gnews_requests"]) if args.providers in {"both", "gnews"} else 0
    queries = 1 if args.stage == "probe" else api_config["max_related_queries"]
    newsdata = min(queries * attempts, api_config["max_newsdata_requests"]) if args.providers in {"both", "newsdata"} else 0
    news = 0 if args.from_cache or args.stage == "select" else min(api_config["max_news_requests"], gnews + newsdata)
    issues = 1 if args.stage == "summarize" else args.max_issues or api_config["max_gpt_issues"]
    # Rejected candidates can consume calls without increasing the published count.
    candidate_limit = 1 if args.stage == "summarize" else min(config["max_candidates"], issues) if api_config.get("selection_strategy") == "overlap_then_engagement" else config["max_candidates"]
    gpt = min(3 * candidate_limit, api_config["max_gpt_requests"]) if args.stage in {"summarize", "live"} else 0
    needed = []
    if news:
        if args.providers in {"gnews", "both"}:
            needed.append("GNEWS_API_KEY")
        if args.providers in {"newsdata", "both"}:
            needed.append("NEWSDATA_API_KEY")
    if gpt:
        needed += ["OPENAI_API_KEY", "OPENAI_MODEL"]
    return {"stage": args.stage, "dryRun": args.dry_run, "usageScope": api_config["usage_scope"],
            "maximumNewsRequestAttempts": news, "maximumGPTLogicalRequests": gpt,
            "maxIssues": issues, "maxRelatedQueries": api_config["max_related_queries"],
            "cacheMayReduceCalls": not args.fresh, "articleWindowHours": config["hours"],
            "missingConfiguration": [name for name in needed if not os.environ.get(name, "").strip()],
            "estimatedCostUsd": None, "costNote": "Token sizes are unknown before processing; no fabricated cost estimate",
            "accountPlans": api_config["account_plan"], "accountPlansVerified": False,
            "generatedSummary": False}


def run_api_stage(args: Any) -> int:
    config = json.loads(args.config.read_text(encoding="utf-8"))
    api_config = load_api_settings(args.api_config)
    for option, setting in [("max_news_requests", "max_news_requests"), ("max_related_queries", "max_related_queries"),
                             ("max_gpt_requests", "max_gpt_requests")]:
        value = getattr(args, option)
        if value is not None:
            api_config[setting] = value
    if getattr(args, "max_newsdata_requests", None) is not None:
        api_config["max_newsdata_requests"] = args.max_newsdata_requests
    if args.max_issues is not None:
        api_config["max_gpt_issues"] = args.max_issues
    if not 0 <= api_config["max_news_requests"] <= 50 or not 0 <= api_config["max_related_queries"] <= 10 or not 0 <= api_config["max_gpt_requests"] <= 60 or not 0 <= api_config["max_newsdata_requests"] <= 20:
        raise ValueError("CLI request limits out of range")
    plan = request_plan(args, config, api_config)
    LOG.info("Request plan: news <= %d, GPT <= %d; scope=%s", plan["maximumNewsRequestAttempts"], plan["maximumGPTLogicalRequests"], plan["usageScope"])
    if args.dry_run:
        print(json.dumps(redact(plan), ensure_ascii=False, indent=2))
        return 0
    if args.stage != "probe" and args.providers != "both":
        raise ValueError("Use --providers only for probe; collection uses GNews discovery and NewsData enrichment")
    if args.stage == "select" and not args.from_cache:
        raise ValueError("Selection is offline: add --from-cache after collecting news")
    ledger = UsageLedger(max_news_requests=api_config["max_news_requests"],
                         provider_limits={"gnews": api_config["max_gnews_requests"], "newsdata": api_config["max_newsdata_requests"]},
                         max_gpt_requests=api_config["max_gpt_requests"], pricing=api_config.get("pricing", {}))
    report_file = ROOT / "data/reports" / f"{args.stage}.json"
    report: dict = {"startedAt": datetime.now(KST).isoformat(), "plan": plan, "state": "running",
                    "actualArticleCount": None, "finalIssueCount": None, "apiChecks": {}}
    output = args.output or ROOT / "public/data/latest.json"
    try:
        with pipeline_lock(ROOT / "data/raw/.api-pipeline.lock"):
            if args.stage == "probe":
                end = datetime.now(KST)
                with httpx.Client(timeout=api_config["timeout_seconds"], follow_redirects=False) as client:
                    cache = LocalCache(ROOT / "data/cache", api_config["cache_ttl_hours"])
                    adapters = {"gnews": GNewsAdapter(client, api_config, ledger, cache, args.fresh),
                                "newsdata": NewsDataAdapter(client, api_config, ledger, cache, args.fresh)}
                    providers = list(adapters) if args.providers == "both" else [args.providers]
                    for provider in providers:
                        try:
                            rows, info = adapters[provider].collect(end - timedelta(hours=config["hours"]), end, args.query)
                            report["apiChecks"][provider] = info
                        except (NewsAPIError, BudgetExceeded) as exc:
                            report["apiChecks"][provider] = {"state": "not_run" if getattr(exc, "category", "") == "missing_configuration" else "error",
                                                            "reason": str(exc), "httpStatus": getattr(exc, "status", None)}
                report["state"] = "success" if all(v["state"] in {"success", "cached"} for v in report["apiChecks"].values()) else "incomplete"
                return 0 if report["state"] == "success" else 1
            snapshot_path = ROOT / "data/raw/api-collected.json"
            if args.from_cache:
                articles, end, errors = load_snapshot(snapshot_path, api_config["cache_ttl_hours"], config["hours"])
                report["collectionState"] = "snapshot_reused"
            else:
                end = datetime.now(KST)
                with httpx.Client(timeout=api_config["timeout_seconds"], follow_redirects=False) as client:
                    cache = LocalCache(ROOT / "data/cache", api_config["cache_ttl_hours"])
                    result = collect_api_news(GNewsAdapter(client, api_config, ledger, cache, args.fresh),
                                              NewsDataAdapter(client, api_config, ledger, cache, args.fresh),
                                              end - timedelta(hours=config["hours"]), end, config, api_config)
                articles, errors = result.articles, result.errors
                report["apiChecks"] = result.diagnostics
                if not articles:
                    raise ValueError("No real API articles collected; no fabricated or demo fallback")
                history_path = ROOT / "data/raw/api-history.json"
                prior = []
                prior_path = history_path if history_path.exists() else snapshot_path
                if prior_path.exists():
                    history = json.loads(prior_path.read_text(encoding="utf-8"))
                    if history.get("usageScope") == api_config["usage_scope"]:
                        prior = [Article.model_validate(a) for a in history.get("articles", [])]
                prior = [a for a in prior if end - timedelta(hours=config["hours"]) <= a.published_at <= end and a.method == "official_api"]
                current_ids = {a.id for a in articles}
                report["historyArticlesReused"] = sum(a.id not in current_ids for a in prior)
                articles.extend(a for a in prior if a.id not in current_ids)
                atomic_json(history_path, redact({"usageScope": api_config["usage_scope"], "articles": [a.model_dump(mode="json") for a in deduplicate(articles)]}))
                atomic_json(snapshot_path, redact({"kind": "api_collection", "mode": "live", "windowEnd": end.isoformat(),
                            "windowHours": config["hours"],
                            "usageScope": api_config["usage_scope"], "errors": errors,
                            "articles": [a.model_dump(mode="json") for a in articles]}))
            ranking_config = effective_ranking_config(config, api_config)
            cleaned, inspection = inspect_candidates(articles, end, ranking_config)
            report.update({"actualArticleCount": len(articles), "analysis": inspection, "collectionWindowEnd": end.isoformat(), "sourceErrors": errors})
            if args.stage in {"collect", "select"}:
                report["state"] = "success"
                return 0
            if not inspection["eligibleIssueCount"]:
                raise ValueError("No adequately supported multi-source issue; previous edition preserved")
            if not os.environ.get("OPENAI_API_KEY", "").strip() or not os.environ.get("OPENAI_MODEL", "").strip():
                raise ValueError("Set OPENAI_API_KEY and OPENAI_MODEL locally before summarization")
            # Explicitly disable hidden SDK retries so request budgets are exact.
            client = OpenAI(timeout=45, max_retries=0)
            summarizer = GPTSummarizer(client=client, ledger=ledger, cache=LocalCache(ROOT / "data/cache"), fresh=args.fresh)
            processing_config = {**ranking_config, "max_issues": api_config["max_gpt_issues"]}
            if api_config.get("selection_strategy") == "overlap_then_engagement":
                processing_config["max_candidates"] = min(config["max_candidates"], api_config["max_gpt_issues"])
            if args.stage == "summarize":
                processing_config.update({"max_issues": 1, "max_candidates": 1})
            from .run import build_edition
            try:
                edition, debug = build_edition(cleaned, end, processing_config, summarizer, errors)
            finally:
                client.close()
            warnings = list(edition.warnings)
            if api_config.get("selection_strategy") == "overlap_then_engagement":
                warnings.append("최근 7일의 복수 출처 보도를 묶었습니다. 조회수·댓글수가 제공되지 않으면 독립 출처 수와 최신성으로 최대 6개를 선정합니다.")
            if api_config["usage_scope"] == "local_private":
                warnings.append("로컬 비공개 API 평가용 에디션입니다. 무료 플랜의 지연과 짧은 제공 텍스트가 반영될 수 있습니다.")
            if args.from_cache:
                warnings.append("저장된 수집 시각의 기사 캐시를 사용했습니다. 데이터 수집 기준 시각은 변경하지 않았습니다.")
            edition = Edition.model_validate({**edition.model_dump(mode="json"), "publicationScope": api_config["usage_scope"], "warnings": warnings})
            if api_config.get("fetch_missing_images", False):
                from .images import first_source_images
                edition, image_report = first_source_images(edition, LocalCache(ROOT / "data/cache"))
                report["firstSourceImages"] = image_report
            report.update({"finalIssueCount": len(edition.issues), "state": "success", "model": summarizer.model,
                           "summaryExamples": [i.model_dump(mode="json") for i in edition.issues], "summaryValidation": "passed"})
            atomic_json(ROOT / "data/debug/api-latest.json", redact(debug))
            if args.stage == "summarize":
                save_edition(ROOT / "data/raw/summary-preview.json", edition)
            else:
                save_edition(output, edition)
                atomic_json(output.parent / "status.json", {"attemptedAt": edition.updatedAt.isoformat(), "state": "ok", "message": "API 기반 검증 에디션을 생성했습니다."})
            return 0
    except (ValueError, OSError, OpenAIError, httpx.HTTPError, KeyError) as exc:
        report.update({"state": "error", "errorClass": type(exc).__name__,
                       "reason": str(exc) if isinstance(exc, (NewsAPIError, BudgetExceeded)) else "Stage failed; see configuration, input completeness and budget diagnostics"})
        if isinstance(exc, OSError):
            report["filesystemError"] = {"path": str(exc.filename) if exc.filename else None,
                                         "target": str(exc.filename2) if exc.filename2 else None,
                                         "windowsCode": getattr(exc, "winerror", None)}
        LOG.error("API stage failed (%s); previous edition preserved", type(exc).__name__)
        if args.stage == "live" and not isinstance(exc, FileExistsError):
            atomic_json(output.parent / "status.json", {"attemptedAt": datetime.now(KST).isoformat(), "state": "error", "message": "API 업데이트에 실패해 기존 정상 에디션을 보존했습니다."})
        return 1
    finally:
        report["usage"] = ledger.report()
        report["finishedAt"] = datetime.now(KST).isoformat()
        if report_file.exists():
            previous = json.loads(report_file.read_text(encoding="utf-8"))
            prior_id = LocalCache.fingerprint(previous.get("startedAt"))[:12]
            atomic_json(ROOT / "data/reports/history" / f"{args.stage}-{prior_id}.json", redact(previous))
        report_id = LocalCache.fingerprint(report["startedAt"])[:12]
        atomic_json(ROOT / "data/reports/history" / f"{args.stage}-{report_id}.json", redact(report))
        atomic_json(report_file, redact(report))
        LOG.info("Private stage report: data/reports/%s.json", args.stage)
