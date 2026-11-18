from src.shared.utils.xml_tratamentos import extrair_tag, extrair_array


def obter_tipo_pagamento_delta(calculo) -> str:
    vencimento_original = calculo.vencimento
    valor_entrada_original = calculo.valor_entrada
    try:
        resultado = calculo.calcular_acordo()
    finally:
        calculo.vencimento = vencimento_original
        calculo.valor_entrada = valor_entrada_original

    possivel_detalhes = extrair_tag(
        resultado,
        "<DetalhesAcordoValoresPossiveis>",
        "</DetalhesAcordoValoresPossiveis>",
    )
    if not possivel_detalhes:
        raise ValueError("DetalhesAcordoValoresPossiveis nao encontrado no XML.")

    valores = set()
    while "<AcordoDetalhe>" in possivel_detalhes:
        detalhe = extrair_array(
            possivel_detalhes, "<AcordoDetalhe>", "</AcordoDetalhe>"
        )
        if not detalhe:
            break
        valor = extrair_tag(detalhe, "<Valor>", "</Valor>")
        if valor:
            valores.add(valor.strip().upper())
        possivel_detalhes = possivel_detalhes.replace(detalhe, "")

    if "PIX" in valores:
        return "PIX"
    if "BOLETO" in valores:
        return "BOLETO"

    raise ValueError("Nenhum tipo de pagamento valido encontrado (PIX/BOLETO).")
