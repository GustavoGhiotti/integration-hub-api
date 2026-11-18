from ..cedente_rules import get_cedente_rule
#from ..cedente_rules.types import CalculoContext
from .dados_usuario import DadosUsuario
from datetime import date, timedelta
from src.shared.utils.data import *
from src.domain.exceptions.collectsys_exception import *
from src.shared.utils import *
from src.shared.utils.env_load import *
from src.shared.utils.env_load import *
from src.infrastructure.external.collectsys.providers.consulta_divida import ConsultaDividaDetalhe
from src.domain.entities.cedentes import CEDENTES_PARCELAMENTO_MIN_MAX
from .method_logger import log_collectsys_method

from ..dto.calcular_request import CalcularAcordoRequest, CalcularAcordoDetalheRequest, CalcularDividaRequest
from ..carteiras.interface import CollectSysCarteiraProtocol   

class Calcular:
    def __init__(self, carteira: CollectSysCarteiraProtocol):
        self.url = carteira.url
        self.credenciais = carteira.obter_credenciais()

    @log_collectsys_method()
    def calcular_acordo(self, request:CalcularAcordoRequest) -> str:
        metodo = "CalcularAcordo"
        url = self.url + metodo
        
        
        headers = {'content-type': 'text/xml'}
        body = (f'''<?xml version="1.0" encoding="utf-8"?>
                <soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
                <soap:Body>
                <CalcularAcordo xmlns="http://soap.collectsys.example/easycollectorws/">
                    <logonUsuario>{self.credenciais.usuario}</logonUsuario>
                    <senhaUsuario>{self.credenciais.senha}</senhaUsuario>
                    <idCliente>{request.id_cliente}</idCliente>
                    <plano>{request.plano}</plano>
                    <dataEntrada>{request.data}</dataEntrada>
                    <valorEntradaDiferenciada>{request.entrada}</valorEntradaDiferenciada>
                    <percentualDesconto>{request.desconto}</percentualDesconto>
                    <taxaJuros>0</taxaJuros>
                    <tipoCalculo>0</tipoCalculo>
                    <dividaXml><![CDATA[{request.xml_divida}]]></dividaXml>
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
        )
        

    @log_collectsys_method()
    def calcular_acordo_com_detalhes(self, request:CalcularAcordoDetalheRequest) -> str:
        url = self.url + "CalcularAcordoComDetalhe"
        rule = get_cedente_rule(self.id_cedente)

        headers = {'content-type': 'application/soap+xml'}
        body = f"""<?xml version="1.0" encoding="utf-8"?>
                <soap12:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap12="http://www.w3.org/2003/05/soap-envelope">
                <soap12:Body>
                    <CalcularAcordoComDetalhe xmlns="http://soap.collectsys.example/easycollectorws/">
                            <logonUsuario>{self.credenciais.usuario}</logonUsuario>
                            <senhaUsuario>{self.credenciais.senha}</senhaUsuario>
                            <idCliente>{request.id_cliente}</idCliente>
                            <plano>{request.plano}</plano>
                            <dataEntrada>{request.data}</dataEntrada>
                            <valorEntradaDiferenciada>{request.entrada}</valorEntradaDiferenciada>
                            <percentualDesconto>{request.desconto}</percentualDesconto>
                            <taxaJuros>0</taxaJuros>
                            <tipoCalculo>0</tipoCalculo>
                            <dataDemaisParcelas>1900-01-01</dataDemaisParcelas>
                            <valorHonorarios>0</valorHonorarios>
                            <idEquipeAprovador>0</idEquipeAprovador>
                            <intervaloVencimento>0</intervaloVencimento>
                            <dividaXml><![CDATA[{request.xml_divida}]]></dividaXml>
                            <detalheCalculoXml><![CDATA[{request.xml_detalhe}]]></detalheCalculoXml>
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
        )
             

    @log_collectsys_method()
    def calcular_divida(self, request:CalcularDividaRequest) -> str:
        url = self.url + "CalcularDivida"

        headers = {'content-type': 'text/xml'}
        body = f"""<?xml version="1.0" encoding="utf-8"?>
                        <soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
                            <soap:Body>
                            <CalcularDivida xmlns="http://soap.collectsys.example/easycollectorws/">
                                <logonUsuario>{self.credenciais.usuario}</logonUsuario>
                                <senhaUsuario>{self.credenciais.senha}</senhaUsuario>
                                <idCliente>{request.id_cliente}</idCliente>
                                <percentualDesconto>0</percentualDesconto>
                                <tipoCalculo>0</tipoCalculo>
                                <dividaXml><![CDATA[{request.xml_divida}]]></dividaXml>
                            </CalcularDivida> 
                            </soap:Body>
                        </soap:Envelope>
                """
        
        return self._post_soap(
            method_name="CalcularDivida",
            url=url,
            body=body,
            headers=headers,
            stream=True,
            response_transform=lambda text: text.replace("&lt;", "<").replace("&gt;", ">"),
        )


    
