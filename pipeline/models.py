from __future__ import annotations

from datetime import datetime
from typing import Literal
from urllib.parse import urlparse

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Engagement(StrictModel):
    views: int | None = Field(default=None, ge=0)
    comments: int | None = Field(default=None, ge=0)
    view_rank: int | None = Field(default=None, ge=1)
    comment_rank: int | None = Field(default=None, ge=1)
    rank_total: int | None = Field(default=None, ge=1)
    observed_at: AwareDatetime | None = None
    provenance: str | None = None

    @model_validator(mode="after")
    def provenance_required(self) -> Engagement:
        observed = any(v is not None for v in [self.views, self.comments, self.view_rank, self.comment_rank])
        if observed and (self.observed_at is None or not self.provenance):
            raise ValueError("Observed engagement requires a timestamp and provenance")
        for rank in [self.view_rank, self.comment_rank]:
            if rank is not None and self.rank_total is not None and rank > self.rank_total:
                raise ValueError("Rank exceeds total")
        return self


def validate_url(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme not in {"https", "http"} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Expected a public HTTP(S) URL without credentials")
    return value


class Article(StrictModel):
    id: str = Field(min_length=1)
    publisher: str = Field(min_length=1)
    title: str = Field(min_length=3)
    url: str
    published_at: AwareDatetime
    collected_at: AwareDatetime
    excerpt: str = ""
    source_url: str
    method: str = "rss"
    independence_key: str = Field(min_length=1)
    engagement: Engagement = Field(default_factory=Engagement)
    providers: list[str] = Field(default_factory=list)
    discovery_signals: list[str] = Field(default_factory=list)
    publisher_key: str | None = None
    description: str = ""
    content: str = ""
    content_truncated: bool | None = None
    image_url: str | None = None

    _urls = field_validator("url", "source_url")(validate_url)

    @field_validator("image_url")
    @classmethod
    def check_image_url(cls, value: str | None) -> str | None:
        return validate_url(value) if value else None


class Source(StrictModel):
    id: str = Field(min_length=1)
    publisher: str = Field(min_length=1)
    title: str = Field(min_length=1)
    url: str
    publishedAt: AwareDatetime
    independenceKey: str = Field(min_length=1)
    method: str
    providers: list[str] = Field(default_factory=list)
    publisherKey: str | None = None
    imageUrl: str | None = None

    _url = field_validator("url")(validate_url)

    @field_validator("imageUrl")
    @classmethod
    def check_image_url(cls, value: str | None) -> str | None:
        return validate_url(value) if value else None


class Statement(StrictModel):
    id: str = Field(min_length=1)
    text: str = Field(min_length=1, max_length=450)
    kind: Literal["fact", "claim"]
    attribution: str | None
    sourceIds: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def attributed(self) -> Statement:
        if self.kind == "claim" and not (self.attribution or "").strip():
            raise ValueError("Claims must identify their speaker")
        return self


class Term(StrictModel):
    term: str = Field(min_length=1)
    explanation: str = Field(min_length=1, max_length=250)


class Summary(StrictModel):
    title: str = Field(min_length=3, max_length=90)
    oneLineSummary: str = Field(min_length=3, max_length=180)
    titleSourceIds: list[str] = Field(min_length=1)
    summarySourceIds: list[str] = Field(min_length=1)
    background: list[Statement]
    currentSituation: list[Statement] = Field(min_length=1)
    response: list[Statement]
    terminology: list[Term]


class Ranking(StrictModel):
    method: Literal["demo", "coverage_recency", "engagement", "headline_coverage"]
    score: float | None
    reason: str
    components: dict[str, float | None]
    missingMetrics: list[str]


class Issue(Summary):
    id: str = Field(min_length=1)
    rank: int = Field(ge=1, le=6)
    sources: list[Source] = Field(min_length=1)
    ranking: Ranking

    @model_validator(mode="after")
    def check_references(self) -> Issue:
        ids = {s.id for s in self.sources}
        if len(ids) != len(self.sources):
            raise ValueError("Duplicate source ID")
        refs = self.titleSourceIds + self.summarySourceIds
        statements = self.background + self.currentSituation + self.response
        if len({s.id for s in statements}) != len(statements):
            raise ValueError("Duplicate statement ID")
        for statement in statements:
            refs += statement.sourceIds
        if not set(refs) <= ids:
            raise ValueError("Unknown source ID in evidence")
        return self


class Edition(StrictModel):
    schemaVersion: Literal[1] = 1
    mode: Literal["demo", "live"]
    date: str
    updatedAt: AwareDatetime
    collectionStartedAt: AwareDatetime
    windowStart: AwareDatetime
    windowEnd: AwareDatetime
    timezone: Literal["Asia/Seoul"] = "Asia/Seoul"
    rankingMethod: Literal["demo", "coverage_recency", "engagement", "mixed", "headline_coverage"]
    publicationScope: Literal["public", "local_private"] = "public"
    warnings: list[str]
    issues: list[Issue] = Field(max_length=6)

    @model_validator(mode="after")
    def consistent(self) -> Edition:
        datetime.strptime(self.date, "%Y-%m-%d")
        if self.windowStart >= self.windowEnd or self.collectionStartedAt < self.windowEnd:
            raise ValueError("Invalid collection window")
        if self.updatedAt < self.collectionStartedAt:
            raise ValueError("Update predates collection")
        if len({i.id for i in self.issues}) != len(self.issues):
            raise ValueError("Duplicate issue ID")
        if [i.rank for i in self.issues] != list(range(1, len(self.issues) + 1)):
            raise ValueError("Ranks must be consecutive")
        if self.mode == "live" and (self.rankingMethod == "demo" or any(i.ranking.method == "demo" or any(s.method == "demo" for s in i.sources) for i in self.issues)):
            raise ValueError("Live edition cannot contain demo content")
        return self
