from marshmallow import Schema, fields

class TokenResponseSchema(Schema):
    token = fields.String()
    expira_em = fields.String()

class TokenErroSchema(Schema):
    erro = fields.String()
