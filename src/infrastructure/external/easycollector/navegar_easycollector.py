from playwright.async_api import Page


class NavegarEasyCollectorTask:

    async def executar(self, page: Page) -> None:

        await page.wait_for_timeout(1500)

        self._obter_frame_menu(page)

    def _obter_frame_menu(self, page: Page):
        for frame in page.frames:
            if "menu" in frame.url.lower():
                return frame

        raise RuntimeError("Nao foi possivel fazer login no EasyCollector")
