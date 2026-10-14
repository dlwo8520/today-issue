from __future__ import annotations

import json
import os
import re
from typing import TypeVar

from openai import OpenAI
from pydantic import Field

from .models import Article, Statement, StrictModel, Summary
from .prompts import EDITOR_SYSTEM, EXTRACT_TASK, SUMMARY_TASK, VERIFY_SYSTEM
from .usage import LocalCache, UsageLedger

T = TypeVar("T", bound=StrictModel)


class Quote(StrictModel):
    sourceId: str
    quote: str = Field(min_length=5)


class Finding(Statement):
    evidence: list[Quote] = Field(min_length=1)
    conflictingWith: list[str]


class Extraction(StrictModel):
    findings: list[Finding]


class SpanReference(StrictModel):
    sourceId: str
    spanId: str


class ReferencedFinding(Statement):
    evidence: list[SpanReference] = Field(min_length=1)
    conflictingWith: list[str]


class ReferencedExtraction(StrictModel):
    findings: list[ReferencedFinding]


def evidence_spans(article: Article) -> list[dict[str, str]]:
    # Preserve the exact text. IDs let a model choose evidence without rewriting quotations.
    pieces = [article.title]
    for sentence in re.split(r"(?<=[.!?。])\s+", article.excerpt):
        for offset in range(0, len(sentence), 180):
            piece = sentence[offset:offset + 180]
            if len(piece) >= 5:
                pieces.append(piece)
    return [{"id": f"span-{index:03}", "text": piece} for index, piece in enumerate(pieces)]


def resolve_evidence(referenced: ReferencedExtraction, articles: list[Article]) -> Extraction:
    span_map = {(a.id, span["id"]): span["text"] for a in articles for span in evidence_spans(a)}
    findings = []
    for finding in referenced.findings:
        quotes = []
        for reference in finding.evidence:
            key = (reference.sourceId, reference.spanId)
            if key not in span_map:
                raise SummaryRejected("Unknown evidence span ID")
            quotes.append({"sourceId": reference.sourceId, "quote": span_map[key]})
        findings.append({**finding.model_dump(), "evidence": quotes})
    return Extraction.model_validate({"findings": findings})


class SegmentVerdict(StrictModel):
    id: str
    supported: bool
    sourceIds: list[str]
    reason: str


class Verification(StrictModel):
    segments: list[SegmentVerdict]
    conflictsHandled: bool


class SummaryRejected(ValueError):
    pass


def source_payload(articles: list[Article]) -> list[dict]:
    return [{"id": a.id, "publisher": a.publisher, "title": a.title, "excerpt": a.excerpt,
             "publishedAt": a.published_at.isoformat(), "independenceKey": a.independence_key} for a in articles]


def validate_extraction(extraction: Extraction, articles: list[Article]) -> None:
    texts = {a.id: a.title + " " + a.excerpt for a in articles}
    findings = {f.id for f in extraction.findings}
    if len(findings) != len(extraction.findings) or not findings:
        raise SummaryRejected("Missing or duplicate findings")
    for finding in extraction.findings:
        if not set(finding.sourceIds) <= texts.keys():
            raise SummaryRejected("Unknown extraction source")
        if set(finding.sourceIds) != {e.sourceId for e in finding.evidence}:
            raise SummaryRejected("Missing quotation for source")
        if not set(finding.conflictingWith) <= findings or finding.id in finding.conflictingWith:
            raise SummaryRejected("Unknown/self conflict reference")
        for evidence in finding.evidence:
            if evidence.sourceId not in texts or evidence.quote not in texts[evidence.sourceId]:
                raise SummaryRejected("Evidence quote absent from source")


def summary_segments(summary: Summary) -> dict[str, tuple[str, list[str]]]:
    segments = {"title": (summary.title, summary.titleSourceIds), "summary": (summary.oneLineSummary, summary.summarySourceIds)}
    statements = summary.background + summary.currentSituation + summary.response
    if len({s.id for s in statements}) != len(statements):
        raise SummaryRejected("Duplicate statement IDs")
    for statement in statements:
        if statement.id in segments or statement.id.startswith("term:"):
            raise SummaryRejected("Reserved segment ID")
        segments[statement.id] = (statement.text, statement.sourceIds)
    for term in summary.terminology:
        key = "term:" + term.term
        if key in segments:
            raise SummaryRejected("Duplicate terminology")
        if term.term not in " ".join(s.text for s in statements):
            raise SummaryRejected("Unused terminology")
        segments[key] = (term.explanation, [])
    return segments


def validate_summary(summary: Summary, articles: list[Article], extraction: Extraction, verification: Verification) -> None:
    texts = {a.id: a.title + " " + a.excerpt for a in articles}
    segments = summary_segments(summary)
    verdicts = {v.id: v for v in verification.segments}
    if len(verdicts) != len(verification.segments) or set(verdicts) != set(segments):
        raise SummaryRejected("Incomplete verification coverage")
    if not verification.conflictsHandled:
        raise SummaryRejected("Unresolved conflicting reports")
    cited_in_extraction = {source for f in extraction.findings for source in f.sourceIds}
    for segment_id, (text, source_ids) in segments.items():
        verdict = verdicts[segment_id]
        refs = set(source_ids or verdict.sourceIds)
        if not verdict.supported or not verdict.reason.strip() or not refs:
            raise SummaryRejected("Unsupported summary segment")
        if not refs <= texts.keys() or not refs <= cited_in_extraction:
            raise SummaryRejected("Unknown or unextracted source reference")
        verified_refs = set(verdict.sourceIds)
        if not verified_refs or not verified_refs <= texts.keys() or not verified_refs <= cited_in_extraction:
            raise SummaryRejected("Verifier referenced unknown or unextracted sources")
        if not set(source_ids) <= verified_refs:
            raise SummaryRejected("Verifier did not support the cited sources")
        evidence_text = " ".join(texts[ref] for ref in refs)
        # Deterministic guard catches novel numbers even when the model approves them.
        numbers = set(re.findall(r"\d+(?:[.,]\d+)*", text))
        if not numbers <= set(re.findall(r"\d+(?:[.,]\d+)*", evidence_text)):
            raise SummaryRejected("Summary introduced a number absent from evidence")


class GPTSummarizer:
    def __init__(self, client: OpenAI | None = None, model: str | None = None, *, ledger: UsageLedger | None = None,
                 cache: LocalCache | None = None, fresh: bool = False):
        self.model = model or os.environ.get("OPENAI_MODEL", "").strip()
        if not self.model or (client is None and not os.environ.get("OPENAI_API_KEY")):
            raise ValueError("Set OPENAI_API_KEY and OPENAI_MODEL; no default model or fake fallback")
        self.client = client or OpenAI(timeout=45.0, max_retries=2)
        self.ledger, self.cache, self.fresh = ledger, cache, fresh

    def structured(self, system: str, payload: dict, schema: type[T]) -> T:
        stage = schema.__name__
        key = {"model": self.model, "system": system, "payload": payload, "schema": schema.model_json_schema()}
        cached = self.cache.get("gpt", key, permanent=True) if self.cache and not self.fresh else None
        if cached:
            try:
                parsed = schema.model_validate(cached["value"])
                if self.ledger:
                    self.ledger.record("openai", stage, "cached", model=self.model, cachedAt=cached["savedAt"])
                return parsed
            except ValueError:
                pass
        if self.ledger:
            self.ledger.reserve_gpt()
        try:
            response = self.client.responses.parse(model=self.model, store=False,
                input=[{"role": "system", "content": system},
                       {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
                text_format=schema, max_output_tokens=6000)
        except Exception as exc:
            if self.ledger:
                self.ledger.record("openai", stage, "error", model=self.model, errorClass=type(exc).__name__,
                                   inputTokens=None, outputTokens=None, estimatedUsd=None)
            raise
        if self.ledger:
            self.ledger.record_gpt(stage, self.model, getattr(response, "usage", None),
                                   response_model=getattr(response, "model", None), response_id=getattr(response, "id", None))
        parsed = response.output_parsed
        if parsed is None:
            raise SummaryRejected("Refused, truncated or unparseable model output")
        if self.cache:
            self.cache.put("gpt", key, parsed.model_dump(mode="json"))
        return parsed

    def summarize(self, articles: list[Article]) -> Summary:
        payload = source_payload(articles)
        extraction_input = [{**row, "evidenceSpans": evidence_spans(article)} for row, article in zip(payload, articles, strict=True)]
        referenced = self.structured(EDITOR_SYSTEM + EXTRACT_TASK, {"articles": extraction_input}, ReferencedExtraction)
        extraction = resolve_evidence(referenced, articles)
        try:
            validate_extraction(extraction, articles)
        except SummaryRejected as exc:
            if self.ledger:
                self.ledger.record("validation", "Extraction", "rejected", reason=str(exc))
            raise
        summary = self.structured(EDITOR_SYSTEM + SUMMARY_TASK,
                                  {"articles": payload, "extraction": extraction.model_dump()}, Summary)
        body_text = " ".join(s.text for s in summary.background + summary.currentSituation + summary.response)
        unused_terms = [t for t in summary.terminology if t.term not in body_text]
        if unused_terms:
            summary = Summary.model_validate({**summary.model_dump(),
                "terminology": [t.model_dump() for t in summary.terminology if t.term in body_text]})
            if self.ledger:
                self.ledger.record("validation", "Terminology", "omitted", count=len(unused_terms),
                                   reason="Definitions not used in the displayed body are omitted")
        segments = summary_segments(summary)
        verification = self.structured(VERIFY_SYSTEM,
                                      {"articles": payload, "extraction": extraction.model_dump(),
                                       "summary": summary.model_dump(), "requiredSegmentIds": list(segments)}, Verification)
        # Definitions are optional. If the source does not define a term, omit it;
        # core title/summary/statements still require complete successful verification.
        unsupported_terms = {v.id for v in verification.segments if v.id.startswith("term:") and not v.supported}
        if unsupported_terms:
            summary = Summary.model_validate({**summary.model_dump(),
                "terminology": [t.model_dump() for t in summary.terminology if "term:" + t.term not in unsupported_terms]})
            verification = Verification.model_validate({**verification.model_dump(),
                "segments": [v.model_dump() for v in verification.segments if v.id not in unsupported_terms]})
            if self.ledger:
                self.ledger.record("validation", "Terminology", "omitted", count=len(unsupported_terms),
                                   reason="Optional definitions unsupported by the provided articles")
        try:
            validate_summary(summary, articles, extraction, verification)
        except SummaryRejected as exc:
            if self.ledger:
                self.ledger.record("validation", "Summary", "rejected", reason=str(exc))
            raise
        return summary
