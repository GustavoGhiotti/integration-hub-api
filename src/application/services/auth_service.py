from flask_jwt_extended import create_access_token
from src.infrastructure.repositories.sql_auth_token import UserAPI
from datetime import timedelta
import base64

class AuthService:
    def __init__(self):
        self.repo = UserAPI()

    def autenticar(self, auth_header:str):

        if not auth_header or not auth_header.startswith("Basic "):
            return None, None

        try:
            #Pega o valor Base64
            base64_credentials = auth_header.split(" ")[1]
            decoded_credentials = base64.b64decode(base64_credentials).decode("utf-8")
            usuario, senha = decoded_credentials.split(":")
        except Exception:
            return None, None


        user = self.repo.consultar(usuario, senha)
        if not user or not user["ATIVO"]:
            return None, None

        if senha != user["PASSWORD"]:
            return None, None

        expira_em = self.expiracao_por_rota(user["ID"])

        token = create_access_token(identity=str(user["ID"]), 
                                    additional_claims= {"usuario": user["USERNAME"],
                                                        "rotas": user["ROTAS_PERMITIDAS"]},
                                    expires_delta=expira_em
                                    )
        return token, expira_em

    def expiracao_por_rota(self, id_usuario:int):
        match id_usuario:
            case 1:
                expired = timedelta(hours=12)
            case 3:
                expired = timedelta(minutes=20)
            case _:
                expired = timedelta(hours=1)

        return expired
            
