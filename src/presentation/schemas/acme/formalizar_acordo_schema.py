from types import SimpleNamespace
from marshmallow import Schema, fields, validates, post_load


class PropostaDividaSchema(Schema):
    idCliente = fields.Integer(required=True)
    idContrato = fields.Integer(required=True)
    dataPagamento = fields.Date(required=True)
    valorEntrada = fields.Float(required=True)
    parcelamento = fields.Integer(required=True)
    condicao = fields.Raw(required=False, allow_none=True)
    
    @post_load
    def make_obj(self, data, **kwargs):
        return SimpleNamespace(**data)