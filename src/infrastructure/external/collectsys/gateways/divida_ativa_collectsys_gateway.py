import asyncio

from src.application.gateways.divida_ativa_gateway import DividaAtivaGateway
from src.domain.dtos.divida_ativa_dto import AcordoResumoDTO, CedenteDividaDTO, ContratoResumoDTO
from src.domain.entities.contrato import Contrato
from src.infrastructure.external.collectsys import DadosAcordo, ObterDivida
from src.shared.utils.xml_tratamentos import extrair_array, extrair_tag

class CollectSysDividaAtivaGateway(DividaAtivaGateway):
    _MENSAGENS_SEM_DIVIDA: tuple[str, ...] = (
        "Nenhum cliente localizado com este CPFCNPJ.",
        "O cliente não possui dívida ativa.",
    )

    async def obter_por_cpf(self, cpf: str) -> list[CedenteDividaDTO]:
        divida_cobranca, divida_vega = await asyncio.gather(
            asyncio.to_thread(lambda: ObterDivida("Cobrancas").consultar_por_cpf(cpf)),
            asyncio.to_thread(lambda: ObterDivida("Vega").consultar_por_cpf(cpf)),
        )

        cedentes: list[CedenteDividaDTO] = []

        for xml in (divida_vega, divida_cobranca):
            if self._sem_divida(xml):
                continue

            cedentes.extend(self._mapear_xml(xml))

        return self._agrupar_cedentes(cedentes)

    def _sem_divida(self, xml: str) -> bool:
        return any(mensagem in xml for mensagem in self._MENSAGENS_SEM_DIVIDA)

    def _mapear_xml(self, xml: str) -> list[CedenteDividaDTO]:
        cedentes: list[CedenteDividaDTO] = []

        while "<DividaAtiva>" in xml:
            divida_xml = extrair_array(xml, "<DividaAtiva>")

            nome_cedente = extrair_tag(divida_xml, "NmCedente") or ""
            id_cedente = int(extrair_tag(divida_xml, "IdCedente") or 0)
            id_cliente = int(extrair_tag(divida_xml, "IdCliente") or 0)
            tipo_divida = extrair_tag(divida_xml, "TipoDivida") or ""

            cedente = CedenteDividaDTO(
                origem="COLLECTSYS",
                cedente=nome_cedente,
                id_cedente=id_cedente,
                id_cliente=id_cliente,
            )

            if "acordo" in tipo_divida.lower():
                id_acordo = int(extrair_tag(divida_xml, "IdAcordo") or 0)
                faturas_xml = DadosAcordo(nome_cedente, id_cliente, id_acordo).obter_faturas()
                acordo = Contrato(faturas_xml, nome_cedente, id_cedente, id_cliente).acordo(1)

                cedente.acordos.append(
                    AcordoResumoDTO(
                        id_acordo=acordo.id_acordo,
                        grupo=acordo.nome_cedente,
                        valor=acordo.valor,
                        data_pagamento=acordo.vencimento_boleto,
                    )
                )
            else:
                contrato = Contrato(divida_xml, nome_cedente, id_cedente, id_cliente).divida()

                cedente.contratos.append(
                    ContratoResumoDTO(
                        id_contrato=contrato.id_contrato,
                        grupo=contrato.nome_cedente,
                    )
                )

            cedentes.append(cedente)
            xml = xml.replace(divida_xml, "")

        return cedentes

    def _agrupar_cedentes(self, cedentes: list[CedenteDividaDTO]) -> list[CedenteDividaDTO]:
        agrupados: dict[tuple[str, int], CedenteDividaDTO] = {}

        for cedente in cedentes:
            chave = (cedente.origem, cedente.id_cedente)

            if chave not in agrupados:
                agrupados[chave] = CedenteDividaDTO(
                    origem=cedente.origem,
                    cedente=cedente.cedente,
                    id_cedente=cedente.id_cedente,
                    id_cliente=cedente.id_cliente,
                )

            destino = agrupados[chave]

            ids_contratos = {contrato.id_contrato for contrato in destino.contratos}
            for contrato in cedente.contratos:
                if contrato.id_contrato not in ids_contratos:
                    destino.contratos.append(contrato)

            ids_acordos = {acordo.id_acordo for acordo in destino.acordos}
            for acordo in cedente.acordos:
                if acordo.id_acordo not in ids_acordos:
                    destino.acordos.append(acordo)

        return list(agrupados.values())
