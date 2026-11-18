from flask import request, jsonify
from flask_smorest import Blueprint
from flask_jwt_extended import create_access_token

from src.infrastructure.repositories.users_repository import Users_Repository
from src.application.use_cases.login_user import LoginUser
from src.presentation.schemas.auth_schema import parse_login
from src.application.services.users_service import enviar_email_recuperacao
from src.application.services.users_service import gerar_codigo
from src.application.services.users_service import hash_token

bp = Blueprint("Login de Mensagens", __name__, url_prefix="/mensagens")


@bp.post("/login")
def login():
    payload = request.get_json(silent=True) or {}

    try:
        username, password = parse_login(payload)
        repo = Users_Repository()
        use_case = LoginUser(repo)
        user = use_case.execute(username, password)

        token = create_access_token(
            identity=str(user["id"]),
            additional_claims={
                "usuario": user.get("username"),
                "vega": user.get("VEGA"),
            },
        )

        return jsonify({"success": True, "data": {**user, "token": token}}), 200
    except Exception:
        return jsonify({"success": False, "message": "Usuario ou senha invalidos"}), 401


@bp.post("/recuperar-senha")
def recuperar_senha():
    email = request.json.get("email")
    repo = Users_Repository()
    usuario = repo.buscar_usuario_por_email(email)
    if not usuario:
        return {"erro": "email invalido"}, 400

    codigo = gerar_codigo()
    token_hash = hash_token(codigo)

    repo.salvar_token(
        usuario_id=usuario["id"],
        token_hash=token_hash,
    )

    enviar_email_recuperacao(email, codigo)

    return {"ok": True}


@bp.post("/validar-codigo")
def validar_codigo():
    email = request.json.get("email")
    codigo = request.json.get("codigo")
    repo = Users_Repository()
    usuario = repo.buscar_usuario_por_email(email)
    if not usuario:
        return {"erro": "Codigo invalido"}, 400

    token_hash = hash_token(codigo)

    registro = repo.buscar_token_valido(usuario["id"], token_hash)

    if not registro:
        return {"erro": "Codigo invalido ou expirado"}, 400

    return {"ok": True}


@bp.post("/redefinir-senha")
def redefinir_senha():
    email = request.json.get("email")
    nova_senha = request.json.get("password")
    codigo = request.json.get("codigo")
    repo = Users_Repository()
    token_hash = hash_token(codigo)
    registro = repo.buscar_token_valido_por_email(email, token_hash)
    if not registro:
        return {"erro": "Codigo invalido"}, 400

    repo.atualizar_senha_usuario(nova_senha, email)
    repo.marcar_token_como_usado(registro["id"])

    return {"ok": True}
