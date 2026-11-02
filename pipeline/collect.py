"""Collect ~100 recent fashion articles from RSS feeds and Google News."""
from __future__ import annotations

import html
import re
import sys
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import quote_plus, urlsplit, urlunsplit

import feedparser
import yaml

FEEDS_FILE = Path(__file__).with_name("feeds.yaml")
USER_AGENT = "WeeklyStyleBot/1.0 (+weekly fashion digest)"
MAX_AGE_DAYS = 7


def _clean(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def _norm_url(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc.lower(), parts.path.rstrip("/"), "", ""))


def _published(entry) -> datetime | None:
    stamp = entry.get("published_parsed") or entry.get("updated_parsed")
    return datetime(*stamp[:6], tzinfo=timezone.utc) if stamp else None


def _parse(url: str, outlet: str | None, audience: str, cutoff: datetime) -> list[dict]:
    feed = feedparser.parse(url, agent=USER_AGENT)
    if feed.bozo and not feed.entries:
        print(f"  ! skipped {outlet or url}: {feed.get('bozo_exception')}", file=sys.stderr)
        return []

    articles = []
    for entry in feed.entries:
        published = _published(entry)
        if not published or published < cutoff or not entry.get("link"):
            continue
        title = _clean(entry.get("title", ""))
        source = outlet or (entry.get("source") or {}).get("title") or "Unknown"
        if not outlet:
            # Google News appends " - Outlet" to titles.
            title = re.sub(rf"\s+-\s+{re.escape(source)}$", "", title)
        articles.append({
            "title": title,
            "url": entry.link,
            "outlet": source,
            "audience": audience,
            "published": published.isoformat(),
            "snippet": _clean(entry.get("summary", ""))[:500],
        })
    return articles


def _dedupe(articles: list[dict]) -> list[dict]:
    seen_urls, kept = set(), []
    for art in articles:
        key = _norm_url(art["url"])
        if key in seen_urls:
            continue
        title = art["title"].lower()
        if any(SequenceMatcher(None, title, k["title"].lower()).ratio() > 0.85 for k in kept):
            continue
        seen_urls.add(key)
        kept.append(art)
    return kept


def _pick(articles: list[dict], n: int, max_per_outlet: int) -> list[dict]:
    per_outlet: dict[str, int] = {}
    picked = []
    for art in articles:
        if len(picked) >= n:
            break
        if per_outlet.get(art["outlet"], 0) >= max_per_outlet:
            continue
        per_outlet[art["outlet"]] = per_outlet.get(art["outlet"], 0) + 1
        picked.append(art)
    return picked


def collect(now: datetime | None = None) -> list[dict]:
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=MAX_AGE_DAYS)
    config = yaml.safe_load(FEEDS_FILE.read_text(encoding="utf-8"))

    raw: list[dict] = []
    for feed in config["feeds"]:
        raw += _parse(feed["url"], feed["outlet"], feed["audience"], cutoff)
    for search in config["google_news"]:
        url = ("https://news.google.com/rss/search?q="
               f"{quote_plus(search['query'] + ' when:7d')}&hl=en-US&gl=US&ceid=US:en")
        raw += _parse(url, None, search["audience"], cutoff)

    raw.sort(key=lambda a: a["published"], reverse=True)
    articles = _dedupe(raw)

    total, men = config["target_total"], config["target_men"]
    cap = config["max_per_outlet"]
    men_pool = [a for a in articles if a["audience"] == "men"]
    women_pool = [a for a in articles if a["audience"] == "women"]
    chosen = _pick(men_pool, men, cap)
    chosen += _pick(women_pool, total - len(chosen), cap)

    for i, art in enumerate(chosen):
        art["id"] = i
    print(f"Collected {len(raw)} entries -> {len(articles)} unique -> {len(chosen)} kept "
          f"({sum(a['audience'] == 'men' for a in chosen)} menswear)")
    return chosen


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    for a in collect():
        print(f"[{a['audience']:5}] {a['outlet']:<18} {a['title'][:80]}")
