"""Read candidate feeds once for diagnostics, saving no article text and enabling no sources."""
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import feedparser
import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pipeline.normalize import KST  # noqa: E402
from pipeline.sources import fetch_feed  # noqa: E402


def probe(source):
    result = {"id": source["id"], "publisher": source["publisher"], "url": source["url"],
              "observedAt": datetime.now(KST).isoformat(), "permission": "not_granted", "enabled": False,
              "entryCount": None, "hasViewCounts": None, "hasCommentCounts": None}
    try:
        with httpx.Client(timeout=12, follow_redirects=True, headers={"User-Agent": "TodaysIssue/1.0 RSS diagnostics"}) as client:
            feed = feedparser.parse(fetch_feed(client, source["url"], retries=0))
            result["entryCount"] = len(feed.entries)
            result["status"] = "accessible" if feed.entries else "no_readable_entries"
            if feed.entries:
                result["hasViewCounts"] = any("views" in e or "viewcount" in e for e in feed.entries)
                result["hasCommentCounts"] = any("commentcount" in e or "comments_count" in e for e in feed.entries)
    except httpx.HTTPStatusError as exc:
        result["status"] = f"http_{exc.response.status_code}"
    except (httpx.HTTPError, ValueError) as exc:
        result["status"] = type(exc).__name__
    return result


sources = json.loads((ROOT / "config/sources.json").read_text(encoding="utf-8"))
with ThreadPoolExecutor(max_workers=4) as executor:
    results = list(executor.map(probe, sources))
target = ROOT / "data/source-probe.json"
target.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
for result in results:
    print(f"{result['id']}: {result['status']}, entries={result['entryCount']}, permission=not_granted")
