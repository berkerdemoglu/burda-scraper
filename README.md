# Job Listings Scraper & Dashboard

A small end-to-end application that scrapes remote job listings from
[RemoteOK's public JSON API](https://remoteok.com/api), stores them in
MySQL, exposes them through a REST API, and displays them on a simple
dashboard.

## Tech Stack

- **Backend:** Python 3.10, Flask
- **ORM:** SQLAlchemy (`Base.metadata.create_all(engine)` for automatic
  schema creation at startup — no separate migration step)
- **Database:** MySQL 8.0, via PyMySQL, run as a Docker Compose service
- **Frontend:** Vanilla JavaScript, single `frontend/index.html`, Tailwind
  and Chart.js loaded via CDN — no build tools, no frontend framework
- **CI:** GitHub Actions, running ruff and pytest on every push to `master`

## Prerequisites & Startup

### Prerequisites
- Docker and Docker Compose (Docker Desktop on Windows, or Docker Engine +
  the `docker-compose-plugin` in WSL2/Linux). Verify with:
  ```bash
  docker --version
  docker compose version
  ```
- No local Python, MySQL, or pip installs are required — everything runs
  inside containers.

### Running the app
From the repository root:

```bash
docker compose up --build
```

Then open [http://localhost:8000](http://localhost:8000).

This single command builds the `web` image, starts a MySQL 8.0 container
(`jobs_db`) with a healthcheck, waits for MySQL to report healthy, then
starts the Flask app. Tables are created automatically on startup via
`Base.metadata.create_all(engine)`.

The `jobs` table is empty on first run. Trigger a scrape via the
dashboard's "Run Scrape" button, or:

```bash
curl -X POST http://localhost:8000/scrape
```

### Stopping
```bash
docker compose down       # stop containers, keep data
docker compose down -v    # stop containers and wipe the database volume
```

## Triggering a Scrape

Via the dashboard: click **"Run Scrape"** — the frontend calls
`POST /scrape` and refreshes the stats/table once it completes.

Via the command line:
```bash
curl -X POST http://localhost:8000/scrape
```

Example response (first run, empty database):
```json
{
  "status": "success",
  "message": "Scrape completed successfully",
  "added": 487,
  "skipped": 0,
  "total_processed": 487
}
```

Example response (re-running against unchanged upstream data — no
duplicates created):
```json
{
  "status": "success",
  "message": "Scrape completed successfully",
  "added": 0,
  "skipped": 487,
  "total_processed": 487
}
```

If the scraper raises an unexpected exception (not RemoteOK simply being
unreachable — see **Known Limitations**), the endpoint returns:
```json
{
  "status": "error",
  "message": "Failed to fetch jobs from upstream source"
}
```
with HTTP status `502`.

## API Endpoints

### `POST /scrape`
Triggers a scrape run against RemoteOK, normalizes results, and inserts
only jobs not already present (matched by RemoteOK's own listing ID,
stored as `job_id`).

**Response** — see [Triggering a Scrape](#triggering-a-scrape) above.

---

### `GET /jobs`
Returns stored jobs, optionally filtered.

| Query param | Description |
|-------------|-------------|
| `keyword`   | Case-insensitive substring match against title and tags |
| `company`   | Case-insensitive substring match against company name |

```bash
curl "http://localhost:8000/jobs?keyword=python&company=stripe"
```

```json
{
  "status": "success",
  "count": 1,
  "jobs": [
    {
      "id": 42,
      "job_id": "1032812",
      "title": "Senior Python Backend Engineer",
      "company": "Stripe",
      "tags": ["python", "flask", "postgres"],
      "location": "Remote",
      "date_posted": "2026-08-30T14:22:00+00:00",
      "url": "https://remoteok.com/remote-jobs/1032812"
    }
  ]
}
```

---

### `GET /stats`
Returns aggregate stats over all stored jobs.

```bash
curl http://localhost:8000/stats
```

```json
{
  "status": "success",
  "total_jobs": 487,
  "top_tags": [
    { "tag": "python", "count": 58 },
    { "tag": "remote", "count": 51 },
    { "tag": "javascript", "count": 44 },
    { "tag": "senior", "count": 39 },
    { "tag": "engineer", "count": 33 }
  ],
  "jobs_per_day": [
    { "date": "2026-08-29", "count": 12 },
    { "date": "2026-08-30", "count": 21 },
    { "date": "2026-08-31", "count": 9 }
  ]
}
```

## Dashboard Description

The dashboard shows, top to bottom: a header with a "Run Scrape" button; a
status banner confirming the last scrape result (e.g. "Scrape done: 0
added, 100 skipped, 100 processed."); a Total Jobs count and Top 5 Tags
pill badges; a line chart of jobs posted per day; two filter inputs
(keyword/tag and company); and a job table with Title, Company, Tags,
Location, Posted date, and a link to the original listing.

## Dashboard Behavior

The dashboard is a single page served by Flask at `/`, using Tailwind and
Chart.js via CDN with no build step or framework.

**Header.** Page title on the left; a **"Run Scrape"** button on the right
that triggers `POST /scrape`.

**Status banner.** A single banner above the stat cards reports state in
three colors: blue for "Scraping in progress...", green with a result
summary on success (e.g. `Scrape done: 0 added, 100 skipped, 100
processed.`), and red with a specific error message if any request fails.

**Stats cards.** **Total Jobs** as a large number, and **Top 5 Tags** as
pill-shaped badges labeled with occurrence counts (e.g. `exec (53)`), both
from `GET /stats`.

**Chart.** A Chart.js line/area chart, "Jobs Posted Per Day," built from
the `jobs_per_day` array — X-axis date, Y-axis job count.

**Filters.** Two debounced text inputs (300ms) — keyword/tag and company —
call `GET /jobs` with the corresponding query params as the user types,
re-rendering the table without a full page reload.

**Job table.** Columns: Title, Company, Tags, Location, Posted date, and a
"View" link to the original RemoteOK listing. Shows "No jobs found." if a
filter returns zero results.

**Loading and error states.** The "Run Scrape" button disables itself
while a scrape is in flight, re-enabling on completion or failure. Each of
the three API calls (stats, jobs, scrape) catches its own failure
independently and surfaces a specific error in the status banner rather
than failing silently — a stats-fetch failure doesn't block the job table
from still loading. Initial page load shows no loading indicator on the
stat cards or table; they populate once their fetch resolves. Job data
rendered into the table is escaped before insertion (`textContent`
round-trip), since job titles and tags originate from an external upstream
source and shouldn't be trusted as pre-sanitized HTML.

## Source Data & Assumptions

**Source:** [RemoteOK's public JSON API](https://remoteok.com/api) — no
authentication required. The first element of the response is RemoteOK's
own legal notice, not a job entry, and is skipped explicitly (`data[1:]`).

**Field extraction and cleaning** (`backend/scraper.py`):

- **Title, company, tags, location** pass through a shared cleaning step:
  `html.unescape()` for HTML entities, a mojibake repair step
  (`_fix_mojibake`, reversing UTF-8 bytes misread as Latin-1/CP1252), and
  regex-based whitespace collapsing.
- **Encoding.** `response.encoding` is explicitly set to `"utf-8"` before
  parsing, to reduce mojibake caused by `requests` guessing the wrong
  encoding.
- **Tags.** RemoteOK returns tags as a JSON list; they're flattened into a
  single comma-separated string column rather than a normalized second
  table, since the current scope only needs tags for display and simple
  in-memory aggregation (see Known Limitations). Jobs with no tags store
  `None`, not an empty string.
- **Date posted.** RemoteOK's `epoch` field (Unix timestamp) is parsed
  first; if missing or invalid, an ISO 8601 `date` string is tried instead
  (handling a trailing `Z` for UTC). If neither succeeds, `date_posted` is
  stored as `None` rather than dropping the whole job.
- **Location.** Optional; stored as `None` when RemoteOK omits it (common
  for fully-remote/worldwide listings).
- **Required fields.** Entries missing `id`, `title`, `company`, or `url`
  are dropped entirely by `normalize_raw_job()` before reaching the
  database — deduplication depends on `id`, and the UI's "View" link
  depends on `url`.

**Assumption:** RemoteOK's own listing `id` is a stable, unique identifier
across scrapes, and is the sole key used for deduplication (stored as
`job_id`, distinct from the database's own auto-increment primary key).

## Architecture & Design Decisions

**Scraper/API layer split.** `scraper.py` only knows how to talk to
RemoteOK and normalize its response into plain dicts — it has no
knowledge of SQLAlchemy or sessions. `main.py` owns all persistence: it
calls `Scraper().run()`, gets back a list of clean dicts, and decides what
to do with them. This lets persistence logic (idempotency, error
handling) be tested by mocking `Scraper.run()`, with no real network call
or database dependency for that part of the test.

**SQLite in tests, MySQL in production.** The app's `engine` is built once
from the `DATABASE_URL` environment variable, so the test suite overrides
that variable to a temporary SQLite file before importing the app, instead
of running a MySQL service container in CI. SQLAlchemy abstracts the SQL
dialect, so the same route code and ORM queries run unmodified against
either backend. This keeps CI fast and dependency-free, at the cost of not
verifying any genuinely MySQL-specific behavior (e.g. collation-sensitive
`LIKE` matching) — that's only exercised by the actual `docker compose up`
run.

**Skip-only deduplication, not upsert.** On a re-scrape, jobs whose
`job_id` already exists are skipped entirely — their stored fields are
never refreshed, even if RemoteOK's copy of that listing changed since the
last scrape. This is a deliberate scope decision: implementing upsert
correctly means deciding what "changed" means per field and accepting
extra write load on every scrape when most listings are unchanged.
Skip-only guarantees no duplicate rows (the stated requirement) with the
simplest possible logic, at the cost of stale data if RemoteOK edits a
listing after it's already been stored.

## Duplicate Handling & Error Handling

**Duplicate prevention — two layers.**

1. **Application-level pre-check.** `trigger_scrape()` loads all existing
   `job_id` values into a Python `set`, then skips any incoming job whose
   `job_id` is already present, incrementing `skipped` instead of
   inserting. IDs added during the current batch are added to this set
   immediately, so a repeated ID within a single scrape response is also
   caught.
2. **Database-level constraint.** `job_id` is `unique=True` in the `Job`
   model — the actual guarantee. The pre-check exists for efficiency and
   accurate `added`/`skipped` counts; the constraint is what prevents
   duplicates even under a race between two concurrent scrape requests.

**Handling malformed or missing upstream fields.** `normalize_raw_job()`
drops any entry missing `id`, `title`, `company`, or `url` before it
reaches the database. Optional fields are stored as `None` when absent,
not empty strings.

**Handling database failures.** If the insert transaction fails
(`SQLAlchemyError`), the session is rolled back and `500` is returned.
`GET /jobs` and `GET /stats` follow the same pattern for query failures.

## Known Limitations

- **Upstream network failures currently return `200`, not an error.**
  `fetch_jobs()` catches `requests.RequestException`, JSON decode errors,
  and unexpected response shapes internally, logs them, and returns an
  empty list rather than raising. As a result, `POST /scrape` cannot
  currently distinguish "RemoteOK is down" from "RemoteOK returned zero
  new listings" — both produce `200` with `added: 0`. The `502` response
  path only fires for exceptions that escape `fetch_jobs()` entirely
  (e.g. an unexpected bug during normalization), which is a rare,
  largely theoretical path given how defensively `normalize_raw_job()` is
  written. A more complete implementation would have `fetch_jobs()` raise
  a dedicated exception on real upstream failures, letting `trigger_scrape()`
  return a genuine `502` for that case specifically.

- **Keyword filtering is substring-based, not exact-tag matching.**
  `GET /jobs?keyword=python` matches against `title` and the flattened
  `tags` string using a case-insensitive `LIKE '%python%'`. A job tagged
  `python3` or `pythonista` would also match, since it's a raw substring
  search rather than a match against a discrete tag list. Accepted for
  simplicity; a stricter implementation would split `tags` into a
  normalized `job_tags` table (one row per tag) and match exact values.

- **No database indexes on filterable columns.** `title` and `company`
  are plain `String` columns with no explicit index. A standard B-tree
  index wouldn't actually help here, since a leading wildcard (`%keyword%`)
  prevents index-based prefix scans. At RemoteOK's scale (a few thousand
  listings), a full table scan is fast enough that this isn't a real
  bottleneck. At larger scale, the correct fix would be a MySQL
  `FULLTEXT` index with `MATCH ... AGAINST` queries instead of `LIKE`.

- **Tags are not queryable in SQL.** Tags are stored as a flattened
  comma-separated string, with top-5 aggregation done in Python
  (`Counter` over all rows) rather than via `GROUP BY`/`COUNT` in SQL. A
  normalized `job_tags` table (one row per job-tag pair) would enable
  database-level aggregation, but at this scale the in-memory approach is
  fast enough that the added schema complexity wasn't justified.

- **Some upstream listings contain incomplete or unrecoverably corrupted
  fields** — e.g. a missing slug (producing a bare `/remote-jobs/` URL
  with no identifier), or text that was already double-encoded/lossily
  transcoded before RemoteOK exported it, which can't be reversed by
  decoding alone. Entries with a malformed URL are dropped as incomplete
  records (via the required-field check); entries with unrecoverable text
  corruption are kept as-is, since dropping on text quality would require
  a fragile heuristic rather than a deterministic check.

- **Skip-only deduplication.** Re-scraping never updates a previously
  stored job's fields, even if RemoteOK's copy changed. See
  **Architecture & Design Decisions**.
