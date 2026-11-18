import time
import uuid
import threading
from flask import Flask, request, jsonify, make_response, g, redirect
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_jwt_extended import JWTManager
from flask_smorest import Api

from secrets import token_urlsafe
from datetime import datetime

from src.infrastructure.queue.config_queue import start_workers
from src.presentation.controllers import *
from src.presentation.error import register_error_handles
from src.infrastructure.logging.logger_config import setup_global_logger, set_log_context
from src.infrastructure.logging.api_audit_http import register_api_audit
from src.shared.utils.env_load import JWT_SECRET
from src.domain.utils.agendador import *
from src.infrastructure.database.sql_server_connection import *
from src.infrastructure.external.telegram.telegram_bot import TelegramBot
from src.presentation.schemas.collectsys import (
        TabularVegaSchema,
        TabularCobrancaSchema,
        TabularCobrancaMuSchema,
    )


#Importar o front
import os
from flask import send_from_directory
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "frontend/dist")
CORS_ALLOWED_ORIGINS = {"http://localhost:8080", "http://127.0.0.1:8080"}


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "sim", "on"}


def register_request_middleware(app: Flask, logger):
    """
    registra o início e fim de cada requisição,
    com ID único e contexto de log completo 
    (rota, IP, método, CPF etc.)
    """

    LOGS_IGNORADOS = ("/sendgrid", "/infobip")
    @app.before_request
    def start_timer():
        # Marca o início da requisição
        request.start_time = time.time()
        request.id = str(uuid.uuid4())
        forwarded_for = request.headers.get("X-Forwarded-For", "")
        client_ip = forwarded_for.split(",")[0].strip() if forwarded_for else request.remote_addr

        # Define o contexto para logs
        set_log_context(
            request_id=request.id,
            user=request.headers.get("cpfCnpj", "-"),
            path=request.path,
            method=request.method,
            ip=client_ip,
            execution_id=request.id,
            reset=True,
        )

        # Ignorar rotas de start
        if request.path.startswith(LOGS_IGNORADOS):
            return

        # Log de início da requisição
        logger.info("Iniciando requisição")

    @app.after_request
    def log_request(response):
        # Ignorar rotas de resposta
        if request.path.startswith(LOGS_IGNORADOS):
            return response


        # Calcula a duração da requisição
        duration = time.time() - getattr(request, "start_time", time.time())

        # Log de finalização com status e tempo
        logger.info(f"Finalizada - Status={response.status_code} - Tempo={duration:.3f}s")

        # Inclui o ID da requisição no cabeçalho de resposta (útil para rastreamento externo)
        response.headers["X-Request-ID"] = request.id
        return response


def register_security_middlewares(app: Flask):
    @app.before_request
    def set_csp_nonce():
        # Define sempre um nonce válido
        g.csp_nonce = token_urlsafe(16)

    #Security
    @app.after_request
    def apply_security_headers(response):
        path = request.path
        nonce = getattr(g, "csp_nonce", None)
        if not nonce:
            nonce = token_urlsafe(16)
            g.csp_nonce = nonce

        # CSP base - nível alto de segurança
        if path.startswith(("/docs", "/redoc", "/openapi.json")):
            csp = (
                "default-src 'none'; "
                "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "img-src 'self' data: https://cdn.jsdelivr.net; "
                "font-src 'self' https://cdn.jsdelivr.net; "
                "connect-src 'self' https://cdn.jsdelivr.net; "
                "frame-ancestors 'none'; "
                "object-src 'none'; "
            )

        else:
            # Aplicação principal
            csp = (
                "default-src 'none'; "
                f"script-src 'self' 'nonce-{nonce}'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data:; "
                "font-src 'self'; "
                "connect-src 'self'; "
                "base-uri 'self'; "
                "form-action 'self'; "
                "frame-ancestors 'none'; "
                "object-src 'none'; "
            )

        response.headers["Content-Security-Policy"] = csp

        # Segurança de transporte e conteúdo
        response.headers["Strict-Transport-Security"] = (
            "max-age=63072000; includeSubDomains; preload"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"  # redundante com frame-ancestors, mas ok
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Restringe APIs poderosas do navegador
        response.headers["Permissions-Policy"] = (
            "geolocation=(), microphone=(), camera=(), payment=(), usb=(), "
            "fullscreen=(self)"
        )

        # Desativar X-XSS-Protection (mecanismo antigo e problemático em alguns casos)
        response.headers["X-XSS-Protection"] = "0"

        # Remover exposição do servidor
        response.headers.pop("Server", None)
        response.headers.pop("X-Powered-By", None)

        return response


def register_cors_middleware(app: Flask):
    def _apply_cors_headers(response):
        origin = request.headers.get("Origin")
        if origin in CORS_ALLOWED_ORIGINS:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Vary"] = "Origin"
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = request.headers.get(
                "Access-Control-Request-Headers",
                "Authorization, Content-Type"
            )
        return response

    @app.before_request
    def handle_cors_preflight():
        if request.method == "OPTIONS" and request.headers.get("Origin") in CORS_ALLOWED_ORIGINS:
            return _apply_cors_headers(make_response("", 204))

    @app.after_request
    def apply_cors_headers(response):
        return _apply_cors_headers(response)


def config_jwt(app:Flask):
    app.config["JWT_SECRET_KEY"] = JWT_SECRET

    JWTManager(app)



def create_docs(app: Flask):

    app.config["API_TITLE"] = "API Grupo Acme"
    app.config["API_VERSION"] = "v1"
    app.config["OPENAPI_VERSION"] = "3.0.3"
    app.config["OPENAPI_JSON_PATH"] = "openapi.json"

    # Rota /docs
    app.config["OPENAPI_URL_PREFIX"] = "/docs"
    app.config["OPENAPI_SWAGGER_UI_PATH"] = ""
    app.config["OPENAPI_SWAGGER_UI_URL"] = "https://cdn.jsdelivr.net/npm/swagger-ui-dist/"
    app.config["OPENAPI_SWAGGER_UI_FAVICON"] = "/src/static/images/favicon.ico"
    
    app.config["OPENAPI_SWAGGER_UI_CONFIG"] = {
                                                "fetch": {
                                                    "credentials": "same-origin"
                                                }
                                            }
    app.config["SMOREST_DISABLE_422"] = True
    app.config["API_SPEC_OPTIONS"] = {
                                        "components": {
                                            "securitySchemes": {
                                                "BearerAuth": {
                                                    "type": "http",
                                                    "scheme": "bearer",
                                                    "bearerFormat": "JWT"
                                                },
                                                "BasicAuth": {
                                                    "type": "http",
                                                    "scheme": "basic"
                                                }
                                            }
                                        },
                                        "security": [{"BearerAuth": []}],
                                    }

    api = Api(app)


    api.spec.components.schema("TabularVegaSchema", schema=TabularVegaSchema)
    api.spec.components.schema("TabularCobrancaSchema", schema=TabularCobrancaSchema)
    api.spec.components.schema("TabularCobrancaMuSchema", schema=TabularCobrancaMuSchema)

    api.register_blueprint(bp_auth)
    api.register_blueprint(bp_collectsys)
    api.register_blueprint(bp_digital)
    api.register_blueprint(bp_hvoice)
    api.register_blueprint(bp_upload)

    return api


def create_app():
    app = Flask(__name__)
    app.json.sort_keys = False
    app.config["JSON_SORT_KEYS"] = False
    app.url_map.strict_slashes = False
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)

    #Criando validação JWT
    config_jwt(app)    

    start_workers()

    # A sincronizacao da Twilio e um processo auxiliar. Em homologacao ela
    # fica desligada por padrao para a indisponibilidade externa nao poluir o
    # startup nem gerar chamadas periodicas desnecessarias.
    homologacao = env_bool("HOMOLOGACAO")
    if env_bool("ENABLE_TEMPLATE_SCHEDULER", default=not homologacao):
        iniciar_template_scheduler()


    # Logger global
    global_logger = setup_global_logger(json_output=False)
    app.logger.handlers.clear()
    for handler in global_logger.handlers:
        app.logger.addHandler(handler)
    app.logger.setLevel(global_logger.level)
    app.logger.propagate = False

    # Middleware global de auditoria
    register_request_middleware(app, global_logger)
    register_api_audit(app)

    #Registro de segurança no cabeçalho da API
    register_security_middlewares(app)
    register_cors_middleware(app)

    # Rate limiter global
    limiter = Limiter(
        key_func=get_remote_address,
        app=app,
        default_limits=["20 per seconds"],  # limite genérico
        storage_uri="memory://"
    )
    
    @limiter.request_filter
    def ignorar_rate_limit_webhooks_externos():
        return request.path in {
            "/monitoria-whatsapp/webhook/meta",
        }

    # Exclui os webhooks externos do limitador (nao pode perder eventos)
    limiter.exempt(bp_sendgrid)
    limiter.exempt(bp_infobip)


    # Rota de verificação (home)
    @app.route("/", methods=["GET"])
    def home():
        return send_from_directory(FRONTEND_DIR, "index.html")

    @app.route("/debug/headers", methods=["GET"])
    def debug_headers():
        if not app.debug:
            return jsonify({"success": False, "message": "Not Found"}), 404
        return jsonify({
            "remote_addr": request.remote_addr,
            "x_forwarded_for": request.headers.get("X-Forwarded-For"),
            "x_forwarded_proto": request.headers.get("X-Forwarded-Proto"),
            "headers": dict(request.headers),
        })

    @app.route("/<path:path>")
    def serve_static_files(path):
        return send_from_directory(FRONTEND_DIR, path)
    
    @app.errorhandler(404)
    def spa_fallback(e):

        static_ext = (
            ".js", ".css", ".png", ".jpg", ".jpeg", ".svg",
            ".ico", ".json", ".map", ".woff", ".woff2", ".ttf"
        )

        path = request.path

        # Se for arquivo estático inexistente → 404 JSON
        if path.endswith(static_ext):
            return jsonify({
                "code": 404,
                "error": "Not Found",
                "description": "Arquivo estático não encontrado."
            }), 404

        # Senão → React
        return send_from_directory(FRONTEND_DIR, "index.html")

    # Registro de rotas sem documentação
    #app.register_blueprint(bp_sendgrid, url_prefix="/sendgrid")
    app.register_blueprint(bp_sms, url_prefix="/sms")
    app.register_blueprint(bp_ad, url_prefix="/ad")
    app.register_blueprint(bp_infobip, url_prefix="/infobip")
    app.register_blueprint(bp_easycollector, url_prefix="/easycollector")
    app.register_blueprint(bp_acionamento, url_prefix="/api/acionamento")
    app.register_blueprint(bp_mensagens, url_prefix="/api/mensagens")
    app.register_blueprint(bp_meta_webhook, url_prefix="/monitoria-whatsapp")
    app.register_blueprint(bp_gmail, url_prefix="/gmail")

    #Registro da documentação
    create_docs(app)
    #Adiciona o icon na documentação
    @app.route('/favicon.ico')
    def favicon():
        return send_from_directory(
            os.path.join(app.root_path, 'src','static', 'images'),
            'favicon.ico',
            mimetype='image/vnd.microsoft.icon'
            )
    
    @app.before_request
    def fix_docs_slash():
        if request.path == "/docs/":
            return redirect("/docs", code=301)

    #Registro de handlers globais
    register_error_handles(app)

    # ATENÇÃO: o consumidor do SendGrid NÃO é iniciado aqui de propósito.
    # Sob IIS/wfastcgi (e Waitress) a API roda em VÁRIOS processos de worker, e
    # cada um iniciaria seus próprios consumidores -> duplicação e contenção no
    # banco. O consumidor roda em UM processo dedicado: `python run_consumer.py`
    # (configurado como um serviço à parte). A API web só recebe o webhook e grava
    # na RAW; o processamento acontece no processo dedicado.

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=8030, debug=False)
