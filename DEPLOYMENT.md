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
- `KN_NEWS_ENGLISH_ANALYSIS`: `1` (master on/off switch for the classical-content pipeline - name kept for backward compatibility, see below)
- `KN_NEWS_CLASSICAL_MIN_GAP_HOURS`: `9` (default; ~2.6 posts/day - lower this once content quality is validated and you want more volume)
- `KN_NEWS_MAX_ANALYSIS_TOKENS`: `180`
- `OPENAI_MODEL`: `gpt-4o-mini`
- `FACEBOOK_TARGET`: `disabled`
- `KN_NEWS_REFRESH_STYLE`: `0`

## Classical-Content Pipeline (Vedavidhya analysis channel + Facebook)

The analysis channel/Facebook page no longer reacts to daily news. `classical_content.py` generates
original Kannada content mapped to specific classical Indian systems - Jyotisha (Vedic Astrology),
Tantra/Sadhana/Shakti, Vedic Science, Dharmashastra, Arthashastra, Nyayashastra, Itihasa (Ramayana &
Mahabharata), Panchatantra, and Indian classical arts/literature - in a rotating mix of content genres:
critique, debate, elaboration, story, correlation, guidance, and lifestyle. This replaced the old
"analyze today's news through a dharmic lens" pipeline, which produced generic current-affairs
commentary rather than content actually about these systems.

Each run picks one (system, specific angle, genre) combination that hasn't been used recently, drafts it
in English with Gemini, and translates it to Kannada with the same Groq-first pipeline used before (see
`analyzer.py`'s translation functions, reused by `classical_content.py`). A shared set of safety rules
applies to every genre: never fabricate verse numbers/citations/studies, never disparage a rival school
or tradition even in a critique/debate post, and any health/legal/psychological guidance post must
include a plain disclaimer that it is not a substitute for professional care.

Even though the workflow's cron fires every 15 minutes, this pipeline only actually posts roughly every
`KN_NEWS_CLASSICAL_MIN_GAP_HOURS` hours (default 9, i.e. ~2-3 posts/day to start). `content_state.py`
tracks the last-post time and recent topic/genre history in `docs/content_state.json`, which the workflow
commits back to the repo alongside `docs/analysis_feed.xml` - this is what makes the cadence gate and the
topic/genre rotation survive across runs, since `news.db` itself does not (see below). Once you're happy
with post quality, lower `KN_NEWS_CLASSICAL_MIN_GAP_HOURS` to increase volume - no other code change is
needed.

## Telegram Setup

Add the bot as an admin in each Telegram channel and give it permission to post messages.
`TELEGRAM_ANALYSIS_CHANNEL_IDS` accepts a comma-separated list, so a second analysis channel
is just another entry in that secret (e.g. `-1001111111111,-1002222222222` or `@channel1,@channel2`) -
no code change needed. Use the channel username, such as `@your_channel`, or the numeric channel ID.
If `TELEGRAM_ANALYSIS_BOT_TOKEN` is unset, the bot falls back to `TELEGRAM_BOT_TOKEN`.

Normal scheduled runs publish at most one classical-content post per `KN_NEWS_CLASSICAL_MIN_GAP_HOURS`
window to the analysis channel (see above) - not one per run.
The style corpus is cached in `style_corpus.json`; set `KN_NEWS_REFRESH_STYLE=1` only when you want GitHub Actions to refresh it from the configured Vedavidhya URLs. `curated: true` samples (real excerpts pulled from the brand's own Facebook export, used as voice anchors) are preserved across refreshes - only the scraped-from-URL samples get replaced.
The generated `news.db` and `news_export.jsonl` files are runtime artifacts and should stay out of git.
If you need state across GitHub Actions runs, store the SQLite DB in external persistent storage and point `KN_NEWS_DB` / `KN_NEWS_JSONL` there.

## Facebook: via a free RSS-to-social tool, not the direct Graph API

The direct Facebook posting path (`facebook_post.py`, `FACEBOOK_TARGET=page`) exists in the
code but is currently blocked - in practice, Meta requires a full App Review (a weeks-long
process, even though it's free) before a personal/business Facebook App is allowed to call
`pages_manage_posts` in production, which is almost certainly the "glitch" that was hit. Leave
`FACEBOOK_TARGET` at its default `disabled` and don't set `FACEBOOK_PAGE_ACCESS_TOKEN` - setting
both later would risk double-posting to the Page once/if that App Review is ever completed.

Instead, every run regenerates `docs/analysis_feed.xml` (see `feed.py`) - an RSS 2.0 feed of the
last `feed.MAX_ITEMS` classical-content posts - and the workflow commits it (along with
`docs/content_state.json`, the cadence/rotation state - see above) back to the repo if either
changed. This feed is provider-agnostic: point any RSS-to-social tool at it. One-time setup:

1. In the GitHub repo: **Settings -> Pages -> Build and deployment -> Source: Deploy from a
   branch**, branch `main`, folder `/docs`. This gives you a public URL like
   `https://<github-username>.github.io/<repo>/analysis_feed.xml`.
2. Connect that feed URL to your Facebook Page in a free RSS-to-social tool - these already have
   their own Meta-approved app, so connecting your Page is just a standard "Login with Facebook"
   click, no App Review needed on your side:
   - **dlvr.it** (recommended): free Basic plan = 2 profiles, 3 feeds, up to 5 posts/day (3/day
     per profile) - comfortably covers our volume of roughly 1-4 analysis posts/day. Add the
     feed under Feeds (RSS/Atom), route it to your connected Facebook Page.
   - **IFTTT**: free plan allows 2 active Applets, which is exactly what's needed here (one
     Applet: "new item in this RSS feed -> post to this Facebook Page"). Polling can be slower
     than dlvr.it on the free tier, which is fine for this use case.
   - **ViralDashboard**: same RSS-feed input works here too if budget allows later - nothing
     about the feed itself is ViralDashboard-specific.

Only ever have ONE of these tools/routes pointed at the feed and at Telegram at a time - since
Telegram already gets posts directly from this bot, routing the same feed to Telegram as well
would double-post there, and running two RSS-to-Facebook tools against the same feed at once
would double-post to the Page.

`feed.py` reads back whatever is already committed in `docs/analysis_feed.xml` before writing,
merges in this run's new item(s), dedupes by guid, and keeps a rolling window - this matters
because `news.db` does **not** persist across scheduled runs (see above), so without that
merge step every run would overwrite the feed with just its own 0-1 items instead of a history.
`content_state.json` works the same way for the cadence gate and topic/genre rotation history.
