# Stablecoin Daily X Draft Agent (2x/day)

This project runs as two Render Cron Jobs (morning + evening).
Each run:
- reads RSS feeds
- filters stablecoin-related items
- generates one X-ready post using Gemini
- emails you the draft
- exits

No X API needed.

## Key env vars
- GEMINI_API_KEY, GEMINI_MODEL
- EMAIL_TO, GMAIL_USER, GMAIL_APP_PASSWORD
- RUN_SLOT=morning or RUN_SLOT=evening
- LANGUAGE_MODE=auto | en | es
- MAX_ARTICLES=5
