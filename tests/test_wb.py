import pytest
from decimal import Decimal
from os import getenv
from src.scrapers.wildberries import WildberriesScraper
from src.scrapers.base import ScrapedData, ScrapeStatus
from src.scrapers.factory import ScraperFactory


# pytestmark = pytest.mark.skipif(
#     getenv("RUN_LIVE_TESTS") != "1",
#     reason="Для тестов с парсингом в реальном времени требуется резидентный IP-адрес, поэтому они не выполняются в рамках стандартного CI"
# )

@pytest.fixture(scope="module")
def scraper():
    """Единая фабричная фикстура скрапера для тестового модуля"""
    return ScraperFactory.get_scraper_by_url("https://www.wildberries.ru/catalog/1/detail.aspx")


class TestWildberriesUrlParsing:
    """Модульные тесты извлечения артикулов из ссылок различных форматов."""

    @pytest.mark.parametrize(
        "url, expected_id",
        [
            ("https://www.wildberries.ru/catalog/1011171034/detail.aspx", "1011171034"),
            ("https://wildberries.ru/catalog/1011171034/detail.aspx", "1011171034"),
            ("https://www.wildberries.ru/catalog/1011171034/", "1011171034"),
            ("https://wildberries.ru/catalog/1011171034", "1011171034"),
            ("https://www.wildberries.ru/catalog/1011171034/detail.aspx?targetUrl=GP", "1011171034"),
        ]
    )
    def test_extract_item_id_valid_formats(self, scraper, url: str, expected_id: str):
        # Act
        extracted = scraper.extract_item_id(url)

        # Assert
        assert extracted == expected_id

    @pytest.mark.parametrize(
        "invalid_url",
        [
            "https://www.wildberries.ru/catalog/abc/detail.aspx",
            "https://www.wildberries.ru/promotions/sale",
            "https://www.dns-shop.ru/product/12345678/",
            "not_a_valid_url"
        ]
    )
    def test_extract_item_id_invalid_formats_raise_value_error(self, scraper, invalid_url: str):
        # Act & Assert
        with pytest.raises(ValueError):
            scraper.extract_item_id(invalid_url)


class TestWildberriesLiveScraping:
    """
    Интеграционные тесты с реальным сетевым взаимодействием через Playwright.
    Проверяют поведение на различных категориях товаров и граничных состояниях.
    """

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "test_name, url",
        [
            ("Процессор AMD Ryzen", "https://www.wildberries.ru/catalog/1011171034/detail.aspx"),
            ("Оперативная память DDR4", "https://www.wildberries.ru/catalog/813575618/detail.aspx"),
        ]
    )
    async def test_scrape_valid_in_stock_hardware(self, scraper, test_name: str, url: str):
        """Проверка успешного сбора реальных комплектующих ПК в наличии."""
        # Act
        result: ScrapedData = await scraper.scrape(url)

        # Assert
        assert result.status == ScrapeStatus.SUCCESS
        assert result.is_in_stock is True
        assert result.price is not None
        assert isinstance(result.price, Decimal)
        assert result.price > Decimal("0.00")
        assert result.currency == "RUB"
        assert result.raw_title is not None
        assert len(result.raw_title.strip()) > 3
        assert result.raw_title != "Что-то не так..."

    @pytest.mark.asyncio
    async def test_scrape_non_existent_item_returns_not_found(self, scraper):
        """Проверка обработки 404 / отсутствующего артикула (заглушка 'Что-то не так...')."""
        # Arrange
        invalid_item_url = "https://www.wildberries.ru/catalog/99999999999999/detail.aspx"

        # Act
        result: ScrapedData = await scraper.scrape(invalid_item_url)

        # Assert
        assert result.status == ScrapeStatus.NOT_FOUND
        assert result.is_in_stock is False
        assert result.price is None

    @pytest.mark.asyncio
    async def test_scrape_corrupted_url_returns_parsing_error(self, scraper):
        """Проверка реакции на некорректный URL без падения скрипта."""
        # Arrange
        corrupted_url = "https://www.wildberries.ru/invalid-path/no-catalog"

        # Act
        result: ScrapedData = await scraper.scrape(corrupted_url)

        # Assert
        assert result.status == ScrapeStatus.PARSING_ERROR
        assert result.is_in_stock is False
        assert result.price is None

    @pytest.mark.asyncio
    async def test_scrape_via_network_api(self):
        """Проверка перехвата чистого JSON из API витрины."""
        url = "https://www.wildberries.ru/catalog/1011171034/detail.aspx"
        scraper = WildberriesScraper(block_api=False)
        
        result = await scraper.scrape(url)
        
        assert result.status == ScrapeStatus.SUCCESS
        assert result.source == "API"
        assert result.price is not None
        assert result.price > Decimal("0")

    @pytest.mark.asyncio
    async def test_scrape_dom_fallback_when_api_fails(self):
        """Проверка срабатывания DOM-fallback при недоступности API."""
        url = "https://www.wildberries.ru/catalog/1011171034/detail.aspx"

        scraper = WildberriesScraper(block_api=True)
        
        result = await scraper.scrape(url)
        
        assert result.status == ScrapeStatus.SUCCESS
        assert result.source == "DOM", "Парсер должен был переключиться на DOM-селекторы."
        assert result.price is not None
        assert result.price > Decimal("0")
        assert result.raw_title is not None