from src.infrastructure.database.sql_server_connection import SQLServerConnection
from src.shared.utils.env_load import DB_66


class SqlApiAuditRepository:
    _SCHEMA_PRODUCAO = "API"
    _SCHEMA_HOMOLOGACAO = "ApiHomolog"
    _START = (
        "ID_EXECUCAO", "REQUEST_ID", "CORRELATION_ID", "DT_INICIO_UTC", "METODO_HTTP", "ROTA",
        "ENDPOINT", "CONTENT_TYPE", "QUERY_STRING", "PARAMETROS_ROTA_JSON", "HEADERS_JSON",
        "PAYLOAD_ENTRADA", "TAMANHO_ENTRADA_BYTES", "PAYLOAD_TRUNCADO", "FLUXO", "ID_CLIENTE", "ID_CEDENTE",
        "NOME_CEDENTE", "ID_CONTRATO", "ID_ACORDO", "DOCUMENTO_HASH", "DOCUMENTO_MASCARADO",
        "TELEFONE_FINAL", "CHAVES_BUSCA_JSON", "ID_USUARIO", "USUARIO", "TIPO_AUTENTICACAO",
        "IP_CLIENTE", "USER_AGENT", "ORIGEM_CHAMADA", "AMBIENTE", "NOME_APLICACAO",
        "VERSAO_APLICACAO", "HOST_APLICACAO", "PROCESSO_APLICACAO",
    )
    _FINAL = (
        "ID_EXECUCAO", "DT_FIM_UTC", "DURACAO_MS", "ID_USUARIO", "USUARIO", "TIPO_AUTENTICACAO", "FLUXO", "ID_CLIENTE",
        "ID_CEDENTE", "NOME_CEDENTE", "ID_CONTRATO", "ID_ACORDO", "SUCESSO", "STATUS_PROCESSO",
        "STATUS_HTTP", "ORIGEM_ERRO", "ETAPA_ERRO", "CODIGO_ERRO", "RETORNO_USUARIO",
        "TAMANHO_RETORNO_BYTES", "PAYLOAD_TRUNCADO", "TIPO_EXCECAO", "MENSAGEM_ERRO", "STACK_TRACE",
    )
    _STAGE = (
        "ID_EXECUCAO", "ID_ETAPA_PAI", "ORDEM", "TENTATIVA", "TIPO_ETAPA", "PROVEDOR", "OPERACAO",
        "CLASSE_METODO", "METODO_HTTP", "ENDPOINT_EXTERNO", "ID_CLIENTE", "ID_CEDENTE", "NOME_CEDENTE",
        "ID_CONTRATO", "ID_ACORDO", "DT_INICIO_UTC", "DT_FIM_UTC", "DURACAO_MS", "SUCESSO",
        "STATUS_HTTP_EXTERNO", "RETORNO_ERRO_NEGOCIO", "PAYLOAD_ENVIO", "PAYLOAD_RETORNO",
        "TAMANHO_ENVIO_BYTES", "TAMANHO_RETORNO_BYTES", "HASH_RETORNO", "PAYLOAD_TRUNCADO",
        "TIPO_EXCECAO", "MENSAGEM_ERRO", "STACK_TRACE", "METADADOS_JSON",
    )

    def __init__(self):
        self.db = SQLServerConnection(server=DB_66, database="LOGS_ROBOS")

    def _execute(
        self,
        procedure: str,
        parameters: tuple[str, ...],
        data: dict,
        homologacao: bool = False,
    ):
        schema = self._SCHEMA_HOMOLOGACAO if homologacao else self._SCHEMA_PRODUCAO
        query, values = self._command(schema, procedure, parameters, data)
        return self.db.execute(
            query=query,
            parametros=values,
            fetch=False,
        )

    @staticmethod
    def _command(schema: str, procedure: str, parameters: tuple[str, ...], data: dict):
        if schema not in {"API", "ApiHomolog"}:
            raise ValueError(f"Schema de auditoria invalido: {schema}")
        assignments = ", ".join(f"@{name}=?" for name in parameters)
        return (
            f"EXEC [{schema}].[{procedure}] {assignments}",
            tuple(data.get(name) for name in parameters),
        )

    def iniciar(self, data: dict, homologacao: bool = False):
        return self._execute("SP_API_EXECUCAO_INICIAR", self._START, data, homologacao)

    def finalizar(self, data: dict, homologacao: bool = False):
        return self._execute("SP_API_EXECUCAO_FINALIZAR", self._FINAL, data, homologacao)

    def registrar_etapa(self, data: dict, homologacao: bool = False):
        return self._execute("SP_API_ETAPA_REGISTRAR", self._STAGE, data, homologacao)

    def processar_lote(self, events: list[dict]):
        operations = {
            "iniciar": ("SP_API_EXECUCAO_INICIAR", self._START),
            "registrar_etapa": ("SP_API_ETAPA_REGISTRAR", self._STAGE),
            "finalizar": ("SP_API_EXECUCAO_FINALIZAR", self._FINAL),
        }
        statements = []
        # Uma rotacao pode capturar etapas no mesmo lote do respectivo inicio.
        # Priorizar os pais evita violacao de FK sem alterar a ordem das etapas.
        priority = {"iniciar": 0, "registrar_etapa": 1, "finalizar": 2}
        ordered_events = sorted(
            enumerate(events),
            key=lambda item: (priority.get(item[1].get("operation"), 99), item[0]),
        )
        for _, event in ordered_events:
            operation = event.get("operation")
            if operation not in operations:
                raise ValueError(f"Operacao de auditoria desconhecida: {operation}")
            procedure, parameters = operations[operation]
            homologacao = event.get("homologacao", False)
            if not isinstance(homologacao, bool):
                raise ValueError("Campo homologacao deve ser true ou false")
            schema = self._SCHEMA_HOMOLOGACAO if homologacao else self._SCHEMA_PRODUCAO
            statements.append(self._command(schema, procedure, parameters, event["data"]))
        return self.db.execute_transaction(statements) if statements else 0
