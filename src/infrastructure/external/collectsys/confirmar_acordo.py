from .dados_usuario import DadosUsuario
from src.domain.exceptions import ErroFormalizarAcordo
from src.infrastructure.external.collectsys.cedente_rules import get_cedente_rule
from .method_logger import log_collectsys_method

class ConfirmarAcordo(DadosUsuario):
    def __init__(self, id_cedente:int, id_cliente:int, xml_acordo:str):
        super().__init__("", id_cedente)
        self.id_cliente = id_cliente
        self.xml_acordo = xml_acordo

    @log_collectsys_method()
    def formalizar(self) -> str:
        url = self.url + "ConfirmarAcordo"

        headers = {'content-type': 'application/soap+xml; charset=utf-8'}
        body = f"""<?xml version="1.0" encoding="utf-8"?>
                    <soap12:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap12="http://www.w3.org/2003/05/soap-envelope">
                    <soap12:Body>
                        <ConfirmarAcordo xmlns="http://soap.collectsys.example/easycollectorws/">
                        <logonUsuario>{self.usuario}</logonUsuario>
                        <senhaUsuario>{self.senha}</senhaUsuario>
                        <idCliente>{self.id_cliente}</idCliente>
                        <acordoXml><![CDATA[{self.xml_acordo}]]></acordoXml>
                        </ConfirmarAcordo>
                    </soap12:Body>
                    </soap12:Envelope>
                """

        resultado = self._post_soap(
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

        if "<RetornoErro>" in resultado:
            rule = get_cedente_rule(self.id_cedente)
            mensagem = rule.tratar_erro_formalizacao(resultado)
            raise ErroFormalizarAcordo(mensagem=mensagem)

        return resultado
