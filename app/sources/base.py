from __future__ import annotations

from abc import ABC, abstractmethod

from app.models import ListingItem, ProductDetail


class SourceParser(ABC):

    name: str

    @abstractmethod
    def build_search_url(self, query: str, page: int = 1) -> str:
        pass

    @abstractmethod
    def build_product_url(self, external_id: str) -> str:
        pass

    @abstractmethod
    def parse_listing(self, html: str) -> list[ListingItem]:
        pass

    @abstractmethod
    def parse_product(self, html: str, external_id: str) -> ProductDetail:
        pass