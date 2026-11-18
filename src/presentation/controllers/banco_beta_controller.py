from flask_smorest import Blueprint
from src.infrastructure.security.auth_decorator import token_require
from src.presentation.schemas import Erro401Schema
from src.presentation.schemas.collectsys import EmitirBoletoBetaRequest, EmitirBoletoResponseSchema


bp = Blueprint("Integração Banco Beta", __name__, url_prefix="/BancoBeta")


@bp.post("/emitir-boleto")
@bp.doc(
    description="Método para emitir o boleto exclusivo do Banco Beta",
    summary="Emissão de boleto",
    tag="Negociação Acme"
    )
@bp.arguments(EmitirBoletoBetaRequest, location="json")
@bp.response(200, EmitirBoletoResponseSchema, description="Boleto emitido")
@bp.response(401, Erro401Schema, description="Retorno de erro")
@token_require("/acme")
def emitir(body: EmitirBoletoBetaRequest):
    pass
