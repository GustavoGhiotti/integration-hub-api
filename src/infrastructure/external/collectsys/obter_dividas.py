from .dados_usuario import DadosUsuario
from src.domain.exceptions.collectsys_exception import CollectSysException
from .method_logger import log_collectsys_method

class ObterDivida(DadosUsuario):
    def __init__(self, servidor:str):
        super().__init__(servidor)

    @log_collectsys_method()
    def consultar_por_cpf(self, cpf: str):
        url = self.url + "ObterDividaAtivaPorCPF"

        headers = {'content-type': 'text/xml'}
        body = (f'''<?xml version="1.0" encoding="utf-8"?>
                <soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
                <soap:Body>
                    <ObterDividaAtivaPorCPF xmlns="http://soap.collectsys.example/easycollectorws/">
                        <logonUsuario>{self.usuario}</logonUsuario>
                        <senhaUsuario>{self.senha}</senhaUsuario>
                        <cpfCnpj>{cpf}</cpfCnpj>
                    </ObterDividaAtivaPorCPF>
                </soap:Body>
                </soap:Envelope>''')
        resultado = self._post_soap(
            method_name="consultar_por_cpf",
            url=url,
            body=body,
            headers=headers,
            response_transform=lambda text: text.replace("&lt;", "<").replace("&gt;", ">"),
        )

        return resultado

    @log_collectsys_method()
    def consultar_por_id(self, id_cliente: int):
        url = self.url + "ObterDividaAtiva"

        headers = {'content-type': 'text/xml'}
        body = f"""<?xml version="1.0" encoding="utf-8"?>
                <soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
                    <soap:Body>
                    <ObterDividaAtiva xmlns="http://soap.collectsys.example/easycollectorws/">
                        <logonUsuario>{self.usuario}</logonUsuario>
                        <senhaUsuario>{self.senha}</senhaUsuario>
                        <idCliente>{id_cliente}</idCliente>
                    </ObterDividaAtiva>
                    </soap:Body>
                </soap:Envelope>
                """

        resultado = self._post_soap(
            method_name="consultar_por_id",
            url=url,
            body=body,
            headers=headers,
            response_transform=lambda text: text.replace("&lt;", "<").replace("&gt;", ">"),
        )

        return resultado
