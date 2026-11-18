import asyncio
from playwright.async_api import Page, Frame
from src.shared.utils.env_load import Settings


class LerExecucoesTask:

    async def executar(
        self,
        page: Page,
        tarefa: str | None,
        status: str | None = None,
        data_ref: str | None = None,
    ):

        frame = await self._aguardar_frame_execucoes(page)

        if data_ref:
            await self._aplicar_data(frame, data_ref)

        if tarefa:
            await frame.locator("span.select2-selection--single").click()

            search = frame.locator("input.select2-search__field")
            try:
                await search.wait_for(timeout=5000)
            except Exception:
                search = page.locator("input.select2-search__field")
                await search.wait_for(timeout=Settings.PLAYWRIGHT_TIMEOUT)

            await search.fill(tarefa)
            await search.press("Enter")

        if status:
            await frame.locator("#dropDownStatus").select_option(value=status)

        await self._atualizar_execucoes(frame)

        try:
            await frame.wait_for_selector(
                "#divVdrBlqAc",
                state="hidden",
                timeout=Settings.PLAYWRIGHT_TIMEOUT
            )
        except Exception:
            pass

        await frame.wait_for_selector(
            "#gridExecucoes tr:nth-child(2)",
            timeout=Settings.PLAYWRIGHT_TIMEOUT
        )

        if status:
            mapa = {
                "0": "Aguardando",
                "1": "Executando",
                "2": "Concluido",
                "3": "Interrompido"
            }
            texto = mapa.get(status)
            if texto:
                await frame.wait_for_selector(
                    f"#gridExecucoes tr:has-text('{texto}')",
                    timeout=Settings.PLAYWRIGHT_TIMEOUT
                )

    async def _aplicar_data(self, frame: Frame, data_ref: str) -> None:
        await frame.wait_for_selector("#txtDe", timeout=Settings.PLAYWRIGHT_TIMEOUT)
        await frame.wait_for_selector("#txtAte", timeout=Settings.PLAYWRIGHT_TIMEOUT)

        await frame.locator("#txtDe").fill(data_ref)
        await frame.locator("#txtAte").fill(data_ref)

        await frame.locator("#txtDe").dispatch_event("change")
        await frame.locator("#txtAte").dispatch_event("change")

        await self._clicar_duas_setas_refresh(frame)

    async def _atualizar_execucoes(self, frame: Frame) -> None:
        await frame.wait_for_selector("#cmdRefresh", timeout=Settings.PLAYWRIGHT_TIMEOUT)
        await frame.locator("#cmdRefresh").click()

    async def _clicar_duas_setas_refresh(self, frame: Frame) -> None:
        await frame.wait_for_selector("#cmdRefresh", timeout=Settings.PLAYWRIGHT_TIMEOUT)
        refresh = frame.locator("#cmdRefresh").first
        await refresh.click()
        await frame.wait_for_timeout(250)
        await refresh.click()

    async def _aguardar_frame_execucoes(self, page: Page) -> Frame:

        timeout_s = Settings.PLAYWRIGHT_TIMEOUT / 1000
        inicio = asyncio.get_event_loop().time()

        while True:
            for frame in page.frames:
                if frame.name == "iframePagina" or "execucoes.aspx" in frame.url.lower():
                    try:
                        await frame.wait_for_selector(
                            "#dropDownTarefa",
                            timeout=1000
                        )
                        return frame
                    except Exception:
                        pass

            if asyncio.get_event_loop().time() - inicio > timeout_s:
                raise RuntimeError("Tela Execucoes nao carregou dentro do iframe")

            await page.wait_for_timeout(500)
