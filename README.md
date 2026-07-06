# JobRadar

[![Tests](https://github.com/AlexHalanyk/JobRadar/actions/workflows/tests.yml/badge.svg)](https://github.com/AlexHalanyk/JobRadar/actions/workflows/tests.yml)

A Telegram bot that monitors company ATS APIs directly and notifies subscribers
about new graduate software engineering vacancies — often hours or days before
they appear on job aggregators.

Built as a real tool for my own 2027 UK grad-scheme search: rolling applications
reward whoever applies first, so the bot watches the primary source (the same
API a company's careers page is rendered from) instead of waiting for Indeed
or weekly digest emails.

## Features

- Monitors company ATS boards directly (Greenhouse for now), checking every
  15 minutes — often ahead of job aggregators.
- Two-stage filtering keeps LLM costs near zero: a keyword prefilter, then a
  Gemini 2.5 Flash relevance check for survivors.
- Self-service via chat: `/start` to subscribe, or send a Greenhouse slug or
  URL (e.g. `monzo`) to add a company to the watchlist — no redeploy needed.
- Per-subscriber filter profiles: `/profile <text>` lets each subscriber
  describe what they're looking for in free text; every job is evaluated
  once per distinct profile, and only matching subscribers get notified.
- Dedup via SQLite: every processed job is remembered, so nothing is
  evaluated or sent twice, even across restarts.
- Resilient to LLM API errors and rate limits: failures are retried next
  cycle instead of crashing the bot.

## Architecture

- `main.py` — the main loop: every 15 minutes, fetch jobs, filter, notify,
  and poll for incoming Telegram messages.
- `bot.py` — services: sending/receiving Telegram messages, the Gemini LLM
  relevance check, and SQLite persistence (sent jobs, subscribers, tracked
  companies).
- `sources.py` — ATS fetchers (currently Greenhouse's public board API),
  normalising job fields into a common shape (title, company, location,
  link, id).

**Two-stage filtering**: a cheap keyword filter drops obviously irrelevant
titles without an API call. Survivors go to Gemini 2.5 Flash with a YES/NO
prompt asking whether the role is a graduate/junior SWE role suitable for a
UK CS graduate. LLM output is never trusted blindly — it's normalised
(`strip`/`upper`/substring check) since the model occasionally returns
`YES.`, `Yes`, or a full sentence instead of one word.

**Dedup via SQLite**: processed job links are stored in the `sent_jobs`
table so a job is only ever evaluated and sent once. The database lives in a
Docker volume so history survives restarts and redeploys.

## Evaluation

Relevance filtering is benchmarked offline against a golden set of ~70
hand-labelled job titles (`golden_set.csv`), across three configurations:

| Configuration | Accuracy | Precision | Recall | Coverage |
|---|---|---|---|---|
| Ollama (Gemma 4 12B, self-hosted) | 100% | 100% | 100% | 70/70 |
| Gemini | 100%* | 100%* | 100%* | 51/70 (19 undecided) |
| Cascade (Ollama → Gemini) | 98.6% | 100% | 90% | 70/70 |

\* Measured only over the titles Gemini returned a decision for — 19/70 came
back undecided due to Gemini API 503s at measurement time.

Cascade inherits the availability of both models: its one miss was caused by
the second-stage (Gemini) call being unavailable when the first stage
(Gemma) had already flagged the job as a candidate. Run `eval_filter.py` to
reproduce or rerun the benchmark.

## Tech stack

Python · SQLite · Docker / docker-compose · Telegram Bot API ·
Google Gemini API · Greenhouse ATS API. Deployed on a Nutanix AHV VM
(git-based deploys: push → pull → rebuild).

## Setup

Environment variables (put them in `.env`, see `.env.example`):

- `TELEGRAM_TOKEN` — Telegram bot token from BotFather
- `GEMINI_API_KEY` — Google Gemini API key

```
git clone https://github.com/AlexHalanyk/JobRadar.git
cd JobRadar
cp .env.example .env   # fill in TELEGRAM_TOKEN and GEMINI_API_KEY
docker compose up --build -d
```

## Roadmap

- Workday adapter for enterprise employers (banks, consultancies)
- Self-hosted LLM via Ollama, as a cost/quality comparison against hosted Gemini
- Mobile client
