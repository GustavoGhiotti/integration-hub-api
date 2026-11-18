from src.infrastructure.external.collectsys.carteiras.interface import CollectSysCarteiraProtocol

from .dados_usuario import DadosUsuario
from .method_logger import log_collectsys_method
from ..dto.consultar_cliente_request import ConsultarClienteRequest

class ConsultarCliente:
    def __init__(self, carteira: CollectSysCarteiraProtocol):
        self.url = carteira.url
        self.credenciais = carteira.obter_credenciais()
        
    @log_collectsys_method()
    def consultar(self, request: ConsultarClienteRequest) -> str:
        url = self.url + "ConsultarCliente"

        headers = {"Content-Type": "text/xml; charset=utf-8"}
        body = f"""<?xml version="1.0" encoding="utf-8"?>
                    <soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
                    <soap:Body>
                        <ConsultarCliente xmlns="http://soap.collectsys.example/easycollectorws/">
                        <logonUsuario>{self.credenciais.usuario}</logonUsuario>
                        <senhaUsuario>{self.credenciais.senha}</senhaUsuario>
                        <idCliente>{request.id_cliente}</idCliente>
                        </ConsultarCliente>
                    </soap:Body>
                    </soap:Envelope>
                    """
        
        resultado = self._post_soap(
            method_name="consultar",
            url=url,
            body=body,
            headers=headers,
            response_transform=lambda text: text.replace("&lt;", "<").replace("&gt;", ">"),
        )

        return resultado
