from src.presentation.schemas.hvoice import HvoiceSchema
from src.presentation.schemas.collectsys import (EmitirPixSchema, 
                                                 EmitirBoletoSchema, 
                                                 EmitirBoletoBetaRequest,
                                                 ObterDividaAtivaSchema, 
                                                 TabularSchema,
                                                 PropostaDividaSchema,
                                                 EmitirQRcodeSchema)

from src.presentation.schemas.digital import (TwilioTemplateRequestSchema,
                                             VariaveisNecessariasSchema,
                                              TwilioTemplateInfoSchema,
                                               TwilioTemplateResponseSchema,
                                               EnvioMensagemSchema,
                                               EnvioMensagemResultadoSchema,
                                               EnvioMensagemResponseSchema,
                                               )
from src.presentation.schemas.collectsys import *
from src.presentation.schemas.digital import EnvioMensagemSchema, TwilioTemplateRequestSchema



from marshmallow import Schema, fields

class Erro401Schema(Schema):
    status = fields.Boolean(load_default=False, dump_default=False)
    erro = fields.String()
