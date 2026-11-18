from marshmallow import Schema, fields, validates, validates_schema, ValidationError, validate, post_load
from types import SimpleNamespace

class HvoiceSchema(Schema):
    carteira = fields.String(
        required=True,
        validate=validate.Length(min=1)
    )
    data = fields.Date(required=True)
    data_final = fields.Date(required=False, allow_none=True)
    dataFinal = fields.Date(required=False, allow_none=True, load_only=True)
    produto = fields.String(
        required=True,
        validate=validate.Length(min=1)
    )
    tabulacao = fields.String(
        required=True,
        validate=validate.Length(min=1)
    )
    minsegundos = fields.Integer(required=True)
    maxsegundos = fields.Integer(required=True)
    mintotalmax = fields.Integer(required=True)
    qtdoperador = fields.Integer(required=True)
    

    @validates("carteira")
    @validates("produto")
    @validates("tabulacao")
    def nao_vazio(self, value, **kwargs):
        if value is None or str(value).strip() == "":
            raise ValidationError("campo não pode ser vazio")

        
    
    @validates_schema
    def validar_periodo(self, data, **kwargs):
        data_final = data.get("data_final") or data.get("dataFinal")
        if data_final and data_final < data["data"]:
            raise ValidationError("data_final deve ser maior ou igual a data", field_name="data_final")

    @post_load
    def make_obj(self, data, **kwargs):
        if data.get("dataFinal") and not data.get("data_final"):
            data["data_final"] = data["dataFinal"]
        data.pop("dataFinal", None)
        return SimpleNamespace(**data)
