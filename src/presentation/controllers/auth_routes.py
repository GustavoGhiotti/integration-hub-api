import base64
from flask import request, jsonify
from flask_smorest import Blueprint
from src.application.services.auth_service import AuthService
from src.presentation.schemas.auth import *

bp = Blueprint("auth", __name__, url_prefix="/auth")
auth_service = AuthService()

@bp.get("/token")
@bp.doc(
    security=[{"BasicAuth": []}],
    description="Rota para obter o token",
    summary="Token"
)
@bp.response(200, TokenResponseSchema)
@bp.response(401, TokenErroSchema)
def gerar_token():
    auth_header = request.headers.get("Authorization")

    # Compatibilidade com clientes que enviam credenciais em headers separados.
    if not auth_header:
        username = request.headers.get("Username")
        password = request.headers.get("Password")
        if username and password:
            basic = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("utf-8")
            auth_header = f"Basic {basic}"

    if not auth_header or not auth_header.startswith("Basic "):
        return jsonify({"erro": "Credenciais ausentes ou invalidas"}), 401

    token, tempo_token = auth_service.autenticar(auth_header)
    if not token:
        return jsonify({"erro": "Usuário ou senha inválidos"}), 401

    return jsonify({
        "token": token,
        "expira_em": f"H:M:S - {str(tempo_token)}"
    }), 200

    
