import asyncio
import os
from datetime import datetime
import re

from playwright.async_api import Page, Frame

from src.shared.utils.env_load import Settings


class ScreenshotExecucoesTask:

    async def executar(self, page: Page, job_id: str) -> list[str]:

        frame = await self._aguardar_frame_execucoes(page)

        await frame.wait_for_selector(
            "#gridExecucoes",
            timeout=Settings.PLAYWRIGHT_TIMEOUT
        )

        os.makedirs(Settings.SCREENSHOT_DIR, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        screenshots: list[str] = []
        total_paginas = await self._obter_paginas(frame)

        for pagina in total_paginas:
            if pagina > 1:
                await self._ir_para_pagina(frame, pagina)

            filename = f"execucoes_{job_id}_{timestamp}_p{pagina}.png"
            filepath = os.path.join(Settings.SCREENSHOT_DIR, filename)
            await self._tirar_screenshot_grid(frame, filepath)
            screenshots.append(filepath)

        return screenshots

    async def _tirar_screenshot_grid(self, frame: Frame, filepath: str) -> None:
        for tentativa in range(4):
            grid = frame.locator("#gridExecucoes").first
            try:
                await grid.wait_for(
                    state="visible",
                    timeout=Settings.PLAYWRIGHT_TIMEOUT
                )
                await grid.scroll_into_view_if_needed()
                await grid.screenshot(path=filepath)
                return
            except Exception as exc:
                if "not attached to the DOM" in str(exc) and tentativa < 3:
                    await frame.wait_for_timeout(500)
                    continue
                raise

    async def _obter_paginas(self, frame: Frame) -> list[int]:
        paginas = {1}
        rodape = frame.locator("tr.gridExecucoesRodape").first

        spans = rodape.locator("span")
        qtd_spans = await spans.count()
        for i in range(qtd_spans):
            try:
                texto = (await spans.nth(i).inner_text()).strip()
            except Exception:
                continue
            if re.fullmatch(r"\d+", texto):
                paginas.add(int(texto))

        links = rodape.locator("a")
        qtd_links = await links.count()
        for i in range(qtd_links):
            try:
                href = (await links.nth(i).get_attribute("href") or "").strip()
                match = re.search(r"Page\$(\d+)", href)
                if match:
                    paginas.add(int(match.group(1)))
                    continue
            except Exception:
                pass

            try:
                texto = (await links.nth(i).inner_text()).strip()
            except Exception:
                continue
            if re.fullmatch(r"\d+", texto):
                paginas.add(int(texto))

        return sorted(paginas)

    async def _ir_para_pagina(self, frame: Frame, pagina: int) -> None:
        clicou = await frame.evaluate(
            """(pagina) => {
                const grid = document.querySelector("#gridExecucoes");
                if (!grid) return false;
                const links = Array.from(grid.querySelectorAll("a"));
                const alvo = links.find((a) => (a.textContent || "").trim() === String(pagina));
                if (!alvo) return false;
                alvo.click();
                return true;
            }""",
            pagina,
        )
        if not clicou:
            raise RuntimeError(f"Nao foi possivel abrir a pagina {pagina} da grade")

        try:
            await frame.wait_for_selector(
                "#divVdrBlqAc",
                state="hidden",
                timeout=Settings.PLAYWRIGHT_TIMEOUT,
            )
        except Exception:
            pass

        await frame.wait_for_selector(
            "#gridExecucoes tr:nth-child(2)",
            timeout=Settings.PLAYWRIGHT_TIMEOUT,
        )
        await frame.wait_for_timeout(300)

    async def _aguardar_frame_execucoes(self, page: Page) -> Frame:
        timeout_s = Settings.PLAYWRIGHT_TIMEOUT / 1000
        inicio = asyncio.get_event_loop().time()

        while True:
            for frame in page.frames:
                try:
                    if frame.name == "iframePagina" or "execucoes.aspx" in frame.url.lower():
                        return frame
                    if await frame.locator("#gridExecucoes").count() > 0:
                        return frame
                except Exception:
                    pass

            if asyncio.get_event_loop().time() - inicio > timeout_s:
                raise RuntimeError("iframe de Execucoes nao encontrado para screenshot")

            await page.wait_for_timeout(500)
