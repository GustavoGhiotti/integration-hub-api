from .dados_usuario import DadosUsuario
from src.domain.exceptions import ClienteNaoEncontrado
from .method_logger import log_collectsys_method

class ConsultarCliente(DadosUsuario):
    def __init__(self, servidor:str, id_cliente:int):
        super().__init__(servidor)
        self.id_cliente = id_cliente

    @log_collectsys_method()
    def consultar(self):
        url = self.url + "ConsultarCliente"

        headers = {"Content-Type": "text/xml; charset=utf-8"}
        body = f"""<?xml version="1.0" encoding="utf-8"?>
                    <soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
                    <soap:Body>
                        <ConsultarCliente xmlns="http://soap.collectsys.example/easycollectorws/">
                        <logonUsuario>{self.usuario}</logonUsuario>
                        <senhaUsuario>{self.senha}</senhaUsuario>
                        <idCliente>{self.id_cliente}</idCliente>
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

        if "<RetornoErro>" in resultado:
            return None

        return resultado
