from .dados_usuario import DadosUsuario
from .method_logger import log_collectsys_method
from ..dto.envio_email_request import EnviarEmailRequest

class Email(DadosUsuario):
    def __init__(self):
        super().__init__()

    @log_collectsys_method()
    def enviar_boleto(self, request: EnviarEmailRequest):
        url = self.url + "ConsultarAcordo"

        headers = {"Content-Type" : "text/xml; charset=utf-8"}
        body = f"""<?xml version="1.0" encoding="utf-8"?>
                    <soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
                    <soap:Body>
                        <EnviarBoletoPorEmail xmlns="http://soap.collectsys.example/easycollectorws/">
                        <logonUsuario>{self.usuario}</logonUsuario>
                        <senhaUsuario>{self.senha}</senhaUsuario>
                        <idCliente>{request.id_cliente}</idCliente>
                        <idAcordo>{request.id_acordo}</idAcordo>
                        <parcela>{request.parcela}</parcela>
                        <emailDestino>{request.email}/emailDestino>
                        </EnviarBoletoPorEmail>
                    </soap:Body>
                    </soap:Envelope>
                """

        return self._post_soap(
            method_name="enviar_boleto",
            url=url,
            body=body,
            headers=headers,
            response_transform=lambda text: text.replace("&lt;", "<").replace("&gt;", ">"),
        )

