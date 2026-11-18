
from src.infrastructure.external.infobip.infobip_client import InfobipClient
from src.infrastructure.repositories.sql_sms_repository import SqlSmsInfobipRepository

class SmsService:

    @staticmethod
    def processar_sms(
        id_msg,
        enviado_para,
        hora_envio,
        entrega_msg,
        status,
        status_desc,
        valor_sms,
        erro,
        raw_json
    ):
        repo = SqlSmsInfobipRepository()
        repo.salvar_sms(
            id_msg=id_msg,
            enviado_para=enviado_para,
            hora_envio=hora_envio,
            entrega_msg=entrega_msg,
            status=status,
            status_desc=status_desc,
            valor_sms=valor_sms,
            erro=erro,
            raw_json=raw_json
        )


    @staticmethod

    def processar_batch(batch):
        repo = SqlSmsInfobipRepository()
        repo.salvar_lote(batch)


class InfobipApi:
    client = InfobipClient()
    DEFAULT_LIMIT = 999

    @classmethod
    def pegar_filas(cls):
        return cls.client.get(
            "/ccaas/1/queues",
            params={"limit": cls.DEFAULT_LIMIT, "pageSize": cls.DEFAULT_LIMIT, "size": cls.DEFAULT_LIMIT},
        )
    

    @classmethod
    def pegar_agentes(cls):
        return cls.client.get(
            "/ccaas/1/agents/",
            params={"limit": cls.DEFAULT_LIMIT, "pageSize": cls.DEFAULT_LIMIT, "size": cls.DEFAULT_LIMIT},
        )
    
    @classmethod 
    def pegar_agentes_da_fila(cls,queue_id: str):
        return cls.client.get(
            f"/ccaas/1/queues/{queue_id}/agents",
            params={"limit": cls.DEFAULT_LIMIT, "pageSize": cls.DEFAULT_LIMIT, "size": cls.DEFAULT_LIMIT},
        )
    
    @classmethod
    def pegar_conversas(cls, fila=None, atendente=None, status=None, data_inicio=None, data_fim=None, limit=None):
        limit = limit or cls.DEFAULT_LIMIT
        params = {
            "limit": limit,
            "pageSize": limit,
            "size": limit,
        }

        if fila:
            params["queueId"] = fila
        if atendente:
            params["agentId"] = atendente
        if status:
            params["status"] = status
        if data_inicio:
            params["createdAtFrom"] = data_inicio
        if data_fim:
            params["createdAtTo"] = data_fim

        return cls.client.get("/ccaas/1/conversations", params=params)
    

    @classmethod 
    def pegar_conversas_do_agente(cls, agente_id: str):
        return cls.client.get(
            f"/ccaas/1/agents/{agente_id}/conversations",
            params={"limit": cls.DEFAULT_LIMIT, "pageSize": cls.DEFAULT_LIMIT, "size": cls.DEFAULT_LIMIT},
        )
    
    @classmethod 
    def pegar_mensagens_da_conversa(cls, conversation_id: str):
        return cls.client.get(
            f"/ccaas/1/conversations/{conversation_id}/messages",
            params={"limit": cls.DEFAULT_LIMIT, "pageSize": cls.DEFAULT_LIMIT, "size": cls.DEFAULT_LIMIT},
        )


    



    


    
