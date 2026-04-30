SaveTicker / 오선 reference

User-provided URL:
- https://www.saveticker.com/app/news

Why this matters:
- This is the "오선꺼 SAVE" reference the user meant.
- Use it as a fast Korean-language market/news signal source for stock-research-agent.
- Treat it as a data/UX/reference source, not as code to copy.

Observed public web/API surfaces:
- App page: https://www.saveticker.com/app/news
- News list API: https://api.saveticker.com/api/news/list
  - Useful params observed from web bundle/public calls:
    - page, page_size
    - search
    - keywords
    - tickers, e.g. tickers=NVDA
    - sources, e.g. sources=fivelines_news for SAVE/user-authored items
    - label_name, tag_ids, general_tag_ids, ticker_tag_ids
    - start, end, start_date, end_date, time_range
- Top stories API: https://api.prod.fivelines.co.kr/api/news/top-stories
- Content labels config: https://media.saveticker.com/config/content-labels.json
- SSE endpoint in app bundle: https://sse.saveticker.com/sse/

Useful interpretation:
- `sources=fivelines_news` surfaces SAVE/original items; author_name often includes `오선`.
- `search=오선` or `keywords=오선` can surface 오선 노트 posts.
- `tickers=NVDA` can return ticker-specific SaveTicker items; ticker tags may appear in `tag_names` as `$NVDA`, `$AMD`, etc.
- Items include title, source, author_name, created_at, view_count, tag_names, id.

Implementation note:
- `src/saveticker_data.py` now prefers the public JSON API and falls back to Jina-rendered app markdown.
- The normalizer preserves source/author in the source field as `saveticker_api:<source>:<author_name>` and maps `$TICKER` tag names into ticker symbols.

Risk/guardrails:
- Do not imply this is exhaustive market news; use as one signal source.
- Mark `(카더라)`/rumor-like items as lower-confidence, not confirmed facts.
- Avoid copying SaveTicker app code/assets; only use public JSON responses and high-level UX inspiration.
