from decimal import Decimal

from app.sources.amazon_pl.parser import AmazonPLParser
from app.fetcher import Fetcher

parser = AmazonPLParser()


class TestParseListing:
    def test_returns_expected_number_of_items(self, search_html):
        items = parser.parse_listing(search_html)
        assert len(items) == 60

    def test_every_item_has_required_fields(self, search_html):
        items = parser.parse_listing(search_html)
        for item in items:
            assert item.external_id
            assert item.title
            assert str(item.url).startswith("https://www.amazon.pl")
            assert item.source == "amazon_pl"

    def test_prices_are_parsed_for_all_items(self, search_html):
        items = parser.parse_listing(search_html)
        with_price = [i for i in items if i.price is not None]
        assert len(with_price) == len(items)
        assert all(i.currency == "PLN" for i in with_price)
        assert all(Decimal("10") < i.price < Decimal("50000") for i in with_price)

    def test_most_items_have_rating_and_reviews(self, search_html):
        items = parser.parse_listing(search_html)
        with_rating = [i for i in items if i.rating is not None]
        with_reviews = [i for i in items if i.reviews_count is not None]
        assert len(with_rating) >= len(items) - 2
        assert len(with_reviews) >= len(items) - 2
        assert all(0 <= i.rating <= 5 for i in with_rating)

    def test_first_item_matches_known_values(self, search_html):
        items = parser.parse_listing(search_html)
        first = items[0]
        assert first.external_id == "B0GKHW3V7Q"
        assert "Siemens" in first.title
        assert first.price == Decimal("4769.47")
        assert first.rating == 4.6
        assert first.reviews_count == 10


class TestParseProduct:
    def test_basic_fields(self, product_html):
        product = parser.parse_product(product_html, "B0GKHW3V7Q")
        assert product.source == "amazon_pl"
        assert product.external_id == "B0GKHW3V7Q"
        assert "Siemens" in product.title
        assert product.price == Decimal("4769.47")
        assert product.currency == "PLN"
        assert product.rating == 4.6
        assert product.reviews_count == 10

    def test_description_is_present(self, product_html):
        product = parser.parse_product(product_html, "B0GKHW3V7Q")
        assert product.description
        assert len(product.description) > 100

    def test_bullet_points_present(self, product_html):
        product = parser.parse_product(product_html, "B0GKHW3V7Q")
        assert len(product.bullet_points) == 5
        assert all(len(bp) > 10 for bp in product.bullet_points)

    def test_attributes_present(self, product_html):
        product = parser.parse_product(product_html, "B0GKHW3V7Q")
        assert len(product.attributes) == 26
        assert "Moc w watach" in product.attributes
        assert product.attributes["Moc w watach"] == "1500 W"

    def test_images_present(self, product_html):
        product = parser.parse_product(product_html, "B0GKHW3V7Q")
        assert len(product.images) == 7
        assert all(str(img).startswith("http") for img in product.images)

    def test_in_stock(self, product_html):
        product = parser.parse_product(product_html, "B0GKHW3V7Q")
        assert product.in_stock is True


class TestCaptchaDetection:
    def test_normal_page_is_not_captcha(self, search_html):
        assert Fetcher._looks_like_captcha(search_html) is False

    def test_captcha_markers_are_detected(self):
        fake_captcha_html = """
        <html><body>
        <form action="/errors/validateCaptcha">
        Enter the characters you see below
        </form>
        </body></html>
        """
        assert Fetcher._looks_like_captcha(fake_captcha_html) is True
