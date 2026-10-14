from __future__ import annotations

import math
import re
from collections import Counter

from .models import Article


def normalized_title(title: str, aliases: dict[str, str]) -> str:
    title = re.sub(r"우크라(?!이나)", "우크라이나", title).replace("北", "북").replace("북포로", "북한군포로")
    for before, after in aliases.items():
        title = title.replace(before, after)
    title = re.sub(r"\[[^]]*\]|\([^)]*\)", "", title)
    return re.sub(r"[^가-힣a-z0-9]", "", title.lower()).replace("북포로", "북한군포로")


def title_vectors(articles: list[Article], aliases: dict[str, str]) -> list[dict[str, float]]:
    counts = []
    for article in articles:
        title = normalized_title(article.title, aliases)
        counts.append(Counter(title[n:n + size] for size in (2, 3, 4) for n in range(len(title) - size + 1)))
    document_frequency = Counter(key for count in counts for key in count)
    vectors = []
    for count in counts:
        weighted = {key: (1 + math.log(value)) * (1 + math.log((1 + len(counts)) / (1 + document_frequency[key]))) for key, value in count.items()}
        norm = math.sqrt(sum(v * v for v in weighted.values())) or 1
        vectors.append({key: value / norm for key, value in weighted.items()})
    return vectors


def compatible(a: Article, b: Article, config: dict) -> bool:
    if abs((a.published_at - b.published_at).total_seconds()) > config["max_cluster_hours"] * 3600:
        return False
    x = normalized_title(a.title, config["entity_aliases"])
    y = normalized_title(b.title, config["entity_aliases"])
    # Explicit dates in titles provide a second, stricter event-date guard.
    date_pattern = r"\d{1,2}월\d{1,2}일|\d{4}년\d{1,2}월"
    dates_a, dates_b = set(re.findall(date_pattern, x)), set(re.findall(date_pattern, y))
    if dates_a and dates_b and dates_a != dates_b:
        return False
    entities_a = {e for e in config["entity_anchors"] if e in x}
    entities_b = {e for e in config["entity_anchors"] if e in y}
    if entities_a and entities_b and entities_a.isdisjoint(entities_b):
        return False
    for left, right in config["opposite_actions"]:
        if (left in x and right in y and right not in x) or (right in x and left in y and left not in x):
            return False
    return True


def group_articles(articles: list[Article], config: dict) -> list[list[Article]]:
    """Complete-link clustering avoids joining two events through a vague bridge title."""
    vectors = title_vectors(articles, config["entity_aliases"])
    contexts = [a.model_copy(update={"title": a.title + " " + a.excerpt[:1500]}) for a in articles]
    context_vectors = title_vectors(contexts, config["entity_aliases"]) if config.get("quoted_event_terms") else []
    groups: list[list[int]] = []
    def similarity(i: int, j: int) -> float:
        return sum(value * vectors[j].get(key, 0) for key, value in vectors[i].items())
    def event_phrases(article: Article) -> set[str]:
        phrases = set()
        for quote in re.findall(r"[\"'“‘]([^\"'”’]{4,45})[\"'”’]", article.title + " " + article.excerpt[:1500]):
            for event in config.get("quoted_event_terms", []):
                if event in quote:
                    core = normalized_title(quote[:quote.index(event) + len(event)], {})
                    if len(event) + 2 <= len(core) <= 20:
                        phrases.add(core)
        return phrases
    def shared_specific_event(i: int, j: int) -> bool:
        same_quote = bool(event_phrases(articles[i]).intersection(event_phrases(articles[j])))
        left_title = normalized_title(articles[i].title, config["entity_aliases"])
        right_title = normalized_title(articles[j].title, config["entity_aliases"])
        same_anchor = any(anchor in left_title and anchor in right_title for anchor in config.get("specific_event_anchors", []))
        if not context_vectors or not (same_quote or same_anchor):
            return False
        left = contexts[i].title
        right = contexts[j].title
        left_context = normalized_title(left, config["entity_aliases"])
        right_context = normalized_title(right, config["entity_aliases"])
        actors = {e for e in config.get("context_entities", []) if normalized_title(e, {}) in left_context and normalized_title(e, {}) in right_context}
        context_similarity = sum(value * context_vectors[j].get(key, 0) for key, value in context_vectors[i].items())
        # Exact quoted event phrase + two shared actors + lexical evidence, still complete-link.
        return len(actors) >= 2 and similarity(i, j) >= 0.08 and context_similarity >= 0.10
    for index, article in enumerate(articles):
        matches = [(min(similarity(index, other) for other in group), n)
                   for n, group in enumerate(groups)
                   if all(compatible(article, articles[other], config) and
                          (similarity(index, other) >= config["similarity_threshold"] or shared_specific_event(index, other)) for other in group)]
        if matches:
            groups[max(matches)[1]].append(index)
        else:
            groups.append([index])
    return [[articles[index] for index in group] for group in groups]
