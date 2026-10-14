"""First-source photo metadata; never stores or summarizes article HTML."""
from __future__ import annotations

import ipaddress
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

import httpx

from .models import Edition, validate_url
from .usage import LocalCache


def public_image_url(value: str) -> str:
    validate_url(value)
    host = urlsplit(value).hostname or ""
    if "." not in host or host.endswith((".local", ".localhost")) or host == "localhost":
        raise ValueError("Local image host")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return value
    if not address.is_global:
        raise ValueError("Nonpublic image host")
    return value


class ImageMetadata(HTMLParser):
    def __init__(self, base: str):
        super().__init__(convert_charrefs=True)
        self.base, self.images = base, []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        row = dict(attrs)
        if tag.lower() == "meta" and (row.get("property") or row.get("name") or "").lower() in {"og:image", "og:image:url", "twitter:image"}:
            if not row.get("content"):
                return
            candidate = urljoin(self.base, row.get("content") or "")
            try:
                self.images.append(public_image_url(candidate))
            except ValueError:
                pass


def first_source_images(edition: Edition, cache: LocalCache) -> tuple[Edition, list[dict]]:
    issues, diagnostics = [], []
    with httpx.Client(timeout=10, follow_redirects=False, headers={"User-Agent": "TodaysIssue/1.0 (first-source image metadata)"}) as client:
        for issue in edition.issues:
            source = issue.sources[0]
            if source.imageUrl:
                issues.append(issue)
                diagnostics.append({"issueId": issue.id, "state": "api_image"})
                continue
            image, state = None, "unavailable"
            cached = cache.get("images", {"url": source.url})
            if cached:
                image, state = cached["value"].get("imageUrl"), "cached"
            else:
                try:
                    url = public_image_url(source.url)
                    for _ in range(3):
                        with client.stream("GET", url) as response:
                            if response.status_code in {301, 302, 303, 307, 308} and response.headers.get("location"):
                                url = public_image_url(urljoin(url, response.headers["location"]))
                                continue
                            if response.status_code != 200:
                                break
                            body = bytearray()
                            for chunk in response.iter_bytes(chunk_size=8192):
                                body.extend(chunk)
                                if b"</head>" in body.lower() or len(body) >= 524288:
                                    break
                            parser = ImageMetadata(url)
                            parser.feed(bytes(body).decode(response.charset_encoding or "utf-8", errors="replace"))
                            image = parser.images[0] if parser.images else None
                            state = "metadata_image" if image else "unavailable"
                            break
                except (ValueError, httpx.HTTPError, LookupError):
                    pass
                cache.put("images", {"url": source.url}, {"imageUrl": image})
            updated = source.model_copy(update={"imageUrl": image})
            issues.append(issue.model_copy(update={"sources": [updated, *issue.sources[1:]]}))
            diagnostics.append({"issueId": issue.id, "state": state})
    return Edition.model_validate({**edition.model_dump(mode="json"), "issues": [i.model_dump(mode="json") for i in issues]}), diagnostics
