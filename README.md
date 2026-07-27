# Junior Scraper API

The application scrapes product information from amazon.pl, stores normalized data in PostgreSQL and exposes it through a REST API.

## Achievements 

- Built an async product-scraping API (FastAPI, async SQLAlchemy 2.0, PostgreSQL, curl_cffi) that scrapes amazon.pl, normalizes data via Pydantic, and serves it over REST with freshness-based caching.
- Designed an anti-bot bypass layer using curl_cffi TLS/JA3 browser impersonation, a health-scored proxy pool with exponential cooldown, and captcha/block detection with retry + backoff.
- Engineered a browser-driven cookie-warming pipeline (patchright/Playwright + APScheduler) running as an isolated worker that mints session cookies unavailable to JS-less HTTP clients and shares them with the fetcher through a Postgres-backed pool.
- Implemented a full cookie lifecycle (active → used → expired → burned) with health/LRU-weighted selection and SELECT … FOR UPDATE SKIP LOCKED for safe concurrent access across processes.
- Improved request success rate by aligning cookie provenance with proxy exit IP and switching to sticky proxy sessions, cutting captcha/block responses on protected endpoints.
- Managed schema evolution with Alembic and containerized the API + warmer as separate services via Docker Compose.
- Implemented a self-balancing proxy rotation pool with Bayesian-smoothed success scoring and weighted-random selection, so healthier proxies are favored while failing ones are temporarily benched via exponential cooldown — keeping throughput up without manual proxy management.

## Tech Stack

- Python 3.12 
- FastAPI
- PostgreSQL
- SQLAlchemy
- Alembic
- curl_cffi
- BeautifulSoup4
- Docker Compose
- Pydantic
- asyncio


## Project Structure

```
app/
    main.py
    fetcher.py
    proxy.py
    crud.py
    config.py
    db.py
    models.py
    sources/
        base.py
        amazon_pl/
            parser.py
            urls.py
    routes/
        amazon_pl.py
        utils.py
migrations/
    versions/
    env.py
tests/
    fixtures/
    conftest.py
    test_parsers.py
.env.example
docker-compose.yml
Dockerfile
README.md
NOTES.md
requirements.txt
```


## Running with Docker

Clone repository.

Build containers.

_docker compose up --build_

API will become available at

_http://localhost:8000_

PostgreSQL starts automatically.


## API 

Open Swagger UI:

http://localhost:8000/docs
or
http://127.0.0.1:8000/docs

for /listing and /search enter:

- source: e.g. amazon_pl
- query: e.g. coffie makers
- page: starting page form 1 to 20
- max_pages: how many pages will be parsed from 1 to 10
- force_refresh: if True parses all cards no matter how fresh they are
and does not take data from db

for /products/{external_id} enter:

- source: e.g. amazon_pl
- external_id: id of product from site
- force_refresh: if True parses card no matter how fresh it is
and does not take data from db


### Relevant environment variables

- `COOKIES_ENABLED` (default true) — inject cookies on the fetch path
- `COOKIE_TARGET_POOL_SIZE` (default 5) — active sets to keep per source
- `COOKIE_TTL_HOURS` (default 6) — safety TTL for a minted set
- `WARMER_ENABLED` (default true) — master switch for the warmer process
- `WARMER_REFRESH_INTERVAL` (default 60) — top-up interval in seconds
- `WARMER_REFRESH_MARGIN_MIN` (default 30) — sets with less life left are refreshed
- `WARMER_HEADLESS` (default true) — run Chromium headless
