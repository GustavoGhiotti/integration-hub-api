from flask import request, g
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity, get_jwt
from functools import wraps
from src.infrastructure.repositories.sql_auth_token import AuthAPI
from src.domain.exceptions import TokenInvalido
from src.domain.entities.usuario_collectsys import UsuarioCollectSys
from src.infrastructure.repositories.sql_collectsys_repository import SqlCollectSysRepository
from src.shared.utils.env_load import DB_66
from src.infrastructure.logging.logger_config import set_log_context

import re

def token_required_collectsys(f):
    """Decorador que valida o token antes de acessar a rota"""
    """
        :arg = chaves passada na requisição
        :kwargs = valores passado na requisição
        Exmeplo: {"args": "kwargs"}
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get("Authorization")
        
        if not token:
            raise TokenInvalido("Token de autorização ausente")

        token = re.sub(r"^Bearer\s+", "", token, flags=re.IGNORECASE).strip()

        validar = AuthAPI().obter_token(token)

        dados = validar[0] if validar else None 
        if not dados:
            raise TokenInvalido("Token inválido")

        # Atualiza contexto de log com o usuário do token CollectSys
        forwarded_for = request.headers.get("X-Forwarded-For", "")
        client_ip = forwarded_for.split(",")[0].strip() if forwarded_for else request.remote_addr
        set_log_context(
            request_id=getattr(request, "id", None),
            user=dados.get("USUARIO", "-"),
            path=request.path,
            method=request.method,
            ip=client_ip,
            execution_id=getattr(request, "id", None),
            auth_type="API_TOKEN",
        )

        
        g.collectsys = UsuarioCollectSys(dados["USUARIO"], dados["SENHA"])

        return f(*args, **kwargs)
    
    return decorated


def token_require(rota_permitida):
    """Decorador que valida o token antes de acessar a rota"""
    """
        :arg = chaves passada na requisição
        :kwargs = valores passado na requisição
        Exmeplo: {"args": "kwargs"}
    """
    def wrapper(fn):
        @wraps(fn)
        def decorated(*args, **kwargs):
            token = request.headers.get("Authorization")
            
            if not token:
                raise TokenInvalido("Token de autorização ausente")

            verify_jwt_in_request()

            id_usuario = int(get_jwt_identity())
            complementos = get_jwt()

            # Atualiza contexto de log com o usuário do JWT
            forwarded_for = request.headers.get("X-Forwarded-For", "")
            client_ip = forwarded_for.split(",")[0].strip() if forwarded_for else request.remote_addr
            usuario = complementos.get("usuario") or str(id_usuario)
            set_log_context(
                request_id=getattr(request, "id", None),
                user=usuario,
                path=request.path,
                method=request.method,
                ip=client_ip,
                execution_id=getattr(request, "id", None),
                user_id=id_usuario,
                auth_type="JWT",
            )
            
            #Verifica se as rotas permitidas de cada provedor (caso ID = 1 é o usuário do DEV)
            if (rota_permitida not in complementos["rotas"] and id_usuario != 1) :
                raise TokenInvalido("Acesso negado a esta rota")


            if rota_permitida == "/acme":
                resultado = SqlCollectSysRepository(DB_66, "DB_DESENVOLVIMENTO").obter_usuario_collectsys(id_usuario)
                g.collectsys = UsuarioCollectSys(resultado["USUARIO"], resultado["SENHA"])

            
            return fn(*args, **kwargs)
 
        return decorated 
    
    return wrapper
