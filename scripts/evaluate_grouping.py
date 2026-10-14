"""Synthetic grouping smoke evaluation, not a real-news accuracy benchmark."""
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pipeline.grouping import group_articles  # noqa: E402
from pipeline.models import Article  # noqa: E402

config = json.loads((ROOT / "config/pipeline.json").read_text(encoding="utf-8"))
now = datetime.fromisoformat("2026-10-13T07:00:00+09:00")
titles = ["한국은행 기준금리 동결 결정", "한은 기준금리 동결 결정 배경은", "한국은행 기준금리 유지 결정",
          "한국은행 기준금리 인하 결정", "새봄은행 기준금리 동결 결정"]
rows = [Article(id=f"synthetic-{i}", publisher=f"가상 매체 {i}", title=title, url=f"https://example.com/{i}",
                published_at=now, collected_at=now, source_url="https://example.com/rss",
                independence_key=f"synthetic-{i}") for i, title in enumerate(titles)]
groups = group_articles(rows, config)
print("SYNTHETIC evaluation only; not production accuracy.")
for index, group in enumerate(groups, 1):
    print(f"Group {index}: " + " | ".join(a.title for a in group))
if sorted(len(g) for g in groups) != [1, 1, 3]:
    raise SystemExit("Synthetic grouping expectation failed")
