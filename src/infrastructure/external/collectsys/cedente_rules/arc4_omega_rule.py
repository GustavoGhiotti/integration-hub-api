import re

from src.shared.utils.xml_tratamentos import extrair_array

from .arc4_rule import Arc4CedenteRule


class Arc4OmegaCedenteRule(Arc4CedenteRule):
    """O cedente 96 recebe todas as parcelas marcadas para o cálculo."""

    def montar_xml_divida_calcular_acordo(self, calcular, parcelado: str = "") -> str:
        return self._marcar_todas_parcelas(calcular.xml_divida)

    def montar_xml(self, context):
        context.xml_divida = self._marcar_todas_parcelas(context.xml_divida)
        super().montar_xml(context)
        context.desconto = 200

    def _marcar_todas_parcelas(self, xml_divida: str) -> str:
        parcelas = []
        xml_restante = xml_divida or ""

        while "<DividaAtiva>" in xml_restante:
            divida = extrair_array(xml_restante, "<DividaAtiva>", "</DividaAtiva>")
            if not divida:
                break

            divida_original = divida
            divida = re.sub(
                r"<Marcado>\s*(?:true|false)\s*</Marcado>",
                "<Marcado>true</Marcado>",
                divida,
                count=1,
                flags=re.IGNORECASE,
            )
            parcelas.append(divida)

            xml_restante = xml_restante.replace(divida_original, "", 1)

        return f"<ArrayOfDividaAtiva>{''.join(parcelas)}</ArrayOfDividaAtiva>"
