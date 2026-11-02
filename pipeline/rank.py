"""Score collected articles with Claude and pick the week's top 7."""
from __future__ import annotations

import json
import os
from collections import defaultdict
from datetime import datetime, timezone
from typing import Callable

import anthropic
from pydantic import BaseModel

MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-5-5")
TOP_N = 7
MAX_PER_OUTLET = 2

# Weights out of 100. Edit freely; each criterion is scored 1-10.
WEIGHTS = {
    "applicability": 20,   # useful to an average person, not just insiders
    "helpfulness": 20,     # concrete guidance that improves someone's style
    "trendiness": 15,      # computed from how many outlets cover the topic
    "affordability": 15,   # doable on a normal budget / with what you own
    "longevity": 10,       # versatile, outlasts a micro-trend
    "seasonal": 7,         # fits the current season
    "inclusivity": 7,      # works across body types, sizes, ages
    "credibility": 6,      # reputable source + freshness (computed half)
}


class ArticleScore(BaseModel):
    id: int
    topic: str
    is_style_advice: bool
    applicability: int
    helpfulness: int
    affordability: int
    longevity: int
    seasonal: int
    inclusivity: int
    credibility: int


class Scores(BaseModel):
    scores: list[ArticleScore]


SYSTEM = """You are the fashion editor of a weekly style newsletter for ordinary people \
(mostly women, some men) who want to dress better without big budgets.

You will receive a list of recent fashion articles (id, outlet, title, snippet). For EVERY article return:
- topic: a short 2-4 word topic label in lowercase (e.g. "barrel-leg jeans", "burgundy everything", \
"men's chore coats"). Use the SAME label for articles about the same trend so they can be grouped.
- is_style_advice: true if a reader could take a wearable idea from it; false for business news, \
celebrity gossip, obituaries, pure runway reports, shopping deals with no styling angle, or sponsored content.
- Integer scores from 1 to 10:
  applicability: relevant to an average person's real life (10 = anyone could use it)
  helpfulness: concrete, actionable guidance that improves how someone dresses
  affordability: achievable cheaply or with clothes people already own (luxury-only = 1)
  longevity: versatile and lasting rather than a fleeting micro-trend
  seasonal: fits {season} in the northern hemisphere right now
  inclusivity: works across body types, sizes, ages and genders where relevant
  credibility: how reputable and original the source is (affiliate listicles score low)"""


def _season(now: datetime) -> str:
    return ["winter", "spring", "summer", "autumn"][(now.month % 12) // 3] + f" ({now:%B})"


def _clamp(value: int) -> int:
    return max(1, min(10, value))


def score(articles: list[dict], now: datetime | None = None) -> list[dict]:
    now = now or datetime.now(timezone.utc)
    listing = [{k: a[k] for k in ("id", "outlet", "title", "snippet")} for a in articles]
    client = anthropic.Anthropic()
    response = client.messages.parse(
        model=MODEL,
        max_tokens=16000,
        output_config={"effort": "medium"},
        system=SYSTEM.format(season=_season(now)),
        messages=[{"role": "user", "content": json.dumps(listing, ensure_ascii=False)}],
        output_format=Scores,
    )
    if response.stop_reason in ("refusal", "max_tokens"):
        raise RuntimeError(f"Scoring call stopped early: {response.stop_reason}")

    by_id = {s.id: s for s in response.parsed_output.scores}

    # Trendiness: how many articles and distinct outlets share the topic.
    topic_articles: dict[str, int] = defaultdict(int)
    topic_outlets: dict[str, set] = defaultdict(set)
    for a in articles:
        s = by_id.get(a["id"])
        if s:
            topic_articles[s.topic] += 1
            topic_outlets[s.topic].add(a["outlet"])
    buzz = {t: topic_articles[t] + 2 * len(topic_outlets[t]) for t in topic_articles}
    top_buzz = max(buzz.values(), default=1)

    scored = []
    for a in articles:
        s = by_id.get(a["id"])
        if not s:
            continue
        age_days = (now - datetime.fromisoformat(a["published"])).days
        criteria = {
            "applicability": _clamp(s.applicability),
            "helpfulness": _clamp(s.helpfulness),
            "trendiness": round(1 + 9 * buzz[s.topic] / top_buzz),
            "affordability": _clamp(s.affordability),
            "longevity": _clamp(s.longevity),
            "seasonal": _clamp(s.seasonal),
            "inclusivity": _clamp(s.inclusivity),
            "credibility": round((_clamp(s.credibility) + max(1, 10 - age_days)) / 2),
        }
        total = sum(WEIGHTS[k] * v for k, v in criteria.items()) / 10  # 0-100
        scored.append({**a, "topic": s.topic, "is_style_advice": s.is_style_advice,
                       "criteria": criteria, "score": round(total, 1)})
    scored.sort(key=lambda a: a["score"], reverse=True)
    return scored


def select(scored: list[dict], readable: Callable[[dict], bool] = lambda a: True) -> list[dict]:
    """Top N by score, one per topic, MAX_PER_OUTLET per outlet, at least one menswear.
    `readable` is checked last (it may fetch the article) so only candidates are fetched."""
    pool = [a for a in scored if a["is_style_advice"]]
    picked, topics, outlets = [], set(), defaultdict(int)
    for a in pool:
        if len(picked) == TOP_N:
            break
        if a["topic"] in topics or outlets[a["outlet"]] >= MAX_PER_OUTLET or not readable(a):
            continue
        picked.append(a)
        topics.add(a["topic"])
        outlets[a["outlet"]] += 1

    if picked and not any(a["audience"] == "men" for a in picked):
        best_men = next((a for a in pool if a["audience"] == "men" and a["topic"] not in topics
                         and readable(a)), None)
        if best_men:
            picked[-1] = best_men
    picked.sort(key=lambda a: a["score"], reverse=True)
    return picked
