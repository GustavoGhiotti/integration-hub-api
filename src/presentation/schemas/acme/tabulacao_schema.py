from marshmallow import Schema, fields, validates, post_load
from types import SimpleNamespace


class TabularBaseSchema(Schema):
    cedente = fields.String(required=True)
    idCliente = fields.Integer(required=True)
    idAcao = fields.Integer(required=True)
    descricaoAcao = fields.String(required=True)
    telefone = fields.String(required=True)

    @post_load
    def make_obj(self, data, **kwargs):
        return SimpleNamespace(**data)
    

#Vega
class DadosComplementarVegaSchema(Schema):
    callId = fields.String(allow_none=True, metadata={"description": "Obrigatório para algumas ações da VEGA."})
    detalheData = fields.String(allow_none=True, metadata={"description": "Obrigatório para algumas ações da VEGA (formatos de data: dd/mm/aaaa, aaaa/mm/dd, dd-mm-aaaa, aaaa-mm-dd)"})
    tipoEnvio = fields.String(allow_none=True, metadata={"description": "Obrigatório para algumas ações da VEGA (email, whatsapp, sms, carta)."})
    detalhe = fields.String(allow_none=True, metadata={"description": "Obrigatório para algumas ações da VEGA."})

    @post_load
    def make_obj(self, data, **kwargs):
        return SimpleNamespace(**data)
    
class TabularVegaSchema(TabularBaseSchema):
    dadosComplementar = fields.Nested(DadosComplementarVegaSchema,required=False,allow_none=True)

#Mu
class DadosComplementarMuSchema(Schema):
    tipoEnvio = fields.String(allow_none=True, metadata={"description": "Obrigatório para algumas ações do Mu (email, whatsapp, sms, carta)."})

class TabularMuSchema(TabularBaseSchema):
    dadosComplementar = fields.Nested(DadosComplementarMuSchema,required=False,allow_none=True)

