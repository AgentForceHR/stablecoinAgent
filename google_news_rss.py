import urllib.parse
import feedparser

def google_news_rss_url(query: str, hl="en-US", gl="US", ceid="US:en") -> str:
    # Google News RSS search endpoint
    q = urllib.parse.quote(query)
    return f"https://news.google.com/rss/search?q={q}&hl={hl}&gl={gl}&ceid={ceid}"

def fetch_google_news(query: str, max_items: int = 10):
    url = google_news_rss_url(query)
    d = feedparser.parse(url)
    items = []
    for e in (d.entries or [])[:max_items]:
        items.append({
            "title": getattr(e, "title", ""),
            "link": getattr(e, "link", ""),
            "published": getattr(e, "published", "") or getattr(e, "updated", ""),
            "summary": getattr(e, "summary", "") or getattr(e, "description", "")
        })
    return items
