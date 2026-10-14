from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Protocol

import feedparser
import httpx
from pydantic import Field, ValidationError, model_validator

from .models import Article, StrictModel, validate_url
from .normalize import KST, article_id, canonical_url, clean_text, parse_date

LOG = logging.getLogger(__name__)


class SourceConfig(StrictModel):
    id: str
    publisher: str
    url: str
    policyUrl: str
    enabled: bool
    reuseGranted: bool
    llmProcessingGranted: bool
    permissionReference: str | None
    reviewedAt: str | None
    independenceKey: str
    notes: str
    adapter: str = "rss"
    assumedTimezone: str | None = None
    syndicationMarkers: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def permission_gate(self) -> SourceConfig:
        validate_url(self.url)
        validate_url(self.policyUrl)
        if self.enabled and not (self.reuseGranted and self.llmProcessingGranted and self.permissionReference and self.reviewedAt):
            raise ValueError(f"Source {self.id}: public reuse and LLM processing permission required")
        return self


class NewsSourceAdapter(Protocol):
    def collect(self, source: SourceConfig, start: datetime, end: datetime) -> list[Article]: ...


def fetch_feed(client: httpx.Client, url: str, retries: int = 2, max_bytes: int = 2_097_152) -> bytes:
    """No access bypass: 4xx is terminal, transient failures have bounded retry."""
    for attempt in range(retries + 1):
        try:
            with client.stream("GET", url) as response:
                response.raise_for_status()
                payload = bytearray()
                for chunk in response.iter_bytes():
                    payload.extend(chunk)
                    if len(payload) > max_bytes:
                        raise ValueError("RSS size limit exceeded")
                return bytes(payload)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code < 500 or attempt == retries:
                raise
        except httpx.TransportError:
            if attempt == retries:
                raise
        time.sleep(0.5 * (2 ** attempt))
    raise RuntimeError("Unreachable retry state")


class RSSAdapter:
    def __init__(self, client: httpx.Client, config: dict):
        self.client, self.config = client, config

    def collect(self, source: SourceConfig, start: datetime, end: datetime) -> list[Article]:
        if not source.enabled:
            return []
        payload = fetch_feed(self.client, source.url, self.config["retries"], self.config["max_feed_bytes"])
        feed = feedparser.parse(payload)
        if not feed.entries:
            raise ValueError("Feed contains no readable entries")
        result = []
        for entry in feed.entries[:self.config["max_articles_per_source"]]:
            try:
                # 'updated' is not substituted for publication time.
                published = parse_date(entry.get("published", ""), source.assumedTimezone)
                if not start <= published <= end:
                    continue
                title = clean_text(entry.get("title", ""))
                excerpt = clean_text(entry.get("summary", ""))[:2000]
                url = canonical_url(entry.get("link", ""))
                independence = source.independenceKey
                # Conservative downgrade for explicitly attributed wire copy.
                markers = {"연합뉴스": "wire:yna", "뉴시스": "wire:newsis", "뉴스1": "wire:news1", **source.syndicationMarkers}
                for marker, origin in markers.items():
                    if marker in title + " " + excerpt:
                        independence = origin
                        break
                result.append(Article(id=article_id(url), publisher=source.publisher, title=title, url=url,
                                      published_at=published, collected_at=datetime.now(KST), excerpt=excerpt,
                                      source_url=source.url, independence_key=independence))
            except (ValueError, TypeError, ValidationError):
                LOG.info("Discarded invalid entry from %s", source.id)
        return result


def collect_sources(sources: list[SourceConfig], adapters: dict[str, NewsSourceAdapter], start: datetime, end: datetime) -> tuple[list[Article], list[str], int]:
    articles, errors, successful = [], [], 0
    for source in sources:
        if not source.enabled:
            continue
        try:
            articles.extend(adapters[source.adapter].collect(source, start, end))
            successful += 1
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            # Only class names go into public status; URLs/content stay out of logs.
            LOG.warning("Source %s failed (%s)", source.id, type(exc).__name__)
            errors.append(source.id)
    return articles, errors, successful
