from marshmallow import Schema, fields, validate, post_load
from types import SimpleNamespace


class TwilioTemplateRequestSchema(Schema):
    sidTemplate = fields.String(required=True)
    @post_load
    def make_obj(self, data, **kwargs):
        return SimpleNamespace(**data)


class InfobipTemplateRequestSchema(Schema):
    nomeTemplate = fields.String(required=True)

    @post_load
    def make_obj(self, data, **kwargs):
        return SimpleNamespace(**data)

class VariaveisNecessariasSchema(Schema):
    variaveis = fields.Dict()

class TwilioTemplateInfoSchema(Schema):
    sidTemplate = fields.String()
    telefoneCliente = fields.String()  
    idCedente = fields.Integer()       
    variaveis = fields.Dict()

class TwilioTemplateResponseSchema(Schema):
    status = fields.Boolean()
    necessarioTemplate = fields.Nested(TwilioTemplateInfoSchema)


class EnvioMensagemSchema(Schema):
    telefoneCliente = fields.String(required=True)
    idCedente = fields.Integer(required=True)
    canal = fields.String(required=True)
    sidTemplate = fields.String(required=True)
    variaveis = fields.Dict(required=True)      

    @post_load
    def make_obj(self, data, **kwargs):
        return SimpleNamespace(**data)
    

class EnvioMensagemResultadoSchema(Schema):
    messageSid = fields.String()
    status = fields.String()
    template = fields.String()
    variaveis_enviadas = fields.Dict()

class EnvioMensagemResponseSchema(Schema):
    status = fields.Boolean()
    resultado = fields.Nested(EnvioMensagemResultadoSchema)



