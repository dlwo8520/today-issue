from __future__ import annotations

import hashlib
import html
import re
from datetime import datetime
from email.utils import parsedate_to_datetime
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from zoneinfo import ZoneInfo

from .models import Article, validate_url

KST = ZoneInfo("Asia/Seoul")


def clean_text(value: str) -> str:
    value = re.sub(r"<(script|style)\b[^>]*>.*?</\1>", "", value, flags=re.I | re.S)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]*>", " ", value))).strip()


def canonical_url(value: str) -> str:
    validate_url(value)
    url = urlsplit(value.strip())
    query = [(k, v) for k, v in parse_qsl(url.query, keep_blank_values=True)
             if not k.lower().startswith("utm_") and k.lower() not in {"fbclid", "gclid"}]
    host = url.netloc.lower()
    return urlunsplit((url.scheme.lower(), host, url.path or "/", urlencode(sorted(query)), ""))


def parse_date(value: str, assumed_timezone: str | None = None) -> datetime:
    try:
        result = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        result = parsedate_to_datetime(value)
    if result.tzinfo is None:
        if assumed_timezone is None:
            raise ValueError("Unspecified publication timezone")
        result = result.replace(tzinfo=ZoneInfo(assumed_timezone))
    return result.astimezone(KST)


def article_id(url: str) -> str:
    return "src-" + hashlib.sha256(canonical_url(url).encode()).hexdigest()[:16]


def deduplicate(articles: list[Article]) -> list[Article]:
    unique: dict[str, Article] = {}
    for article in articles:
        key = canonical_url(article.url)
        article = article.model_copy(update={"url": key, "id": article_id(key)})
        previous = unique.get(key)
        if previous is None:
            unique[key] = article
        else:
            preferred = article if len(article.excerpt) > len(previous.excerpt) else previous
            unique[key] = preferred.model_copy(update={
                "providers": sorted(set(previous.providers + article.providers)),
                "discovery_signals": sorted(set(previous.discovery_signals + article.discovery_signals)),
                "collected_at": min(previous.collected_at, article.collected_at),
                "image_url": preferred.image_url or previous.image_url or article.image_url,
            })
    # Some suppliers use different URLs for an identical publisher headline.
    # Exact titles + near-identical publication times only; follow-up reports remain separate.
    result: list[Article] = []
    for article in sorted(unique.values(), key=lambda a: (a.published_at, a.url), reverse=True):
        title = re.sub(r"[^가-힣a-z0-9]", "", article.title.casefold())
        key = article.publisher_key or article.publisher
        match = next((n for n, prior in enumerate(result)
                      if (prior.publisher_key or prior.publisher) == key
                      and re.sub(r"[^가-힣a-z0-9]", "", prior.title.casefold()) == title
                      and abs((prior.published_at - article.published_at).total_seconds()) <= 3600), None)
        if match is None:
            result.append(article)
        else:
            previous = result[match]
            preferred = article if len(article.excerpt) > len(previous.excerpt) else previous
            result[match] = preferred.model_copy(update={
                "providers": sorted(set(previous.providers + article.providers)),
                "discovery_signals": sorted(set(previous.discovery_signals + article.discovery_signals)),
                "collected_at": min(previous.collected_at, article.collected_at),
                "image_url": preferred.image_url or previous.image_url or article.image_url,
            })
    return result
