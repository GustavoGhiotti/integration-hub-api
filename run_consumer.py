"""Processo DEDICADO do consumidor SendGrid.

Rode este script como UM ÚNICO serviço (ex.: nssm), separado da API web.

Por quê: a API web roda em vários processos de worker (IIS/wfastcgi e/ou Waitress).
Se o consumidor subisse dentro dela, CADA worker teria seus próprios consumidores,
brigando pelo banco (duplicação, deadlock, lentidão). Aqui o consumidor roda em UM
processo só — não importa quantos workers a API web tenha.

  API web (N workers)  -> só recebe o webhook e grava na RAW
  run_consumer.py (1)  -> lê a RAW, processa e atualiza as tabelas

Ajuste por variável de ambiente (.env):
    SENDGRID_LOTE         (padrão 300)
    SENDGRID_CONSUMIDORES (padrão 1 — recomendado neste processo dedicado)
"""
import sys
import time

from src.infrastructure.logging.logger_config import setup_logger
from src.infrastructure.queue.sendgrid_consumer import iniciar_consumidor


def main() -> int:
    log = setup_logger("sendgrid_consumer", "sendgrid_consumer.log", True)
    log.info("== Processo dedicado do consumidor SendGrid iniciando ==")

    consumidor = iniciar_consumidor()
    log.info(
        "Consumidor ativo | threads=%d | lote=%d",
        consumidor.consumidores_vivos(), consumidor.tamanho_lote,
    )

    try:
        while True:
            time.sleep(30)
            if not consumidor.esta_vivo():
                # Todas as threads morreram: sai com erro para o serviço reiniciar.
                log.error("Nenhuma thread de consumo viva — encerrando para reinício")
                return 1
    except KeyboardInterrupt:
        log.info("Encerrando consumidor (KeyboardInterrupt)")
        consumidor.parar()
        return 0


if __name__ == "__main__":
    sys.exit(main())
