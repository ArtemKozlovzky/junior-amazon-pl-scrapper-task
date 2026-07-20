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

SOURCES: dict[str, SourceParser] = {
    "amazon_pl": AmazonPLParser(),
}