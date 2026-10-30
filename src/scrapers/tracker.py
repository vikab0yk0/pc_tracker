import asyncio
import logging
from typing import Optional, Tuple
from sqlalchemy.orm import Session

from src import crud
from src.models import StoreVariant
from src.scrapers.base import ScrapedData, ScrapeStatus
from src.scrapers.factory import ScraperFactory


logger = logging.getLogger(__name__)


class PriceTrackerService:
    def __init__(self, db: Session, concurrency_limit: int = 3):
        """
        :param db: Сессия SQLAlchemy (используется строго синхронно в главном потоке)
        :param concurrency_limit: Ограничение параллельных вкладок скрапера
        """
        self.db = db
        self.semaphore = asyncio.Semaphore(concurrency_limit)

    async def _fetch_variant_data(self, variant: StoreVariant) -> Tuple[StoreVariant, Optional[ScrapedData]]:
        """Изолированный конкурентный сетевой сбор без обращения к сессии БД."""
        async with self.semaphore:
            scraper = ScraperFactory.get_scraper_by_shop_type(variant.shop_type)
            if not scraper:
                logger.warning(f"Парсер для {variant.shop_type} не найден.")
                return variant, None

            data = await scraper.scrape(variant.url)
            return variant, data

    def _apply_variant_update(self, variant: StoreVariant, scraped: ScrapedData) -> bool:
        """Синхронное сохранение результатов в БД (потокобезопасно)."""
        if scraped.status == ScrapeStatus.CAPTCHA_OR_BLOCKED:
            logger.warning(f"Парсер заблокирован при проверке {variant.id} ({variant.url})")
            return False

        if scraped.status == ScrapeStatus.NOT_FOUND:
            logger.info(f"Товар {variant.id} удален с площадки.")
            crud.update_variant_price(
                db=self.db, variant_id=variant.id, new_price=variant.current_price, in_stock=False
            )
            return False

        if scraped.status == ScrapeStatus.OUT_OF_STOCK or not scraped.is_in_stock:
            logger.info(f"Товар {variant.id} закончился на складе.")
            crud.update_variant_price(
                db=self.db, variant_id=variant.id, new_price=variant.current_price, in_stock=False
            )
            return False

        if scraped.status == ScrapeStatus.SUCCESS and scraped.price is not None:
            old_price = variant.current_price
            price_dropped = (old_price is not None) and (scraped.price < old_price)
            
            crud.update_variant_price(
                db=self.db, variant_id=variant.id, new_price=scraped.price, in_stock=True
            )
            return price_dropped

        return False

    async def run_tracker_cycle(self) -> dict:
        variants = crud.get_active_tracked_variants(self.db)
        if not variants:
            logger.info("Нет активных позиций для трекинга.")
            return {"checked": 0, "price_drops": 0}

        logger.info(f"Запуск трекинга для {len(variants)} позиций...")

        tasks = [self._fetch_variant_data(variant) for variant in variants]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        price_drops_count = 0
        success_checked = 0

        for res in results:
            if isinstance(res, Exception):
                logger.error(f"Необработанная ошибка задачи трекинга: {res}")
                continue

            variant, scraped_data = res
            if scraped_data is not None:
                success_checked += 1
                if self._apply_variant_update(variant, scraped_data):
                    price_drops_count += 1

        logger.info(
            f"Цикл завершен. Успешно проверено: {success_checked}/{len(variants)}, Снижений цен: {price_drops_count}"
        )
        return {"checked": success_checked, "price_drops": price_drops_count}