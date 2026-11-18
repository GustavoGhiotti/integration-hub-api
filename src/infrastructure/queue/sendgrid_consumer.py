import os
import time
import logging
import threading

from src.application.services.sendgrid_service import SendGridService
from src.infrastructure.repositories.sql_email_event_repository import SqlEmailEventRepository

log = logging.getLogger("sendgrid_consumer")


class SendGridConsumer:
    """Processamento em background dos eventos do SendGrid, em DUAS etapas
    desacopladas (roda tudo no processo dedicado run_consumer.py):

      1. CONSUMIDORES (N threads): reivindicam lotes da RAW, fazem o parse e
         GRAVAM SÓ O DETALHE na MONITOR_SENDGRID_EVENTOS (append-only). Como não
         fazem o MERGE, vários rodam em paralelo praticamente sem contenção.

      2. AGREGADOR (1 thread): recalcula o resumo (MONITOR_SENDGRID) a partir dos
         eventos ainda não agregados. Sozinho -> sem MERGE concorrente, sem
         deadlock. É aqui que a parte pesada fica isolada.

    O buffer durável é a própria RAW; o "buffer" da agregação é a coluna AGREGADO
    da tabela de eventos. Nada fica em memória."""

    def __init__(
        self,
        repo=None,
        service=None,
        tamanho_lote: int = 300,
        num_consumidores: int = 3,
        agregador_lote: int = 2000,
        intervalo_ocioso: float = 2.0,
        retencao_dias: int = 30,
        intervalo_limpeza_seg: int = 3600,
    ):
        self.repo = repo or SqlEmailEventRepository()
        self.service = service or SendGridService()
        self.tamanho_lote = tamanho_lote
        self.num_consumidores = max(1, num_consumidores)
        self.agregador_lote = agregador_lote
        self.intervalo_ocioso = intervalo_ocioso
        self.retencao_dias = retencao_dias
        self.intervalo_limpeza_seg = intervalo_limpeza_seg

        self._parar = threading.Event()
        self._threads = []
        self._ultima_limpeza = 0.0
        self._limpeza_lock = threading.Lock()

    # ------------------------------------------------------------------ #
    def iniciar(self):
        if self.esta_vivo():
            return
        # Recupera linhas que ficaram "em processamento" de uma execução anterior.
        try:
            recuperadas = self.repo.resetar_processando()
            if recuperadas:
                log.warning("Recuperadas %d linhas travadas em PROCESSANDO", recuperadas)
        except Exception as e:
            log.error("Falha ao resetar PROCESSANDO no startup: %s", e, exc_info=True)

        self._parar.clear()
        self._threads = []

        # N consumidores (detalhe, append-only)
        for i in range(self.num_consumidores):
            t = threading.Thread(target=self._loop_consumidor, name=f"sg-consumidor-{i+1}", daemon=True)
            t.start()
            self._threads.append(t)

        # 1 agregador (resumo)
        t_agg = threading.Thread(target=self._loop_agregador, name="sg-agregador", daemon=True)
        t_agg.start()
        self._threads.append(t_agg)

        log.info(
            "SendGrid iniciado | consumidores=%d | lote=%d | agregador_lote=%d",
            self.num_consumidores, self.tamanho_lote, self.agregador_lote,
        )

    def parar(self):
        self._parar.set()

    def esta_vivo(self) -> bool:
        return any(t.is_alive() for t in self._threads)

    def consumidores_vivos(self) -> int:
        return sum(1 for t in self._threads if t.is_alive())

    # ------------------------------------------------------------------ #
    #  Etapa 1 — consumidores (detalhe)                                  #
    # ------------------------------------------------------------------ #
    def _loop_consumidor(self):
        while not self._parar.is_set():
            try:
                processou = self._processar_um_lote()
                self._talvez_limpar()
                if not processou:
                    time.sleep(self.intervalo_ocioso)
            except Exception as e:
                log.error("Erro no loop do consumidor: %s", e, exc_info=True)
                time.sleep(self.intervalo_ocioso)

    def _processar_um_lote(self) -> bool:
        inicio = time.time()

        linhas = self.repo.reivindicar_lote(self.tamanho_lote)
        if not linhas:
            return False

        eventos = []
        ids_ok = []
        ids_erro_parse = []

        for raw_id, body, _tentativas in linhas:
            try:
                eventos.extend(self.service.parse_body(body, raw_id))
                ids_ok.append(raw_id)
            except Exception as e:
                log.error("RAW %s com JSON inválido: %s", raw_id, e)
                ids_erro_parse.append(raw_id)

        try:
            self.repo.gravar_detalhe(eventos)
        except Exception as e:
            # Falha (provavelmente transitória): devolve o lote para nova tentativa.
            log.error("Falha ao gravar detalhe do lote: %s", e, exc_info=True)
            self.repo.marcar_falha(ids_ok, erro=str(e)[:1000])
            if ids_erro_parse:
                self.repo.marcar_erro_parse(ids_erro_parse, "JSON inválido")
            return True

        if ids_ok:
            self.repo.marcar_processados(ids_ok)
        if ids_erro_parse:
            self.repo.marcar_erro_parse(ids_erro_parse, "JSON inválido")

        log.info(
            "LOTE | linhas=%d | eventos=%d | erros_parse=%d | tempo=%.3fs",
            len(linhas), len(eventos), len(ids_erro_parse), time.time() - inicio,
        )
        return True

    # ------------------------------------------------------------------ #
    #  Etapa 2 — agregador (resumo)                                      #
    # ------------------------------------------------------------------ #
    def _loop_agregador(self):
        while not self._parar.is_set():
            try:
                total = self.repo.agregar_lote(self.agregador_lote)
                if not total:
                    time.sleep(self.intervalo_ocioso)
            except Exception as e:
                log.error("Erro no agregador: %s", e, exc_info=True)
                time.sleep(self.intervalo_ocioso)

    # ------------------------------------------------------------------ #
    def _talvez_limpar(self):
        agora = time.time()
        if agora - self._ultima_limpeza < self.intervalo_limpeza_seg:
            return
        if not self._limpeza_lock.acquire(blocking=False):
            return
        try:
            if agora - self._ultima_limpeza < self.intervalo_limpeza_seg:
                return
            self._ultima_limpeza = agora
            removidas = self.repo.limpar_raw_antigo(self.retencao_dias)
            if removidas:
                log.info("Limpeza RAW: %d linhas antigas removidas", removidas)
        except Exception as e:
            log.error("Falha na limpeza da RAW: %s", e, exc_info=True)
        finally:
            self._limpeza_lock.release()


def _env_int(nome: str, padrao: int) -> int:
    try:
        valor = int(os.getenv(nome, str(padrao)))
        return valor if valor > 0 else padrao
    except (TypeError, ValueError):
        return padrao


# Singleton usado pelo processo dedicado (run_consumer.py).
# Ajustável por variável de ambiente, sem mexer no código:
#   SENDGRID_LOTE           -> tamanho do lote dos consumidores (padrão 300)
#   SENDGRID_CONSUMIDORES   -> quantas threads de consumo (padrão 3)
#   SENDGRID_AGREGADOR_LOTE -> quantos eventos o agregador processa por ciclo (padrão 2000)
consumidor = SendGridConsumer(
    tamanho_lote=_env_int("SENDGRID_LOTE", 300),
    num_consumidores=_env_int("SENDGRID_CONSUMIDORES", 3),
    agregador_lote=_env_int("SENDGRID_AGREGADOR_LOTE", 20000),
)


def iniciar_consumidor():
    consumidor.iniciar()
    return consumidor
