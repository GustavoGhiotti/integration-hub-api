from marshmallow import Schema, fields, validates, post_load
from types import SimpleNamespace
from src.domain.entities.documento import ValidacaoDocumento
from src.domain.exceptions.usuario_exception import CpfCnpjInvalidoException

class ObterDividaAtivaSchema(Schema):
    cpfCnpj = fields.String(required=True)

    @validates("cpfCnpj")
    def validar_documento(self, value, **kwargs):
        validador = ValidacaoDocumento(value)
        documento_limpo = validador.remove_caracteres()

        if not documento_limpo:
            raise CpfCnpjInvalidoException("CPF/CNPJ é obrigatório")

        if not validador.validar_documento():
            raise CpfCnpjInvalidoException("Documento inválido")
    
    @post_load
    def make_obj(self, data, **kwargs):
        return SimpleNamespace(**data)