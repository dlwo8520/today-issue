from __future__ import annotations

import json
import logging
import os
import re
import time
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit
from zoneinfo import ZoneInfoNotFoundError

import httpx
from pydantic import ValidationError

from .models import Article
from .normalize import KST, article_id, canonical_url, clean_text, deduplicate, parse_date
from .service import require_updates_enabled
from .usage import BudgetExceeded, LocalCache, UsageLedger, redact

ENDPOINTS = {"gnews": "https://gnews.io/api/v4/top-headlines", "newsdata": "https://newsdata.io/api/1/latest"}
KEY_NAMES = {"gnews": "GNEWS_API_KEY", "newsdata": "NEWSDATA_API_KEY"}
SIGNAL = "gnews_top_headlines"
WIRE_DOMAINS = {"yna.co.kr": "wire:yna", "newsis.com": "wire:newsis", "news1.kr": "wire:news1"}
WIRE_NAMES = {"연합뉴스": "wire:yna", "뉴시스": "wire:newsis", "뉴스1": "wire:news1"}
UNKNOWN_PORTAL_NAMES = {"daum", "naver", "google news", "다음", "네이버", "구글 뉴스",
                        "v.daum.net", "daum.net", "naver.com", "news.naver.com", "google.com"}


def known_publisher(article: Article) -> bool:
    return article.publisher.casefold() not in UNKNOWN_PORTAL_NAMES


class NewsAPIError(ValueError):
    def __init__(self, provider: str, category: str, status: int | None = None):
        self.provider, self.category, self.status = provider, category, status
        super().__init__(f"{provider}: {category}" + (f" (HTTP {status})" if status else ""))


def media_domain(url: str) -> str:
    host = (urlsplit(url).hostname or "").lower().removeprefix("www.")
    pieces = host.split(".")
    suffix = ".".join(pieces[-2:])
    size = 3 if suffix in {"co.kr", "or.kr", "go.kr", "ac.kr", "co.uk", "com.au"} else 2
    return ".".join(pieces[-size:])


def publisher_identity(name: str, source_url: str, article_url: str, aliases: dict[str, str]) -> tuple[str, str]:
    name = unicodedata.normalize("NFKC", clean_text(name))
    match = {k.casefold(): v for k, v in aliases.items()}
    name = match.get(name.casefold(), name)
    domain = media_domain(source_url or article_url)
    # A portal host does not identify the original reporting organization.
    key = ("name:" + re.sub(r"\s+", "", name.casefold())) if domain in {"naver.com", "daum.net", "google.com"} else "media:" + domain
    if not name or not domain:
        raise ValueError("Missing publisher identity")
    return name, key


def permitted_text(value: object) -> str:
    if not isinstance(value, str):
        return ""
    if re.search(r"only available in paid|upgrade (?:your |the )?plan|premium feature", value, re.I):
        return ""
    value = re.sub(r"\s*\[\+?\d+\s*(?:chars|characters)\]\s*$", "", value)
    return clean_text(value)


def independence_key(publisher: str, source_url: str, article_url: str, text: str, publisher_key: str) -> str:
    domain = media_domain(source_url or article_url)
    if domain in WIRE_DOMAINS:
        return WIRE_DOMAINS[domain]
    if publisher in WIRE_NAMES:
        return WIRE_NAMES[publisher]
    for name, origin in WIRE_NAMES.items():
        if re.search(re.escape(name) + r"\s*(?:제공|전재|보도|=|에 따르면|는)", text):
            return origin
    return publisher_key


def newsdata_date(value: str, zone: str | None) -> datetime:
    # The official response documents pubDateTZ; do not silently assume KST.
    try:
        return parse_date(value)
    except ValueError:
        pass
    if zone and re.fullmatch(r"[+-]\d{2}:?\d{2}", zone):
        normalized_zone = zone if ":" in zone else zone[:3] + ":" + zone[3:]
        return parse_date(value + normalized_zone)
    return parse_date(value, zone)


def normalize_api_articles(provider: str, payload: dict, collected: datetime, config: dict) -> tuple[list[Article], dict]:
    field_name = "articles" if provider == "gnews" else "results"
    rows = payload.get(field_name)
    if not isinstance(rows, list):
        raise NewsAPIError(provider, "invalid_payload")
    articles, invalid = [], 0
    fields = set()
    for row in rows[:config["articles_per_request"]]:
        if not isinstance(row, dict):
            invalid += 1
            continue
        fields.update(row.keys())
        try:
            url = canonical_url(row.get("url" if provider == "gnews" else "link", ""))
            title = permitted_text(row.get("title"))
            if not re.search(r"[가-힣]", title):
                raise ValueError("Not a Korean headline")
            if any(re.search(pattern, title) for pattern in config.get("excluded_title_patterns", [])):
                raise ValueError("Generic or non-event headline")
            source = row.get("source") or {} if provider == "gnews" else {}
            publisher = source.get("name", "") if provider == "gnews" else row.get("source_name") or row.get("source_id", "")
            source_url = source.get("url", "") if provider == "gnews" else row.get("source_url", "")
            if source_url:
                source_url = canonical_url(source_url)
            publisher, key = publisher_identity(publisher, source_url, url, config.get("publisher_aliases", {}))
            if publisher.casefold() in UNKNOWN_PORTAL_NAMES:
                raise ValueError("Portal metadata does not identify the original publisher")
            description = permitted_text(row.get("description"))
            content_raw = row.get("content")
            content = permitted_text(content_raw)
            excerpt = " ".join(dict.fromkeys(part for part in [description, content] if part))[:config["max_excerpt_chars"]]
            published = parse_date(row.get("publishedAt", "")) if provider == "gnews" else newsdata_date(row.get("pubDate", ""), row.get("pubDateTZ"))
            truncated = bool(re.search(r"\[\+?\d+\s*(?:chars|characters)\]", content_raw)) if isinstance(content_raw, str) else None
            image = row.get("image" if provider == "gnews" else "image_url")
            try:
                image = canonical_url(image) if isinstance(image, str) and image else None
            except ValueError:
                image = None
            articles.append(Article(id=article_id(url), publisher=publisher, publisher_key=key,
                                    title=title, url=url, published_at=published, collected_at=collected,
                                    source_url=ENDPOINTS[provider], method="official_api",
                                    excerpt=excerpt, description=description[:4000], content=content[:config["max_excerpt_chars"]],
                                    content_truncated=truncated, image_url=image, providers=[provider],
                                    discovery_signals=[SIGNAL] if provider == "gnews" else [],
                                    independence_key=independence_key(publisher, source_url, url, title + " " + excerpt, key)))
        except (ValueError, TypeError, AttributeError, ValidationError, ZoneInfoNotFoundError):
            invalid += 1
    info = {"returnedCount": len(rows), "parsedCount": len(articles), "invalidCount": invalid,
            "actualFields": sorted(fields), "publishers": {p: sum(a.publisher == p for a in articles) for p in sorted({a.publisher for a in articles})},
            "publicationDates": [a.published_at.isoformat() for a in articles],
            "descriptionLengths": [len(a.description) for a in articles], "excerptLengths": [len(a.excerpt) for a in articles]}
    return articles, info


@dataclass
class APICollection:
    articles: list[Article] = field(default_factory=list)
    diagnostics: dict = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


class NewsAPIAdapter:
    provider: str

    def __init__(self, client: httpx.Client, config: dict, ledger: UsageLedger, cache: LocalCache, fresh: bool = False):
        self.client, self.config, self.ledger, self.cache, self.fresh = client, config, ledger, cache, fresh
        self.next_request_at = 0.0

    def fetch(self, params: dict[str, object], endpoint: str | None = None) -> tuple[dict, datetime, str]:
        require_updates_enabled()
        endpoint = endpoint or ENDPOINTS[self.provider]
        key = os.environ.get(KEY_NAMES[self.provider], "").strip()
        if not key:
            self.ledger.record(self.provider, "collect", "missing_configuration", variable=KEY_NAMES[self.provider])
            raise NewsAPIError(self.provider, "missing_configuration")
        cache_key = {"provider": self.provider, "endpoint": endpoint, "params": params, "usageScope": self.config["usage_scope"], "credentialFingerprint": LocalCache.fingerprint(key)}
        cached = None if self.fresh else self.cache.get("news", cache_key)
        if cached:
            self.ledger.record(self.provider, "collect", "cached")
            return cached["value"], datetime.fromisoformat(cached["savedAt"]), "cached"
        # httpx INFO includes the full URL; authenticated queries must never reach logs.
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)
        for attempt in range(self.config["news_retries"] + 1):
            self.ledger.reserve_news(self.provider)
            delay = self.next_request_at - time.monotonic()
            if delay > 0:
                time.sleep(delay)
            status = None
            try:
                with self.client.stream("GET", endpoint, params={**params, "apikey": key}) as response:
                    status = response.status_code
                    if status != 200:
                        category = ("quota" if status == 403 and self.provider == "gnews" else "authentication" if status in (401, 403)
                                    else "rate_limit" if status == 429 and self.provider == "gnews" else "quota" if status == 429
                                    else "transient" if status >= 500 else "bad_request")
                        raise NewsAPIError(self.provider, category, status)
                    raw = bytearray()
                    for chunk in response.iter_bytes():
                        raw.extend(chunk)
                        if len(raw) > self.config["max_response_bytes"]:
                            raise NewsAPIError(self.provider, "response_too_large", status)
                    payload = redact(json.loads(raw))
                    if not isinstance(payload, dict):
                        raise NewsAPIError(self.provider, "invalid_payload", status)
                    if self.provider == "newsdata" and payload.get("status") != "success":
                        raise NewsAPIError(self.provider, "provider_error", status)
                    required = "articles" if self.provider == "gnews" else "results"
                    if not isinstance(payload.get(required), list):
                        raise NewsAPIError(self.provider, "invalid_payload", status)
                    quota = {name: response.headers[name] for name in ("x-ratelimit-limit", "x-ratelimit-remaining", "x-ratelimit-reset") if name in response.headers}
                self.cache.put("news", cache_key, payload)
                self.ledger.record(self.provider, "collect", "success", httpStatus=status, quotaHeaders=quota)
                return payload, datetime.now(KST), "success"
            except httpx.TimeoutException:
                error = NewsAPIError(self.provider, "timeout", status)
            except httpx.TransportError:
                error = NewsAPIError(self.provider, "network", status)
            except (ValueError, NewsAPIError) as exc:
                error = exc if isinstance(exc, NewsAPIError) else NewsAPIError(self.provider, "invalid_json", status)
            finally:
                # Space completed calls as well as starts; server timing can differ.
                self.next_request_at = time.monotonic() + self.config.get("request_interval_seconds", {}).get(self.provider, 0)
            self.ledger.record(self.provider, "collect", "error", httpStatus=error.status, category=error.category)
            if error.category not in {"timeout", "network", "transient"} or attempt == self.config["news_retries"]:
                raise error from None
            time.sleep(0.5 * (2 ** attempt))
        raise NewsAPIError(self.provider, "retry_exhausted")

    def collect(self, start: datetime, end: datetime, query: str | None = None, *, page: int = 1) -> tuple[list[Article], dict]:
        endpoint = "https://gnews.io/api/v4/search" if self.provider == "gnews" and query else ENDPOINTS[self.provider]
        params = self.parameters(query, start, end)
        if page > 1 and self.provider == "gnews":
            params["page"] = page
        payload, collected, state = self.fetch(params, endpoint)
        articles, info = normalize_api_articles(self.provider, payload, collected, self.config)
        if self.provider == "gnews" and query:
            articles = [a.model_copy(update={"discovery_signals": ["gnews_search"], "source_url": endpoint}) for a in articles]
        within_window = [a for a in articles if start <= a.published_at <= end]
        info.update({"state": state, "withinWindowCount": len(within_window), "outsideWindowCount": len(articles) - len(within_window),
                     "query": query, "accountPlan": self.config["account_plan"].get(self.provider, "unknown"),
                     "accountPlanVerified": False, "endpoint": endpoint,
                     "requestedFrom": start.isoformat(), "requestedTo": end.isoformat(), "requestPage": page})
        return within_window, info

    def parameters(self, query: str | None, start: datetime | None = None, end: datetime | None = None) -> dict[str, object]:
        raise NotImplementedError


class GNewsAdapter(NewsAPIAdapter):
    provider = "gnews"

    def parameters(self, query: str | None = None, start: datetime | None = None, end: datetime | None = None) -> dict[str, object]:
        params = {"lang": "ko", "country": "kr", "max": self.config["articles_per_request"]}
        params.update({"q": query[:200], "sortby": "relevance"} if query else {"category": "general"})
        if start is not None and end is not None:
            params.update({"from": start.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
                           "to": end.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")})
        return params


class NewsDataAdapter(NewsAPIAdapter):
    provider = "newsdata"

    def parameters(self, query: str | None = None, start: datetime | None = None, end: datetime | None = None) -> dict[str, object]:
        params: dict[str, object] = {"language": "ko", "country": "kr", "size": self.config["articles_per_request"]}
        if query:
            params["q"] = query[:100]
        # No pagination or paid-only/full-text parameters are requested.
        return params


def related_query(group: list[Article], config: dict, api_config: dict) -> str:
    title = max(group, key=lambda a: len(a.excerpt)).title
    for before, after in config["entity_aliases"].items():
        title = title.replace(before, after)
    cleaned = re.sub(r"\[[^]]*\]|\([^)]*\)", " ", title)
    tokens = re.findall(r"[가-힣A-Za-z0-9]{2,20}", cleaned)
    tokens = [re.sub(r"(?:은|는|의|을|를|에|와|과)$", "", token) if len(token) >= 3 else token for token in tokens]
    stop = {"단독", "속보", "종합", "영상", "사진", "오늘", "어제", "내일", "기자", "뉴스", "관련", "대한", "위한", "이유", "발표", "결정", "배경은"}
    entities = [e for e in dict.fromkeys(config["entity_anchors"] + api_config.get("context_entities", [])) if e in cleaned]
    named_people = re.findall(r"(?:대통령|총리|장관|보컬|가수|배우|의원|회장)\s+([가-힣]{2,4})", cleaned)
    topics = [e for e in api_config["query_terms"] if e in cleaned]
    candidates = named_people + entities + topics + [t for t in tokens if t not in stop and not t.isdecimal()]
    chosen = []
    for token in candidates:
        if not any(token in previous or previous in token for previous in chosen):
            chosen.append(token)
        if len(chosen) == api_config.get("query_keyword_limit", 3):
            break
    return " ".join(chosen)[:80]


def collect_api_news(gnews: GNewsAdapter, newsdata: NewsDataAdapter, start: datetime, end: datetime, config: dict, api_config: dict) -> APICollection:
    from .grouping import group_articles
    result = APICollection()
    seeds, discovery = [], []
    windows = min(api_config.get("gnews_discovery_windows", 1), max(1, int((end - start).total_seconds() / 86400 + 0.9999)))
    for index in range(windows):
        slice_end = end - timedelta(days=index)
        slice_start = max(start, slice_end - timedelta(days=1)) if windows > 1 else start
        try:
            rows, info = gnews.collect(slice_start, slice_end)
            seeds.extend(rows)
            discovery.append(info)
            if index < api_config.get("gnews_extra_page_windows", 0):
                rows, info = gnews.collect(slice_start, slice_end, page=2)
                seeds.extend(rows)
                discovery.append(info)
        except (NewsAPIError, BudgetExceeded) as exc:
            result.errors.append(str(exc))
            if isinstance(exc, BudgetExceeded) or getattr(exc, "category", "") in {"authentication", "quota", "rate_limit", "missing_configuration"}:
                break
    result.diagnostics["gnewsDiscovery"] = discovery
    result.diagnostics["gnews"] = {"returnedCount": sum(d["returnedCount"] for d in discovery),
                                    "parsedCount": sum(d["parsedCount"] for d in discovery),
                                    "withinWindowCount": len(seeds), "requestWindows": len(discovery)}
    seeds = deduplicate(seeds)
    result.articles.extend(seeds)
    seed_groups = group_articles(seeds, config)
    # Original API order is discarded. Source diversity and recency prioritize limited searches.
    seed_groups.sort(key=lambda g: (-max(a.published_at.timestamp() for a in g), -len({a.independence_key for a in g}), min(a.id for a in g))
                     if api_config.get("selection_strategy") == "latest" else
                     (-len({a.independence_key for a in g}), -max(a.published_at.timestamp() for a in g), min(a.id for a in g)))
    queries = []
    for group in seed_groups:
        query = related_query(group, config, api_config)
        if query and query not in queries:
            queries.append(query)
        if len(queries) >= api_config["max_related_queries"]:
            break
    if api_config["max_related_queries"] == 0:
        queries = []
    result.diagnostics["newsdata"], result.diagnostics["gnewsRelated"] = [], []
    gnews_search_enabled = True
    for index, query in enumerate(queries):
        if gnews_search_enabled and index < api_config.get("max_gnews_related_queries", 0):
            try:
                articles, info = gnews.collect(start, end, query)
                result.articles.extend(articles)
                result.diagnostics["gnewsRelated"].append(info)
            except (NewsAPIError, BudgetExceeded) as exc:
                result.errors.append(str(exc))
                if isinstance(exc, BudgetExceeded) or getattr(exc, "category", "") in {"authentication", "quota", "rate_limit", "missing_configuration"}:
                    gnews_search_enabled = False
        try:
            articles, info = newsdata.collect(start, end, query)
            result.articles.extend(articles)
            result.diagnostics["newsdata"].append(info)
        except (NewsAPIError, BudgetExceeded) as exc:
            result.errors.append(str(exc))
            if isinstance(exc, BudgetExceeded) or getattr(exc, "category", "") in {"authentication", "quota", "missing_configuration"}:
                break
    return result
