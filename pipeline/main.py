"""Weekly run: collect -> rank -> write -> render -> publish.

    python pipeline/main.py             # full run, publishes to Shopify
    python pipeline/main.py --dry-run   # writes preview/index.html instead
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone

from collect import collect
from publish import publish
from rank import WEIGHTS, score, select
from render import ROOT, render_fragment, render_preview
from write import attach_text, write


def _print_table(scored: list[dict], picked: list[dict]) -> None:
    chosen = {a["id"] for a in picked}
    keys = list(WEIGHTS)
    print(f"\n{'':2}{'score':>6}  " + " ".join(k[:5] for k in keys) + "  title")
    for a in scored[:20]:
        mark = "*" if a["id"] in chosen else " "
        cells = " ".join(f"{a['criteria'][k]:>5}" for k in keys)
        print(f"{mark} {a['score']:>6}  {cells}  [{a['outlet']}] {a['title'][:60]}")
    print()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="write preview/index.html, don't publish")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    now = datetime.now(timezone.utc)
    articles = collect(now)
    if len(articles) < 20:
        raise SystemExit(f"Only {len(articles)} articles collected; aborting so last week's page stays up.")

    scored = score(articles, now)
    picked = select(scored, readable=attach_text)
    if len(picked) < 5:
        raise SystemExit(f"Only {len(picked)} readable picks; aborting so last week's page stays up.")
    _print_table(scored, picked)

    edition = write(picked)
    fragment = render_fragment(edition, week_of=f"{now:%B} {now.day}, {now:%Y}", considered=len(articles))

    # Archive scores and our own summaries, but not the publishers' article text.
    def strip(a: dict) -> dict:
        return {k: v for k, v in a.items() if k != "text"}

    archive = {"date": now.isoformat(), "weights": WEIGHTS,
               "edition": {**edition, "items": [strip(a) for a in edition["items"]]},
               "ranked": [strip(a) for a in scored]}
    data_dir = ROOT / "data"
    data_dir.mkdir(exist_ok=True)
    (data_dir / f"{now:%Y-%m-%d}.json").write_text(
        json.dumps(archive,
                   indent=2, ensure_ascii=False), encoding="utf-8")

    if args.dry_run:
        out = ROOT / "preview" / "index.html"
        out.parent.mkdir(exist_ok=True)
        out.write_text(render_preview(fragment), encoding="utf-8")
        print(f"Preview written to {out}")
    else:
        print(f"Published: {publish(fragment)}")


if __name__ == "__main__":
    main()
