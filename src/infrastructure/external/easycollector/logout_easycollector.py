import asyncio

from playwright.async_api import Page

from src.shared.utils.env_load import Settings


class LogoutEasyCollectorTask:
    async def executar(self, page: Page) -> None:

        timeout_s = Settings.PLAYWRIGHT_TIMEOUT / 1000
        inicio = asyncio.get_event_loop().time()

        while True:
            for frame in page.frames:
                if "menu" in frame.url.lower():
                    try:
                        await frame.wait_for_selector("#cmdSair", timeout=1000)
                        await frame.locator("#cmdSair").click()
                        return
                    except Exception:
                        pass

            if asyncio.get_event_loop().time() - inicio > timeout_s:
                raise RuntimeError("Menu lateral nao encontrado para logout")

            await page.wait_for_timeout(500)
