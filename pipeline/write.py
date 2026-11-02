"""Fetch the chosen articles and have Claude write summaries plus the closing paragraph."""
from __future__ import annotations

import json

import anthropic
import trafilatura
from pydantic import BaseModel

from rank import MODEL

MAX_CHARS = 6000
MIN_CHARS = 800  # below this we can't summarize honestly


class Entry(BaseModel):
    id: int
    headline: str
    summary: str
    tip: str


class Edition(BaseModel):
    intro: str
    entries: list[Entry]
    practice: list[str]


SYSTEM = """You write a weekly style-tips page for ordinary readers (mostly women, some men) \
who want to dress better on a normal budget. Tone: warm, editorial, confident, never snobbish.

For each article you get (id, outlet, original title, text):
- headline: a clean headline (you may tighten the original title; keep it accurate).
- summary: 2-3 sentences, entirely in your own words. Never copy sentences or quote more than \
a few words from the source.
- tip: one short, actionable sentence a reader can try this week.

Also write:
- intro: one sentence introducing this week's edit.
- practice: 2 short paragraphs under the heading "Putting it into practice" that combine \
the week's ideas into concrete, budget-friendly actions (shop your closet first, what to buy if \
anything, how the pieces work together). Address the reader as "you"."""


def attach_text(article: dict) -> bool:
    """Fetch the article body into article["text"]; False if it can't be read.
    Google News links are JS redirects, so those only count toward trendiness."""
    if "text" not in article:
        text = None
        if "news.google.com" not in article["url"]:
            try:
                downloaded = trafilatura.fetch_url(article["url"])
                text = trafilatura.extract(downloaded) if downloaded else None
            except Exception:
                text = None
        article["text"] = (text or "")[:MAX_CHARS]
    return len(article["text"]) >= MIN_CHARS


def write(picked: list[dict]) -> dict:
    payload = [{"id": a["id"], "outlet": a["outlet"], "title": a["title"], "text": a["text"]}
               for a in picked]
    client = anthropic.Anthropic()
    response = client.messages.parse(
        model=MODEL,
        max_tokens=16000,
        output_config={"effort": "medium"},
        system=SYSTEM,
        messages=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
        output_format=Edition,
    )
    if response.stop_reason in ("refusal", "max_tokens"):
        raise RuntimeError(f"Writing call stopped early: {response.stop_reason}")

    edition = response.parsed_output
    written = {e.id: e for e in edition.entries}
    items = []
    for a in picked:
        e = written.get(a["id"])
        if e:
            items.append({**a, "headline": e.headline, "summary": e.summary, "tip": e.tip})
    return {"intro": edition.intro, "items": items, "practice": edition.practice}
