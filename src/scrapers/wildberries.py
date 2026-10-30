import re
import logging
import asyncio
from decimal import Decimal
from typing import Optional
from playwright.async_api import async_playwright, Browser
from playwright_stealth import Stealth
from src.scrapers.base import BaseScraper, ScrapedData, ScrapeStatus

logger = logging.getLogger("WildberriesScraper")

NOT_FOUND_MARKERS = ("что-то не так", "не найден", "не существует", "ничего не нашлось", "404")
CAPTCHA_MARKERS = ("проверка безопасности", "подтвердите, что вы не робот", "smartcaptcha", "turnstile")


class WildberriesScraper(BaseScraper):
    def __init__(self, browser: Optional[Browser] = None, block_api: bool = False):
        """
        :param browser:   Переиспользуемый инстанс браузера. Если не передан, 
                          создается локально на время запроса.
        :param block_api: Тестовый флаг: Python-перехватчик игнорирует сетевой API, 
                          вынуждая скрапер парсить данные из разметки DOM.
        """
        self._external_browser = browser
        self._block_api = block_api

    def extract_item_id(self, url: str) -> str:
        match = re.search(r"catalog/(\d+)", url)
        if not match:
            raise ValueError(f"Не удалось извлечь артикул WB из URL: {url}")
        return match.group(1)

    async def scrape(self, url: str) -> ScrapedData:
        try:
            self.extract_item_id(url)
        except ValueError as e:
            logger.error(str(e))
            return ScrapedData(status=ScrapeStatus.PARSING_ERROR)

        if self._external_browser:
            return await self._scrape_with_browser(self._external_browser, url)

        try:
            async with Stealth().use_async(async_playwright()) as p:
                browser = await p.chromium.launch(
                    headless=True,
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-infobars",
                    ]
                )
                try:
                    return await self._scrape_with_browser(browser, url)
                finally:
                    await browser.close()
        except Exception as exc:
            logger.error(f"Ошибка жизненного цикла Playwright при парсинге {url}: {exc}")
            return ScrapedData(status=ScrapeStatus.PARSING_ERROR)

    async def _scrape_with_browser(self, browser: Browser, url: str) -> ScrapedData:
        price: Optional[Decimal] = None
        title: Optional[str] = None
        has_stock: bool = False
        is_not_found: bool = False
        is_blocked: bool = False
        source: Optional[str] = None

        data_resolved_event = asyncio.Event()

        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            locale="ru-RU",
            viewport={"width": 1920, "height": 1080}
        )
        page = await context.new_page()

        try:
            async def handle_response(response):
                nonlocal price, title, has_stock, is_not_found, is_blocked, source


                if self._block_api:
                    return

                if "/cards/v4/detail" in response.url or "/cards/v2/detail" in response.url:
                    if response.status == 403:
                        logger.warning(f"WB API отклонил доступ (403): {response.url}")
                        is_blocked = True
                        data_resolved_event.set()
                        return

                    if response.status == 404:
                        is_not_found = True
                        data_resolved_event.set()
                        return

                    try:
                        data = await response.json()
                        products = data.get("products") or data.get("data", {}).get("products", [])
                        if not products and response.status == 200:
                            is_not_found = True
                            data_resolved_event.set()
                            return

                        if products:
                            prod = products[0]
                            brand = prod.get("brand", "")
                            name = prod.get("name", "")
                            title = f"{brand} {name}".strip() if brand else name

                            total_qty = prod.get("totalQuantity", 0)
                            sizes = prod.get("sizes", [])
                            for s in sizes:
                                p_info = s.get("price")
                                if p_info:
                                    raw = p_info.get("total") or p_info.get("product") or p_info.get("basic")
                                    if raw:
                                        price = Decimal(str(raw)) / Decimal(100)
                                        has_stock = total_qty > 0 or len(s.get("stocks", [])) > 0
                                        break
                            source = "API"
                            logger.info(f"Данные получены через API для {url}")
                            data_resolved_event.set()
                    except Exception:
                        pass

            page.on("response", handle_response)

            nav_resp = await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            if nav_resp and nav_resp.status == 403:
                return ScrapedData(status=ScrapeStatus.CAPTCHA_OR_BLOCKED)


            if not self._block_api:
                try:
                    await asyncio.wait_for(data_resolved_event.wait(), timeout=8.0)
                except asyncio.TimeoutError:
                    pass


            if any(m in page.url.lower() for m in ("geo.captcha-delivery", "challenge")):
                return ScrapedData(status=ScrapeStatus.CAPTCHA_OR_BLOCKED)

            body_text = (await page.inner_text("body")).lower()
            if any(ph in body_text for ph in CAPTCHA_MARKERS):
                return ScrapedData(status=ScrapeStatus.CAPTCHA_OR_BLOCKED)


            error_el = await page.query_selector("h1, .page404, .content404, .error-page")
            if error_el:
                err_text = (await error_el.inner_text()).lower().strip()
                if any(ph in err_text for ph in NOT_FOUND_MARKERS):
                    is_not_found = True


            if not is_not_found and not title:
                page_title = await page.title()
                if not any(ph in page_title.lower() for ph in NOT_FOUND_MARKERS):
                    for sel in ("h1.product-page__title", "h1", "meta[property='og:title']"):
                        if sel.startswith("meta"):
                            val = await page.get_attribute(sel, "content")
                        else:
                            el = await page.query_selector(sel)
                            val = (await el.inner_text()).strip() if el else None

                        if val and not any(ph in val.lower() for ph in NOT_FOUND_MARKERS):
                            title = val.replace("Wildberries", "").strip()
                            break

            if not is_not_found and not price:
                try:
                    await page.wait_for_selector(
                        "[class*='priceBlockFinalPrice'], [class*='priceBlockWalletPrice'], [class*='productPrice']",
                        timeout=8000
                    )
                except Exception:
                    pass

            if not is_not_found and not price:
                selectors = [
                    "[class*='priceBlockWalletPrice']",
                    "[class*='priceBlockFinalPrice']",
                    "[class*='productPrice']",
                ]
                for sel in selectors:
                    p_el = await page.query_selector(sel)
                    if p_el:
                        raw_text = await p_el.inner_text()
                        cleaned = re.sub(r"[^\d]", "", raw_text)
                        if cleaned and int(cleaned) > 0:
                            price = Decimal(cleaned)
                            has_stock = True
                            source = "DOM"
                            logger.info(f"Данные получены через DOM для {url}")
                            break

        except Exception as exc:
            logger.error(f"Ошибка Playwright при парсинге {url}: {exc}")
            return ScrapedData(status=ScrapeStatus.PARSING_ERROR)
        finally:
            await context.close()

        if is_blocked:
            return ScrapedData(status=ScrapeStatus.CAPTCHA_OR_BLOCKED)
        if is_not_found or (not price and not title):
            return ScrapedData(status=ScrapeStatus.NOT_FOUND)
        if not price:
            return ScrapedData(raw_title=title, is_in_stock=False, status=ScrapeStatus.OUT_OF_STOCK, source=source)

        return ScrapedData(
            price=price,
            is_in_stock=has_stock,
            raw_title=title,
            status=ScrapeStatus.SUCCESS,
            source=source
        )