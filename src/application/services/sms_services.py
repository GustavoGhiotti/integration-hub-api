import logging
from src.infrastructure.repositories.sql_sms_repository import SqlSmsRepository

# Logger principal do serviço SMS (controla registros no arquivo sms.log)
log = logging.getLogger("sms_service")

class SmsService:
    """
    Classe responsavel por:
    - Processar callbakcs (envios, resultados e entregas) enviados pela Sinch
    - Garantir que o mesmo MESSAGE_ID nunca gere duplicidades na base
    """
    def __init__(self, repo: SqlSmsRepository | None = None):
        self.repo = repo or SqlSmsRepository()

    # Disparo simples: apenas registra o pedido de envio
    def disparar(self, campanha: str, numero: str, mensagem: str) -> dict:
        self.repo.registrar_disparo(campanha, numero, mensagem)
        return {
            "status": "registrado", 
            "campanha": campanha, 
            "numero": numero, 
            "mensagem": mensagem
        }
    
    # Callback da Sinch
    def handle_callback(self, data: dict, headers: dict | None = None, raw_body: str | None = None) -> None:
        # Salvar RAW
        try:
            self.repo.salvar_raw(str(headers or {}), raw_body or str(data))
        except Exception as e:
            log.error("Erro ao salvar RAW: %s", e, exc_info=True)

        # Extrair informações principais do callback
        evento = (data.get("event") or "").strip()
        message_id = (data.get("id") or "").strip()
        numero = (data.get("identity", {}).get("endpoint") or "").strip()
        reference = (data.get("reference") or "").strip()

        # Captura e normaliza status recebido da Sinch
        status_sinch = (
            data.get("status")
            or data.get("smsResult")
            or data.get("result")
            or data.get("status_text")
            or ""
        ).strip().lower()

        # Captura o motivo (em caso de falha) ou detalhes adicionais
        motivo = (data.get("reason") or data.get("error") or "").strip()

        # Traduz status da Sinch → português
        status_mapa = {
            "successful": "SUCESSO",
            "success": "SUCESSO",
            "fail": "FALHA",
            "failed": "NÃO ENTREGUE",
            "denied": "FALHA",
            "error": "ERRO",
            "delivered": "ENTREGUE",
            "sent": "ENVIADO",
            "pending": "PENDENTE",
            "submitted": "ENVIADO",
            "requested": "ENVIADO",
        }

        # Determina o status legivel conforme o tipo de evento
        if evento == "VerificationRequestEvent":
            status_texto = "enviado"
        else:
            status_texto = status_mapa.get(status_sinch, "DESCONHECIDO")

        # Define status binário (1=sucesso, 0=erro)
        status_bin = self.definir_status_binario(status_texto)
     
        # Atualiza ou insere o registro de forma inteligente
        try:
            afetadas = self.repo.atualizar_status_por_msgid(
                message_id, status_bin, status_texto
            )

            if afetadas == 0:
                # Caso o registro ainda não exista, cria um novo
                self.repo.inserir_delivery_se_nao_existir(
                    campanha=reference or "N/A",
                    numero=numero,
                    conteudo="",
                    status_bin=status_bin,
                    status_texto=status_texto,
                    message_id=message_id,
                )
                acao = "INSERIDO"
            else:
                # Atualização de registro existente
                acao = "ATUALIZADO"

            log.info(
                    f"[Sinch] {acao} | Evento={evento} | MsgID={message_id} | "
                    f"Numero={numero or '-'} | Status={status_texto} | Motivo={motivo or '-'}"
            )

        except Exception as e:
            log.error(f"[Sinch] Erro ao processar evento {evento}: {e}", exc_info=True)

    @staticmethod
    def definir_status_binario(status_texto: str) -> int:
        """Retorna 1 para status positivos e 0 para falhas"""
        positivos = {"SUCESSO", "ENTREGUE", "ENVIADO"}
        return 1 if status_texto.upper() in positivos else 0