from playwright.async_api import async_playwright
from src.shared.utils.env_load import Settings


class BrowserFactory:

    @staticmethod
    async def create():

        playwright = await async_playwright().start()

        browser = await playwright.chromium.launch(
            headless=Settings.PLAYWRIGHT_HEADLESS,
            slow_mo=0
        )

        context = await browser.new_context()
        page = await context.new_page()

        return playwright, browser, context, page
