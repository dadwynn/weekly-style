"""Render the edition to an HTML fragment (the Shopify page body) or a standalone preview."""
from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

ROOT = Path(__file__).resolve().parent.parent
CSS = ROOT / "shopify-theme" / "assets" / "weekly-style.css"
FONTS = ("https://fonts.googleapis.com/css2?family=Bodoni+Moda:ital,opsz,wght@0,6..96,400;"
         "1,6..96,400&family=Inter:wght@400;600&display=swap")

_env = Environment(loader=FileSystemLoader(Path(__file__).with_name("templates")),
                   autoescape=select_autoescape(["html", "j2"]))


def render_fragment(edition: dict, week_of: str, considered: int) -> str:
    return _env.get_template("tips.html.j2").render(week_of=week_of, considered=considered, **edition)


def render_preview(fragment: str) -> str:
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Weekly Style Tips</title>
<link rel="stylesheet" href="{FONTS}">
<style>body{{margin:0;background:#fff}}
{CSS.read_text(encoding="utf-8")}</style>
</head><body><div class="ws">
{fragment}
</div></body></html>"""
