from flask import jsonify
from flask_smorest import Blueprint
from src.application.services.collectsys import *
from src.infrastructure.security.auth_decorator import token_require
from src.infrastructure.logging.logger_config import setup_logger
from src.presentation.schemas.collectsys import *
from src.presentation.schemas import *
from src.shared.utils.xml_tratamentos import *
from src.application.services.collectsys.meios_pagamentos_service import *
from src.application.services.collectsys.dados_vega_service import *
from src.application.services.vcom import VcomNegociacaoService
from src.presentation.response_dto_selector import obter_negociacao_response_dto
from src.domain.entities.cedentes import CEDENTES_BETA
from datetime import date
import asyncio


bp = Blueprint("Acme", __name__, url_prefix="/acme")

log = setup_logger("collectsys", "collectsys.log")
NegociacaoResponseDTO = obter_negociacao_response_dto()


def _somente_digitos(valor) -> str:
    return "".join(char for char in str(valor or "") if char.isdigit())


def _tem_tamanho_documento(valor) -> bool:
    return len(_somente_digitos(valor)) in (10, 11, 13, 14)


def _tem_contrato_vcom(valor) -> bool:
    digitos = _somente_digitos(valor)
    return len(digitos) >= 11 and len(digitos) != 8


def _tem_padrao_id_collectsys(body) -> bool:
    id_cliente = _somente_digitos(getattr(body, "idCliente", None))
    id_contrato = _somente_digitos(getattr(body, "idContrato", None))
    return len(id_cliente) == 8 and (not id_contrato or len(id_contrato) == 8)


def _eh_vcom(body) -> bool:
    origem = str(getattr(body, "origem", "") or "").strip().lower()
    if origem == "vcom":
        return True

    if getattr(body, "codigoCalculo", None) is not None or getattr(body, "codigoBoleto", None) is not None:
        return True

    if (
        getattr(body, "idAcordo", None) is not None
        and getattr(body, "idCliente", None) is None
        and getattr(body, "idCedente", None) is None
    ):
        return True

    if _tem_tamanho_documento(getattr(body, "idCliente", None)):
        return True

    if _tem_contrato_vcom(getattr(body, "idContrato", None)):
        return True

    for campo in ("cedente", "idCedente", "idCredor"):
        valor = getattr(body, campo, None)
        if valor is None:
            continue
        try:
            if int(valor) >= 1000:
                return True
        except (TypeError, ValueError):
            continue

    if _tem_padrao_id_collectsys(body):
        return False

    return False


def _id_credor_vcom(body):
    cedente = getattr(body, "cedente", None)
    if cedente is not None:
        try:
            if int(cedente) >= 1000:
                return cedente
        except (TypeError, ValueError):
            pass

    return getattr(body, "idCredor", None) or getattr(body, "idCedente", None)


def _cpf_cnpj_vcom(body):
    documento = getattr(body, "cpfCnpj", None) or getattr(body, "idCliente", None)
    documento_limpo = _somente_digitos(documento)
    if len(documento_limpo) == 10:
        return documento_limpo.zfill(11)
    if len(documento_limpo) == 13:
        return documento_limpo.zfill(14)
    return documento_limpo if len(documento_limpo) >= 11 else documento


def _contrato_vcom(body):
    contrato = getattr(body, "contrato", None) or getattr(body, "idContrato", None)
    contrato_limpo = _somente_digitos(contrato)
    if contrato_limpo and str(contrato).strip().isdigit() and len(contrato_limpo) == 14:
        return contrato_limpo.zfill(15)
    return str(contrato).strip() if contrato is not None else contrato


def _remover_origem(retorno):
    return NegociacaoResponseDTO.remover_origem(retorno)


def _jsonify_sem_origem(retorno):
    return jsonify(_remover_origem(retorno))


def _eh_beta(body) -> bool:
    try:
        return int(getattr(body, "idCedente", 0) or 0) in CEDENTES_BETA
    except (TypeError, ValueError):
        return False


def _normalizar_retorno_parcelamento(retorno):
    return NegociacaoResponseDTO.normalizar_parcelamento(retorno)


def _normalizar_retorno_proposta(retorno, id_cedente=None):
    return NegociacaoResponseDTO.normalizar_proposta(retorno, id_cedente)


def _normalizar_retorno_formalizacao(id_acordo, id_cliente, proposta):
    return NegociacaoResponseDTO.normalizar_informacoes_acordo(id_cliente, proposta)


def _normalizar_contratos_verifica(contratos):
    return NegociacaoResponseDTO.normalizar_verifica(contratos)


async def _obter_dividas_agregadas(cpf_cnpj: str):
    return await asyncio.gather(
        DadosDivida.obter_cedentes(cpf_cnpj),
        VcomNegociacaoService.obter_cedentes(cpf_cnpj),
        return_exceptions=True,
    )


@bp.get("/obter-dividas-ativa")
@bp.doc(
    description="Método para obter dívidas ativas",
    summary="Obter Dívidas",
    tag="Negociação Acme"
    )
@bp.arguments(ObterDividaAtivaSchema, location="headers")
@bp.response(200, ObterDividasResponse, description="Retorno das dívidas do cliente")
@bp.response(401, Erro401Schema, description="Retorno de erro")
@token_require("/acme")
def obter_dividas_ativa(body: ObterDividaAtivaSchema):
    log.info("obter_dividas_ativa iniciado cpfCnpj=%s", body.cpfCnpj)

    cpf_cnpj = _cpf_cnpj_vcom(body)
    dividas_collectsys, dividas_vcom = asyncio.run(_obter_dividas_agregadas(cpf_cnpj))

    dividas: list[dict] = []
    if not isinstance(dividas_collectsys, Exception):
        for divida in dividas_collectsys:
            divida.setdefault("possuiDividaAtiva", True)
        dividas.extend(dividas_collectsys)
    if not isinstance(dividas_vcom, Exception):
        dividas.extend(dividas_vcom)

    if not dividas:
        cliente = asyncio.run(VcomNegociacaoService.dados_cliente(cpf_cnpj))
        if not cliente.get("nome"):
            erro = dividas_collectsys if isinstance(dividas_collectsys, Exception) else dividas_vcom
            if isinstance(erro, Exception):
                raise erro
        return _jsonify_sem_origem({
            "status": True,
            "possuiDividaAtiva": False,
            "mensagem": "Cliente localizado, mas nao possui divida ativa.",
            "cliente": cliente,
            "dividas": [],
        })

    if not isinstance(dividas_collectsys, Exception) and dividas_collectsys:
        cliente = asyncio.run(ClienteService.dados_cliente(dividas_collectsys))
    else:
        cliente = asyncio.run(VcomNegociacaoService.dados_cliente(cpf_cnpj))

    possui_divida_ativa = any(
        divida.get("possuiDividaAtiva", True)
        for divida in dividas
    )
    
    log.info("obter_dividas_ativa concluido idCliente=%s totalCedentes=%s", dividas, len(dividas))
    retorno = {
        "status": True,
        "possuiDividaAtiva": possui_divida_ativa,
        "cliente": cliente,
        "dividas": dividas,
    }
    if not possui_divida_ativa:
        retorno["mensagem"] = "Cliente localizado, mas nao possui divida ativa."
    return _jsonify_sem_origem(retorno)


@bp.get("/verifica-divida-cedente")
@bp.doc(
    description="Método para obter os contratos de cada cedente",
    summary="Obter contratos ativos",
    tag="Negociação Acme",
)
@bp.arguments(VerificaDividaCedenteSchema, location="headers")
@bp.response(200, VerificarCedenteResponse, description="Retorno das dívidas do cliente")
@bp.response(401, Erro401Schema, description="Retorno de erro")
@token_require("/acme")
def verifica_divida_cedente(body: VerificaDividaCedenteSchema):
    log.info(
        "verifica_divida_cedente iniciado idCliente=%s cedente=%s",
        getattr(body, "idCliente", None),
        body.cedente,
    )

    if _eh_vcom(body):
        contratos = asyncio.run(
            VcomNegociacaoService.obter_dados_divida(
                _cpf_cnpj_vcom(body),
                _id_credor_vcom(body),
                getattr(body, "data", None),
            )
        )
    elif 'vega' in str(body.cedente).lower() or str(body.cedente) == "1" :
        contratos = DadosDividaVega().obter_divida_vega(body.idCliente)

    else:
        data_ref = getattr(body, "data", None)
        contratos = asyncio.run(DadosDivida.obter_dados_divida(body.idCliente, body.cedente, data_ref))

    contratos = _normalizar_contratos_verifica(contratos)
    
    log.info("verifica_divida_cedente concluido idCliente=%s", body.idCliente)

    return _jsonify_sem_origem({"status":True, "contratos": contratos}), 200


@bp.get("/propostas-parcelado")
@bp.doc(
    description="Método para obter algumas opções de parcelamento",
    summary="Obter valores parcelados",
    tag="Negociação Acme"
    )
@bp.arguments(PropostaParceladoSchema, location="headers")
@bp.response(200, PropostasParcelamentoResponse, description="Retorno do parcelamento da divida")
@bp.response(401, Erro401Schema, description="Retorno de erro")
@token_require("/acme")
def parcelamento(body: PropostaParceladoSchema):
    log.info(
        "parcelamento iniciado idCliente=%s idContrato=%s",
        getattr(body, "idCliente", None),
        getattr(body, "idContrato", None),
    )
    if _eh_vcom(body):
        propostas_parceladas = asyncio.run(
            VcomNegociacaoService.negociacao_parcelado(
                _cpf_cnpj_vcom(body),
                _contrato_vcom(body),
                _id_credor_vcom(body),
                getattr(body, "idContrato", None),
                getattr(body, "data", None),
            )
        )
    else:
        propostas_parceladas = asyncio.run(NegociacaoDivida.negociacao_parcelado(body.idCliente, body.idContrato))
    propostas_parceladas = _normalizar_retorno_parcelamento(propostas_parceladas)
    log.info("parcelamento concluido idCliente=%s idContrato=%s", getattr(body, "idCliente", None), getattr(body, "idContrato", None))
    
    return _jsonify_sem_origem({"status":True, "parcelamento": propostas_parceladas}), 200


@bp.post("/proposta-divida") 
@bp.doc(
    description="Método para obter o valor da proposta",
    summary="Obter valor da proposta",
    tag="Negociação Acme"
    )   
@bp.arguments(PropostaDividaSchema, location="json")
@bp.response(200, PropostaDividaResponseSchema, description="Proposta gerada com sucesso")
@bp.response(401, Erro401Schema, description="Retorno de erro")
@token_require("/acme")
def proposta_divida(body: PropostaDividaSchema):
    log.info(
        "proposta_divida iniciada idCliente=%s idContrato=%s parcelamento=%s",
        getattr(body, "idCliente", None),
        getattr(body, "idContrato", None),
        body.parcelamento,
    )
    if _eh_vcom(body):
        proposta, id_cedente = asyncio.run(
            VcomNegociacaoService.proposta_cliente(
                _cpf_cnpj_vcom(body),
                _contrato_vcom(body),
                _id_credor_vcom(body),
                body.valorEntrada,
                body.parcelamento,
                body.dataPagamento,
                False,
                getattr(body, "idContrato", None),
                getattr(body, "idOpcaoParcelamento", None),
                getattr(body, "idCampanhaCalculo", None),
            )
        )
    else:
        proposta, id_cedente = asyncio.run(NegociacaoDivida.proposta_cliente(body.idCliente,body.idContrato
                    ,body.valorEntrada, body.parcelamento, body.dataPagamento, False, getattr(body, "condicao", None)))
    proposta = _normalizar_retorno_proposta(proposta, id_cedente)
    log.info("proposta_divida concluida idCliente=%s idContrato=%s", getattr(body, "idCliente", None), getattr(body, "idContrato", None))

    return _jsonify_sem_origem({"status":True, "proposta": proposta}), 200


@bp.post("/formalizar")
@bp.doc(
    description="Método para formalizar o acordo",
    summary="Formalização do acordo",
    tag="Negociação Acme"
    )   
@bp.arguments(PropostaDividaSchema, location="json")
@bp.response(200, FormalizarAcordoResponseSchema, description="Acordo formalizado com sucesso")
@bp.response(401, Erro401Schema, description="Retorno de erro")
@token_require("/acme")
def formalizar(body: PropostaDividaSchema):
    log.info(
        "formalizar iniciado idCliente=%s idContrato=%s parcelamento=%s",
        getattr(body, "idCliente", None),
        getattr(body, "idContrato", None),
        body.parcelamento,
    )
    
    if _eh_vcom(body):
        proposta, _ = asyncio.run(
            VcomNegociacaoService.proposta_cliente(
                _cpf_cnpj_vcom(body),
                _contrato_vcom(body),
                _id_credor_vcom(body),
                body.valorEntrada,
                body.parcelamento,
                body.dataPagamento,
                True,
                getattr(body, "idContrato", None),
                getattr(body, "idOpcaoParcelamento", None),
                getattr(body, "idCampanhaCalculo", None),
            )
        )
        acordo = proposta.get("codigoCalculo")
    else:
        proposta = None
        if NegociacaoResponseDTO.INCLUI_INFORMACOES_ACORDO:
            proposta, _ = asyncio.run(NegociacaoDivida.proposta_cliente(body.idCliente,body.idContrato
                    ,body.valorEntrada, body.parcelamento, body.dataPagamento, False, getattr(body, "condicao", None)))
        xml_acordo, id_cedente = asyncio.run(NegociacaoDivida.proposta_cliente(body.idCliente,body.idContrato
                ,body.valorEntrada, body.parcelamento, body.dataPagamento, True, getattr(body, "condicao", None)))
        
        acordo = Formalizar.gerar(body.idCliente, xml_acordo, id_cedente)
    formalizacao = _normalizar_retorno_formalizacao(acordo, body.idCliente, proposta)
    log.info("formalizar concluido idCliente=%s idAcordo=%s", getattr(body, "idCliente", None), acordo)

    retorno = {"status": True, "idAcordo": acordo}
    if formalizacao is not None:
        retorno["informacoesAcordo"] = formalizacao
    return _jsonify_sem_origem(retorno), 200


@bp.post("/tabular")
@bp.doc(
    description="Método para tabulação",
    summary="Tabulação",
    tag="Negociação Acme"
    )  
@bp.doc(
    requestBody={
        "required": True,
        "content": {
            "application/json": {
                "schema": {
                    "oneOf": [
                        {"$ref": "#/components/schemas/TabularVegaSchema"},
                        {"$ref": "#/components/schemas/TabularCobrancaSchema"},
                        {"$ref": "#/components/schemas/TabularCobrancaMuSchema"},
                    ],
                    "description": "Usa TabularVegaSchema quando cedente=vega. Usa TabularCobrancaMuSchema somente quando cedente=mu and idAcao=252(Acordo Formalizado). Outros usa TabularCobrancaSchema.",
                }
            }
        },
    }
)
@bp.arguments(TabularSchema, location="json")
@bp.response(200, TabularResponse, description="Tabulação efetuada com sucesso.")
@bp.response(401, Erro401Schema, description="Retorno de erro")
@token_require("/acme")
def tabular(body: TabularSchema):
    log.info(
        "tabular iniciado cedente=%s idCliente=%s idAcao=%s",
        body.cedente,
        getattr(body, "idCliente", None),
        body.idAcao,
    )
    
    if _eh_vcom(body):
            resulta = VcomNegociacaoService.tabular(
                cpf_cnpj=_cpf_cnpj_vcom(body),
                id_credor=_id_credor_vcom(body),
                id_acao=body.idAcao,
                descricao=body.descricaoAcao,
                telefone=body.telefone,
                contrato=_contrato_vcom(body),
                valor=getattr(body, "vlrDetalhe", None),
            )
    elif 'vega' in body.cedente.lower() or body.cedente == 1:
            callId = getattr(body, "callId", None)
            detalheData = getattr(body, "detalheData", None)
            tipoEnvio = getattr(body, "tipoEnvio", None)
            detalhe = getattr(body, "detalhe", None)
            resulta = TabularService(body.cedente,
                             body.idCliente, 
                             body.idAcao, 
                             body.descricaoAcao, 
                             body.telefone
                             ).vega(callId, detalheData, tipoEnvio, detalhe)

    else:
        nm_detalhe = getattr(body, "nmDetalhe", None)
        vlr_detalhe = getattr(body, "vlrDetalhe", None)
        qtd_detalhe = getattr(body, "qtdDetalhe", None)
        resulta = TabularService(body.cedente,
                                body.idCliente, 
                                body.idAcao, 
                                body.descricaoAcao, 
                                body.telefone
                                ).cobranca(nm_detalhe, vlr_detalhe, qtd_detalhe)
    log.info("tabular concluido cedente=%s idCliente=%s idAcao=%s", body.cedente, body.idCliente, body.idAcao)
    
    return _jsonify_sem_origem({"status":True, "tabulacao":resulta}), 200


@bp.post("/emitir-boleto")
@bp.doc(
    description="Método para emitir o boleto",
    summary="Emissão de boleto",
    tag="Negociação Acme"
    )  
@bp.arguments(EmitirBoletoSchema, location="json")
@bp.response(200, EmitirBoletoResponseSchema, description="Boleto emitido")
@bp.response(401, Erro401Schema, description="Retorno de erro")
@token_require("/acme")
def emitir_boleto(body: EmitirBoletoSchema):
    log.info(
        "emitir_boleto iniciado idCliente=%s idAcordo=%s idCedente=%s parcela=%s",
        getattr(body, "idCliente", None),
        getattr(body, "idAcordo", None),
        getattr(body, "idCedente", None),
        getattr(body, "parcela", None),
    )
    if _eh_vcom(body):
        boleto = VcomNegociacaoService.emitir_boleto(
            getattr(body, "codigoCalculo", None) or getattr(body, "idAcordo", None),
            getattr(body, "codigoBoleto", None) or 0,
        )
    elif _eh_beta(body):
        boleto = Boleto.obter_boleto_beta(
            body.idCliente,
            body.idAcordo,
            body.idCedente,
            getattr(body, "email", None),
            body.parcela,
            getattr(body, "cpfCnpj", None),
        )
    else:
        boleto = Boleto.obter(body.idCliente, 
                            body.idAcordo, 
                            body.idCedente, 
                            body.parcela)
    log.info("emitir_boleto concluido idCliente=%s idAcordo=%s", getattr(body, "idCliente", None), getattr(body, "idAcordo", None))

    return _jsonify_sem_origem({"status":True, "boleto":boleto}), 200


@bp.post("/emitir-pix")
@bp.doc(
    description="Método para emitir o código pix",
    summary="Emissão do código pix",
    tag="Negociação Acme"
    ) 
@bp.arguments(EmitirPixSchema, location="json")
@bp.response(200, EmitirPixResponse, description="Codigo pix")
@bp.response(401, Erro401Schema, description="Retorno de erro")
@token_require("/acme")
def pix(body:EmitirPixSchema):
    log.info(
        "emitir_pix iniciado cedente=%s idCliente=%s idAcordo=%s idCedente=%s",
        body.cedente,
        body.idCliente,
        body.idAcordo,
        body.idCedente,
    )

    codigo_pix = CodigoPix.obter(body.cedente, 
                                    body.idCliente, 
                                    body.idAcordo, 
                                    body.idCedente)

    resposta_json = {
            "status": "Sucesso",
            "mensagem": "Codigo PIX gerado",
            "codigoPix": codigo_pix
        }
    log.info("emitir_pix concluido idCliente=%s idAcordo=%s", body.idCliente, body.idAcordo)
    
    return _jsonify_sem_origem({"dados": resposta_json}), 200


@bp.post("/emitir-pix-qrcode")
@bp.doc(
    description="Método para emitir o qrcide do pix",
    summary="Emissão do qrcode pix",
    tag="Negociação Acme"
    ) 
@bp.arguments(EmitirQRcodeSchema, location="json")
@bp.response(200,EmitirQRcodeResponseSchema, description="Geração do QRcode")
@bp.response(401, Erro401Schema, description="Retorno de erro")
@token_require("/acme")
def pix_qrCode(body:EmitirQRcodeSchema):
    log.info("emitir_pix_qrcode iniciado idCliente=%s idAcordo=%s", body.idCliente, body.idAcordo)
    imagem = QrCode.gerar(body.idCliente, body.idAcordo, body.codigoPix)
    log.info("emitir_pix_qrcode concluido idCliente=%s idAcordo=%s", body.idCliente, body.idAcordo)

    return _jsonify_sem_origem({"status":True, "QRcode":imagem}), 200


@bp.post("/linha-digitavel")
@bp.doc(
    description="Método para obter a linha digitavel",
    summary="Emissão linha digitavel",
    tag="Negociação Acme"
    ) 
@bp.arguments(LinhaDigitavelSchema, location="json")
@bp.response(200, LinhaDigitavelResponseSchema,description="Resultado da linha digitavel")
@bp.response(401, Erro401Schema, description="Retorno de erro")
@token_require("/acme")
def linha_digitavel(body:LinhaDigitavelSchema):
    log.info("linha_digitavel iniciada idCliente=%s idAcordo=%s", body.idCliente, body.idAcordo)
    linha_digitavel = LinhaDigitavel.obter(body.idCliente, body.idAcordo)
    log.info("linha_digitavel concluida idCliente=%s idAcordo=%s", body.idCliente, body.idAcordo)

    return _jsonify_sem_origem({"status":True, "linhaDigitavel": linha_digitavel}), 200



@bp.post("/emitir-boleto-beta")
@bp.doc(
    description="Método para emitir o boleto exclusivo do Banco Beta",
    summary="Emissão de boleto",
    tag="Negociação Acme"
    )
@bp.arguments(EmitirBoletoBetaRequest, location="json")
@bp.response(200, EmitirBoletoResponseSchema, description="Boleto emitido BETA")
@bp.response(401, Erro401Schema, description="Retorno de erro")
@token_require("/acme")
def emitir(body: EmitirBoletoBetaRequest):
    boleto = Boleto.obter_boleto_beta(body.idCliente, 
                          body.idAcordo, 
                          body.idCedente, 
                          body.email,
                          body.parcela
                          )

    return _jsonify_sem_origem({"status":True, "boleto":boleto}), 200



