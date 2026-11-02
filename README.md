# Weekly Style

A two-page editorial site on Shopify, updated automatically every Sunday:

- **Home**: typographic hero with a button linking to the tips page.
- **Weekly Style Tips** (`/pages/style-tips`): this week's top 7 articles, each with a summary, a one-line tip and a link to the full piece, followed by a "Putting it into practice" section.

Every Sunday a GitHub Action collects about 100 articles from the past 7 days (RSS feeds and Google News, roughly 80% womenswear and 20% menswear). Claude scores each one, the pipeline picks the top 7, writes the page and replaces the Shopify page body.

## Ranking

Weights live in `pipeline/rank.py` → `WEIGHTS`:

| Criterion | Weight | How it's scored |
|---|---|---|
| Applicability | 20 | Claude, 1–10 |
| Helpfulness | 20 | Claude, 1–10 |
| Trendiness | 15 | Computed: number of articles and distinct outlets covering the same topic |
| Affordability | 15 | Claude, 1–10 |
| Longevity / versatility | 10 | Claude, 1–10 |
| Seasonal relevance | 7 | Claude, 1–10 (current month passed in) |
| Inclusivity | 7 | Claude, 1–10 |
| Credibility & freshness | 6 | Average of Claude's source score and article age |

Selection rules: non-advice pieces (business news, gossip, deals) are dropped; at most 1 article per topic and 2 per outlet; at least 1 menswear piece.

## One-time setup

1. **Push this folder to a GitHub repo.**
2. **Theme files:** in Shopify admin → Online Store → Themes → ⋯ → Edit code, add:
   - `assets/weekly-style.css`
   - `templates/page.home-hero.liquid`
   - `templates/page.style-tips.liquid`

   (Or run `shopify theme push --only templates/page.home-hero.liquid ...` with the Shopify CLI.)
3. **Pages:** Online Store → Pages:
   - "Home": template `page.home-hero`. To make it the landing page, link to it from your navigation, or redirect `/` to it.
   - "Style Tips": handle `style-tips`, template `page.style-tips`. The body can be blank to start.
4. **API access:** create an app for your store with the `read_content` and `write_content` Admin API scopes.
   - Legacy custom app (Settings → Apps → Develop apps): copy the Admin API access token → secret `SHOPIFY_ADMIN_TOKEN`.
   - Dev Dashboard app: install it on your store, then set secrets `SHOPIFY_CLIENT_ID` and `SHOPIFY_CLIENT_SECRET`. The pipeline exchanges them for a token on every run.
5. **GitHub secrets** (repo → Settings → Secrets and variables → Actions): `ANTHROPIC_API_KEY`, `SHOPIFY_STORE` (e.g. `my-shop.myshopify.com`) and the Shopify credentials from step 4.
6. Actions tab → *Weekly style tips* → **Run workflow** (try `dry_run` first and download the preview artifact).

## Running locally

```bash
pip install -r requirements.txt
cd pipeline
python collect.py            # just list what would be collected (no API key needed)
python main.py --dry-run     # full run, writes preview/index.html (needs ANTHROPIC_API_KEY)
```

Each run saves its ranking and edition to `data/YYYY-MM-DD.json`. If fewer than 20 articles are collected, the run aborts and last week's page stays up.

Optional env vars: `CLAUDE_MODEL` (default `claude-sonnet-5-5`), `SHOPIFY_PAGE_HANDLE` (default `style-tips`), `SHOPIFY_API_VERSION` (default `2026-10`).


## Install link
https://admin.shopify.com/oauth/install_custom_app?client_id=861b57de7f4342e4c045de0596bba65e&no_redirect=true&signature=eyJleHBpcmVzX2F0IjoxNzk0MTg0NTk3LCJwZXJtYW5lbnRfZG9tYWluIjoiaWNleWNyZXcubXlzaG9waWZ5LmNvbSIsImNsaWVudF9pZCI6Ijg2MWI1N2RlN2Y0MzQyZTRjMDQ1ZGUwNTk2YmJhNjVlIiwicHVycG9zZSI6ImN1c3RvbV9hcHAiLCJtZXJjaGFudF9vcmdhbml6YXRpb25faWQiOjEyODQ0MTE0fQ%3D%3D--4f7bd7761fd3fab7805f932cd1d5a1f939d9d6fe