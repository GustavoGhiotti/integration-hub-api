from src.infrastructure.external.collectsys.carteiras.interface import CollectSysCarteiraProtocol

from .dados_usuario import DadosUsuario
from src.domain.exceptions import ErroFormalizarAcordo
from .method_logger import log_collectsys_method
from ..dto.confirmar_acordo_request import FormalizarAcordoRequest


class ConfirmarAcordo:
    def __init__(self,carteira: CollectSysCarteiraProtocol):
        self.url = carteira.url
        self.credenciais = carteira.obter_credenciais()


    @log_collectsys_method()
    def formalizar(self, request:FormalizarAcordoRequest) -> str:   
        url = self.url + "ConfirmarAcordo"

        headers = {'content-type': 'application/soap+xml; charset=utf-8'}
        body = f"""<?xml version="1.0" encoding="utf-8"?>
                    <soap12:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap12="http://www.w3.org/2003/05/soap-envelope">
                    <soap12:Body>
                        <ConfirmarAcordo xmlns="http://soap.collectsys.example/easycollectorws/">
                        <logonUsuario>{self.credenciais.usuario}</logonUsuario>
                        <senhaUsuario>{self.credenciais.senha}</senhaUsuario>
                        <idCliente>{request.id_cliente}</idCliente>
                        <acordoXml><![CDATA[{request.xml_acordo}]]></acordoXml>
                        </ConfirmarAcordo>
                    </soap12:Body>
                    </soap12:Envelope>
                """

        return self._post_soap(
            method_name="formalizar",
            url=url,
            body=body,
            headers=headers,
            response_transform=lambda text: (
                text.replace("&amp;lt;", "&lt;")
                .replace("&amp;gt;", "&gt;")
                .replace("&lt;", "<")
                .replace("&gt;", ">")
            ),
        )
        
