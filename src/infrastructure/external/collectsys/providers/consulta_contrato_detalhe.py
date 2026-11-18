from src.infrastructure.external.collectsys.carteiras.interface import CollectSysCarteiraProtocol

from .dados_usuario import DadosUsuario
from src.shared.utils import *
from .method_logger import log_collectsys_method
from ..dto.consultar_contrato import ConsultarContratoRequest


class ConsultaContratoDetalhe:
    def __init__(self,carteira: CollectSysCarteiraProtocol):
        self.url = carteira.url
        self.credenciais = carteira.obter_credenciais()

    @staticmethod
    def extrair_nm_produto(xml: str) -> str | None:
        return extrair_nm_produto(xml)

    @log_collectsys_method()
    def consulta(self, request:ConsultarContratoRequest):
        url = "http://10.0.0.64/easycollectorws/easycollectorWs.asmx?op=ConsultarContratoDetalhes"

        headers = {'content-type': 'text/xml'}
        body = (f'''<?xml version="1.0" encoding="utf-8"?>
                    <soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
                    <soap:Body>
                        <ConsultarContratoDetalhes xmlns="http://soap.collectsys.example/easycollectorws/">
                        <logonUsuario>{self.credenciais.usuario}</logonUsuario>
                        <senhaUsuario>{self.credenciais.senha}</senhaUsuario>
                        <idCliente>{request.id_cliente}</idCliente>
                        <idContrato>{request.id_contrato}</idContrato>
                        </ConsultarContratoDetalhes>
                    </soap:Body>
                    </soap:Envelope>
                '''
                )

        return self._post_soap(
            method_name="consulta",
            url=url,
            body=body,
            headers=headers,
            response_transform=lambda text: text.replace("&lt;", "<").replace("&gt;", ">"),
        )

