from .dados_usuario import DadosUsuario
from src.shared.utils import *
from .method_logger import log_collectsys_method


class ConsultaDividaDetalhe(DadosUsuario):
    def __init__(self, idCliente, xml_divida, id_cedente):
        if id_cedente == 1:
            servidor = "vega"
        else:
            servidor = "cobranca"
        super().__init__(servidor)
        self.idCliente = idCliente
        self.idContato, self.divida = ajusta_xml(xml_divida)


    @log_collectsys_method()
    def consulta(self):
        url = "http://10.0.0.64/easycollectorws/easycollectorWs.asmx?op=ConsultarDividaDetalhes"

        headers = {'content-type': 'text/xml'}
        body = (f'''<?xml version="1.0" encoding="utf-8"?>
                    <soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
                    <soap:Body>
                        <ConsultarDividaDetalhes xmlns="http://soap.collectsys.example/easycollectorws/">
                        <logonUsuario>{self.usuario}</logonUsuario>
                        <senhaUsuario>{self.senha}</senhaUsuario>
                        <idCliente>{self.idCliente}</idCliente>
                        <idContrato>{self.idContato}</idContrato>
                        <idDivida>{self.divida}</idDivida>
                        </ConsultarDividaDetalhes>
                    </soap:Body>
                    </soap:Envelope>
                '''
                )

        return self._post_soap(
            method_name="consulta",
            url=url,
            body=body,
            headers=headers,
            response_transform=lambda text: text.replace("&lt;", "<").replace("&gt;", ">"),
        )

    @log_collectsys_method()
    def consultar_divida(self):
        tentativas_max = 10
        for tentativa in range(1, tentativas_max + 1):
            resultado = self.consulta()

            if '<Mensagem>Não há detalhe de divida para o contrato do cliente.</Mensagem>' in resultado:
                resultado = []
                produto = 'CAMPANHA ENTRADA R$100,00_V21'
                tipo = 'BOLETO'
                resultado.append((produto, tipo))

                return resultado

            else:
                resultado = extrair_tag(resultado, "<Valor>", "</Valor>")
                valores = resultado.split("</Valor><Valor>")

                for v in valores:
                    resultado = []
                    v = v.replace("<Valor>", "").replace("</Valor>", "").strip()
                    partes = v.split(";")

                    primeiro = partes[0] if len(partes) > 0 else None
                    quinto = partes[5] if len(partes) > 5 else None

                    resultado.append((primeiro, quinto))


            return resultado
        return resultado
