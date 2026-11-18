from src.infrastructure.external.collectsys.carteiras.interface import CollectSysCarteiraProtocol

from .dados_usuario import DadosUsuario
from src.domain.exceptions.collectsys_exception import CollectSysException
from .method_logger import log_collectsys_method
from ..dto.emitir_boleto_request import EmitirBoletoRequest, EmitirBoletoOriginalRequest

class EmitirBoleto:
  def __init__(self, carteira: CollectSysCarteiraProtocol):
    self.url = carteira.url
    self.credenciais = carteira.obter_credenciais()

  @log_collectsys_method()
  def emitir(self, request: EmitirBoletoRequest) -> str:
    url = self.url + "EmitirBoleto"

    headers = {'content-type': 'text/xml'}
    body = f"""<?xml version="1.0" encoding="utf-8"?>
                <soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
                <soap:Body>
                    <EmitirBoleto xmlns="http://soap.collectsys.example/easycollectorws/">
                    <logonUsuario>{self.credenciais.usuario}</logonUsuario>
                    <senhaUsuario>{self.credenciais.senha}</senhaUsuario>
                    <idCliente>{request.id_cliente}</idCliente>
                    <idAcordo>{request.id_acordo}</idAcordo>
                    <parcela>{request.parcela}</parcela>
                    <TipoArquivoRetorno>pdf</TipoArquivoRetorno>
                    </EmitirBoleto>
                </soap:Body>
                </soap:Envelope>
            """

    return self._post_soap(
      method_name="emitir",
      url=url,
      body=body,
      headers=headers,
      response_transform=lambda text: text.replace("&lt;", "<").replace("&gt;", ">"),
    )


  @log_collectsys_method()
  def emitir_original(self, request:EmitirBoletoOriginalRequest) -> str:
    url = self.url + "EmitirBoletoOriginal"
    
    headers = {'content-type': 'text/xml'}
    body = f"""<?xml version="1.0" encoding="utf-8"?>
                <soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
                <soap:Body>
                    <EmitirBoletoOriginal xmlns="http://soap.collectsys.example/easycollectorws/">
                    <logonUsuario>{self.usuario}</logonUsuario>
                    <senhaUsuario>{self.senha}</senhaUsuario>
                    <idCliente>{request.id_cliente}</idCliente>
                    <dividaXml><![CDATA[{request.xml_divida}]]></dividaXml>
                    <TipoArquivoRetorno>pdf</TipoArquivoRetorno>
                    </EmitirBoletoOriginal>
                </soap:Body>
                </soap:Envelope>
            """

    return self._post_soap(
      method_name="emitir_original",
      url=url,
      body=body,
      headers=headers,
      response_transform=lambda text: text.replace("&lt;", "<").replace("&gt;", ">"),
    )
