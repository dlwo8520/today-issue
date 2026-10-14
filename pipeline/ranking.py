from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime

from .models import Article, Ranking


def normalized_engagement(articles: list[Article]) -> dict[str, float | None]:
    """Normalize only observed metrics, within publisher. A missing value stays None."""
    by_publisher: dict[str, list[Article]] = defaultdict(list)
    for article in articles:
        by_publisher[article.publisher_key or article.publisher].append(article)
    result: dict[str, float | None] = {}
    for rows in by_publisher.values():
        for article in rows:
            values = []
            metrics = article.engagement
            for rank in [metrics.view_rank, metrics.comment_rank]:
                if rank is not None and metrics.rank_total is not None and metrics.rank_total > 1:
                    values.append(1 - (rank - 1) / (metrics.rank_total - 1))
            for field in ["views", "comments"]:
                observed = getattr(metrics, field)
                population = [math.log1p(getattr(row.engagement, field)) for row in rows if getattr(row.engagement, field) is not None]
                if observed is not None and len(population) >= 2 and len(set(population)) > 1:
                    x = math.log1p(observed)
                    # Midrank percentile handles ties without comparing raw audiences.
                    lower = sum(y < x for y in population)
                    equal = sum(y == x for y in population)
                    values.append((lower + (equal - 1) / 2) / (len(population) - 1))
            result[article.id] = sum(values) / len(values) if values else None
    return result


def rank_groups(groups: list[list[Article]], now: datetime, config: dict) -> list[tuple[list[Article], Ranking]]:
    engagement = normalized_engagement([a for group in groups for a in group])
    ranked = []
    weights = config["weights"]
    if any(v < 0 for v in weights.values()) or sum(weights.values()) <= 0:
        raise ValueError("Ranking weights must be nonnegative and nonzero")
    for group in groups:
        publishers = {a.publisher_key or a.publisher for a in group}
        independent = {a.independence_key for a in group}
        overlap_selection = config.get("selection_strategy") in {"overlap_then_engagement", "latest"}
        if overlap_selection and len(publishers) < 2:
            continue
        if len(independent) < config["min_independent_sources"]:
            continue
        api_group = any(a.providers for a in group)
        headline = any("gnews_top_headlines" in a.discovery_signals for a in group)
        if config.get("require_gnews_candidate") and not headline:
            continue
        if config.get("min_excerpt_chars") is not None:
            sufficiently_supported = {a.independence_key for a in group if len(a.excerpt) >= config["min_excerpt_chars"]}
            if len(sufficiently_supported) < config["min_independent_sources"]:
                continue
        # Repeated articles from one publisher cannot multiply interest.
        by_publisher: dict[str, list[float]] = defaultdict(list)
        for article in group:
            if engagement[article.id] is not None:
                by_publisher[article.publisher_key or article.publisher].append(engagement[article.id])
        observed = [max(values) for values in by_publisher.values()]
        engagement_value = sum(observed) / len(observed) if observed else None
        age = max(0, (now - max(a.published_at for a in group)).total_seconds() / 3600)
        sufficient = {a.independence_key for a in group if len(a.excerpt) >= 50}
        components = {"engagement": engagement_value, "diversity": min(len(publishers) / 6, 1),
                      "independence": min(len(independent) / 6, 1), "recency": math.exp(-age / 12),
                      "sufficiency": min(len(sufficient) / 3, 1)}
        if api_group:
            components["headline"] = 1.0 if headline else 0.0
        available_weight = sum(weights.get(key, 0) for key, value in components.items() if value is not None)
        if available_weight <= 0:
            raise ValueError("No positive weight for available ranking components")
        score = sum(weights.get(key, 0) * value for key, value in components.items() if value is not None) / available_weight
        missing = [label for fields, label in [(('views',), '조회수'), (('comments',), '댓글수'),
                                              (('view_rank', 'comment_rank'), '인기 순위')]
                   if not any(any(getattr(a.engagement, field) is not None for field in fields) for a in group)]
        method = "headline_coverage" if api_group and not overlap_selection else "engagement" if engagement_value is not None else "coverage_recency"
        reason = (f"{len(publishers)}개 언론사의 보도, 중복 전재를 제외한 {len(independent)}개 출처와 최신성을 반영했습니다. "
                  + ("관측된 관심도 지표를 언론사 내부에서 정규화했습니다." if engagement_value is not None
                     else "사용자 반응을 직접 측정하지 못해 주요 보도 이슈로 선정했습니다."))
        if headline and not overlap_selection:
            reason += " GNews 주요 뉴스 후보 포함 여부를 반영했으며 API 배열 순서는 인기 순위로 사용하지 않았습니다."
        ranked.append((group, Ranking(method=method, score=round(score, 6), reason=reason,
                                      components=components, missingMetrics=missing)))
    if config.get("selection_strategy") == "latest":
        for group, ranking in ranked:
            ranking.method = "coverage_recency"
            ranking.score = ranking.components["recency"]
            ranking.reason = f"{len({a.publisher_key or a.publisher for a in group})}개 언론사의 복수 출처 보도에서 가장 최근 기사 발행 시각을 기준으로 정렬했습니다."
        return sorted(ranked, key=lambda row: (-max(a.published_at.timestamp() for a in row[0]), min(a.id for a in row[0])))
    if config.get("selection_strategy") == "overlap_then_engagement":
        # Missing interest is unknown, not zero: don't penalize unmeasured events.
        use_engagement = len(ranked) > config["max_issues"] and all(row[1].components["engagement"] is not None for row in ranked)
        for _, ranking in ranked:
            ranking.method = "engagement" if use_engagement else "coverage_recency"
            if use_engagement:
                ranking.score = round(ranking.components["engagement"], 6)
            ranking.reason += (" 후보가 6개를 넘고 모든 후보의 비교 가능한 조회수·댓글수 지표가 있어 관심도 순으로 최대 6개를 선택했습니다."
                               if use_engagement else " 같은 사건의 독립 보도가 겹치는 후보에서 원출처 수, 언론사 수, 최신성 순으로 최대 6개를 선택했습니다. 조회수·댓글수가 없거나 일부 후보에서만 관측되면 인기 순위로 비교하지 않습니다.")
        return sorted(ranked, key=lambda row: (
            -(row[1].components["engagement"] or 0) if use_engagement else 0,
            -len({a.independence_key for a in row[0]}),
            -len({a.publisher_key or a.publisher for a in row[0]}),
            -max(a.published_at.timestamp() for a in row[0]),
            -row[1].components["sufficiency"], min(a.id for a in row[0])))
    return sorted(ranked, key=lambda row: (-row[1].score, min(a.id for a in row[0])))


def balanced_sources(group: list[Article], limit: int, *, prefer_latest: bool = False) -> list[Article]:
    ordered = sorted(group, key=lambda a: (a.published_at, len(a.excerpt)) if prefer_latest else (len(a.excerpt), a.published_at), reverse=True)
    preferred, extras, seen = [], [], set()
    for article in ordered:
        if article.independence_key in seen:
            extras.append(article)
        else:
            seen.add(article.independence_key)
            preferred.append(article)
    return (preferred + extras)[:limit]
