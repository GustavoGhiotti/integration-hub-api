import json
import hmac
import hashlib
import re
import requests
from datetime import datetime
from src.infrastructure.repositories.sql_whatsapp_template_repository import SqlWhatsappTemplateRepository
from src.shared.utils.env_load import (
    COPILOT_META_WEBHOOK_TOKEN,
    COPILOT_META_WEBHOOK_URL,
    META_APP_SECRET,
    META_VERIFY_TOKEN,
    WHATSAPP_META_ACCESS_TOKEN,
    WHATSAPP_META_API_VERSION,
    WHATSAPP_META_WABA_ID,
)


HEADER_TOKEN_INTERNO = "X-Internal-Token"
HEADER_REQUEST_ID = "X-Request-ID"
HEADER_FORWARDER = "X-Forwarded-By"
HEADER_FORWARDER_VALUE = "api-acme-meta-webhook"
TIMEOUT_WEBHOOK_SECONDS = 15
TIMEOUT_META_SECONDS = 30
META_GRAPH_BASE_URL = "https://graph.facebook.com"


class WebhookMetaService:
    def __init__(
        self,
        *,
        verify_token: str | None = META_VERIFY_TOKEN,
        app_secret: str | None = META_APP_SECRET,
        target_url: str | None = COPILOT_META_WEBHOOK_URL,
        internal_token: str | None = COPILOT_META_WEBHOOK_TOKEN,
        internal_header: str = HEADER_TOKEN_INTERNO,
        timeout_seconds: int = TIMEOUT_WEBHOOK_SECONDS,
    ):
        self.verify_token = verify_token
        self.app_secret = app_secret
        self.target_url = target_url
        self.internal_token = internal_token
        self.internal_header = internal_header
        self.timeout_seconds = timeout_seconds

    def validar_token_verificacao(self, token: str | None) -> bool:
        if not self.verify_token or not token:
            return False
        return hmac.compare_digest(str(token), str(self.verify_token))

    def validar_assinatura_meta(self, raw_body: bytes, signature: str | None) -> bool:
        if not self.app_secret or not signature:
            return False

        expected = "sha256=" + hmac.new(
            self.app_secret.encode("utf-8"),
            raw_body,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, signature)

    def encaminhar(
        self,
        raw_body: bytes,
        request_headers: dict | None = None,
        *,
        request_id: str | None = None,
    ) -> requests.Response:
        if not self.target_url:
            raise RuntimeError("COPILOT_META_WEBHOOK_URL nao configurado")

        headers = self._montar_headers_encaminhamento(
            request_headers or {},
            request_id=request_id,
        )
        return requests.post(
            self.target_url,
            data=raw_body,
            headers=headers,
            timeout=(3.05, self.timeout_seconds),
            allow_redirects=False,
        )

    def _montar_headers_encaminhamento(
        self,
        request_headers: dict,
        *,
        request_id: str | None = None,
    ) -> dict[str, str]:
        headers: dict[str, str] = {
            "Accept": "application/json",
            "Content-Type": request_headers.get("Content-Type", "application/json"),
            HEADER_FORWARDER: HEADER_FORWARDER_VALUE,
        }

        for header_name in ("X-Hub-Signature-256", "User-Agent"):
            value = request_headers.get(header_name)
            if value:
                headers[header_name] = value

        correlation_id = request_id or request_headers.get(HEADER_REQUEST_ID)
        if correlation_id:
            headers[HEADER_REQUEST_ID] = correlation_id

        if self.internal_token:
            headers[self.internal_header] = self.internal_token

        return headers

    # =========================================================
    # TEMPLATE
    # =========================================================

    def criar_template_local(self, payload: dict) -> dict:
        self._validar_payload_template(payload)

        repo = SqlWhatsappTemplateRepository()

        existente = repo.buscar_template_por_nome_meta(
            payload["nome_template_meta"],
            payload["idioma"]
        )
        if existente:
            raise ValueError("Ja existe template com este nome Meta e idioma.")

        dados = self._montar_payload_template(payload)
        dados["ativo"] = False
        id_template = repo.criar_template(dados)

        repo.inserir_evento_template(
            id_template=id_template,
            tipo_evento="TEMPLATE_CRIADO",
            status_novo=dados["status_template"],
            quality_novo=dados.get("quality_status"),
            origem_evento="ATLAS",
            descricao_evento="Template criado localmente na APISistemaAcme.",
            payload_evento=payload,
            usuario_responsavel=payload.get("criado_por"),
        )

        return {
            "id_template": id_template,
            "mensagem": "Template criado com sucesso.",
        }

    def atualizar_template_rascunho(self, id_template: int, payload: dict) -> dict:
        self._validar_payload_template(payload)

        repo = SqlWhatsappTemplateRepository()
        template_atual = repo.buscar_template_por_id(id_template)
        if not template_atual:
            raise ValueError("Template nao encontrado.")

        self._validar_template_em_rascunho(template_atual, acao="editar")

        existente = repo.buscar_template_por_nome_meta(
            payload["nome_template_meta"],
            payload["idioma"],
        )
        if existente and existente["ID_TEMPLATE"] != id_template:
            raise ValueError("Ja existe template com este nome Meta e idioma.")

        status_anterior = template_atual.get("STATUS_TEMPLATE")
        quality_anterior = template_atual.get("QUALITY_STATUS")

        dados = self._montar_payload_template(payload)
        dados["status_template"] = status_anterior or "RASCUNHO"
        dados["quality_status"] = quality_anterior or "UNKNOWN"
        dados["ativo"] = False
        dados["id_template_meta"] = None
        dados["ultimo_evento_meta"] = template_atual.get("ULTIMO_EVENTO_META")
        dados["ultimo_payload_meta"] = self._parse_json(template_atual.get("ULTIMO_PAYLOAD_META"))
        dados["data_ultima_sincronia"] = template_atual.get("DATA_ULTIMA_SINCRONIA")


        atualizado = repo.atualizar_template(id_template, dados)
        if not atualizado:
            raise RuntimeError("Falha ao atualizar template em rascunho.")

        repo.inserir_evento_template(
            id_template=id_template,
            tipo_evento="TEMPLATE_ATUALIZADO",
            status_anterior=status_anterior,
            status_novo=dados["status_template"],
            quality_anterior=quality_anterior,
            quality_novo=dados.get("quality_status"),
            origem_evento="ATLAS",
            descricao_evento="Template em rascunho atualizado localmente.",
            payload_evento=payload,
            usuario_responsavel=payload.get("criado_por"),
        )

        return {
            "id_template": id_template,
            "mensagem": "Template atualizado com sucesso.",
        }

    def excluir_template_rascunho(self, id_template: int, usuario_responsavel: str | None = None) -> dict:
        repo = SqlWhatsappTemplateRepository()
        template_atual = repo.buscar_template_por_id(id_template)
        if not template_atual:
            raise ValueError("Template nao encontrado.")

        self._validar_template_em_rascunho(template_atual, acao="excluir")

        status_anterior = template_atual.get("STATUS_TEMPLATE")
        quality_anterior = template_atual.get("QUALITY_STATUS")

        eventos_anteriores = repo.listar_eventos_template(id_template)

        payload_evento = {
            "id_template": template_atual.get("ID_TEMPLATE"),
            "nome_interno": template_atual.get("NOME_INTERNO"),
            "nome_template_meta": template_atual.get("NOME_TEMPLATE_META"),
            "idioma": template_atual.get("IDIOMA"),
            "categoria_meta": template_atual.get("CATEGORIA_META"),
            "status_anterior": status_anterior,
            "quality_anterior": quality_anterior,
            "ativo_anterior": bool(template_atual.get("ATIVO")),
            "total_eventos_anteriores": len(eventos_anteriores),
        }

        excluido = repo.excluir_template_rascunho(
            id_template,
            payload_evento=payload_evento,
        )
        if not excluido:
            raise RuntimeError("Falha ao excluir template em rascunho.")

        repo.inserir_evento_template(
            id_template=id_template,
            tipo_evento="TEMPLATE_DELETADO",
            status_anterior=status_anterior,
            status_novo="DELETADO",
            quality_anterior=quality_anterior,
            quality_novo=quality_anterior,
            origem_evento="ATLAS",
            descricao_evento="Template em rascunho marcado como deletado localmente.",
            payload_evento=payload_evento,
            usuario_responsavel=usuario_responsavel,
        )

        return {
            "id_template": id_template,
            "mensagem": "Template excluido com sucesso.",
        }

    def atualizar_ativo_template(
        self,
        id_template: int,
        ativo: bool,
        usuario_responsavel: str | None = None,
    ) -> dict:
        repo = SqlWhatsappTemplateRepository()
        template_atual = repo.buscar_template_por_id(id_template)
        if not template_atual:
            raise ValueError("Template nao encontrado.")

        status_atual = (template_atual.get("STATUS_TEMPLATE") or "").strip().upper()
        if status_atual != "APROVADO":
            raise ValueError("So e permitido ativar ou desativar templates aprovados.")
        
        id_template_meta = (template_atual.get("ID_TEMPLATE_META") or "").strip()
        if ativo and not id_template_meta:
            raise ValueError("So e permitido ativar templates aprovados com ID Meta preenchido.")

        ativo_atual = bool(template_atual.get("ATIVO"))
        if ativo_atual == bool(ativo):
            return {
                "id_template": id_template,
                "ativo": ativo_atual,
                "mensagem": "Nenhuma alteracao de disponibilidade foi necessaria.",
            }

        quality_atual = template_atual.get("QUALITY_STATUS")
        tipo_evento = "TEMPLATE_ATIVADO" if ativo else "TEMPLATE_DESATIVADO"
        payload_evento = {
            "id_template": template_atual.get("ID_TEMPLATE"),
            "nome_template_meta": template_atual.get("NOME_TEMPLATE_META"),
            "status_template": status_atual,
            "ativo_anterior": ativo_atual,
            "ativo_novo": bool(ativo),
        }

        atualizado = repo.atualizar_ativo_template(
            id_template=id_template,
            ativo=bool(ativo),
            ultimo_evento_meta=tipo_evento,
            ultimo_payload_meta=payload_evento,
        )
        if not atualizado:
            raise RuntimeError("Falha ao atualizar disponibilidade do template.")

        repo.inserir_evento_template(
            id_template=id_template,
            tipo_evento=tipo_evento,
            status_anterior=status_atual,
            status_novo=status_atual,
            quality_anterior=quality_atual,
            quality_novo=quality_atual,
            origem_evento="ATLAS",
            descricao_evento="Template ativado para uso operacional." if ativo else "Template desativado para uso operacional.",
            payload_evento=payload_evento,
            usuario_responsavel=usuario_responsavel,
        )

        return {
            "id_template": id_template,
            "ativo": bool(ativo),
            "mensagem": "Template ativado com sucesso." if ativo else "Template desativado com sucesso.",
        }

    def listar_templates(self, *, filtro: str | None = None) -> list[dict]:
        repo = SqlWhatsappTemplateRepository()
        resultados = repo.listar_templates(filtro=filtro)
        return [self._serializar_template(row) for row in resultados]
    
    def listar_templates_ativos_operacionais(self) -> list[dict]:
        repo = SqlWhatsappTemplateRepository()
        resultados = repo.listar_templates(filtro="ativos")
        return [self._serializar_template_operacional(row) for row in resultados]

    def obter_template(self, id_template: int) -> dict | None:
        repo = SqlWhatsappTemplateRepository()
        row = repo.buscar_template_por_id(id_template)
        if not row:
            return None

        template = self._serializar_template(row)
        template["eventos"] = self._serializar_eventos_template(
            repo.listar_eventos_template(id_template)
        )
        return template

    def submeter_template_meta(self, id_template: int, usuario_responsavel: str | None = None) -> dict:
        if not WHATSAPP_META_WABA_ID or not WHATSAPP_META_ACCESS_TOKEN:
            raise RuntimeError("Configuracao da Meta WhatsApp incompleta.")

        repo = SqlWhatsappTemplateRepository()
        template = repo.buscar_template_por_id(id_template)
        if not template:
            raise ValueError("Template nao encontrado.")

        self._validar_template_para_submissao(template)

        payload_meta = self._montar_payload_submissao_meta(template)
        api_version = WHATSAPP_META_API_VERSION or "v20.0"
        url = f"{META_GRAPH_BASE_URL}/{api_version}/{WHATSAPP_META_WABA_ID}/message_templates"

        resposta = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {WHATSAPP_META_ACCESS_TOKEN}",
                "Content-Type": "application/json",
            },
            json=payload_meta,
            timeout=(3.05, TIMEOUT_META_SECONDS),
        )
        resposta_meta = self._json_resposta_meta(resposta)

        status_anterior = template.get("STATUS_TEMPLATE")
        quality_anterior = template.get("QUALITY_STATUS")

        if resposta.status_code >= 400:
            payload_evento = {
                "request": payload_meta,
                "response": resposta_meta,
                "status_code": resposta.status_code,
            }
            repo.atualizar_status_template(
                id_template=id_template,
                ultimo_evento_meta="TEMPLATE_SUBMISSAO_META_FALHOU",
                ultimo_payload_meta=payload_evento,
                data_ultima_sincronia=datetime.utcnow(),
            )
            repo.inserir_evento_template(
                id_template=id_template,
                tipo_evento="TEMPLATE_SUBMISSAO_META_FALHOU",
                status_anterior=status_anterior,
                status_novo=status_anterior,
                quality_anterior=quality_anterior,
                quality_novo=quality_anterior,
                origem_evento="API",
                descricao_evento="Falha ao submeter template para a Meta.",
                payload_evento=payload_evento,
                usuario_responsavel=usuario_responsavel,
            )
            raise RuntimeError(self._extrair_mensagem_erro_meta(resposta_meta))

        status_novo = self._mapear_status_template_meta_bruto(
            resposta_meta.get("status")
        ) or "SUBMETIDO"
        id_template_meta = resposta_meta.get("id") or template.get("ID_TEMPLATE_META")
        payload_evento = {
            "request": payload_meta,
            "response": resposta_meta,
            "status_code": resposta.status_code,
        }

        repo.atualizar_status_template(
            id_template=id_template,
            status_template=status_novo,
            ultimo_evento_meta="TEMPLATE_SUBMETIDO_META",
            ultimo_payload_meta=payload_evento,
            data_ultima_sincronia=datetime.utcnow(),
            id_template_meta=id_template_meta,
        )
        repo.inserir_evento_template(
            id_template=id_template,
            tipo_evento="TEMPLATE_SUBMETIDO_META",
            status_anterior=status_anterior,
            status_novo=status_novo,
            quality_anterior=quality_anterior,
            quality_novo=quality_anterior,
            origem_evento="API",
            descricao_evento="Template submetido para aprovacao na Meta.",
            payload_evento=payload_evento,
            usuario_responsavel=usuario_responsavel,
        )

        return {
            "id_template": id_template,
            "id_template_meta": id_template_meta,
            "status_template": status_novo,
            "resposta_meta": resposta_meta,
        }

    def processar_eventos_template_meta(self, payload: dict) -> dict:
        repo = SqlWhatsappTemplateRepository()
        eventos_processados = 0

        for evento in self._extrair_eventos_template(payload):
            template = self._resolver_template_evento(repo, evento)
            if not template:
                continue

            status_anterior = template.get("STATUS_TEMPLATE")
            quality_anterior = template.get("QUALITY_STATUS")

            status_novo = self._mapear_status_template(evento)
            quality_novo = self._mapear_quality_status(evento)
            tipo_evento = self._mapear_tipo_evento_template(evento)

            repo.atualizar_status_template(
                id_template=template["ID_TEMPLATE"],
                status_template=status_novo,
                quality_status=quality_novo,
                ultimo_evento_meta=tipo_evento,
                ultimo_payload_meta=evento,
                data_ultima_sincronia=datetime.utcnow(),
                id_template_meta=evento.get("message_template_id") or template.get("ID_TEMPLATE_META"),
            )

            repo.inserir_evento_template(
                id_template=template["ID_TEMPLATE"],
                tipo_evento=tipo_evento,
                status_anterior=status_anterior,
                status_novo=status_novo,
                quality_anterior=quality_anterior,
                quality_novo=quality_novo,
                origem_evento="META",
                descricao_evento="Webhook de template processado pela Meta.",
                payload_evento=evento,
                usuario_responsavel=None,
            )

            eventos_processados += 1

        return {
            "eventos_processados": eventos_processados
        }

    def possui_eventos_template(self, payload: dict) -> bool:
        return len(self._extrair_eventos_template(payload)) > 0

    def _validar_payload_template(self, payload: dict) -> None:
        obrigatorios = [
            "nome_interno",
            "nome_template_meta",
            "idioma",
            "categoria_meta",
            "body_texto",
        ]

        for campo in obrigatorios:
            valor = payload.get(campo)
            if valor is None or (isinstance(valor, str) and not valor.strip()):
                raise ValueError(f"Campo obrigatorio ausente: {campo}")
            
        self._validar_nome_template_meta(payload.get("nome_template_meta"))
        self._validar_categoria_template_meta(payload.get("categoria_meta"))
        self._validar_texto_template_meta(payload.get("body_texto"), "body_texto")
        self._validar_texto_template_meta(payload.get("header_texto"), "header_texto")

        footer_texto = payload.get("footer_texto")
        if footer_texto and self._extrair_placeholders(footer_texto):
            raise ValueError("A Meta nao permite variaveis no rodape do template")

    def _montar_payload_template(self, payload: dict) -> dict:
        return {
            "nome_interno": payload["nome_interno"].strip(),
            "nome_template_meta": payload["nome_template_meta"].strip(),
            "idioma": payload["idioma"].strip(),
            "categoria_meta": payload["categoria_meta"].strip(),
            "status_template": "RASCUNHO",
            "quality_status": "UNKNOWN",
            "ativo": False,
            "header_tipo": payload.get("header_tipo"),
            "header_texto": payload.get("header_texto"),
            "body_texto": payload["body_texto"],
            "footer_texto": payload.get("footer_texto"),
            "buttons_json": payload.get("buttons_json"),
            "componentes_json": payload.get("componentes_json"),
            "variaveis_json": payload.get("variaveis_json"),
            "id_template_meta": None,
            "ultimo_evento_meta": None,
            "ultimo_payload_meta": None,
            "criado_por": payload.get("criado_por"),
            "origem_cadastro": "ATLAS",
            "data_ultima_sincronia": None,
        }

    def _validar_template_para_submissao(self, template: dict) -> None:
        status = (template.get("STATUS_TEMPLATE") or "").strip().upper()
        id_template_meta = template.get("ID_TEMPLATE_META")

        if status in {"APROVADO", "EM_REVISAO", "SUBMETIDO"} and id_template_meta:
            raise ValueError("Template ja foi submetido ou aprovado na Meta.")

        if status in {"PAUSADO", "DESABILITADO"}:
            raise ValueError("Template pausado ou desabilitado nao pode ser submetido.")

        obrigatorios = {
            "NOME_TEMPLATE_META": template.get("NOME_TEMPLATE_META"),
            "IDIOMA": template.get("IDIOMA"),
            "CATEGORIA_META": template.get("CATEGORIA_META"),
            "BODY_TEXTO": template.get("BODY_TEXTO"),
        }
        for campo, valor in obrigatorios.items():
            if valor is None or (isinstance(valor, str) and not valor.strip()):
                raise ValueError(f"Template sem campo obrigatorio para Meta: {campo}")
            
        self._validar_nome_template_meta(template.get("NOME_TEMPLATE_META"))
        self._validar_categoria_template_meta(template.get("CATEGORIA_META"))
        self._validar_texto_template_meta(template.get("BODY_TEXTO"), "BODY_TEXTO")
        self._validar_texto_template_meta(template.get("HEADER_TEXTO"), "HEADER_TEXTO")

        footer_texto = template.get("FOOTER_TEXTO")
        if footer_texto and self._extrair_placeholders(footer_texto):
            raise ValueError("A Meta nao permite variaveis no rodape do template.")

        header_tipo = (template.get("HEADER_TIPO") or "").strip().upper()
        if header_tipo and header_tipo != "TEXT":
            raise ValueError("Submissao automatica de header de midia ainda nao suportada.")

    def _validar_template_em_rascunho(self, template: dict, *, acao: str) -> None:
        status = (template.get("STATUS_TEMPLATE") or "").strip().upper()
        id_template_meta = template.get("ID_TEMPLATE_META")

        if status != "RASCUNHO" or id_template_meta:
            raise ValueError(f"So e permitido {acao} template em rascunho.")
        
    def _validar_nome_template_meta(self, nome_template: str | None) -> None:
        if not nome_template:
            return
        
        nome = nome_template.strip()
        if not re.fullmatch(r"[a-z0-9_]+", nome):
            raise ValueError("Nome Meta do template deve conter apenas letra minusculas, numeros e underline")
        
    def _validar_categoria_template_meta(self, categoria: str | None) -> None:
        if not categoria:
            return
        
        categorias_permitidas = {"UTILITY", "MARKETING", "AUTHENTICATION"}
        if str(categoria).strip().upper() not in categorias_permitidas:
            raise ValueError("Categoria Meta invalida. Use UTILITY, MARKETING ou AUTHENTICATION.")
    
    def _validar_texto_template_meta(self, texto: str | None, campo: str) -> None:
        if not texto:
            return
        
        texto_limpo = texto.strip()
        placeholders = self._extrair_placeholders(texto_limpo)
        if not placeholders:
            return
        
        if self._texto_comeca_com_variavel(texto_limpo):
            raise ValueError(f"A Meta nao permite variavel no inicio do campo {campo}")
        
        if self._texto_termina_com_variavel(texto_limpo):
            raise ValueError(f"A Meta nao permite variavel no fim do campo {campo}")
        
        if re.search(r"\}\}\s*\{\{", texto_limpo):
            raise ValueError(f"A Meta nao permite variaveis consecutivas no campo {campo}")
        
        esperados = [str(indice) for indice in range(1, len(placeholders) + 1)]
        if placeholders != esperados:
            raise ValueError(f"As variaveis do campo {campo} devem ser sequenciais, comecando em {{{{1}}}}")
        
    def _texto_comeca_com_variavel(self, texto: str) -> bool:
        return bool(re.match(r"^\s*\{\{\s*\d+\s*\}\}", texto))
    
    def _texto_termina_com_variavel(self, texto: str) -> bool:
        return bool(re.search(r"\{\{\s*\d+\s*\}\}\s*[\.\!\?\,\;\:]*\s*$", texto))

    def _montar_payload_submissao_meta(self, template: dict) -> dict:
        return {
            "name": template["NOME_TEMPLATE_META"],
            "language": template["IDIOMA"],
            "category": template["CATEGORIA_META"],
            "components": self._montar_componentes_submissao_meta(template),
        }

    def _montar_componentes_submissao_meta(self, template: dict) -> list[dict]:
        componentes = []

        header_tipo = (template.get("HEADER_TIPO") or "").strip().upper()
        header_texto = template.get("HEADER_TEXTO")
        if header_tipo == "TEXT" and header_texto:
            header = {
                "type": "HEADER",
                "format": "TEXT",
                "text": header_texto,
            }
            exemplos_header = self._montar_exemplos_para_texto(
                header_texto,
                template.get("VARIAVEIS_JSON"),
            )
            if exemplos_header:
                header["example"] = {"header_text": exemplos_header}
            componentes.append(header)

        body_texto = template["BODY_TEXTO"]
        body = {
            "type": "BODY",
            "text": body_texto,
        }
        exemplos_body = self._montar_exemplos_para_texto(
            body_texto,
            template.get("VARIAVEIS_JSON"),
        )
        if exemplos_body:
            body["example"] = {"body_text": [exemplos_body]}
        componentes.append(body)

        footer_texto = template.get("FOOTER_TEXTO")
        if footer_texto:
            componentes.append({
                "type": "FOOTER",
                "text": footer_texto,
            })

        botoes = self._normalizar_botoes_submissao_meta(
            template.get("BUTTONS_JSON")
        )
        if botoes:
            componentes.append({
                "type": "BUTTONS",
                "buttons": botoes,
            })

        return componentes

    def _montar_exemplos_para_texto(self, texto: str, variaveis_json) -> list[str]:
        placeholders = self._extrair_placeholders(texto)
        if not placeholders:
            return []

        variaveis = self._parse_json(variaveis_json) or []
        exemplos_por_indice = {}
        if isinstance(variaveis, list):
            for variavel in variaveis:
                if not isinstance(variavel, dict):
                    continue
                indice = variavel.get("indice")
                if indice is None:
                    continue
                exemplos_por_indice[str(indice)] = (
                    variavel.get("exemplo")
                    or variavel.get("valor_exemplo")
                    or variavel.get("nome")
                    or f"exemplo_{indice}"
                )

        return [
            str(exemplos_por_indice.get(indice) or f"exemplo_{indice}")
            for indice in placeholders
        ]

    def _extrair_placeholders(self, texto: str | None) -> list[str]:
        if not texto:
            return []
        encontrados = re.findall(r"\{\{\s*(\d+)\s*\}\}", texto)
        return sorted(set(encontrados), key=lambda valor: int(valor))

    def _normalizar_botoes_submissao_meta(self, buttons_json) -> list[dict]:
        botoes = self._parse_json(buttons_json) or []
        if not isinstance(botoes, list):
            return []

        normalizados = []
        for botao in botoes:
            if not isinstance(botao, dict):
                continue

            tipo = str(botao.get("type") or "").strip().upper()
            texto = botao.get("text")
            if not tipo or not texto:
                continue

            if tipo == "URL":
                url = botao.get("url")
                if not url:
                    continue
                normalizado = {
                    "type": "URL",
                    "text": texto,
                    "url": url,
                }
                if "{{" in url and not botao.get("example"):
                    normalizado["example"] = [
                        self._substituir_placeholders_por_exemplo(url)
                    ]
                elif botao.get("example"):
                    normalizado["example"] = botao["example"]
                normalizados.append(normalizado)
                continue

            if tipo == "PHONE_NUMBER":
                telefone = botao.get("phone_number")
                if telefone:
                    normalizados.append({
                        "type": "PHONE_NUMBER",
                        "text": texto,
                        "phone_number": telefone,
                    })
                continue

            if tipo == "QUICK_REPLY":
                normalizados.append({
                    "type": "QUICK_REPLY",
                    "text": texto,
                })

        return normalizados

    def _substituir_placeholders_por_exemplo(self, texto: str) -> str:
        return re.sub(r"\{\{\s*\d+\s*\}\}", "exemplo", texto)

    def _json_resposta_meta(self, resposta: requests.Response) -> dict:
        try:
            conteudo = resposta.json()
            if isinstance(conteudo, dict):
                return conteudo
            return {"data": conteudo}
        except Exception:
            return {"raw": resposta.text}

    def _extrair_mensagem_erro_meta(self, resposta_meta: dict) -> str:
        erro = resposta_meta.get("error")
        if isinstance(erro, dict):
            mensagem = erro.get("message")
            if mensagem:
                return f"Meta rejeitou template: {mensagem}"
        return "Meta rejeitou template."

    def _mapear_status_template_meta_bruto(self, status_bruto: str | None) -> str | None:
        if not status_bruto:
            return None

        status = str(status_bruto).strip().upper()
        mapa = {
            "APPROVED": "APROVADO",
            "REJECTED": "REJEITADO",
            "PENDING": "EM_REVISAO",
            "PAUSED": "PAUSADO",
            "DISABLED": "DESABILITADO",
        }
        return mapa.get(status, status)

    def _extrair_eventos_template(self, payload: dict) -> list[dict]:
        eventos = []

        for entry in (payload.get("entry") or []):
            for change in (entry.get("changes") or []):
                value = (change or {}).get("value") or {}

                candidatos = [
                    ("message_template_status_update", value.get("message_template_status_update")),
                    ("message_template_quality_update", value.get("message_template_quality_update")),
                    ("message_template_components_update", value.get("message_template_components_update")),
                    ("template_category_update", value.get("template_category_update")),
                ]

                for tipo_campo, conteudo in candidatos:
                    if not conteudo:
                        continue

                    if isinstance(conteudo, list):
                        for item in conteudo:
                            if isinstance(item, dict):
                                item["_tipo_evento_meta"] = tipo_campo
                                eventos.append(item)
                    elif isinstance(conteudo, dict):
                        conteudo["_tipo_evento_meta"] = tipo_campo
                        eventos.append(conteudo)

        return eventos

    def _resolver_template_evento(self, repo: SqlWhatsappTemplateRepository, evento: dict):
        id_template_meta = evento.get("message_template_id") or evento.get("template_id")
        nome_template = (
            evento.get("message_template_name")
            or evento.get("name")
            or evento.get("template_name")
        )
        idioma = evento.get("language") or evento.get("locale")

        if id_template_meta:
            template = repo.buscar_template_por_id_meta(str(id_template_meta))
            if template:
                return template

        if nome_template:
            return repo.buscar_template_por_nome_meta(nome_template, idioma)

        return None

    def _mapear_tipo_evento_template(self, evento: dict) -> str:
        tipo_meta = (evento.get("_tipo_evento_meta") or "").upper()

        mapa = {
            "MESSAGE_TEMPLATE_STATUS_UPDATE": "TEMPLATE_STATUS_UPDATE",
            "MESSAGE_TEMPLATE_QUALITY_UPDATE": "TEMPLATE_QUALITY_UPDATE",
            "MESSAGE_TEMPLATE_COMPONENTS_UPDATE": "TEMPLATE_COMPONENTS_UPDATE",
            "TEMPLATE_CATEGORY_UPDATE": "TEMPLATE_CATEGORY_UPDATE",
        }

        return mapa.get(tipo_meta, "TEMPLATE_EVENTO_META")

    def _mapear_status_template(self, evento: dict) -> str | None:
        status_bruto = (
            evento.get("event")
            or evento.get("status")
            or evento.get("message_template_status")
        )
        if not status_bruto:
            return None

        status = str(status_bruto).strip().upper()

        mapa = {
            "APPROVED": "APROVADO",
            "REJECTED": "REJEITADO",
            "PAUSED": "PAUSADO",
            "PENDING": "EM_REVISAO",
            "PENDING_DELETION": "DESABILITADO",
            "DISABLED": "DESABILITADO",
            "IN_APPEAL": "EM_REVISAO",
        }

        return mapa.get(status, status)

    def _mapear_quality_status(self, evento: dict) -> str | None:
        quality = (
            evento.get("new_quality_score")
            or evento.get("quality_score")
            or evento.get("quality")
        )
        if not quality:
            return None

        quality_normalizado = str(quality).strip().upper()

        if quality_normalizado in {"GREEN", "HIGH"}:
            return "HIGH"
        if quality_normalizado in {"YELLOW", "MEDIUM"}:
            return "MEDIUM"
        if quality_normalizado in {"RED", "LOW"}:
            return "LOW"

        return quality_normalizado

    def _serializar_template(self, row: dict) -> dict:
        return {
            "id_template": row["ID_TEMPLATE"],
            "nome_interno": row["NOME_INTERNO"],
            "nome_template_meta": row["NOME_TEMPLATE_META"],
            "idioma": row["IDIOMA"],
            "categoria_meta": row["CATEGORIA_META"],
            "status_template": row["STATUS_TEMPLATE"],
            "quality_status": row.get("QUALITY_STATUS"),
            "ativo": bool(row.get("ATIVO")),
            "header_tipo": row.get("HEADER_TIPO"),
            "header_texto": row.get("HEADER_TEXTO"),
            "body_texto": row.get("BODY_TEXTO"),
            "footer_texto": row.get("FOOTER_TEXTO"),
            "buttons_json": self._parse_json(row.get("BUTTONS_JSON")),
            "componentes_json": self._parse_json(row.get("COMPONENTES_JSON")),
            "variaveis_json": self._parse_json(row.get("VARIAVEIS_JSON")),
            "id_template_meta": row.get("ID_TEMPLATE_META"),
            "ultimo_evento_meta": row.get("ULTIMO_EVENTO_META"),
            "ultimo_payload_meta": self._parse_json(row.get("ULTIMO_PAYLOAD_META")),
            "criado_por": row.get("CRIADO_POR"),
            "origem_cadastro": row.get("ORIGEM_CADASTRO"),
            "data_criacao": row.get("DATA_CRIACAO"),
            "data_atualizacao": row.get("DATA_ATUALIZACAO"),
            "data_ultima_sincronia": row.get("DATA_ULTIMA_SINCRONIA"),
        }
    
    def _serializar_template_operacional(self, row: dict) -> dict:
        return {
            "id_template": row["ID_TEMPLATE"],
            "nome_interno": row["NOME_INTERNO"],
            "nome_template_meta": row["NOME_TEMPLATE_META"],
            "idioma": row["IDIOMA"],
            "categoria_meta": row["CATEGORIA_META"],
            "quality_status": row.get("QUALITY_STATUS"),
            "header_tipo": row.get("HEADER_TIPO"),
            "header_texto": row.get("HEADER_TEXTO"),
            "body_texto": row.get("BODY_TEXTO"),
            "footer_texto": row.get("FOOTER_TEXTO"),
            "buttons_json": self._parse_json(row.get("BUTTONS_JSON")) or [],
            "componentes_json": self._parse_json(row.get("COMPONENTES_JSON")) or {},
            "variaveis_json": self._parse_json(row.get("VARIAVEIS_JSON")) or [],
            "id_template_meta": row.get("ID_TEMPLATE_META"),
            "data_atualizacao": row.get("DATA_ATUALIZACAO"),
        }

    def _serializar_eventos_template(self, rows: list[dict]) -> list[dict]:
        eventos = []

        for row in rows:
            eventos.append({
                "id_evento_template": row["ID_EVENTO_TEMPLATE"],
                "id_template": row["ID_TEMPLATE"],
                "tipo_evento": row["TIPO_EVENTO"],
                "status_anterior": row.get("STATUS_ANTERIOR"),
                "status_novo": row.get("STATUS_NOVO"),
                "quality_anterior": row.get("QUALITY_ANTERIOR"),
                "quality_novo": row.get("QUALITY_NOVO"),
                "origem_evento": row.get("ORIGEM_EVENTO"),
                "descricao_evento": row.get("DESCRICAO_EVENTO"),
                "payload_evento": self._parse_json(row.get("PAYLOAD_EVENTO")),
                "usuario_responsavel": row.get("USUARIO_RESPONSAVEL"),
                "data_evento": row.get("DATA_EVENTO"),
            })

        return eventos

    def _parse_json(self, valor):
        if not valor:
            return None

        if isinstance(valor, (dict, list)):
            return valor

        try:
            return json.loads(valor)
        except Exception:
            return None
