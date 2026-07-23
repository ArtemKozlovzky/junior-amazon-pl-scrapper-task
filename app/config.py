import os
from dotenv import load_dotenv
from sqlalchemy import URL
import logging
from datetime import timedelta
from app.sources.base import SourceParser
from app.sources.amazon_pl.parser import AmazonPLParser

logger = logging.getLogger(__name__)

load_dotenv()

database_url = URL.create(
        drivername='postgresql+asyncpg',
        username= os.getenv('DATABASE_USER'),
        password= os.getenv('DATABASE_PASSWORD'),
        host= os.getenv('DATABASE_HOST'),
        port= os.getenv('DATABASE_PORT', 5432),
        database= os.getenv('DATABASE_NAME')
    )

sync_url = URL.create(
        drivername='postgresql+psycopg2',
        username= os.getenv('DATABASE_USER'),
        password= os.getenv('DATABASE_PASSWORD'),
        host= os.getenv('DATABASE_HOST'),
        port= os.getenv('DATABASE_PORT', 5432),
        database= os.getenv('DATABASE_NAME')
    )

product_freshness_hrs = os.getenv("PRODUCT_FRESHNESS_HOURS", "24")

FRESHNESS_MAX_AGE = timedelta(hours=float(product_freshness_hrs))


def _env_bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes", "on")

COOKIE_TARGET_POOL_SIZE = int(os.getenv("COOKIE_TARGET_POOL_SIZE", "5"))
COOKIE_TTL = timedelta(hours=float(os.getenv("COOKIE_TTL_HOURS", "6")))
WARMER_REFRESH_INTERVAL = float(os.getenv("WARMER_REFRESH_INTERVAL", "60"))
WARMER_REFRESH_MARGIN = timedelta(minutes=float(os.getenv("WARMER_REFRESH_MARGIN_MIN", "30")))
WARMER_HEADLESS = _env_bool("WARMER_HEADLESS", True)
WARMER_ENABLED = _env_bool("WARMER_ENABLED", True)
COOKIES_ENABLED = _env_bool("COOKIES_ENABLED", True)

SOURCES: dict[str, SourceParser] = {
    "amazon_pl": AmazonPLParser(),
}

def _load_proxies_from_env() -> list[str]:
    raw = os.getenv("PROXY_LIST", "")
    return [p.strip() for p in raw.split(",") if p.strip()]