# Deployment Settings

Use these GitHub repository settings for the Vedavidhya Telegram article channel.

## Required Secrets

- `OPENAI_API_KEY`: OpenAI API key for LLM-written posts.
- `TELEGRAM_ANALYSIS_BOT_TOKEN`: Telegram bot token for the Vedavidhya article channel.
- `TELEGRAM_ANALYSIS_CHANNEL_IDS`: comma-separated Telegram channel IDs/usernames for Vedavidhya-style LLM articles.

## Optional Secrets

- `TELEGRAM_BOT_TOKEN`: Telegram bot token for the existing plain fast-news channel.
- `TELEGRAM_CHANNEL_IDS`: comma-separated Telegram channel IDs/usernames for plain fast-news posts.

## Recommended Variables

- `KN_NEWS_ENABLE_LLM`: `1`
- `KN_NEWS_MAX_ANALYSES`: `2`
- `KN_NEWS_MAX_ANALYSIS_TOKENS`: `180`
- `OPENAI_MODEL`: `gpt-4o-mini`
- `FACEBOOK_TARGET`: `disabled`
- `KN_NEWS_REFRESH_STYLE`: `0`

## Telegram Setup

Add the bot as an admin in each Telegram channel and give it permission to post messages.
`TELEGRAM_ANALYSIS_CHANNEL_IDS` accepts a comma-separated list, so a second analysis channel
is just another entry in that secret (e.g. `-1001111111111,-1002222222222` or `@channel1,@channel2`) -
no code change needed. Use the channel username, such as `@your_channel`, or the numeric channel ID.
If `TELEGRAM_ANALYSIS_BOT_TOKEN` is unset, the bot falls back to `TELEGRAM_BOT_TOKEN`.

Normal scheduled runs publish at most `KN_NEWS_MAX_ANALYSES` LLM-written article posts to the analysis channel.
The style corpus is cached in `style_corpus.json`; set `KN_NEWS_REFRESH_STYLE=1` only when you want GitHub Actions to refresh it from the configured Vedavidhya URLs. `curated: true` samples (real excerpts pulled from the brand's own Facebook export, used as voice anchors) are preserved across refreshes - only the scraped-from-URL samples get replaced.
The generated `news.db` and `news_export.jsonl` files are runtime artifacts and should stay out of git.
If you need state across GitHub Actions runs, store the SQLite DB in external persistent storage and point `KN_NEWS_DB` / `KN_NEWS_JSONL` there.

## Facebook: via ViralDashboard, not the direct Graph API

The direct Facebook posting path (`facebook_post.py`, `FACEBOOK_TARGET=page`) exists in the
code but is currently blocked by a Meta-side issue (token/permission/app review) unrelated to
this codebase. Leave `FACEBOOK_TARGET` at its default `disabled` and don't set
`FACEBOOK_PAGE_ACCESS_TOKEN` - setting both would risk double-posting to the Page once the
Meta-side issue is eventually resolved.

Instead, every run regenerates `docs/analysis_feed.xml` (see `feed.py`) - an RSS 2.0 feed of the
last `feed.MAX_ITEMS` analysis posts - and the workflow commits it back to the repo if it
changed. One-time setup to make this live:

1. In the GitHub repo: **Settings -> Pages -> Build and deployment -> Source: Deploy from a
   branch**, branch `main`, folder `/docs`. This gives you a public URL like
   `https://<github-username>.github.io/<repo>/analysis_feed.xml`.
2. In ViralDashboard: **Connect -> RSS Feeds Connect -> Connect your website's feed**, paste
   that URL.
3. In ViralDashboard's **Automation** section, create a rule that publishes new items from that
   feed to the connected Facebook Page (and nowhere else - Telegram already gets posts directly
   from this bot, so routing the same feed to Telegram too would double-post there).

`feed.py` reads back whatever is already committed in `docs/analysis_feed.xml` before writing,
merges in this run's new item(s), dedupes by guid, and keeps a rolling window - this matters
because `news.db` does **not** persist across scheduled runs (see above), so without that
merge step every run would overwrite the feed with just its own 0-1 items instead of a history.
