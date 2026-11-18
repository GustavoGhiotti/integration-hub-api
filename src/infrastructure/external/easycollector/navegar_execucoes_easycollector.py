import asyncio
from playwright.async_api import Page
from src.shared.utils.env_load import Settings


class NavegarExecucoesEasyCollectorTask:

    async def executar(self, page: Page) -> None:

        menu_frame = self._obter_frame_menu(page)

        await menu_frame.wait_for_selector(
            "#imgApoio",
            timeout=Settings.PLAYWRIGHT_TIMEOUT
        )
        await menu_frame.locator("#imgApoio").click()

        tree_frame = await menu_frame.wait_for_selector(
            "iframe#iframeTreeView",
            timeout=Settings.PLAYWRIGHT_TIMEOUT
        )
        tree = await tree_frame.content_frame()
        if not tree:
            raise RuntimeError("iframeTreeView nao carregou")

        await tree.wait_for_selector(
            "#treeViewMenut2",
            timeout=Settings.PLAYWRIGHT_TIMEOUT
        )
        await tree.locator("#treeViewMenut2").click()

        iframe = await self._aguardar_iframe_execucoes(page)

        await iframe.wait_for_selector(
            "table",
            timeout=Settings.PLAYWRIGHT_TIMEOUT
        )


    async def _aguardar_iframe_execucoes(self, page: Page):

        timeout = Settings.PLAYWRIGHT_TIMEOUT / 1000
        inicio = asyncio.get_event_loop().time()

        while True:
            for frame in page.frames:
                if "execucoes.aspx" in frame.url.lower():
                    return frame

            if asyncio.get_event_loop().time() - inicio > timeout:
                raise RuntimeError("iframe de Execucoes nao carregou")

            await asyncio.sleep(0.3)


    def _obter_frame_menu(self, page: Page):
        for frame in page.frames:
            if "menu" in frame.url.lower():
                return frame

        raise RuntimeError("Menu lateral nao encontrado para abrir Execucoes")
