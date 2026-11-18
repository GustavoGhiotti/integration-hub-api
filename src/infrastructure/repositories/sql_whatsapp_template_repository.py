import json
from src.infrastructure.database.sql_server_connection import SQLServerConnection
from src.shared.utils.env_load import DB_66


class SqlWhatsappTemplateRepository:
    def __init__(self):
        self.db = SQLServerConnection(server=DB_66, database="DB_CHATBOT")

    # =========================================================
    # HELPERS
    # =========================================================

    def _execute_insert_returning_one(self, *, query: str, parametros: tuple):
        conexao = None
        try:
            conexao = self.db._connect()
            with conexao.cursor() as cursor:
                cursor.execute(query, parametros)
                colunas = [c[0] for c in cursor.description]
                linha = cursor.fetchone()
                conexao.commit()
                if not linha:
                    return None
                return dict(zip(colunas, linha))
        except Exception:
            if conexao is not None:
                try:
                    conexao.rollback()
                except Exception:
                    pass
            raise
        finally:
            if conexao is not None:
                try:
                    conexao.close()
                except Exception:
                    pass

    def _execute_commit_rowcount(self, *, query: str, parametros: tuple) -> int:
        conexao = None
        try:
            conexao = self.db._connect()
            with conexao.cursor() as cursor:
                cursor.execute(query, parametros)
                rowcount = cursor.rowcount
                conexao.commit()
                return rowcount
        except Exception:
            if conexao is not None:
                try:
                    conexao.rollback()
                except Exception:
                    pass
            raise
        finally:
            if conexao is not None:
                try:
                    conexao.close()
                except Exception:
                    pass

    # =========================================================
    # TEMPLATE
    # =========================================================

    def criar_template(self, dados: dict) -> int:
        query = """
            INSERT INTO whatsapp.TB_WHATSAPP_TEMPLATES (
                NOME_INTERNO,
                NOME_TEMPLATE_META,
                IDIOMA,
                CATEGORIA_META,
                STATUS_TEMPLATE,
                QUALITY_STATUS,
                ATIVO,
                HEADER_TIPO,
                HEADER_TEXTO,
                BODY_TEXTO,
                FOOTER_TEXTO,
                BUTTONS_JSON,
                COMPONENTES_JSON,
                VARIAVEIS_JSON,
                ID_TEMPLATE_META,
                ULTIMO_EVENTO_META,
                ULTIMO_PAYLOAD_META,
                CRIADO_POR,
                ORIGEM_CADASTRO,
                DATA_CRIACAO,
                DATA_ATUALIZACAO,
                DATA_ULTIMA_SINCRONIA
            )
            OUTPUT INSERTED.ID_TEMPLATE
            VALUES (
                ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, SYSUTCDATETIME(), SYSUTCDATETIME(), ?
            )
        """

        result = self._execute_insert_returning_one(
            query=query,
            parametros=(
                dados["nome_interno"],
                dados["nome_template_meta"],
                dados["idioma"],
                dados["categoria_meta"],
                dados["status_template"],
                dados.get("quality_status"),
                1 if dados.get("ativo", True) else 0,
                dados.get("header_tipo"),
                dados.get("header_texto"),
                dados["body_texto"],
                dados.get("footer_texto"),
                json.dumps(dados.get("buttons_json"), ensure_ascii=False) if dados.get("buttons_json") is not None else None,
                json.dumps(dados.get("componentes_json"), ensure_ascii=False) if dados.get("componentes_json") is not None else None,
                json.dumps(dados.get("variaveis_json"), ensure_ascii=False) if dados.get("variaveis_json") is not None else None,
                dados.get("id_template_meta"),
                dados.get("ultimo_evento_meta"),
                json.dumps(dados.get("ultimo_payload_meta"), ensure_ascii=False, default=str) if dados.get("ultimo_payload_meta") is not None else None,
                dados.get("criado_por"),
                dados.get("origem_cadastro", "ATLAS"),
                dados.get("data_ultima_sincronia"),
            ),
        )

        if not result or "ID_TEMPLATE" not in result:
            raise Exception("Falha ao criar template: ID_TEMPLATE nao retornado.")

        return result["ID_TEMPLATE"]

    def buscar_template_por_id(self, id_template: int):
        query = """
            SELECT *
            FROM whatsapp.TB_WHATSAPP_TEMPLATES WITH (NOLOCK)
            WHERE ID_TEMPLATE = ?
        """
        rows = self.db.execute(query=query, parametros=(id_template,), fetch=True)
        return rows[0] if rows else None

    def buscar_template_por_nome_meta(self, nome_template_meta: str, idioma: str | None = None):
        query = """
            SELECT TOP 1 *
            FROM whatsapp.TB_WHATSAPP_TEMPLATES WITH (NOLOCK)
            WHERE NOME_TEMPLATE_META = ?
                AND STATUS_TEMPLATE <> 'DELETADO'
        """
        parametros = [nome_template_meta]

        if idioma:
            query += " AND IDIOMA = ?"
            parametros.append(idioma)

        query += " ORDER BY ID_TEMPLATE DESC"

        rows = self.db.execute(query=query, parametros=tuple(parametros), fetch=True)
        return rows[0] if rows else None

    def buscar_template_por_id_meta(self, id_template_meta: str):
        query = """
            SELECT TOP 1 *
            FROM whatsapp.TB_WHATSAPP_TEMPLATES WITH (NOLOCK)
            WHERE ID_TEMPLATE_META = ?
            ORDER BY ID_TEMPLATE DESC
        """
        rows = self.db.execute(query=query, parametros=(id_template_meta,), fetch=True)
        return rows[0] if rows else None

    def listar_templates(
        self,
        *,
        filtro: str | None = None,
    ):
        query = """
            SELECT
                ID_TEMPLATE,
                NOME_INTERNO,
                NOME_TEMPLATE_META,
                IDIOMA,
                CATEGORIA_META,
                STATUS_TEMPLATE,
                QUALITY_STATUS,
                ATIVO,
                HEADER_TIPO,
                HEADER_TEXTO,
                BODY_TEXTO,
                FOOTER_TEXTO,
                BUTTONS_JSON,
                COMPONENTES_JSON,
                VARIAVEIS_JSON,
                ID_TEMPLATE_META,
                ULTIMO_EVENTO_META,
                ULTIMO_PAYLOAD_META,
                CRIADO_POR,
                ORIGEM_CADASTRO,
                DATA_CRIACAO,
                DATA_ATUALIZACAO,
                DATA_ULTIMA_SINCRONIA
            FROM whatsapp.TB_WHATSAPP_TEMPLATES WITH (NOLOCK)
            WHERE 1 = 1
        """
        parametros = []
        filtro_normalizado = (filtro or "").strip().lower()

        if filtro_normalizado == "todos":
            pass
        elif filtro_normalizado == "ativos":
            query += " AND STATUS_TEMPLATE = 'APROVADO' AND ATIVO = 1 AND ID_TEMPLATE_META IS NOT NULL AND LTRIM(RTRIM(ID_TEMPLATE_META)) <> ''"
        elif filtro_normalizado == "desativados":
            query += " AND STATUS_TEMPLATE = 'APROVADO' AND ATIVO = 0"
        elif filtro_normalizado == "aprovados":
            query += " AND STATUS_TEMPLATE = 'APROVADO'"
        elif filtro_normalizado == "deletados":
            query += " AND STATUS_TEMPLATE = 'DELETADO'"
        elif filtro_normalizado == "rascunhos":
            query += " AND STATUS_TEMPLATE = 'RASCUNHO'"
        elif filtro_normalizado == "em_revisao":
            query += " AND STATUS_TEMPLATE IN ('EM_REVISAO', 'SUBMETIDO')"
        else:
            query += " AND STATUS_TEMPLATE <> 'DELETADO'"

        query += " ORDER BY DATA_ATUALIZACAO DESC, ID_TEMPLATE DESC"

        return self.db.execute(query=query, parametros=tuple(parametros), fetch=True) or []

    def atualizar_template(self, id_template: int, dados: dict) -> bool:
        query = """
            UPDATE whatsapp.TB_WHATSAPP_TEMPLATES
            SET
                NOME_INTERNO = ?,
                NOME_TEMPLATE_META = ?,
                IDIOMA = ?,
                CATEGORIA_META = ?,
                STATUS_TEMPLATE = ?,
                QUALITY_STATUS = ?,
                ATIVO = ?,
                HEADER_TIPO = ?,
                HEADER_TEXTO = ?,
                BODY_TEXTO = ?,
                FOOTER_TEXTO = ?,
                BUTTONS_JSON = ?,
                COMPONENTES_JSON = ?,
                VARIAVEIS_JSON = ?,
                ID_TEMPLATE_META = ?,
                ULTIMO_EVENTO_META = ?,
                ULTIMO_PAYLOAD_META = ?,
                DATA_ATUALIZACAO = SYSUTCDATETIME(),
                DATA_ULTIMA_SINCRONIA = ?
            WHERE ID_TEMPLATE = ?
        """

        rows = self._execute_commit_rowcount(
            query=query,
            parametros=(
                dados["nome_interno"],
                dados["nome_template_meta"],
                dados["idioma"],
                dados["categoria_meta"],
                dados["status_template"],
                dados.get("quality_status"),
                1 if dados.get("ativo", True) else 0,
                dados.get("header_tipo"),
                dados.get("header_texto"),
                dados["body_texto"],
                dados.get("footer_texto"),
                json.dumps(dados.get("buttons_json"), ensure_ascii=False) if dados.get("buttons_json") is not None else None,
                json.dumps(dados.get("componentes_json"), ensure_ascii=False) if dados.get("componentes_json") is not None else None,
                json.dumps(dados.get("variaveis_json"), ensure_ascii=False) if dados.get("variaveis_json") is not None else None,
                dados.get("id_template_meta"),
                dados.get("ultimo_evento_meta"),
                json.dumps(dados.get("ultimo_payload_meta"), ensure_ascii=False, default=str) if dados.get("ultimo_payload_meta") is not None else None,
                dados.get("data_ultima_sincronia"),
                id_template,
            ),
        )
        return rows > 0

    def excluir_template_rascunho(self, id_template: int, payload_evento: dict | None = None) -> bool:
        query = """
            UPDATE whatsapp.TB_WHATSAPP_TEMPLATES
            SET
                STATUS_TEMPLATE = 'DELETADO',
                ATIVO = 0,
                ULTIMO_EVENTO_META = 'TEMPLATE_DELETADO',
                ULTIMO_PAYLOAD_META = ?,
                DATA_ATUALIZACAO = SYSUTCDATETIME()
            WHERE ID_TEMPLATE = ?
        """

        payload_json = None
        if payload_evento is not None:
            payload_json = json.dumps(payload_evento, ensure_ascii=False, default=str)

        rows = self._execute_commit_rowcount(
            query=query,
            parametros=(
                payload_json,
                id_template,
            ),
        )
        return rows > 0

    def atualizar_ativo_template(
        self,
        *,
        id_template: int,
        ativo: bool,
        ultimo_evento_meta: str,
        ultimo_payload_meta: dict | None = None,
    ) -> bool:
        query = """
            UPDATE whatsapp.TB_WHATSAPP_TEMPLATES
            SET
                ATIVO = ?,
                ULTIMO_EVENTO_META = ?,
                ULTIMO_PAYLOAD_META = ?,
                DATA_ATUALIZACAO = SYSUTCDATETIME()
            WHERE ID_TEMPLATE = ?
        """

        payload_json = None
        if ultimo_payload_meta is not None:
            payload_json = json.dumps(ultimo_payload_meta, ensure_ascii=False, default=str)

        rows = self._execute_commit_rowcount(
            query=query,
            parametros=(
                1 if ativo else 0,
                ultimo_evento_meta,
                payload_json,
                id_template,
            ),
        )
        return rows > 0

    def atualizar_status_template(
        self,
        *,
        id_template: int,
        status_template: str | None = None,
        quality_status: str | None = None,
        ultimo_evento_meta: str | None = None,
        ultimo_payload_meta: dict | None = None,
        data_ultima_sincronia=None,
        id_template_meta: str | None = None
    ) -> bool:
        query = """
            UPDATE whatsapp.TB_WHATSAPP_TEMPLATES
            SET
                STATUS_TEMPLATE = COALESCE(?, STATUS_TEMPLATE),
                QUALITY_STATUS = COALESCE(?, QUALITY_STATUS),
                ULTIMO_EVENTO_META = COALESCE(?, ULTIMO_EVENTO_META),
                ULTIMO_PAYLOAD_META = COALESCE(?, ULTIMO_PAYLOAD_META),
                ID_TEMPLATE_META = COALESCE(?, ID_TEMPLATE_META),
                DATA_ATUALIZACAO = SYSUTCDATETIME(),
                DATA_ULTIMA_SINCRONIA = COALESCE(?, DATA_ULTIMA_SINCRONIA)
            WHERE ID_TEMPLATE = ?
        """

        payload_json = None
        if ultimo_payload_meta is not None:
            payload_json = json.dumps(ultimo_payload_meta, ensure_ascii=False, default=str)

        rows = self._execute_commit_rowcount(
            query=query,
            parametros=(
                status_template,
                quality_status,
                ultimo_evento_meta,
                payload_json,
                id_template_meta,
                data_ultima_sincronia,
                id_template,
            ),
        )
        return rows > 0

    # =========================================================
    # EVENTOS
    # =========================================================

    def inserir_evento_template(
        self,
        *,
        id_template: int,
        tipo_evento: str,
        status_anterior: str | None = None,
        status_novo: str | None = None,
        quality_anterior: str | None = None,
        quality_novo: str | None = None,
        origem_evento: str,
        descricao_evento: str | None = None,
        payload_evento: dict | None = None,
        usuario_responsavel: str | None = None
    ) -> int:
        query = """
            INSERT INTO whatsapp.TB_WHATSAPP_TEMPLATE_EVENTOS (
                ID_TEMPLATE,
                TIPO_EVENTO,
                STATUS_ANTERIOR,
                STATUS_NOVO,
                QUALITY_ANTERIOR,
                QUALITY_NOVO,
                ORIGEM_EVENTO,
                DESCRICAO_EVENTO,
                PAYLOAD_EVENTO,
                USUARIO_RESPONSAVEL,
                DATA_EVENTO
            )
            OUTPUT INSERTED.ID_EVENTO_TEMPLATE
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, SYSUTCDATETIME())
        """

        result = self._execute_insert_returning_one(
            query=query,
            parametros=(
                id_template,
                tipo_evento,
                status_anterior,
                status_novo,
                quality_anterior,
                quality_novo,
                origem_evento,
                descricao_evento,
                json.dumps(payload_evento, ensure_ascii=False, default=str) if payload_evento is not None else None,
                usuario_responsavel,
            )
        )

        if not result or "ID_EVENTO_TEMPLATE" not in result:
            raise Exception("Falha ao registrar evento do template.")

        return result["ID_EVENTO_TEMPLATE"]

    def listar_eventos_template(self, id_template: int):
        query = """
            SELECT
                ID_EVENTO_TEMPLATE,
                ID_TEMPLATE,
                TIPO_EVENTO,
                STATUS_ANTERIOR,
                STATUS_NOVO,
                QUALITY_ANTERIOR,
                QUALITY_NOVO,
                ORIGEM_EVENTO,
                DESCRICAO_EVENTO,
                PAYLOAD_EVENTO,
                USUARIO_RESPONSAVEL,
                DATA_EVENTO
            FROM whatsapp.TB_WHATSAPP_TEMPLATE_EVENTOS WITH (NOLOCK)
            WHERE ID_TEMPLATE = ?
            ORDER BY DATA_EVENTO DESC, ID_EVENTO_TEMPLATE DESC
        """
        return self.db.execute(query=query, parametros=(id_template,), fetch=True) or []
