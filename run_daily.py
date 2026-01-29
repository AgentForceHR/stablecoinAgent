# run_daily.py
import os
from datetime import datetime, timezone
from dotenv import load_dotenv

from emailer import send_email
from gemini_agent import GeminiStablecoinWriter
from prompts import MASTER_SYSTEM_PROMPT  # (not strictly needed here, but kept for clarity)

# Regular stablecoin news (RSS feeds)
from news_sources import RSS_FEEDS
from news_fetch import NewsFetcher, ArticleExtractor

# “New stablecoin launches” (Google News RSS search)
from google_news_rss import fetch_google_news
from stablecoin_queries import QUERIES


SLOT_STYLES = {
    "morning": "like a morning briefing: crisp, headline-driven, ‘what happened + why it matters’",
    "evening": "like an evening wrap-up: reflective, risk-aware, ‘what to watch next’",
}

DEFAULT_SLOT_TOPIC_HINT = {
    "morning": "Focus more on regular stablecoin market/news updates.",
    "evening": "Focus more on newly announced/launched stablecoins and what to watch.",
}


def _clean(s: str) -> str:
    return (s or "").strip()


def build_regular_news_brief(articles) -> str:
    """
    Takes a list of Article objects (from news_fetch.py) and builds a compact brief for Gemini.
    """
    lines = []
    for i, a in enumerate(articles, start=1):
        lines.append(f"{i}) {a.title}")
        if a.published:
            lines.append(f"Published: {a.published}")
        lines.append(f"URL: {a.url}")
        if a.summary:
            lines.append(f"Summary: {a.summary}")
        if a.content:
            lines.append(f"Key text: {a.content[:600]}")
        lines.append("")
    return "\n".join(lines).strip()


def build_launch_news_brief(items) -> str:
    """
    Takes a list of dict items from Google News RSS and builds a brief for Gemini.
    Each item is expected to have: title, link, published, summary.
    """
    lines = []
    for i, n in enumerate(items, start=1):
        title = _clean(n.get("title", ""))
        link = _clean(n.get("link", ""))
        published = _clean(n.get("published", ""))
        summary = _clean(n.get("summary", ""))

        if not title or not link:
            continue

        lines.append(f"{i}) {title}")
        if published:
            lines.append(f"Published: {published}")
        lines.append(f"URL: {link}")
        if summary:
            lines.append(f"Snippet: {summary[:280]}")
        lines.append("")
    return "\n".join(lines).strip()


def dedupe_by_key(items, key: str):
    seen = set()
    out = []
    for it in items:
        v = it.get(key)
        if not v or v in seen:
            continue
        seen.add(v)
        out.append(it)
    return out


def main():
    load_dotenv()

    # --- Required env vars ---
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    if not gemini_api_key:
        raise RuntimeError("Missing GEMINI_API_KEY")

    gemini_model = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
    language_mode = os.getenv("LANGUAGE_MODE", "auto").strip().lower()  # auto | en | es

    # RUN_SLOT: morning/evening (set per Render cron job)
    run_slot = os.getenv("RUN_SLOT", "morning").strip().lower()
    slot_style = SLOT_STYLES.get(run_slot, SLOT_STYLES["morning"])
    slot_topic_hint = DEFAULT_SLOT_TOPIC_HINT.get(run_slot, "")

    # NEWS_MODE controls what the run generates
    # regular  = only RSS stablecoin news
    # launches = only “new stablecoin” announcements (Google News RSS queries)
    # both     = combine both into one draft
    news_mode = os.getenv("NEWS_MODE", "both").strip().lower()
    if news_mode not in ("regular", "launches", "both"):
        news_mode = "both"

    # Tuning knobs
    max_articles = int(os.getenv("MAX_ARTICLES", "5"))               # regular RSS items
    max_launch_items = int(os.getenv("MAX_LAUNCH_ITEMS", "6"))       # launch/news items
    limit_per_feed = int(os.getenv("LIMIT_PER_FEED", "15"))          # RSS pull depth
    per_query_items = int(os.getenv("PER_QUERY_ITEMS", "6"))         # google news items per query

    writer = GeminiStablecoinWriter(api_key=gemini_api_key, model_name=gemini_model)

    # --- Log header ---
    now_utc = datetime.now(timezone.utc).isoformat()
    print("=== Stablecoin Daily Draft Runner ===")
    print("Time (UTC):", now_utc)
    print("RUN_SLOT:", run_slot)
    print("NEWS_MODE:", news_mode)
    print("LANGUAGE_MODE:", language_mode)
    print("MAX_ARTICLES:", max_articles, "MAX_LAUNCH_ITEMS:", max_launch_items)

    # --- Build briefs ---
    regular_brief = ""
    regular_sources = []
    launch_brief = ""
    launch_sources = []

    # 1) Regular RSS news
    if news_mode in ("regular", "both"):
        fetcher = NewsFetcher(RSS_FEEDS)
        extractor = ArticleExtractor()

        items = fetcher.fetch(limit_per_feed=limit_per_feed)
        if items:
            top = items[:max_articles]
            for a in top:
                a.content = extractor.extract(a.url)
            regular_brief = build_regular_news_brief(top)
            regular_sources = [{"title": a.title, "url": a.url} for a in top]

    # 2) Launch/announcement news via Google News RSS search
    if news_mode in ("launches", "both"):
        hits = []
        for q in QUERIES:
            hits.extend(fetch_google_news(q, max_items=per_query_items))

        hits = dedupe_by_key(hits, "link")
        hits = hits[:max_launch_items]

        if hits:
            launch_brief = build_launch_news_brief(hits)
            launch_sources = [{"title": h.get("title", ""), "url": h.get("link", "")} for h in hits]

    # If nothing found, email a “no items” notice
    if (news_mode in ("regular", "both") and not regular_brief) and (news_mode in ("launches", "both") and not launch_brief):
        body = f"[{run_slot}] No stablecoin-related items found for mode={news_mode}."
        print(body)
        send_email(f"Stablecoin Agent — {run_slot}: no items", body)
        return

    # --- Combine into one brief (for ONE post draft) ---
    combined_sections = []
    if regular_brief:
        combined_sections.append("REGULAR STABLECOIN NEWS (RSS):\n" + regular_brief)
    if launch_brief:
        combined_sections.append("NEW STABLECOIN LAUNCHES / ANNOUNCEMENTS (Google News RSS):\n" + launch_brief)

    combined_brief = "\n\n".join(combined_sections).strip()

    # Add a small hint so morning/evening feels different even when NEWS_MODE=both
    combined_brief = (slot_topic_hint + "\n\n" + combined_brief).strip()

    # --- Generate post ---
    post = writer.generate_x_post_from_news(
        brief=combined_brief,
        language_mode=language_mode,
        run_slot=run_slot,
        slot_style=slot_style,
    )

    # --- Build email body (copy/paste friendly) ---
    subject = f"Stablecoin Agent — {run_slot} X draft ({news_mode})"

    sources_lines = []
    if regular_sources:
        sources_lines.append("Regular sources:")
        sources_lines.extend([f"- {s['title']} — {s['url']}" for s in regular_sources if s.get("url")])
    if launch_sources:
        sources_lines.append("Launch/announcement sources:")
        sources_lines.extend([f"- {s['title']} — {s['url']}" for s in launch_sources if s.get("url")])

    email_body = (
        f"RUN_SLOT: {run_slot}\n"
        f"NEWS_MODE: {news_mode}\n"
        f"TIME (UTC): {now_utc}\n\n"
        "X DRAFT (copy/paste):\n\n"
        f"{post}\n\n"
        "----\n"
        + ("\n".join(sources_lines) if sources_lines else "No sources listed.")
        + "\n"
    )

    print("\n--- X DRAFT ---\n")
    print(post)
    print("\n--- END ---\n")

    send_email(subject, email_body)


if __name__ == "__main__":
    main()
