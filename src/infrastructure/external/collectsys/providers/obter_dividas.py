from .dados_usuario import DadosUsuario
from src.domain.exceptions.collectsys_exception import CollectSysException
from .method_logger import log_collectsys_method
from ..dto.obter_divida_request import ObterDividaCpfRequest, ObterDividaIdRequest
from ..carteiras.interface import CollectSysCarteiraProtocol   

class ObterDivida:
    def __init__(self, carteira:CollectSysCarteiraProtocol):
        self.url = carteira.url
        self.credenciais = carteira.obter_credenciais()

    @log_collectsys_method()
    def consultar_por_cpf(self, request: ObterDividaCpfRequest) -> str:
        url = self.url + "ObterDividaAtivaPorCPF" 

        headers = {'content-type': 'text/xml'}
        body = (f'''<?xml version="1.0" encoding="utf-8"?>
                <soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
                <soap:Body>
                    <ObterDividaAtivaPorCPF xmlns="http://soap.collectsys.example/easycollectorws/">
                        <logonUsuario>{self.credenciais.usuario}</logonUsuario>
                        <senhaUsuario>{self.credenciais.senha}</senhaUsuario>
                        <cpfCnpj>{request.cpf}</cpfCnpj>
                    </ObterDividaAtivaPorCPF>
                </soap:Body>
                </soap:Envelope>''')
        resultado = self._post_soap(
            method_name="ObterDividaAtivaPorCPF",
            url=url,
            body=body,
            headers=headers,
            response_transform=lambda text: text.replace("&lt;", "<").replace("&gt;", ">"),
        )
    
        return resultado

    @log_collectsys_method()
    def consultar_por_id(self, request: ObterDividaIdRequest):
        url = self.url + "ObterDividaAtiva"

        headers = {'content-type': 'text/xml'}
        body = f"""<?xml version="1.0" encoding="utf-8"?>
                <soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
                    <soap:Body>
                    <ObterDividaAtiva xmlns="http://soap.collectsys.example/easycollectorws/">
                        <logonUsuario>{self.credenciais.usuario}</logonUsuario>
                        <senhaUsuario>{self.credenciais.senha}</senhaUsuario>
                        <idCliente>{request.id_cliente}</idCliente>
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
