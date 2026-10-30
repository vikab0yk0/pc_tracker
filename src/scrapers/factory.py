from typing import Optional
from src.models import ShopType
from src.scrapers.base import BaseScraper
from src.scrapers.wildberries import WildberriesScraper


class ScraperFactory:
    """Фабрика для получения инстанса парсера по URL или типу магазина."""

    @staticmethod
    def get_scraper_by_url(url: str) -> Optional[BaseScraper]:
        url_lower = url.lower()
        if "wildberries.ru" in url_lower:
            return WildberriesScraper()
        # Другие скраперы будут потом
        return None

    @staticmethod
    def get_scraper_by_shop_type(shop_type: ShopType) -> Optional[BaseScraper]:
        mapping = {
            ShopType.WILDBERRIES: WildberriesScraper,
        }
        scraper_cls = mapping.get(shop_type)
        return scraper_cls() if scraper_cls else None