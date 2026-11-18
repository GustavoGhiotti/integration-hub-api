from playwright.async_api import Page, TimeoutError
from src.shared.utils.env_load import Settings


class LoginEasyCollectorTask:

    async def executar(self, page: Page, parametros: dict) -> None:

        usuario = parametros.get("usuario")
        senha = parametros.get("senha")

        if not usuario or not senha:
            raise ValueError("Usuario e senha sao obrigatorios para login")

        await page.goto(
            Settings.EASYCOLLECTOR_LOGIN_URL,
            wait_until="domcontentloaded",
            timeout=Settings.PLAYWRIGHT_TIMEOUT
        )

        await page.wait_for_selector(
            "input[type='text'], input[name*='user'], input[id*='user']",
            timeout=Settings.PLAYWRIGHT_TIMEOUT
        )

        await page.fill(
            "input[type='text'], input[name*='user'], input[id*='user']",
            usuario
        )

        await page.fill(
            "input[type='password']",
            senha
        )

        try:
            async with page.expect_navigation(timeout=Settings.PLAYWRIGHT_TIMEOUT):
                await page.click("button:has-text('Entrar'), input[value='Entrar']")
        except TimeoutError:
            await page.wait_for_timeout(500)
