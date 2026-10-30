import asyncio
from src.scrapers.factory import ScraperFactory


async def main():
    test_url = "https://www.wildberries.ru/catalog/1011171034/detail.aspx"

    scraper = ScraperFactory.get_scraper_by_url(test_url)

    res = await scraper.scrape(test_url)

    print(f"Статус:      {res.status.value}")
    print(f"Товар:       {res.raw_title}")
    print(f"Цена:        {res.price} {res.currency}")
    print(f"В наличии:   {res.is_in_stock}")


if __name__ == "__main__":
    asyncio.run(main())