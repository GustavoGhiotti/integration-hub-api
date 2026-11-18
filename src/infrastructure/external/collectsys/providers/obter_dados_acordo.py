from .dados_usuario import DadosUsuario
from .method_logger import log_collectsys_method
from ..dto.dados_acordo_request import DadosAcordoRequest

class DadosAcordo(DadosUsuario):
    def __init__(self):
        super().__init__()



    @log_collectsys_method()
    def obter_acordo(self, request:DadosAcordoRequest):
        url = self.url + "ConsultarAcordo"

        headers = {"Content-Type" : "text/xml; charset=utf-8"}
        body = f"""<?xml version="1.0" encoding="utf-8"?>
                    <soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
                    <soap:Body>
                        <ConsultarAcordo xmlns="http://soap.collectsys.example/easycollectorws/">
                        <logonUsuario>{self.usuario}</logonUsuario>
                        <senhaUsuario>{self.senha}</senhaUsuario>
                        <idCliente>{request.id_cliente}</idCliente>
                        <idAcordo>{request.id_acordo}</idAcordo>
                        </ConsultarAcordo>
                    </soap:Body>
                    </soap:Envelope>
                """

        return self._post_soap(
            method_name="obter_acordo",
            url=url,
            body=body,
            headers=headers,
            response_transform=lambda text: text.replace("&lt;", "<").replace("&gt;", ">"),
        )

    @log_collectsys_method()
    def obter_faturas(self, request:DadosAcordoRequest) -> str:
        url = self.url + "ConsultarAcordoFaturas"

        headers = {"Content-type": "text/xml; charset=utf-8"}
        body = f"""<?xml version="1.0" encoding="utf-8"?>
                    <soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
                        <soap:Body>
                            <ConsultarAcordoFaturas xmlns="http://soap.collectsys.example/easycollectorws/">
                            <logonUsuario>{self.usuario}</logonUsuario>
                            <senhaUsuario>{self.senha}</senhaUsuario>
                            <idCliente>{request.id_cliente}</idCliente>
                            <idAcordo>{request.id_acordo}</idAcordo>
                            </ConsultarAcordoFaturas>
                        </soap:Body>
                    </soap:Envelope>
                """

        return self._post_soap(
            method_name="obter_faturas",
            url=url,
            body=body,
            headers=headers,
            response_transform=lambda text: text.replace("&lt;", "<").replace("&gt;", ">"),
        )
    
