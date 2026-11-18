from .method_logger import log_collectsys_method
from ..dto.parcelamento_maximo_request import ParcelamentoMaxRequest
from dados_usuario import DadosUsuario

class ParcelamentoMaximo(DadosUsuario):
    def __init__(self):
        super().__init__()

    @log_collectsys_method()
    def obter(self, request: ParcelamentoMaxRequest) -> str:
        url = self.url + "ObterPlanoMaximoAcordo"

        headers = {'content-type': 'text/xml'}
        body =  f"""<?xml version="1.0" encoding="utf-8"?>
                    <soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
                    <soap:Body>
                        <ObterPlanoMaximoAcordo xmlns="http://soap.collectsys.example/easycollectorws/">
                            <logonUsuario>{self.usuario}</logonUsuario>
                            <senhaUsuario>{self.senha}</senhaUsuario>
                            <dividaXml><![CDATA[{request.xml_divida}]]></dividaXml>
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