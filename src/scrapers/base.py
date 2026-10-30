from abc import ABC, abstractmethod
from decimal import Decimal
from enum import Enum
from typing import Optional, Literal
from pydantic import BaseModel, Field


class ScrapeStatus(str, Enum):
    SUCCESS = "SUCCESS"
    OUT_OF_STOCK = "OUT_OF_STOCK"
    NOT_FOUND = "NOT_FOUND"
    CAPTCHA_OR_BLOCKED = "CAPTCHA_OR_BLOCKED"
    PARSING_ERROR = "PARSING_ERROR"


class ScrapedData(BaseModel):
    price: Optional[Decimal] = Field(None, description="Цена за единицу товара в рублях")
    is_in_stock: bool = Field(False, description="Наличие товара")
    raw_title: Optional[str] = Field(None, description="Заголовок/название на площадке")
    currency: str = "RUB"
    status: ScrapeStatus
    source: Optional[Literal["API", "DOM"]] = Field(None, description="Способ получения данных")


class BaseScraper(ABC):
    """Базовый интерфейс парсера торговой площадки."""

    @abstractmethod
    def extract_item_id(self, url: str) -> str:
        """Извлечение артикула товара из URL."""
        pass

    @abstractmethod
    async def scrape(self, url: str) -> ScrapedData:
        """Извлечение актуальных данных о товаре."""
        pass