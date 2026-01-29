import re
from dataclasses import dataclass
from typing import List, Optional

import feedparser
import requests
import trafilatura

STABLECOIN_KEYWORDS = [
    "stablecoin", "stable coin", "peg", "depeg", "parity", "reserve", "reserves",
    "redemption", "issuer", "collateral", "attestation", "audit",
    "usdc", "usdt", "dai", "frax", "crvusd", "pyusd", "eurc", "usd0", "usde"
]

def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip()

def is_stablecoin_related(title: str, summary: str) -> bool:
    text = f"{title} {summary}".lower()
    return any(k in text for k in STABLECOIN_KEYWORDS)

@dataclass
class Article:
    title: str
    url: str
    published: str
    summary: str
    content: Optional[str] = None

class NewsFetcher:
    def __init__(self, feeds: List[str]):
        self.feeds = feeds

    def fetch(self, limit_per_feed: int = 15) -> List[Article]:
        found: List[Article] = []
        for feed_url in self.feeds:
            try:
                d = feedparser.parse(feed_url)
                for e in (d.entries or [])[:limit_per_feed]:
                    title = _clean(getattr(e, "title", ""))
                    url = _clean(getattr(e, "link", ""))
                    summary = _clean(getattr(e, "summary", "") or getattr(e, "description", ""))
                    published = _clean(getattr(e, "published", "") or getattr(e, "updated", ""))

                    if not title or not url:
                        continue
                    if not is_stablecoin_related(title, summary):
                        continue

                    found.append(Article(
                        title=title,
                        url=url,
                        published=published,
                        summary=summary[:400]
                    ))
            except Exception:
                continue

        # Deduplicate by URL
        seen = set()
        deduped = []
        for a in found:
            if a.url in seen:
                continue
            seen.add(a.url)
            deduped.append(a)

        return deduped

class ArticleExtractor:
    def extract(self, url: str, timeout: int = 12, max_chars: int = 3000) -> Optional[str]:
        try:
            r = requests.get(url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code >= 400:
                return None
            text = trafilatura.extract(r.text, include_comments=False, include_tables=False)
            if not text:
                return None
            return _clean(text)[:max_chars]
        except Exception:
            return None