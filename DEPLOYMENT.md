# Deployment Settings

Use these GitHub repository settings for the Vedavidhya Telegram article channel.

## Required Secrets

- `OPENAI_API_KEY`: OpenAI API key for LLM-written posts.
- `TELEGRAM_BOT_TOKEN`: Telegram bot token.
- `TELEGRAM_ANALYSIS_CHANNEL_IDS`: comma-separated Telegram channel IDs/usernames for Vedavidhya-style LLM articles.

## Optional Secrets

- `TELEGRAM_CHANNEL_IDS`: comma-separated Telegram channel IDs/usernames for plain fast-news posts.

## Recommended Variables

- `KN_NEWS_ENABLE_LLM`: `1`
- `KN_NEWS_MAX_ANALYSES`: `2`
- `KN_NEWS_MAX_ANALYSIS_TOKENS`: `180`
- `OPENAI_MODEL`: `gpt-4o-mini`
- `FACEBOOK_TARGET`: `disabled`
- `KN_NEWS_REFRESH_STYLE`: `0`

## Telegram Setup

Add the bot as an admin in the new Telegram channel and give it permission to post messages.
Use the channel username, such as `@your_channel`, or the numeric channel ID in `TELEGRAM_ANALYSIS_CHANNEL_IDS`.

Normal scheduled runs publish at most `KN_NEWS_MAX_ANALYSES` LLM-written article posts to the analysis channel.
The style corpus is cached in `style_corpus.json`; set `KN_NEWS_REFRESH_STYLE=1` only when you want GitHub Actions to refresh it from the configured Vedavidhya URLs.
