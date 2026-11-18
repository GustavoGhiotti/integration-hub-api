from src.shared.utils.env_load import Settings

class ConsultarSiteTask:

    async def executar(self, page, parametros: dict) -> dict:

        await page.goto(Settings.SITE_URL, timeout=Settings.PLAYWRIGHT_TIMEOUT)

        if "cpf" in parametros:
            await page.fill("#cpf", parametros["cpf"])
            await page.click("#btnConsultar")

        await page.wait_for_selector("#resultado", timeout=Settings.PLAYWRIGHT_TIMEOUT)

        nome = await page.inner_text("#nome")
        status = await page.inner_text("#status")

        return {
            "nome": nome,
            "status": status
        }
