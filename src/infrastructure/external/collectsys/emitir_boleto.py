from .dados_usuario import DadosUsuario
from src.domain.exceptions.collectsys_exception import CollectSysException
from src.infrastructure.external.collectsys.cedente_rules import get_cedente_rule
from .method_logger import log_collectsys_method

class EmitirBoleto(DadosUsuario):
  def __init__(self, *,servidor:str, id_cliente:int, id_acordo:int, parcela:int, id_cedente:int):
    super().__init__(servidor, id_cedente)
    self.id_cliente = id_cliente
    self.id_acordo = id_acordo
    self.parcela = parcela

  @log_collectsys_method()
  def emitir(self) -> str:
    url = self.url + "EmitirBoleto"

    headers = {'content-type': 'text/xml'}
    body = f"""<?xml version="1.0" encoding="utf-8"?>
                <soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
                <soap:Body>
                    <EmitirBoleto xmlns="http://soap.collectsys.example/easycollectorws/">
                    <logonUsuario>{self.usuario}</logonUsuario>
                    <senhaUsuario>{self.senha}</senhaUsuario>
                    <idCliente>{self.id_cliente}</idCliente>
                    <idAcordo>{self.id_acordo}</idAcordo>
                    <parcela>{self.parcela}</parcela>
                    <TipoArquivoRetorno>pdf</TipoArquivoRetorno>
                    </EmitirBoleto>
                </soap:Body>
                </soap:Envelope>
            """

    resultado = self._post_soap(
      method_name="emitir",
      url=url,
      body=body,
      headers=headers,
      response_transform=lambda text: text.replace("&lt;", "<").replace("&gt;", ">"),
    )

    if '<RetornoErro>' in resultado:
      if self.id_cedente in (81, 104):
            return resultado
      else:
            mensagem = get_cedente_rule(self.id_cedente).tratar_erro_emissao_boleto(resultado)
            raise CollectSysException(mensagem=mensagem)

    return resultado

  @log_collectsys_method()
  def emitir_original(self, xml_divida) -> str:
    url = self.url + "EmitirBoletoOriginal"


    headers = {'content-type': 'text/xml'}
    body = f"""<?xml version="1.0" encoding="utf-8"?>
                <soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
                <soap:Body>
                    <EmitirBoletoOriginal xmlns="http://soap.collectsys.example/easycollectorws/">
                    <logonUsuario>{self.usuario}</logonUsuario>
                    <senhaUsuario>{self.senha}</senhaUsuario>
                    <idCliente>{self.id_cliente}</idCliente>
                    <dividaXml><![CDATA[{xml_divida}]]></dividaXml>
                    <TipoArquivoRetorno>pdf</TipoArquivoRetorno>
                    </EmitirBoletoOriginal>
                </soap:Body>
                </soap:Envelope>
            """

    resultado = self._post_soap(
      method_name="emitir_original",
      url=url,
      body=body,
      headers=headers,
      response_transform=lambda text: text.replace("&lt;", "<").replace("&gt;", ">"),
    )

    if '<RetornoErro>' in resultado:
      if self.id_cedente in (81, 104):
            return resultado
      else:
            raise CollectSysException(mensagem=resultado)

    return resultado
