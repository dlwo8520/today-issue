from __future__ import annotations

import argparse
import hashlib
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Protocol

import httpx
from dotenv import load_dotenv
from openai import OpenAIError
from pydantic import ValidationError

from .grouping import group_articles
from .models import Article, Edition, Issue, Source, Summary
from .normalize import KST, deduplicate
from .ranking import balanced_sources, rank_groups
from .service import UpdatesDisabled, require_updates_enabled
from .sources import RSSAdapter, SourceConfig, collect_sources
from .storage import atomic_json, pipeline_lock, save_edition
from .summarize import GPTSummarizer, SummaryRejected

ROOT = Path(__file__).resolve().parents[1]
LOG = logging.getLogger(__name__)


class Summarizer(Protocol):
    def summarize(self, articles: list[Article]) -> Summary: ...


def build_edition(articles: list[Article], now: datetime, config: dict, summarizer: Summarizer, errors: list[str] | None = None) -> tuple[Edition, dict]:
    cleaned = deduplicate([a for a in articles if now - timedelta(hours=config["hours"]) <= a.published_at <= now])
    groups = group_articles(cleaned, config)
    candidates = rank_groups(groups, now, config)
    issues, rejected = [], 0
    for group, ranking in candidates[:config["max_candidates"]]:
        if len(issues) >= config["max_issues"]:
            break
        selected = balanced_sources(group, config["max_articles_per_issue"], prefer_latest=config.get("selection_strategy") == "latest")
        try:
            summary_inputs = sorted(selected, key=lambda a: (len(a.excerpt), a.published_at), reverse=True)
            summary = summarizer.summarize(summary_inputs)
            token = hashlib.sha256("|".join(sorted(a.id for a in group)).encode()).hexdigest()[:12]
            sources = [Source(id=a.id, publisher=a.publisher, title=a.title, url=a.url,
                              publishedAt=a.published_at, independenceKey=a.independence_key, method=a.method,
                              providers=a.providers, publisherKey=a.publisher_key, imageUrl=a.image_url) for a in selected]
            issue = Issue(**summary.model_dump(), id=f"{now.date().isoformat()}-{token}", rank=len(issues) + 1,
                          sources=sources, ranking=ranking)
            issues.append(issue)
        except (OpenAIError, SummaryRejected, ValidationError, ValueError) as exc:
            rejected += 1
            LOG.warning("Candidate rejected (%s)", type(exc).__name__)
    if not issues:
        raise ValueError("No verified eligible issues; previous edition preserved")
    methods = {i.ranking.method for i in issues}
    updated = datetime.now(KST)
    if updated < now:
        updated = now  # permits deterministic tests at a specified future instant
    warnings = []
    if errors:
        warnings.append(f"일부 수집원({len(errors)}개)의 연결에 실패해 확보한 자료로 구성했습니다.")
    if rejected:
        warnings.append(f"검증을 통과하지 못한 후보 {rejected}개를 제외했습니다.")
    edition = Edition(mode="live", date=now.date().isoformat(), updatedAt=updated,
                      collectionStartedAt=now, windowStart=now - timedelta(hours=config["hours"]), windowEnd=now,
                      rankingMethod=next(iter(methods)) if len(methods) == 1 else "mixed",
                      issues=issues, warnings=warnings)
    debug = {"collectedAt": now.isoformat(), "articleCount": len(cleaned), "groupCount": len(groups),
             "rejectedCandidates": rejected, "groups": [{"articleIds": [a.id for a in group],
               "titles": [a.title for a in group], "publishers": sorted({a.publisher for a in group}),
               "independenceKeys": sorted({a.independence_key for a in group})} for group in groups],
             "ranking": [{"articleIds": [a.id for a in group], "ranking": ranking.model_dump(),
                           "observations": [{"articleId": a.id, **a.engagement.model_dump(mode="json")} for a in group]} for group, ranking in candidates]}
    return edition, debug


def run_live(output: Path, source_file: Path, config_file: Path) -> int:
    require_updates_enabled()
    now = datetime.now(KST)
    status_file = output.parent / "status.json"
    try:
        with pipeline_lock(output.parent / ".pipeline.lock"):
            config = json.loads(config_file.read_text(encoding="utf-8"))
            if not 1 <= config["max_issues"] <= 6:
                raise ValueError("max_issues must be between 1 and 6")
            sources = [SourceConfig.model_validate(row) for row in json.loads(source_file.read_text(encoding="utf-8"))]
            if not any(s.enabled for s in sources):
                raise ValueError("No permission-approved sources enabled")
            summarizer = GPTSummarizer()
            with httpx.Client(timeout=config["timeout_seconds"], follow_redirects=True,
                              headers={"User-Agent": "TodaysIssue/1.0 (RSS reader; no full-text crawling)"}) as client:
                adapter = RSSAdapter(client, config)
                articles, errors, successful = collect_sources(sources, {"rss": adapter}, now - timedelta(hours=config["hours"]), now)
            if not successful or not articles:
                raise ValueError("No collected data; previous edition preserved")
            edition, debug = build_edition(articles, now, config, summarizer, errors)
            atomic_json(ROOT / "data/debug/latest.json", debug)
            save_edition(output, edition)
            atomic_json(status_file, {"attemptedAt": edition.updatedAt.isoformat(), "state": "ok", "message": "검증된 에디션을 생성했습니다."})
            LOG.info("Published %s verified issues", len(edition.issues))
            return 0
    except FileExistsError:
        LOG.error("Another pipeline process owns the lock; no files changed")
        return 1
    except (OSError, ValueError, OpenAIError, httpx.HTTPError) as exc:
        LOG.error("Update failed (%s): previous edition preserved", type(exc).__name__)
        atomic_json(status_file, {"attemptedAt": datetime.now(KST).isoformat(), "state": "error",
                                 "message": "업데이트에 실패했습니다. 이전 정상 에디션을 보존했습니다."})
        return 1


def main() -> int:
    load_dotenv(ROOT / ".env", override=False)
    parser = argparse.ArgumentParser(description="Daily RSS → grouping → ranking → GPT → validated JSON")
    parser.add_argument("--mode", choices=["demo", "live"], default="demo")
    parser.add_argument("--sources", type=Path, default=ROOT / "config/sources.json")
    parser.add_argument("--config", type=Path, default=ROOT / "config/pipeline.json")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--collector", choices=["api", "rss"], default="api")
    parser.add_argument("--stage", choices=["probe", "collect", "select", "summarize", "live"], default="live")
    parser.add_argument("--api-config", type=Path, default=ROOT / "config/news_apis.json")
    parser.add_argument("--providers", choices=["both", "gnews", "newsdata"], default="both")
    parser.add_argument("--query", help="Optional NewsData probe keywords")
    parser.add_argument("--max-news-requests", type=int)
    parser.add_argument("--max-newsdata-requests", type=int)
    parser.add_argument("--max-related-queries", type=int)
    parser.add_argument("--max-gpt-requests", type=int)
    parser.add_argument("--max-issues", type=int, choices=range(1, 7))
    parser.add_argument("--from-cache", action="store_true", help="Use the previous real-news collection without a news API call")
    parser.add_argument("--fresh", action="store_true", help="Bypass response caches; request budgets still apply")
    parser.add_argument("--dry-run", action="store_true", help="Print request limits without API calls or generating summaries")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    if args.mode == "demo":
        fixture = Edition.model_validate_json((ROOT / "public/data/demo.json").read_text(encoding="utf-8"))
        output = args.output or ROOT / "data/demo-output.json"
        if output.name == "latest.json":
            parser.error("DEMO output cannot use the Live latest.json filename")
        save_edition(output, fixture)
        LOG.info("DEMO fixture validated and saved; no API called")
        return 0
    try:
        require_updates_enabled()
    except UpdatesDisabled as exc:
        LOG.info("%s", exc)
        return 0
    if args.collector == "rss":
        if args.stage != "live" or args.dry_run:
            parser.error("Staged execution and dry-run are available with --collector api")
        return run_live(args.output or ROOT / "public/data/latest.json", args.sources, args.config)
    from .api_pipeline import run_api_stage
    try:
        return run_api_stage(args)
    except (ValueError, OSError, KeyError) as exc:
        logging.error("API configuration error (%s); no edition generated", type(exc).__name__)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
