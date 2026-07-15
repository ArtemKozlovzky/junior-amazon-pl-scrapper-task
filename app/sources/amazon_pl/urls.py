from __future__ import annotations

from urllib.parse import urlencode

BASE_URL = "https://www.amazon.pl"


def build_search_url(query: str, page: int = 1) -> str:
    params = {"k": query, "page": page}
    return f"{BASE_URL}/s?{urlencode(params)}"


def build_product_url(asin: str) -> str:
    return f"{BASE_URL}/dp/{asin}"
