from marshmallow import Schema, ValidationError, fields, post_load, validates, validates_schema
from src.domain.entities.documento import ValidacaoDocumento
from src.domain.exceptions.usuario_exception import CpfCnpjInvalidoException
from types import SimpleNamespace


def _somente_digitos(valor) -> str:
    return "".join(char for char in str(valor or "") if char.isdigit())


def _eh_payload_vcom(data: dict) -> bool:
    origem = str(data.get("origem") or "").strip().lower()
    if origem == "vcom":
        return True

    if data.get("codigoCalculo") is not None or data.get("codigoBoleto") is not None:
        return True

    if data.get("idAcordo") is not None and data.get("idCliente") is None and data.get("idCedente") is None:
        return True

    id_cliente = _somente_digitos(data.get("idCliente"))
    if len(id_cliente) in (10, 11, 13, 14):
        return True

    id_contrato = _somente_digitos(data.get("idContrato"))
    if len(id_contrato) >= 11 and len(id_contrato) != 8:
        return True

    for campo in ("cedente", "idCedente", "idCredor"):
        valor = data.get(campo)
        if valor is None:
            continue
        try:
            if int(valor) >= 1000:
                return True
        except (TypeError, ValueError):
            continue

    return False


def _validar_inteiros_collectsys(data: dict, campos: tuple[str, ...]) -> None:
    if _eh_payload_vcom(data):
        return

    erros = {}
    for campo in campos:
        valor = data.get(campo)
        if valor is None:
            erros[campo] = ["Missing data for required field."]
            continue
        try:
            int(valor)
        except (TypeError, ValueError):
            erros[campo] = ["Not a valid integer."]

    if erros:
        raise ValidationError(erros)


def _converter_inteiros_collectsys(data: dict, campos: tuple[str, ...]) -> dict:
    if _eh_payload_vcom(data):
        return data

    for campo in campos:
        if campo in data and data[campo] is not None:
            data[campo] = int(data[campo])
    return data


# ==============================
# HEADERS
# ==============================
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

class VerificaDividaCedenteSchema(Schema):
    idCliente = fields.Raw(required=True)
    cedente = fields.String(required=True)
    data = fields.Date(required=False, allow_none=True)

    @validates_schema
    def validar_fluxo_collectsys(self, data, **kwargs):
        _validar_inteiros_collectsys(data, ("idCliente",))

    @post_load
    def make_obj(self, data, **kwargs):
        data = _converter_inteiros_collectsys(data, ("idCliente",))
        return SimpleNamespace(**data)

class PropostaParceladoSchema(Schema):
    idCliente = fields.Raw(required=True)
    idContrato = fields.Raw(required=True)
    data = fields.Date(required=False, allow_none=True)


    @validates_schema
    def validar_fluxo_collectsys(self, data, **kwargs):
        _validar_inteiros_collectsys(data, ("idCliente", "idContrato"))

    @post_load
    def make_obj(self, data, **kwargs):
        data = _converter_inteiros_collectsys(data, ("idCliente", "idContrato"))
        return SimpleNamespace(**data)

class PropostaDividaSchema(Schema):
    idCliente = fields.Raw(required=True)
    idContrato = fields.Raw(required=True)
    dataPagamento = fields.Date(required=True)
    valorEntrada = fields.Float(required=True)
    parcelamento = fields.Integer(required=True)
    condicao = fields.Raw(
        required=False,
        allow_none=True,
        metadata={
            "description": (
                "Campo opcional e específico para alguns cedentes, como BETA e Nu. "
                "Informa a quantidade de parcelas usada na negociação parcial. "
                "Não enviar quando o cedente não utilizar essa regra."
            )
        },
    )
    idOpcaoParcelamento = fields.String(
        required=False,
        allow_none=True,
        metadata={
            "description": (
                "Campo opcional, utilizado somente em negociações de cedentes integrados "
                "à VCOM. Identifica a opção de parcelamento retornada na consulta."
            )
        },
    )
    idCampanhaCalculo = fields.String(
        required=False,
        allow_none=True,
        metadata={
            "description": (
                "Campo opcional, utilizado somente em negociações de cedentes integrados "
                "à VCOM. Identifica a campanha de cálculo retornada na consulta."
            )
        },
    )

    @validates_schema
    def validar_fluxo_collectsys(self, data, **kwargs):
        _validar_inteiros_collectsys(data, ("idCliente", "idContrato"))

    @post_load
    def make_obj(self, data, **kwargs):
        data = _converter_inteiros_collectsys(data, ("idCliente", "idContrato"))
        return SimpleNamespace(**data)


class TabularBaseSchema(Schema):
    cedente = fields.Raw(required=True)
    idCliente = fields.Raw(required=True)
    idContrato = fields.Raw(required=False, allow_none=True)
    idAcao = fields.Integer(required=True)
    descricaoAcao = fields.String(required=True)
    telefone = fields.Raw(required=True)

    @validates_schema
    def validar_fluxo_collectsys(self, data, **kwargs):
        _validar_inteiros_collectsys(data, ("idCliente",))

    @post_load
    def make_obj(self, data, **kwargs):
        data = _converter_inteiros_collectsys(data, ("idCliente",))
        for campo in ("cedente", "telefone"):
            if campo in data and data[campo] is not None:
                data[campo] = str(data[campo])
        return SimpleNamespace(**data)

class TabularVegaSchema(TabularBaseSchema):
    callId = fields.String(allow_none=True, metadata={"description": "Obrigatório para algumas ações da VEGA."})
    detalheData = fields.String(allow_none=True, metadata={"description": "Obrigatório para algumas ações da VEGA (formatos de data: dd/mm/aaaa, aaaa/mm/dd, dd-mm-aaaa, aaaa-mm-dd)"})
    tipoEnvio = fields.String(allow_none=True, metadata={"description": "Obrigatório para algumas ações da VEGA (email, whatsapp, sms, carta)."})
    detalhe = fields.String(allow_none=True, metadata={"description": "Obrigatório para algumas ações da VEGA."})

class TabularCobrancaSchema(TabularBaseSchema):
    tipoEnvio = fields.String(allow_none=True, metadata={"description": "Obrigatório para algumas ações do Mu (email, whatsapp, sms, carta)."})


class TabularCobrancaMuSchema(TabularBaseSchema):
    nmDetalhe = fields.String(required=True)
    vlrDetalhe = fields.String(required=True)
    qtdDetalhe = fields.Integer(required=True)

class TabularSchema(TabularBaseSchema):
    callId = fields.String(allow_none=True)
    detalheData = fields.String(allow_none=True)
    tipoEnvio = fields.String(allow_none=True)
    detalhe = fields.String(allow_none=True)

    nmDetalhe = fields.String(allow_none=True)
    vlrDetalhe = fields.Raw(allow_none=True)
    qtdDetalhe = fields.Integer(allow_none=True)

class EmitirBoletoSchema(Schema):
    idCliente = fields.Raw(required=True)
    idAcordo = fields.Integer(required=True)
    parcela = fields.Integer(required=True)
    idCedente = fields.Integer(required=True)
    email = fields.Email(required=False, allow_none=True)
    cpfCnpj = fields.Raw(required=False, allow_none=True)

    @validates_schema
    def validar_fluxo_collectsys(self, data, **kwargs):
        _validar_inteiros_collectsys(data, ("idCliente", "idAcordo", "parcela", "idCedente"))

    @post_load
    def make_obj(self, data, **kwargs):
        data = _converter_inteiros_collectsys(data, ("idCliente", "idAcordo", "parcela", "idCedente"))
        return SimpleNamespace(**data)

class EmitirBoletoBetaRequest(EmitirBoletoSchema):
    email = fields.Email(required=True)

    @post_load
    def make_obj(self, data, **kwargs):
        return SimpleNamespace(**data)
class EmitirPixSchema(Schema):
    cedente = fields.String(required=True)
    idCliente = fields.Integer(required=True)
    idAcordo = fields.Integer(required=True)
    idCedente = fields.Integer(required=True)

    @post_load
    def make_obj(self, data, **kwargs):
        return SimpleNamespace(**data)

class EmitirQRcodeSchema(Schema):
    idCliente = fields.Integer(required=True)
    idAcordo = fields.Integer(required=True)
    codigoPix = fields.String(required=True)

    @post_load
    def make_obj(self, data, **kwargs):
        return SimpleNamespace(**data)


class LinhaDigitavelSchema(Schema):
    idCliente = fields.Integer(required=True)
    idAcordo = fields.Integer(required=True)

    @post_load
    def make_obj(self, data, **kwargs):
        return SimpleNamespace(**data)

# ==============================
# RESPONSES
# ==============================


#rota /obter-divida-ativa
class ClienteSchema(Schema):
    nome = fields.String()
    nomeCompleto = fields.String()
    cpfCnpj = fields.String()
    # telefone = fields.String()
    # email = fields.String()

class ContratoDividaShema(Schema):
    grupo = fields.String()
    idContrato = fields.Raw()

class DividaSchema(Schema):
    idCliente = fields.Raw()
    cedente = fields.String()
    possuiDividaAtiva = fields.Boolean()
    mensagem = fields.String()
    segmento = fields.String(allow_none=True)
    contratos = fields.List(fields.Nested(ContratoDividaShema))
    valor = fields.Float()
    diasAtraso = fields.Integer()


class ObterDividasResponse(Schema):
    status = fields.Boolean()
    possuiDividaAtiva = fields.Boolean()
    mensagem = fields.String()
    cliente = fields.Nested(ClienteSchema)
    dividas = fields.List(fields.Nested(DividaSchema))

#===================================================================#

#verifica-divida-cedente
class AvistaSchema(Schema):
    pagamento = fields.Date()
    valor = fields.Float()
    mensagem = fields.String()

class PropostaSemDescontoSchema(Schema):
    valor = fields.Float()
    mensagem = fields.String()

class ValorOriginalSchema(Schema):
    atrasadoDesde = fields.Date()
    atraso = fields.Integer()
    valor = fields.Float()
    parcelasEmAtraso = fields.Raw()
    quantidadeParcelasEmAtraso = fields.Integer()
    quantidadeParcelas = fields.Integer()

class ContratoUtilizadoSchema(Schema):
    contrato = fields.Raw()
    parcelasEmAtraso = fields.Raw()
    produto = fields.String(allow_none=True)
    valorOriginal = fields.Float()
    valorAtualizado = fields.Float()
    NumeroContratoBanco = fields.String()

class ParcelaAcordoSchema(Schema):
    idAcordo = fields.Raw()
    valor = fields.Float()
    parcela = fields.Integer()
    dataVencimento = fields.String()

class ContratoCedenteSchema(Schema):
    propostaAvista = fields.Nested(AvistaSchema)
    propostaSemDesconto = fields.Nested(PropostaSemDescontoSchema)
    valorOriginal = fields.Nested(ValorOriginalSchema)
    quantidadeContratos = fields.Integer()
    grupo = fields.String()
    metodoNegociacao = fields.String()
    contratosUtilizados = fields.List(fields.Nested(ContratoUtilizadoSchema))
    contrato = fields.Raw()
    contratoExterno = fields.String()
    codigoTitulo = fields.Integer()
    produto = fields.String(allow_none=True)
    quantidadeParcelas = fields.String()
    parcelas = fields.List(fields.Nested(ParcelaAcordoSchema))


class VerificarCedenteResponse(Schema):
    status = fields.Boolean()
    contratos = fields.List(fields.Nested(ContratoCedenteSchema))

#===================================================================#
# /propostas-parcelado
class PropostaItemSchema(Schema):
    valorEntrada = fields.Float()
    mensagem = fields.String()
    valorParcelas = fields.Float()
    valorTotalAcordo = fields.Float()
    qtdParcelas = fields.Integer()
    parcelamentoMax = fields.Integer()
    dataPagamento = fields.String()
    detalhe = fields.String()
    tipoProposta = fields.String()
    boleto = fields.Nested("BoletoSchema")


class ParcelamentoSchema(Schema):
    propostas = fields.Raw()
    nomeCedente = fields.String()
    idCliente = fields.Raw()
    contrato = fields.Raw()
    produto = fields.String(allow_none=True)
    quantidadeContratos = fields.Integer()
    metodoNegociacao = fields.String()
    contratosUtilizados = fields.List(fields.Nested(ContratoUtilizadoSchema))


class PropostasParcelamentoResponse(Schema):
    status = fields.Boolean()
    parcelamento = fields.Nested(ParcelamentoSchema)

#===================================================================#
# /proposta-divida
class PropostaDividaSchema(Schema):
    idCliente = fields.Raw(required=True)
    idContrato = fields.Raw(required=True)
    valorEntrada = fields.Float(required=True)
    parcelamento = fields.Integer(required=True)
    dataPagamento = fields.Date(required=True)
    condicao = fields.Raw(
        required=False,
        allow_none=True,
        metadata={
            "description": (
                "Campo opcional e específico para alguns cedentes, como BETA e Nu. "
                "Informa a quantidade de parcelas usada na negociação parcial. "
                "Não enviar quando o cedente não utilizar essa regra."
            )
        },
    )
    idOpcaoParcelamento = fields.String(
        required=False,
        allow_none=True,
        metadata={
            "description": (
                "Campo opcional, utilizado somente em negociações de cedentes integrados "
                "à VCOM. Identifica a opção de parcelamento retornada na consulta."
            )
        },
    )
    idCampanhaCalculo = fields.String(
        required=False,
        allow_none=True,
        metadata={
            "description": (
                "Campo opcional, utilizado somente em negociações de cedentes integrados "
                "à VCOM. Identifica a campanha de cálculo retornada na consulta."
            )
        },
    )

    @validates_schema
    def validar_fluxo_collectsys(self, data, **kwargs):
        _validar_inteiros_collectsys(data, ("idCliente", "idContrato"))

    @post_load
    def make_obj(self, data, **kwargs):
        data = _converter_inteiros_collectsys(data, ("idCliente", "idContrato"))
        return SimpleNamespace(**data)

class PropostaSchema(Schema):
    origem = fields.String()
    valorEntrada = fields.Float()
    mensagem = fields.String()
    dataPagamento = fields.String()
    idOpcaoParcelamento = fields.String()
    idCampanhaCalculo = fields.String()
    tipoNegociacao = fields.String()
    valorParcelas = fields.Float()
    valorTotalAcordo = fields.Float()
    quantidadeParcelas = fields.Integer()
    detalhe = fields.String()
    tipoProposta = fields.String()
    boleto = fields.Nested("BoletoSchema")
    codigoCalculo = fields.Integer()
    contrato = fields.Raw()
    produto = fields.String(allow_none=True)
    quantidadeContratos = fields.Integer()
    metodoNegociacao = fields.String()
    contratosUtilizados = fields.List(fields.Nested(ContratoUtilizadoSchema))

class PropostaDividaResponseSchema(Schema):
    status = fields.Boolean()
    proposta = fields.Nested(PropostaSchema)

#===================================================================#
# /formalizar
class InformacoesAcordoSchema(Schema):
    idCliente = fields.Raw()
    vencimentoPagamento = fields.String()
    valorEntrada = fields.Float()
    valorParcelas = fields.Float()
    quantidadeParcelas = fields.Integer()
    valorTotalAcordo = fields.Float()
    tipoNegociacao = fields.String()
    detalhe = fields.String()
    tipoProposta = fields.String()
    quantidadeContratos = fields.Integer()
    metodoNegociacao = fields.String()
    contratosUtilizados = fields.List(fields.Nested(ContratoUtilizadoSchema))


class FormalizarAcordoResponseSchema(Schema):
    status = fields.Boolean()
    idAcordo = fields.Raw()
    informacoesAcordo = fields.Nested(InformacoesAcordoSchema)

#===================================================================#
# /tabular
class TabularResponse(Schema):
    status = fields.Boolean()
    tabulacao = fields.String()

#===================================================================#
# /emitir-boleto
class BoletoSchema(Schema):
    boletoEmitidoId = fields.Integer()
    nomeBoleto = fields.String()
    urlBoleto = fields.String()
    linhaDigitavel = fields.String()
    codigoBarras = fields.String()
    valor = fields.Raw()
    vencimento = fields.String()
    statusBoleto = fields.String()
    statusRegistro = fields.String()
    mensagem = fields.String()
    erro = fields.String()

class EmitirBoletoResponseSchema(Schema):
    status = fields.Boolean()
    boleto = fields.Nested(BoletoSchema)

#===================================================================#
# /emitir-pix
class EmitirPixResponse(Schema):
    status = fields.String()
    mensagem = fields.String()
    codigoPix = fields.String()

#===================================================================#
# /emitir-qrcode-pix
class QRcodeSchema(Schema):
    nomeArquivo = fields.String()
    urlArquivo = fields.String()
    mensagem = fields.String()
    erro = fields.String()

class EmitirQRcodeResponseSchema(Schema):
    status = fields.Boolean()
    QRcode = fields.Nested(QRcodeSchema)

#===================================================================#
# /linha-digitavel
class LinhaDigitavelResponseSchema(Schema):
    status = fields.Boolean()
    linhaDigitavel = fields.String()

class UploadArquivoResponseSchema(Schema):
    status = fields.Boolean()
    nomeBoleto = fields.String()
    urlBoleto = fields.String()
    mensagem = fields.String()
