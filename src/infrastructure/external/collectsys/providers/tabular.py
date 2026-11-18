from .dados_usuario import DadosUsuario
from .method_logger import log_collectsys_method
from ..dto.tabular_request import (
    TabularComDetalhesRequest,
    TabularComDividaRequest,
    TabularRequest,
)


class Tabular(DadosUsuario):
    def __init__(self):
        super().__init__()

    @log_collectsys_method()
    def acao(self, request: TabularRequest) -> str:
        url = self.url + "InserirAcao"

        headers = {"content-type": "application/soap+xml"}
        body = f"""<?xml version="1.0" encoding="utf-8"?>
                <soap12:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap12="http://www.w3.org/2003/05/soap-envelope">
                  <soap12:Body>
                    <InserirAcao xmlns="http://soap.collectsys.example/easycollectorws/">
                      <logonUsuario>{self.usuario}</logonUsuario>
                      <senhaUsuario>{self.senha}</senhaUsuario>
                      <idCliente>{request.id_cliente}</idCliente>
                      <idAcao>{request.id_acao}</idAcao>
                      <descricaoAcao>{request.descricao_acao}</descricaoAcao>
                      <ddd>{request.ddd}</ddd>
                      <telefone>{request.telefone}</telefone>
                    </InserirAcao>
                  </soap12:Body>
                </soap12:Envelope>
            """

        return self._post_soap(
            method_name="acao",
            url=url,
            body=body,
            headers=headers,
            response_transform=lambda text: text.replace("&lt;", "<").replace("&gt;", ">"),
        )

    @log_collectsys_method()
    def acao_com_detalhes(self, request: TabularComDetalhesRequest) -> str:
        url = self.url + "InserirAcaoComDetalhe"
        
        headers = {"content-type": "application/soap+xml"}
        body = f"""<?xml version="1.0" encoding="utf-8"?>
                <soap12:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap12="http://www.w3.org/2003/05/soap-envelope">
                  <soap12:Body>
                    <InserirAcaoComDetalhe xmlns="http://soap.collectsys.example/easycollectorws/">
                      <logonUsuario>{self.usuario}</logonUsuario>
                      <senhaUsuario>{self.senha}</senhaUsuario>
                      <idCliente>{request.id_cliente}</idCliente>
                      <idAcao>{request.id_acao}</idAcao>
                      <descricaoAcao>{request.descricao_acao}</descricaoAcao>
                      <ddd>{request.ddd}</ddd>
                      <telefone>{request.telefone}</telefone>
                      <detalhesXml><![CDATA[{request.detalhes_xml}]]></detalhesXml>
                    </InserirAcaoComDetalhe>
                  </soap12:Body>
                </soap12:Envelope>
            """

        return self._post_soap(
            method_name="acao_com_detalhes",
            url=url,
            body=body,
            headers=headers,
            response_transform=lambda text: text.replace("&lt;", "<").replace("&gt;", ">"),
        )

    @log_collectsys_method()
    def acao_com_divida(self, request: TabularComDividaRequest) -> str:
        url = self.url + "InserirAcaoComDivida"

        headers = {"content-type": "text/xml"}
        body = f"""<?xml version="1.0" encoding="utf-8"?>
                <soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
                  <soap:Body>
                    <InserirAcaoComDivida xmlns="http://soap.collectsys.example/easycollectorws/">
                      <logonUsuario>{self.usuario}</logonUsuario>
                      <senhaUsuario>{self.senha}</senhaUsuario>
                      <idCliente>{request.id_cliente}</idCliente>
                      <idAcao>{request.id_acao}</idAcao>
                      <descricaoAcao>{request.descricao_acao}</descricaoAcao>
                      <ddd>{request.ddd}</ddd>
                      <telefone>{request.telefone}</telefone>
                      <detalhesXml>{request.detalhes_xml}</detalhesXml>
                      <dividaXml><![CDATA[{request.divida_xml}]]></dividaXml>
                    </InserirAcaoComDivida>
                  </soap:Body>
                </soap:Envelope>
            """

        return self._post_soap(
            method_name="acao_com_divida",
            url=url,
            body=body,
            headers=headers,
            response_transform=lambda text: text.replace("&lt;", "<").replace("&gt;", ">"),
        )