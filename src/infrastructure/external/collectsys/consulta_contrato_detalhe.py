from .dados_usuario import DadosUsuario
from src.shared.utils import *
from .method_logger import log_collectsys_method


class ConsultaContratoDetalhe(DadosUsuario):
    def __init__(self, idCliente, idContrato):
        super().__init__("Cobranca")
        self.idCliente = idCliente
        self.idContato = idContrato

    @staticmethod
    def extrair_nm_produto(xml: str) -> str | None:
        return extrair_nm_produto(xml)

    @staticmethod
    def extrair_valor_detalhe(xml: str, nome: str, like: bool = False) -> str | None:
        detalhes_xml = extrair_tag(xml, "<ArrayOfContratoDetalhe>", "</ArrayOfContratoDetalhe>") or xml
        nome_normalizado = normalizar_nome(nome)

        while "<ContratoDetalhe>" in detalhes_xml:
            detalhe = extrair_array(detalhes_xml, "<ContratoDetalhe>", "</ContratoDetalhe>")
            if not detalhe:
                break

            nome_detalhe = normalizar_nome(extrair_tag(detalhe, "<NomeDetalhe>", "</NomeDetalhe>") or "")
            if (nome_normalizado in nome_detalhe) if like else (nome_detalhe == nome_normalizado):
                return extrair_tag(detalhe, "<Valor>", "</Valor>")

            detalhes_xml = detalhes_xml.replace(detalhe, "", 1)

        return None

    @staticmethod
    def extrair_valores_detalhe(xml: str, nome: str, like: bool = False) -> list[str]:
        """Retorna todos os valores cujo NomeDetalhe casa com `nome`, na ordem do XML."""
        detalhes_xml = extrair_tag(xml, "<ArrayOfContratoDetalhe>", "</ArrayOfContratoDetalhe>") or xml
        nome_normalizado = normalizar_nome(nome)
        valores = []

        while "<ContratoDetalhe>" in detalhes_xml:
            detalhe = extrair_array(detalhes_xml, "<ContratoDetalhe>", "</ContratoDetalhe>")
            if not detalhe:
                break

            nome_detalhe = normalizar_nome(extrair_tag(detalhe, "<NomeDetalhe>", "</NomeDetalhe>") or "")
            casa = (nome_normalizado in nome_detalhe) if like else (nome_detalhe == nome_normalizado)
            if casa:
                valor = extrair_tag(detalhe, "<Valor>", "</Valor>")
                if valor and valor.strip() and valor.strip() not in valores:
                    valores.append(valor.strip())

            detalhes_xml = detalhes_xml.replace(detalhe, "", 1)

        return valores

    @log_collectsys_method()
    def consulta(self):
        url = "http://10.0.0.64/easycollectorws/easycollectorWs.asmx?op=ConsultarContratoDetalhes"

        headers = {'content-type': 'text/xml'}
        body = (f'''<?xml version="1.0" encoding="utf-8"?>
                    <soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
                    <soap:Body>
                        <ConsultarContratoDetalhes xmlns="http://soap.collectsys.example/easycollectorws/">
                        <logonUsuario>{self.usuario}</logonUsuario>
                        <senhaUsuario>{self.senha}</senhaUsuario>
                        <idCliente>{self.idCliente}</idCliente>
                        <idContrato>{self.idContato}</idContrato>
                        </ConsultarContratoDetalhes>
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

        return resultado

    @log_collectsys_method()
    def consultar_nm_produto(self):
        resultado = self.consulta()
        valores = self.extrair_valores_detalhe(resultado, "PRODUTO", like=True)
        return " - ".join(valores) if valores else None

    @log_collectsys_method()
    def consultar_produto_nu(self):
        resultado = self.consulta()
        produto = self.extrair_valor_detalhe(resultado, "DESCRICAO DO BEM")
        if produto and produto.strip():
            return produto.strip()

        return None

    @log_collectsys_method()
    def consultar_produto_zeta(self):
        resultado = self.consulta()
        return self.extrair_valor_detalhe(resultado, "NMPRODUTOCEDENTE")

    @log_collectsys_method()
    def consultar_detalhes_delta(self):
        resultado = self.consulta()
        return {
            "produto": self.extrair_valor_detalhe(resultado, "PRODUTO"),
            "idt20": self.extrair_valor_detalhe(resultado, "IDT_20"),
        }

    @log_collectsys_method()
    def consultar_produto_teta(self):
        resultado = self.consulta()
        return self.extrair_valor_detalhe(resultado, "PRODUTO TETA")

    @log_collectsys_method()
    def consultar_produto_arc(self):
        resultado = self.consulta()
        produto = self.extrair_valor_detalhe(resultado, "NOME_ESTRATEGIA")
        if produto and produto.strip():
            return produto.strip()

        return None

    @log_collectsys_method()
    def consultar_produto_pi(self):
        resultado = self.consulta()
        for nome in ("PRODUTO", "PRODUTO PI"):
            produto = self.extrair_valor_detalhe(resultado, nome)
            if produto and produto.strip():
                return produto.strip()

        return None

    @log_collectsys_method()
    def consultar_detalhes_teta(self):
        resultado = self.consulta()
        return {
            "produto": self.extrair_valor_detalhe(resultado, "PRODUTO TETA"),
            "valorCurvaAtraso": self.extrair_valor_detalhe(resultado, "VALOR_CURVA_ATRASO"),
        }
