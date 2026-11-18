import asyncio
import unicodedata

from src.infrastructure.external.easycollector.browser_factory import BrowserFactory
from src.infrastructure.external.easycollector.login_easycollector import LoginEasyCollectorTask
from src.infrastructure.external.easycollector.navegar_easycollector import NavegarEasyCollectorTask
from src.infrastructure.external.easycollector.navegar_execucoes_easycollector import NavegarExecucoesEasyCollectorTask
from src.infrastructure.external.easycollector.ler_execucao import LerExecucoesTask
from src.infrastructure.external.easycollector.screenshot_execucoes import ScreenshotExecucoesTask
from src.infrastructure.external.easycollector.logout_easycollector import LogoutEasyCollectorTask
from src.infrastructure.repositories.sql_easycollector_carga_repository import EasycollectorCargaRepository
from src.domain.entities.job_easycollector import Job


class ExecutarJobUseCase:
    def __init__(self) -> None:
        self._cargas_repo = EasycollectorCargaRepository()

    async def executar(self, job: Job) -> dict:

        job.iniciar()

        tarefa = job.parametros.get("tarefa")
        status = job.parametros.get("status")
        data_ref = job.parametros.get("data_ref")
        if not tarefa and not status:
            raise RuntimeError(
                "Job invalido: informe 'tarefa' ou 'status'"
            )

        playwright, browser, context, page = await BrowserFactory.create()

        try:
            await LoginEasyCollectorTask().executar(page, job.parametros)

            await NavegarEasyCollectorTask().executar(page)

            await NavegarExecucoesEasyCollectorTask().executar(page)

            await LerExecucoesTask().executar(
                page,
                tarefa=tarefa,
                status=status,
                data_ref=data_ref,
            )

            screenshot_paths = await ScreenshotExecucoesTask().executar(
                page,
                job_id=job.id
            )
            cargas_banco = await asyncio.to_thread(
                self._consultar_cargas_banco,
                data_ref,
                tarefa,
                status,
            )

            job.finalizar(resultado=screenshot_paths)

            return {
                "job_id": job.id,
                "tarefa": tarefa,
                "status": status,
                "data_ref": data_ref,
                "screenshot": screenshot_paths[0] if screenshot_paths else None,
                "screenshots": screenshot_paths,
                "cargas_banco": cargas_banco["items"],
                "resumo_cargas_banco": cargas_banco["resumo"],
            }

        except Exception as e:
            job.falhar(str(e))
            raise

        finally:
            try:
                await LogoutEasyCollectorTask().executar(page)
            except Exception as e:
                print("[JOB] Falha ao deslogar:", e)
            await context.close()
            await browser.close()
            await playwright.stop()

    def _consultar_cargas_banco(
        self,
        data_ref: str | None,
        tarefa: str | None,
        status: str | None,
    ) -> dict:
        if not data_ref:
            return {"items": [], "resumo": {"data_referencia": None, "total_dia": 0, "total_filtrado": 0, "por_status": {}}}

        registros = self._cargas_repo.listar_por_data(data_ref)
        tarefa_norm = self._normalizar_texto(tarefa)
        status_banco = self._mapear_status_banco(status)

        filtrados = registros
        if tarefa_norm:
            filtrados = [item for item in filtrados if tarefa_norm in self._normalizar_texto(item.get("origem"))]
        if status_banco:
            filtrados = [item for item in filtrados if str(item.get("status") or "").upper() == status_banco]

        por_status: dict[str, int] = {}
        for item in filtrados:
            chave = str(item.get("status") or "").upper()
            por_status[chave] = por_status.get(chave, 0) + 1

        return {
            "items": filtrados[:20],
            "resumo": {
                "data_referencia": data_ref,
                "total_dia": len(registros),
                "total_filtrado": len(filtrados),
                "por_status": por_status,
                "status_banco": status_banco,
            },
        }

    def _mapear_status_banco(self, status: str | None) -> str | None:
        status_norm = self._normalizar_texto(status)
        if not status_norm:
            return None

        mapa = {
            "aguardando": "AGUARDANDO",
            "executando": "EM ANDAMENTO",
            "em andamento": "EM ANDAMENTO",
            "concluido": "PROCESSADO",
            "processado": "PROCESSADO",
            "interrompido": "ERRO",
            "erro": "ERRO",
            "nada": "NADA",
        }
        return mapa.get(status_norm)

    def _normalizar_texto(self, texto: str | None) -> str:
        if not texto:
            return ""
        base = unicodedata.normalize("NFD", str(texto))
        sem_acento = "".join(ch for ch in base if unicodedata.category(ch) != "Mn")
        return sem_acento.strip().lower()
