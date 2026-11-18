from .dados_usuario import DadosUsuario
from .method_logger import log_collectsys_method

class Email(DadosUsuario):
    def __init__(self, servidor:str, id_cliente:int, id_acordo:int, parcela:int, email:str):
        super().__init__(servidor)
        self.id_cliente = id_cliente
        self.id_acordo = id_acordo
        self.parcela = parcela
        self.email = email


    @log_collectsys_method()
    def enviar_boleto(self):
        url = self.url + "ConsultarAcordo"

        headers = {"Content-Type" : "text/xml; charset=utf-8"}
        body = f"""<?xml version="1.0" encoding="utf-8"?>
                    <soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
                    <soap:Body>
                        <EnviarBoletoPorEmail xmlns="http://soap.collectsys.example/easycollectorws/">
                        <logonUsuario>{self.usuario}</logonUsuario>
                        <senhaUsuario>{self.senha}</senhaUsuario>
                        <idCliente>{self.id_cliente}</idCliente>
                        <idAcordo>{self.id_acordo}</idAcordo>
                        <parcela>{self.parcela}</parcela>
                        <emailDestino>{self.email}/emailDestino>
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
