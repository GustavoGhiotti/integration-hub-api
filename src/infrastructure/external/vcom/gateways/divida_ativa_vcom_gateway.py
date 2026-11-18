from src.application.gateways.divida_ativa_gateway import DividaAtivaGateway
from src.application.services.vcom.credor_id import id_credor_externo
from src.domain.dtos.divida_ativa_dto import CedenteDividaDTO, ContratoResumoDTO
from src.infrastructure.external.vcom import VcomTitulo


class VcomDividaAtivaGateway(DividaAtivaGateway):
    def __init__(self, titulo_provider: VcomTitulo | None = None):
        self.titulo_provider = titulo_provider or VcomTitulo()

    async def obter_por_cpf(self, cpf: str) -> list[CedenteDividaDTO]:
        titulos = self.titulo_provider.consultar_por_cpf(cpf)
        cedentes: dict[int, CedenteDividaDTO] = {}

        for titulo in titulos:
            id_credor = int(titulo.get("COD_CRED") or 0)
            titulo_em_aberto = bool(titulo.get("EM_ABERTO", True))
            if id_credor not in cedentes:
                cedentes[id_credor] = CedenteDividaDTO(
                    origem="VCOM",
                    cedente=titulo.get("NOME_CRED") or "VCOM",
                    id_cedente=id_credor_externo(id_credor),
                    id_cliente=cpf,
                    possui_divida_ativa=titulo_em_aberto,
                )
            elif titulo_em_aberto:
                cedentes[id_credor].possui_divida_ativa = True

            # A carteira deve continuar visivel mesmo quando todos os titulos
            # estiverem fechados, mas contrato fechado nao pode ser negociado.
            if not titulo_em_aberto:
                continue

            contrato = str(titulo.get("CONTRATO_TIT") or "").strip()
            parcelas = self._parcelas_abertas(titulo)
            cedentes[id_credor].contratos.append(
                ContratoResumoDTO(
                    id_contrato=contrato,
                    grupo=titulo.get("NOME_CRED") or "VCOM",
                    contrato=contrato,
                    id_credor=id_credor_externo(id_credor),
                    cpf_cnpj=cpf,
                    parcelas=parcelas,
                )
            )

        return list(cedentes.values())

    def _parcelas_abertas(self, titulo: dict) -> list[dict]:
        parcelas = []
        for parcela in titulo.get("PARCELAS") or []:
            if str(parcela.get("STATUS_PARC") or "").upper() != "ABERTO":
                continue

            parcelas.append(
                {
                    "numero": int(parcela.get("NUMERO_PARC") or 0),
                    "vencimento": str(parcela.get("VCTO_PARC") or "").split("T", 1)[0],
                    "valor": float(parcela.get("VR_PARC") or 0),
                    "valorOriginal": float(parcela.get("VR_ORIG_PARC") or parcela.get("VR_PARC") or 0),
                    "codigoParcela": parcela.get("COD_PARC"),
                }
            )
        return parcelas
