from src.application.gateways.divida_ativa_gateway import DividaAtivaGateway
from src.domain.dtos.divida_ativa_dto import CedenteDividaDTO
from src.domain.exceptions.collectsys_exception import NenhumaDividaException
from src.infrastructure.external.collectsys.gateways.divida_ativa_collectsys_gateway import CollectSysDividaAtivaGateway


class DadosDivida:
    @staticmethod
    async def obter_cedentes(cpf_cnpj: str) -> list[dict]:
        gateways: list[DividaAtivaGateway] = [
            CollectSysDividaAtivaGateway(),
        ]

        cedentes: list[CedenteDividaDTO] = []

        for gateway in gateways:
            cedentes.extend(await gateway.obter_por_cpf(cpf_cnpj))

        if not cedentes:
            raise NenhumaDividaException(
                "No momento, não constam dívidas ativas do cliente em nossa assessoria."
            )

        return DadosDivida._serializar_cedentes(cedentes)

    @staticmethod
    def _serializar_cedentes(cedentes: list[CedenteDividaDTO]) -> list[dict]:
        retorno: list[dict] = []

        for cedente in cedentes:
            item: dict = {
                "origem": cedente.origem,
                "cedente": cedente.cedente,
                "idCedente": cedente.id_cedente,
                "idCliente": cedente.id_cliente,
            }

            if cedente.contratos:
                item["Contratos"] = [
                    {
                        "idContrato": contrato.id_contrato,
                        "grupo": contrato.grupo,
                    }
                    for contrato in cedente.contratos
                ]

            if cedente.acordos:
                item["Acordos"] = [
                    {
                        "grupo": acordo.grupo,
                        "idAcordo": acordo.id_acordo,
                        "valor": acordo.valor,
                        "dataPagamento": acordo.data_pagamento,
                    }
                    for acordo in cedente.acordos
                ]

            retorno.append(item)

        return retorno