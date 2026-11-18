from __future__ import annotations
import asyncio
import os
import shutil
import unicodedata
from datetime import datetime, date
from typing import Optional
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters
from src.application.services.easycollector_service import ExecutarJobUseCase
from src.domain.entities.job_easycollector import Job
from src.domain.enums.job_type_easycollector import JobType
from src.infrastructure.repositories.sql_easycollector_tarefa_repository import EasycollectorTarefaRepository
from src.shared.utils.env_load import Settings, TELEGRAM_ALLOWED_CHAT_ID


class TelegramBot:
    def __init__(self, token: str, usuario: str, senha: str) -> None:
        self._token = token
        self._usuario = usuario
        self._senha = senha
        self._allowed_chat_id = TELEGRAM_ALLOWED_CHAT_ID
        self._use_case = ExecutarJobUseCase()
        self._tarefas_repo = EasycollectorTarefaRepository()
        self._status_opcoes = {
            "aguardando": "Aguardando",
            "executando": "Executando",
            "concluido": "Concluido",
            "interrompido": "Interrompido",
        }

    def run(self) -> None:
        app = Application.builder().token(self._token).build()

        app.add_handler(CommandHandler("start", self._handle_start))
        app.add_handler(CommandHandler("consultar", self._handle_consultar))
        app.add_handler(CallbackQueryHandler(self._handle_tarefa_callback, pattern=r"^tarefa:"))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_text))

        app.run_polling(stop_signals=None)

    async def _handle_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if update.message:
            if not await self._ensure_chat_authorized(update):
                return
            await update.message.reply_text(
                "Digite a carga e opcionalmente a data no inicio da mensagem.\n"
                "Ex.: 19/02/2026 minha carga ou 2026-02-19 minha carga.\n"
                "Sem data, o bot usa a data de hoje.\n"
                "Para status, digite: Aguardando, Executando, Concluido ou Interrompido.\n"
                "Status aceita variacao de maiusculas/minusculas e acento.",
                reply_markup=ReplyKeyboardRemove()
            )

    async def _handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message:
            return
        if not await self._ensure_chat_authorized(update):
            return
        tarefa = update.message.text.strip()
        status_norm = self._normalizar_texto(tarefa)
        if status_norm in self._status_opcoes:
            status = self._status_opcoes[status_norm]
            context.user_data["status"] = status
            await update.message.reply_text(f"Status selecionado: {status}.")
            await self._executar_job(update, tarefa=None, status=status, data_ref=None)
            return

        data_ref, termo_tarefa = self._parse_data_e_termo(tarefa)
        if not termo_tarefa:
            await update.message.reply_text(
                "Informe a carga junto com a data. Ex.: 19/02/2026 nome da carga"
            )
            return

        if len(termo_tarefa) < 2:
            await update.message.reply_text("Digite ao menos 2 caracteres para buscar tarefas.")
            return

        tarefas = await asyncio.to_thread(self._tarefas_repo.buscar_por_termo, termo_tarefa, 20)
        if not tarefas:
            await update.message.reply_text("Nenhuma tarefa encontrada para esse trecho.")
            return

        tarefa_exata = self._match_exato(termo_tarefa, tarefas)
        if tarefa_exata:
            await self._executar_job(
                update,
                tarefa_exata,
                context.user_data.get("status"),
                data_ref,
            )
            return

        await self._enviar_sugestoes(update, context, termo_tarefa, tarefas, data_ref)

    async def _handle_consultar(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message:
            return
        if not await self._ensure_chat_authorized(update):
            return
        texto = " ".join(context.args).strip()
        if not texto:
            await update.message.reply_text("Uso: /consultar [data] <tarefa>")
            return

        data_ref, termo_tarefa = self._parse_data_e_termo(texto)
        if not termo_tarefa:
            await update.message.reply_text("Uso: /consultar [data] <tarefa>")
            return

        tarefas = await asyncio.to_thread(self._tarefas_repo.buscar_por_termo, termo_tarefa, 20)
        if not tarefas:
            await update.message.reply_text("Nenhuma tarefa encontrada para esse trecho.")
            return

        tarefa_exata = self._match_exato(termo_tarefa, tarefas)
        if tarefa_exata:
            await self._executar_job(
                update,
                tarefa_exata,
                context.user_data.get("status"),
                data_ref,
            )
            return

        if len(tarefas) == 1:
            await self._executar_job(
                update,
                tarefas[0],
                context.user_data.get("status"),
                data_ref,
            )
            return

        await self._enviar_sugestoes(update, context, termo_tarefa, tarefas, data_ref)

    async def _handle_tarefa_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        if not query:
            return
        if not await self._ensure_chat_authorized(update):
            return

        await query.answer()
        chave = (query.data or "").split(":", 1)[1]
        sugestoes = context.user_data.get("tarefas_sugeridas") or {}
        tarefa = sugestoes.get(chave)
        data_ref = context.user_data.get("data_ref_consulta")
        if not tarefa:
            await query.edit_message_text("Selecao expirada. Digite novamente para buscar a tarefa.")
            return

        await query.edit_message_text(f"Tarefa selecionada: {tarefa}")
        await self._executar_job(
            update,
            tarefa,
            context.user_data.get("status"),
            data_ref,
        )

    async def _executar_job(
        self,
        update: Update,
        tarefa: str | None,
        status: str | None,
        data_ref: str | None,
    ) -> None:
        message = update.message or (update.callback_query.message if update.callback_query else None)
        if not message:
            return

        await message.reply_text("Iniciando consulta...")
        data_ref_exec = data_ref or self._hoje_iso()

        job = Job(
            chat_id=update.effective_chat.id if update.effective_chat else None,
            tipo=JobType.CONSULTAR_SITE,
            parametros={
                "usuario": self._usuario,
                "senha": self._senha,
                "tarefa": tarefa,
                "status": status,
                "data_ref": data_ref_exec,
            }
        )

        try:
            resultado = await self._use_case.executar(job)
            await self._enviar_resultado(update, resultado)
        except Exception as exc:
            await message.reply_text(f"Erro ao executar: {exc}")
        finally:
            self._limpar_pasta_prints()

    async def _enviar_resultado(self, update: Update, resultado: dict) -> None:
        message = update.message or (update.callback_query.message if update.callback_query else None)
        if not message:
            return

        screenshot_path: Optional[str] = resultado.get("screenshot")
        screenshot_paths = resultado.get("screenshots") or ([] if not screenshot_path else [screenshot_path])
        tarefa = resultado.get("tarefa")
        status = resultado.get("status")
        titulo = tarefa if tarefa else f"status {status or 'selecionado'}"
        legenda = self._montar_legenda_inicial(titulo, len(screenshot_paths), resultado)
        detalhes_banco = self._montar_detalhes_banco(resultado)

        if screenshot_paths:
            with open(screenshot_paths[0], "rb") as arquivo:
                await message.reply_photo(
                    photo=arquivo,
                    caption=legenda
                )
            for indice, path in enumerate(screenshot_paths[1:], start=2):
                with open(path, "rb") as arquivo:
                    await message.reply_photo(
                        photo=arquivo,
                        caption=f"Pagina {indice}/{len(screenshot_paths)}"
                    )
            if detalhes_banco:
                await message.reply_text(detalhes_banco)
        else:
            texto = f"Consulta finalizada: {titulo}"
            if detalhes_banco:
                texto = f"{texto}\n\n{detalhes_banco}"
            await message.reply_text(texto)

    def _parse_data_e_termo(self, texto: str) -> tuple[str, str]:
        texto_limpo = texto.strip()
        if not texto_limpo:
            return self._hoje_iso(), ""

        partes = texto_limpo.split(maxsplit=1)
        primeiro = partes[0]
        resto = partes[1].strip() if len(partes) > 1 else ""

        data_ref = self._parse_data_token(primeiro)
        if data_ref:
            return data_ref, resto
        return self._hoje_iso(), texto_limpo

    def _parse_data_token(self, token: str) -> str | None:
        for formato in ("%d/%m/%Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(token, formato).strftime("%Y-%m-%d")
            except ValueError:
                continue
        return None

    def _hoje_iso(self) -> str:
        return date.today().strftime("%Y-%m-%d")

    def _normalizar_texto(self, texto: str) -> str:
        base = unicodedata.normalize("NFD", texto)
        sem_acento = "".join(ch for ch in base if unicodedata.category(ch) != "Mn")
        return sem_acento.strip().lower()

    def _limpar_pasta_prints(self) -> None:
        pasta_data = os.path.join(Settings.BASE_DIR, "data")
        if os.path.isdir(pasta_data):
            shutil.rmtree(pasta_data)

    async def _ensure_chat_authorized(self, update: Update) -> bool:
        try:
            allowed_chat_id = int(self._allowed_chat_id) if self._allowed_chat_id else None
        except ValueError:
            allowed_chat_id = None

        chat_id = update.effective_chat.id if update.effective_chat else None
        if not allowed_chat_id or chat_id != allowed_chat_id:
            if update.message:
                await update.message.reply_text("Acesso negado: chat nao autorizado.")
            elif update.callback_query:
                await update.callback_query.answer("Acesso negado: chat nao autorizado.", show_alert=True)
            return False
        return True

    def _match_exato(self, termo: str, tarefas: list[str]) -> str | None:
        termo_norm = termo.strip().lower()
        for tarefa in tarefas:
            if tarefa.strip().lower() == termo_norm:
                return tarefa
        return None

    def _montar_legenda_inicial(self, titulo: str, total_paginas: int, resultado: dict) -> str:
        resumo = resultado.get("resumo_cargas_banco") or {}
        data_ref = resumo.get("data_referencia") or resultado.get("data_ref") or "-"
        total_filtrado = int(resumo.get("total_filtrado") or 0)
        total_dia = int(resumo.get("total_dia") or 0)
        por_status = resumo.get("por_status") or {}

        linhas = [f"Consulta finalizada: {titulo} (pagina 1/{max(total_paginas, 1)})"]
        linhas.append(f"Banco {data_ref}: {total_filtrado} registro(s) filtrado(s) de {total_dia} no dia.")

        if por_status:
            resumo_status = ", ".join(f"{status}: {qtd}" for status, qtd in por_status.items())
            linhas.append(resumo_status)

        legenda = "\n".join(linhas)
        return legenda[:1024]

    def _montar_detalhes_banco(self, resultado: dict) -> str:
        resumo = resultado.get("resumo_cargas_banco") or {}
        cargas = resultado.get("cargas_banco") or []
        if not resumo and not cargas:
            return ""

        linhas = ["Status no banco:"]
        data_ref = resumo.get("data_referencia")
        status_banco = resumo.get("status_banco")
        if data_ref:
            linhas.append(f"Data: {data_ref}")
        if status_banco:
            linhas.append(f"Status equivalente no banco: {status_banco}")

        total_filtrado = int(resumo.get("total_filtrado") or 0)
        total_dia = int(resumo.get("total_dia") or 0)
        linhas.append(f"Encontrados: {total_filtrado} de {total_dia} registro(s) do dia.")

        if not cargas:
            linhas.append("Nenhum registro correspondente encontrado na TB_CARGA.")
            return "\n".join(linhas)

        for indice, carga in enumerate(cargas[:10], start=1):
            origem = carga.get("origem") or "-"
            status = carga.get("status") or "-"
            remessa = carga.get("remessa") or "-"
            inicio = carga.get("inicio") or "-"
            fim = carga.get("fim") or "-"
            arquivo = carga.get("arquivo") or "-"
            linhas.append(
                f"{indice}. {origem} | {status} | remessa {remessa} | inicio {inicio} | fim {fim} | arquivo {arquivo}"
            )

        restantes = total_filtrado - min(len(cargas), 10)
        if restantes > 0:
            linhas.append(f"... e mais {restantes} registro(s).")

        texto = "\n".join(linhas)
        return texto[:4096]

    async def _enviar_sugestoes(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        termo: str,
        tarefas: list[str],
        data_ref: str,
    ) -> None:
        if not update.message:
            return

        opcoes = {str(i): tarefa for i, tarefa in enumerate(tarefas, start=1)}
        context.user_data["tarefas_sugeridas"] = opcoes
        context.user_data["data_ref_consulta"] = data_ref

        teclado = InlineKeyboardMarkup([
            [InlineKeyboardButton(tarefa, callback_data=f"tarefa:{chave}")]
            for chave, tarefa in opcoes.items()
        ])
        await update.message.reply_text(
            f"Encontrei {len(tarefas)} tarefa(s) para '{termo}'. Selecione uma:",
            reply_markup=teclado
        )
