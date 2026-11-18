from .dados_usuario import DadosUsuario
from .method_logger import log_collectsys_method
from html import escape

class Tabular(DadosUsuario):
  def __init__(self, *,servidor:str,id_cliente:int, id_acao:int, descricao_acao:str,
               ddd:int,telefone:int):

    super().__init__(servidor)
    self.id_cliente = id_cliente
    self.id_acao = id_acao
    self.descricao_acao = descricao_acao
    self.ddd = ddd
    self.telefone = telefone

  @log_collectsys_method()
  def acao(self) -> str:
    url = ""
    if self.servidor.lower() == "vega":
      url = "http://10.0.0.18/easycollectorws/easycollectorWs.asmx?op=InserirAcao"
    else:
      url = "http://10.0.0.64/easycollectorws/easycollectorWs.asmx?op=InserirAcao"

    headers = {'content-type': 'application/soap+xml'}
    body = f"""<?xml version="1.0" encoding="utf-8"?>
                <soap12:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap12="http://www.w3.org/2003/05/soap-envelope">
                  <soap12:Body>
                    <InserirAcao xmlns="http://soap.collectsys.example/easycollectorws/">
                      <logonUsuario>{self.usuario}</logonUsuario>
                      <senhaUsuario>{self.senha}</senhaUsuario>
                      <idCliente>{self.id_cliente}</idCliente>
                      <idAcao>{self.id_acao}</idAcao>
                      <descricaoAcao>{self.descricao_acao}</descricaoAcao>
                      <ddd>{self.ddd}</ddd>
                      <telefone>{self.telefone}</telefone>
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

  @staticmethod
  def _normalizar_detalhes(valor):
    if valor is None:
      return []
    if isinstance(valor, (list, tuple)):
      return list(valor)
    return [valor]

  @classmethod
  def _gerar_xml_detalhes(cls, nmDetalhe, vlrDetalhe, qtdDetalhe) -> str:
    nomes = cls._normalizar_detalhes(nmDetalhe)
    valores = cls._normalizar_detalhes(vlrDetalhe)
    qtd = int(qtdDetalhe or 0)

    if qtd <= 0:
      return "<ArrayOfAcaoDetalheWebService></ArrayOfAcaoDetalheWebService>"

    if len(nomes) < qtd or len(valores) < qtd:
      raise ValueError("Quantidade de detalhes informada nao corresponde aos nomes/valores enviados.")

    detalhes_xml = ""
    for i in range(qtd):
      detalhes_xml += f'''
                <AcaoDetalheWebService>
                    <NomeDetalhe>{escape(str(nomes[i]))}</NomeDetalhe>
                    <ValorDetalhe>{escape(str(valores[i]))}</ValorDetalhe>
                </AcaoDetalheWebService>
            '''

    return f"<ArrayOfAcaoDetalheWebService>{detalhes_xml}</ArrayOfAcaoDetalheWebService>"

  @log_collectsys_method()
  def acao_com_detalhes(self, nmDetalhe, vlrDetalhe, qtdDetalhe) -> str:
    url = ""
    if self.servidor.lower() == "vega":
      url = "http://10.0.0.18/easycollectorws/easycollectorWs.asmx?op=InserirAcaoComDetalhe"
    else:
      url = "http://10.0.0.64/easycollectorws/easycollectorWs.asmx?op=InserirAcaoComDetalhe"


    detalhe = self._gerar_xml_detalhes(nmDetalhe, vlrDetalhe, qtdDetalhe)

    headers = {'content-type': 'application/soap+xml'}
    body = f'''<?xml version="1.0" encoding="utf-8"?>
                    <soap12:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap12="http://www.w3.org/2003/05/soap-envelope">
                     <soap12:Body>
                       <InserirAcaoComDetalhe xmlns="http://soap.collectsys.example/easycollectorws/">
                         <logonUsuario>{self.usuario}</logonUsuario>
                         <senhaUsuario>{self.senha}</senhaUsuario>
                         <idCliente>{self.id_cliente}</idCliente>
                         <idAcao>{self.id_acao}</idAcao>
                         <descricaoAcao>{self.descricao_acao}</descricaoAcao>
                         <ddd>{self.ddd}</ddd>
                         <telefone>{self.telefone}</telefone>
                         <detalhesXml><![CDATA[{detalhe}]]></detalhesXml>
                       </InserirAcaoComDetalhe>
                     </soap12:Body>
                   </soap12:Envelope>
             '''
    return self._post_soap(
      method_name="acao_com_detalhes",
      url=url,
      body=body,
      headers=headers,
      response_transform=lambda text: text.replace("&lt;", "<").replace("&gt;", ">"),
    )



  @log_collectsys_method()
  def acao_com_divida(self, divida_xml) -> str:
    url = ""
    if "vega" in self.servidor.lower():
      url = "http://10.0.0.18/easycollectorws/easycollectorWs.asmx?op=InserirAcaoComDivida"
    else:
      url = "http://10.0.0.64/easycollectorws/easycollectorWs.asmx?op=InserirAcaoComDivida"

    headers = {'content-type': 'text/xml'}
    body = f'''<?xml version="1.0" encoding="utf-8"?>
                    <soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
                      <soap:Body>
                        <InserirAcaoComDivida xmlns="http://soap.collectsys.example/easycollectorws/">
                          <logonUsuario>{self.usuario}</logonUsuario>
                          <senhaUsuario>{self.senha}</senhaUsuario>
                          <idCliente>{self.id_cliente}</idCliente>
                          <idAcao>{self.id_acao}</idAcao>
                          <descricaoAcao>{self.descricao_acao}</descricaoAcao>
                          <ddd>{self.ddd}</ddd>
                          <telefone>{self.telefone}</telefone>
                          <detalhesXml></detalhesXml>
                          <dividaXml><![CDATA[{divida_xml}]]></dividaXml>
                        </InserirAcaoComDivida>
                      </soap:Body>
                    </soap:Envelope>
             '''
    return self._post_soap(
      method_name="acao_com_divida",
      url=url,
      body=body,
      headers=headers,
      response_transform=lambda text: text.replace("&lt;", "<").replace("&gt;", ">"),
    )
