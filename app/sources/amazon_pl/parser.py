from __future__ import annotations

import re
import logging
import json
from decimal import Decimal, InvalidOperation

from bs4 import BeautifulSoup, Tag

from app.models import ListingItem, ProductDetail
from app.sources.base import SourceParser
from app.sources.amazon_pl.urls import build_search_url, build_product_url, BASE_URL

logger = logging.getLogger(__name__)

SEARCH_CARD_SELECTOR = "div[data-component-type='s-search-result']"
TITLE_SELECTOR = "h2 span"
PRICE_SELECTOR = ".a-price-whole"
IMAGE_SELECTOR = "img.s-image"

class AmazonPLParser(SourceParser):
    name = "amazon_pl"

    def build_search_url(self, query: str, page: int = 1) -> str:
        return build_search_url(query, page)

    def build_product_url(self, external_id: str) -> str:
        return build_product_url(external_id)

    def parse_listing(self, html: str) -> list[ListingItem]:
        soup = BeautifulSoup(html, "lxml")
        items: list[ListingItem] = []

        cards = soup.select(SEARCH_CARD_SELECTOR)
        for card in cards:
            try:
                item = self._parse_card(card)
                if item is not None:
                    items.append(item)
            except Exception:
                logger.exception(
                    "Failed to parse listing card (asin=%s)",
                    card.get("data-asin")
                )

        return items

    def _parse_card(self, card: Tag) -> ListingItem | None:
        asin = card.get("data-asin") or None
        if not asin:
            return None

        if self._is_sponsored(card):
            return None

        title_el = card.select_one(TITLE_SELECTOR)
        title = title_el.get_text(strip=True) if title_el else None
        if not title:
            return None

        link_el = card.select_one("h2 a")
        href = link_el["href"] if link_el and link_el.get("href") else None
        url = f"{BASE_URL}{href}" if href else build_product_url(asin)

        price = self._parse_price(card)
        rating = self._parse_rating(card)
        reviews_count = self._parse_reviews_count(card)
        image_url = self._parse_image(card)

        return ListingItem(
            source=self.name,
            external_id=asin,
            title=title,
            url=url,
            price=price,
            currency="PLN" if price is not None else None,
            rating=rating,
            reviews_count=reviews_count,
            image_url=image_url,
        )

    def parse_product(self, html: str, external_id: str) -> ProductDetail:
        soup = BeautifulSoup(html, "lxml")

        title_el = soup.select_one("#productTitle")
        title = title_el.get_text(strip=True) if title_el else ""

        price = self._parse_price(soup)
        rating = self._parse_rating(soup)
        reviews_count = self._parse_reviews_count(soup)

        description = self._parse_description(soup)

        bullet_points = [
            li.get_text(strip=True)
            for li in soup.select("#feature-bullets ul li span.a-list-item")
            if li.get_text(strip=True)
        ]

        attributes: dict[str, str] = {}
        rows = soup.select("table.prodDetTable tr") or soup.select(
            "#productDetails_techSpec_section_1 tr"
        )
        for row in rows:
            key_el = row.select_one("th")
            val_el = row.select_one("td")
            if key_el and val_el:
                attributes[key_el.get_text(strip=True)] = val_el.get_text(strip=True)

        images = []

        img = soup.select_one("img[data-a-dynamic-image]")

        if img:
            dynamic = img.get("data-a-dynamic-image")

            if dynamic:
                try:
                    images = list(json.loads(dynamic).keys())
                except json.JSONDecodeError:
                    images = []

        if not images:
            for img in soup.select("#altImages img"):
                src = img.get("src")
                if src:
                    full_res = re.sub(r"\._[A-Z0-9,_]+_\.", ".", src)
                    if full_res not in images:
                        images.append(full_res)

        availability_el = soup.select_one("#availability span")
        in_stock = None
        if availability_el:
            text = availability_el.get_text(strip=True).lower()
            in_stock = "dostępny" in text or "w magazynie" in text

        return ProductDetail(
            source=self.name,
            external_id=external_id,
            title=title,
            url=build_product_url(external_id),
            price=price,
            currency="PLN" if price is not None else None,
            rating=rating,
            reviews_count=reviews_count,
            description=description,
            bullet_points=bullet_points,
            attributes=attributes,
            images=images,
            in_stock=in_stock,
        )

    @staticmethod
    def _parse_description(soup) -> str | None:
        classic = soup.select_one("#productDescription")
        if classic and classic.get_text(strip=True):
            return classic.get_text(strip=True, separator=" ")

        aplus = soup.select_one("#aplus_feature_div") or soup.select_one("#aplus")
        if aplus:
            text = aplus.get_text(" ", strip=True)
            if text:
                return text

        return None

    @staticmethod
    def _parse_price(scope: Tag | BeautifulSoup) -> Decimal | None:
        whole = scope.select_one(PRICE_SELECTOR)
        if not whole:
            return None
        fraction = scope.select_one(".a-price-fraction")

        raw = whole.get_text(strip=True).replace("\xa0", "").replace(" ", "")
        raw = raw.rstrip(",.")
        if fraction:
            raw += "." + fraction.get_text(strip=True)

        raw = raw.replace(",", ".")
        try:
            return Decimal(raw)
        except InvalidOperation:
            logger.warning("Failed to parce price from %r", raw)
            return None

    @staticmethod
    def _parse_rating(scope: Tag | BeautifulSoup) -> float | None:
        rating_el = scope.select_one("span.a-icon-alt")
        if not rating_el:
            return None
        match = re.search(r"([\d,.]+)\s*(?:na|z)\s*5", rating_el.get_text(strip=True))
        if not match:
            return None
        try:
            return float(match.group(1).replace(",", "."))
        except ValueError:
            return None

    @staticmethod
    def _parse_reviews_count(scope: Tag | BeautifulSoup) -> int | None:
        el = scope.select_one("#acrCustomerReviewText")
        if el:
            digits = re.sub(r"[^\d]", "", el.get_text(strip=True))
            return int(digits) if digits else None

        for a in scope.select("a[aria-label]"):
            label = a["aria-label"]
            if re.match(r"^[\d\s\u00a0]+\s*ocen", label, re.IGNORECASE):
                digits = re.sub(r"[^\d]", "", label)
                return int(digits) if digits else None

        return None

    @staticmethod
    def _is_sponsored(card: Tag) -> bool:
        label = card.select_one("span.puis-sponsored-label-text")
        if label and label.get_text(strip=True):
            return True
        text = card.get_text(" ", strip=True).lower()
        return text.startswith("sponsorowane") or text.startswith("sponsored")

    @staticmethod
    def _parse_image(card) -> str | None:
        img_el = card.select_one(IMAGE_SELECTOR)
        return img_el["src"] if img_el and img_el.get("src") else None