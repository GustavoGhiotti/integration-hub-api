from .cedente_rules import get_cedente_rule
from .dados_usuario import DadosUsuario
from datetime import date, timedelta
from src.shared.utils.data import *
from src.domain.exceptions.collectsys_exception import *
from src.shared.utils import *
from src.shared.utils.env_load import *
from src.infrastructure.repositories.sql_collectsys_repository import SqlCollectSysRepository, SQLServerConnection
from src.shared.utils.env_load import *
from src.infrastructure.external.collectsys.consulta_divida import ConsultaDividaDetalhe
from src.shared.utils.tratativa_detalhe import obter_tipo_pagamento_delta
from src.domain.entities.cedentes import CEDENTES_PARCELAMENTO_MIN_MAX
from .method_logger import log_collectsys_method
import time

class Calcular(DadosUsuario):
    def __init__(self, servidor:str, id_cliente:int, id_cedente:int, plano:int,valor_entrada:float,
                 xml_divida:str, vencimento:date = None, condicao=None):
        super().__init__(servidor, id_cedente)
        self.id_cliente = id_cliente
        self.id_cedente = id_cedente
        self.plano = plano
        self.valor_entrada = valor_entrada
        self.vencimento = vencimento
        self.xml_divida = xml_divida
        self.condicao = condicao


    @log_collectsys_method()
    def calcular_acordo(self, parcelado = "") -> str:
        url = self.url + "CalcularAcordo"
        method_log = self._get_method_logger("calcular_acordo")
        rule = get_cedente_rule(self.id_cedente)

        match self.id_cedente:
            case 3:
                desconto = 199
            case _:
                desconto = 100

        if self.id_cedente in (14, 43):
            rule.definir_data_vencimento(self)
            data_vencimento = self.data_vencimento
        else:
            if not self.vencimento:
                self.vencimento = date.today() + timedelta(days=7)

            data_vencimento = validacao_dia_util(self.vencimento)

        def calcular() -> str:
            headers = {'content-type': 'text/xml'}
            xml_divida = rule.montar_xml_divida_calcular_acordo(self, parcelado)
            body = (f'''<?xml version="1.0" encoding="utf-8"?>
                    <soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
                    <soap:Body>
                    <CalcularAcordo xmlns="http://soap.collectsys.example/easycollectorws/">
                        <logonUsuario>{self.usuario}</logonUsuario>
                        <senhaUsuario>{self.senha}</senhaUsuario>
                        <idCliente>{self.id_cliente}</idCliente>
                        <plano>{self.plano}</plano>
                        <dataEntrada>{data_vencimento}</dataEntrada>
                        <valorEntradaDiferenciada>{self.valor_entrada}</valorEntradaDiferenciada>
                        <percentualDesconto>{desconto}</percentualDesconto>
                        <taxaJuros>0</taxaJuros>
                        <tipoCalculo>0</tipoCalculo>
                        <dividaXml><![CDATA[{xml_divida}]]></dividaXml>
                    </CalcularAcordo>
                    </soap:Body>
                </soap:Envelope>''')

            return self._post_soap(
                method_name="calcular_acordo",
                url=url,
                body=body,
                headers=headers,
                stream=True,
                response_transform=lambda text: (
                    text.replace("&amp;lt;", "&lt;")
                    .replace("&amp;gt;", "&gt;")
                    .replace("&lt;", "<")
                    .replace("&gt;", ">")
                    if self.id_cedente not in (4, 14)
                    else text.replace("&lt;", "<")
                    .replace("&gt;", ">")
                    .replace("&amp;lt;", "&lt;")
                    .replace("&amp;gt;", "&gt;")
                ),
                extra_context={"parcelado": parcelado, "tentativa": tentativa},
            )

        tentativa = 0
        while tentativa < 5:
            tentativa += 1
            resultado = calcular()
            valido = True
            tratativa_aplicada = False

            if "<RetornoErro>" not in resultado:
                return resultado

            if "<RetornoErro>" in resultado and "data" in resultado.lower():
                tratativa_aplicada = True
                nova_data = capturar_data(resultado)
                if nova_data:
                    data_vencimento = nova_data
                    resultado = calcular()
                else:
                    method_log.warning(
                        "capturar_data_sem_match id_cliente=%s id_cedente=%s plano=%s",
                        self.id_cliente,
                        self.id_cedente,
                        self.plano,
                    )

            elif "<RetornoErro>" in resultado and (
                "desconto máximo" in resultado.lower()
                or "desconto maximo" in resultado.lower()
            ):
                tratativa_aplicada = True
                novo_desconto = capturar_desconto(resultado)
                if novo_desconto is not None:
                    desconto = novo_desconto
                    resultado = calcular()
                else:
                    method_log.warning(
                        "capturar_desconto_sem_match id_cliente=%s id_cedente=%s plano=%s",
                        self.id_cliente,
                        self.id_cedente,
                        self.plano,
                    )

            elif "valor" in resultado.lower():
                tratativa_aplicada = True
                self.valor_entrada = capturar_valor(resultado) if capturar_valor(resultado) else self.valor_entrada
                resultado = calcular()

            # No fluxo de parcelamento maximo, nao repete tentativas quando
            # nao houve nenhuma tratativa aplicavel para o erro retornado.
            if parcelado and not tratativa_aplicada:
                return resultado

        return resultado


    @log_collectsys_method()
    def calcular_acordo_com_detalhes(
        self,
        produto: str = None,
        parcelado: str = "",
        cartao_35=None,
        percentual_desconto: float | int | None = None,
    ) -> str:
        url = self.url + "CalcularAcordoComDetalhe"
        rule = get_cedente_rule(self.id_cedente)
        rule.preparar_calculo_com_detalhes(self, produto, parcelado, cartao_35)

        def calculo() -> str:
            rule.montar_xml(self)
            if percentual_desconto is not None:
                self.desconto = percentual_desconto
            headers = {'content-type': 'application/soap+xml'}
            body = f"""<?xml version="1.0" encoding="utf-8"?>
                  <soap12:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap12="http://www.w3.org/2003/05/soap-envelope">
                    <soap12:Body>
                      <CalcularAcordoComDetalhe xmlns="http://soap.collectsys.example/easycollectorws/">
                                <logonUsuario>{self.usuario}</logonUsuario>
                                <senhaUsuario>{self.senha}</senhaUsuario>
                                <idCliente>{self.id_cliente}</idCliente>
                                <plano>{self.plano}</plano>
                                <dataEntrada>{self.data_vencimento}</dataEntrada>
                                <valorEntradaDiferenciada>{self.valor_entrada}</valorEntradaDiferenciada>
                                <percentualDesconto>{self.desconto}</percentualDesconto>
                                <taxaJuros>0</taxaJuros>
                                <tipoCalculo>0</tipoCalculo>
                                <dataDemaisParcelas>1900-01-01</dataDemaisParcelas>
                                <valorHonorarios>0</valorHonorarios>
                                <idEquipeAprovador>0</idEquipeAprovador>
                                <intervaloVencimento>0</intervaloVencimento>
                                <dividaXml><![CDATA[{self.xml_divida}]]></dividaXml>
                                <detalheCalculoXml><![CDATA[{self.detalhe_xml}]]></detalheCalculoXml>
                            </CalcularAcordoComDetalhe>
                            </soap12:Body>
                        </soap12:Envelope>
                    """

            return self._post_soap(
                method_name="calcular_acordo_com_detalhes",
                url=url,
                body=body,
                headers=headers,
                stream=True,
                response_transform=lambda text: (
                    text.replace("&amp;lt;", "&lt;")
                    .replace("&amp;gt;", "&gt;")
                    .replace("&lt;", "<")
                    .replace("&gt;", ">")
                    if self.id_cedente not in (60, 71)
                    else text.replace("&lt;", "<")
                    .replace("&gt;", ">")
                    .replace("&amp;lt;", "&lt;")
                    .replace("&amp;gt;", "&gt;")
                ),
                extra_context={
                    "parcelado": parcelado,
                    "tentativa": tentativa,
                    "percentual_desconto": percentual_desconto,
                },
            )


        tentativa = 0
        while tentativa < 5:
            tentativa += 1
            resultado = calculo()
            valido = True

            if "<RetornoErro>" not in resultado:
                if xml_invalido_cedente_77(self.id_cedente, resultado):
                    valido = False
                elif self.id_cedente in CEDENTES_PARCELAMENTO_MIN_MAX and "VALOR ENTRADA" in parcelado:
                    pass
                else:
                    return resultado

            resultado_tratado = extrair_tag(resultado.lower(), "<mensagem>", "</mensagem>")
            rule.atualizar_retorno(self, resultado, resultado_tratado, valido)

            try:
                decisao = rule.tratar_retorno(self)
                if decisao is None:
                    continue

                if decisao.acao == "recalcular":
                    continue

                if decisao.acao == "retornar":
                    return decisao.valor

            except (RetornoTratadoBeta, ErroFormalizarAcordo, NenhumaDividaException):
                raise
            except Exception:
                rule.lancar_erro_inesperado(self)

        if parcelado != "":
            if self.id_cedente in CEDENTES_PARCELAMENTO_MIN_MAX and "VALOR ENTRADA" in parcelado:
                if hasattr(rule, "_montar_retorno_entrada"):
                    return rule._montar_retorno_entrada(
                        self,
                        valor_minimo_entrada=self.valor_minimo_entrada,
                        valor_maximo_entrada=self.valor_maximo_entrada,
                        parcelamento_min=self.parcelamento_min,
                        parcelamento_max=self.parcelamento_max,
                    )
                return rule._montar_retorno_parcelamento(self)
            return resultado
        rule.finalizar_falha(self)


    @log_collectsys_method()
    def calcular_divida(self) -> str:
        url = self.url + "CalcularDivida"
        rule = get_cedente_rule(self.id_cedente)
        xml_divida = rule.montar_xml_divida_calcular_acordo(self)

        headers = {'content-type': 'text/xml'}
        body = f"""<?xml version="1.0" encoding="utf-8"?>
                        <soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
                            <soap:Body>
                            <CalcularDivida xmlns="http://soap.collectsys.example/easycollectorws/">
                                <logonUsuario>{self.usuario}</logonUsuario>
                                <senhaUsuario>{self.senha}</senhaUsuario>
                                <idCliente>{self.id_cliente}</idCliente>
                                <percentualDesconto>0</percentualDesconto>
                                <tipoCalculo>0</tipoCalculo>
                                <dividaXml><![CDATA[{xml_divida}]]></dividaXml>
                            </CalcularDivida>
                            </soap:Body>
                        </soap:Envelope>
                """

        return self._post_soap(
            method_name="calcular_divida",
            url=url,
            body=body,
            headers=headers,
            stream=True,
            response_transform=lambda text: text.replace("&lt;", "<").replace("&gt;", ">"),
        )

    @log_collectsys_method()
    def obter_parcelamento_max(self) -> str:
        url = self.url + "ObterPlanoMaximoAcordo"
        rule = get_cedente_rule(self.id_cedente)
        xml_divida = rule.montar_xml_divida_calcular_acordo(self)

        headers = {'content-type': 'text/xml'}
        body =  f"""<?xml version="1.0" encoding="utf-8"?>
                    <soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
                    <soap:Body>
                        <ObterPlanoMaximoAcordo xmlns="http://soap.collectsys.example/easycollectorws/">
                            <logonUsuario>{self.usuario}</logonUsuario>
                            <senhaUsuario>{self.senha}</senhaUsuario>
                            <dividaXml><![CDATA[{xml_divida}]]></dividaXml>
                        </ObterPlanoMaximoAcordo>
                    </soap:Body>
                    </soap:Envelope>
                """

        return self._post_soap(
            method_name="obter_parcelamento_max",
            url=url,
            body=body,
            headers=headers,
            response_transform=lambda text: text.replace("&lt;", "<").replace("&gt;", ">"),
        )
