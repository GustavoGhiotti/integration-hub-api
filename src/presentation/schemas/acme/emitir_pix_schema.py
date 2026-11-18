from marshmallow import Schema, fields, validates, post_load
from types import SimpleNamespace

class EmitirPixSchema(Schema):
    cedente = fields.String(required=True)
    idCliente = fields.Integer(required=True)
    idAcordo = fields.Integer(required=True)
    idCedente = fields.Integer(required=True)

    @post_load
    def make_obj(self, data, **kwargs):
        return SimpleNamespace(**data)

