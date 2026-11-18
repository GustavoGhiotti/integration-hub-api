from marshmallow import Schema, fields, validates, post_load
from types import SimpleNamespace

class VerificaDividaCedenteSchema(Schema):
    idCliente = fields.Integer(required=True)
    cedente = fields.String(required=True)
    data = fields.Date(required=False, allow_none=True)

    @post_load
    def make_obj(self, data, **kwargs):
        return SimpleNamespace(**data)
