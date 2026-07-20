import pathlib

import pytest

FIXTURES_DIR = pathlib.Path(__file__).parent / "fixtures" / "amazon_pl"


@pytest.fixture(scope="session")
def search_html() -> str:
    path = FIXTURES_DIR / "search_ekspresy_do_kawy.html"
    return path.read_text(encoding="utf-8")


@pytest.fixture(scope="session")
def product_html() -> str:
    path = FIXTURES_DIR / "product_siemens_eq700.html"
    return path.read_text(encoding="utf-8")
