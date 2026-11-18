import re
import unicodedata
from datetime import datetime


def _normalizar_tag(tag: str) -> str:
    return str(tag or "").strip().strip("<>").lstrip("/")


def extrair_tag(xml: str, tag: str, tag_fechamento: str | None = None) -> str | None:
    tag_abertura = _normalizar_tag(tag)
    tag_final = _normalizar_tag(tag_fechamento or tag)
    inicio_tag = f"<{tag_abertura}>"
    fim_tag = f"</{tag_final}>"
    conteudo = xml or ""
    inicio = conteudo.find(inicio_tag) + len(inicio_tag)
    fim = conteudo.find(fim_tag, inicio)
    return conteudo[inicio:fim] if inicio > -1 and fim > -1 else None


def extrair_array(xml: str, tag: str, tag_fechamento: str | None = None) -> str | None:
    tag_abertura = _normalizar_tag(tag)
    tag_final = _normalizar_tag(tag_fechamento or tag)
    inicio_tag = f"<{tag_abertura}>"
    fim_tag = f"</{tag_final}>"
    conteudo = xml or ""
    inicio = conteudo.find(inicio_tag)
    fim = conteudo.find(fim_tag, inicio) + len(fim_tag)
    return conteudo[inicio:fim] if inicio > -1 and fim > -1 else None

def extrair_tags(xml: str, tag: str) -> tuple[int, ...]:
    tag_normalizada = _normalizar_tag(tag)
    valores = re.findall(fr"<{tag_normalizada}>(.*?)</{tag_normalizada}>", xml or "", re.DOTALL)
    return tuple(int(valor) for valor in valores)


def capturar_parcelamento_max(resultado: str) -> int | None:
    try:
        mensagem = extrair_tag(resultado, "<Mensagem>")
        mensagem = mensagem or resultado

        match = re.search(
                r"menor\s*\((\d+)\).*?maior\s*\((\d+)\)",
                mensagem,
                re.IGNORECASE
            )
        if match:
            return int(match.group(2))

        match = re.search(
            r"plano m[íi]nimo\s*[ée]?\s*(\d+).*?plano m[áa]ximo\s*[ée]?\s*(\d+)",
            mensagem,
            re.IGNORECASE | re.DOTALL,
        )
        if match:
            return int(match.group(2))

        match = re.search(
            r"plano m[áa]ximo permitido [^0-9]*(\d+)",
            mensagem,
            re.IGNORECASE | re.DOTALL,
        )
        if match:
            return int(match.group(1))

        match = re.search(
            r"(?:em|de|ate|at[Ã©e])\s*(\d+)\s*parcela",
            mensagem,
            re.IGNORECASE | re.DOTALL,
        )
        if match:
            return int(match.group(1))

        return None
    except Exception:
        return None


def capturar_intervalo_parcelamento(resultado: str) -> tuple[int | None, int | None]:
    try:
        mensagem = extrair_tag(resultado, "<Mensagem>")
        mensagem = mensagem or resultado

        match_min = re.search(
            r"quantidade de parcelas deve ser no m\S*nimo(?: igual a)?\s*(\d+)",
            mensagem,
            re.IGNORECASE | re.DOTALL,
        )
        if match_min:
            return int(match_min.group(1)), None

        match_plano = re.search(
            r"plano m\S*nimo\s*(?:[ée]\s*)?(?:de\s*)?(\d+).*?m\S*ximo\s*(?:[ée]\s*)?(?:de\s*)?(\d+)",
            mensagem,
            re.IGNORECASE | re.DOTALL,
        )
        if match_plano:
            return int(match_plano.group(1)), int(match_plano.group(2))

        match = re.search(
            r"menor\s*\((\d+)\).*?maior\s*\((\d+)\)",
            mensagem,
            re.IGNORECASE | re.DOTALL,
        )
        if match:
            return int(match.group(1)), int(match.group(2))

        match = re.search(
            r"plano m[Ã­i]nimo\s*[Ã©e]?\s*(\d+).*?plano m[Ã¡a]ximo\s*[Ã©e]?\s*(\d+)",
            mensagem,
            re.IGNORECASE | re.DOTALL,
        )
        if match:
            return int(match.group(1)), int(match.group(2))

        match_max = re.search(
            r"plano m[Ã¡a]ximo permitido [^0-9]*(\d+)",
            mensagem,
            re.IGNORECASE | re.DOTALL,
        )
        if match_max:
            return None, int(match_max.group(1))

        return None, None
    except Exception:
        return None, None

def mensagem_retorno_calculo(resultado: str) -> str | None:
    if not resultado:
        return None

    mensagem = extrair_tag(resultado, "<Mensagem>", "</Mensagem>")
    if mensagem:
        return mensagem.strip()

    resultado_limpo = re.sub(r"<[^>]+>", " ", str(resultado))
    resultado_limpo = re.sub(r"\s+", " ", resultado_limpo).strip()
    return resultado_limpo or None


def _converter_valor_monetario(valor: str) -> float:
    valor = re.sub(r"[^0-9,.]", "", valor or "")
    if not valor:
        raise ValueError("Valor monetario vazio")

    if "," in valor and "." in valor:
        # O ultimo separador e o decimal: 1.234,56 ou 1,234.56.
        if valor.rfind(",") > valor.rfind("."):
            valor = valor.replace(".", "").replace(",", ".")
        else:
            valor = valor.replace(",", "")
    elif "," in valor:
        inteiro, decimal = valor.rsplit(",", 1)
        valor = inteiro.replace(",", "") + (f".{decimal}" if len(decimal) <= 2 else decimal)
    elif "." in valor:
        inteiro, decimal = valor.rsplit(".", 1)
        if valor.count(".") == 1 and len(decimal) <= 2:
            valor = f"{inteiro}.{decimal}"
        else:
            valor = valor.replace(".", "")

    return float(valor)


def capturar_valor(xml: str) -> float | None:
    try:
        mensagem = extrair_tag(xml, "<Mensagem>")

        padrao_com_moeda = re.search(r'R\$ ?([\d\.,]+)', mensagem)
        if padrao_com_moeda:
            return _converter_valor_monetario(padrao_com_moeda.group(1))

        padrao_com_virgula = re.search(r'(\d[\d\.]*,\d+)', mensagem)
        if padrao_com_virgula:
            return _converter_valor_monetario(padrao_com_virgula.group(1))

        return None

    except Exception:
        return None


def capturar_intervalo_valor_entrada_cedente_81(resultado: str) -> tuple[float | None, float | None]:
    try:
        mensagem = extrair_tag(resultado, "<Mensagem>") or resultado or ""

        def converter(valor: str) -> float:
            if "," in valor:
                valor = valor.replace(".", "").replace(",", ".")
            return float(valor)

        padrao_valor = r"\(\s*(?:r\s*\$\s*)?([\d\.,]+)\s*\)"
        valor_minimo = re.search(rf"menor\s*{padrao_valor}", mensagem, re.IGNORECASE | re.DOTALL)
        valor_maximo = re.search(rf"maior\s*{padrao_valor}", mensagem, re.IGNORECASE | re.DOTALL)

        if valor_minimo and valor_maximo:
            return converter(valor_minimo.group(1)), converter(valor_maximo.group(1))

        faixa_entre = re.search(
            r"entre\s+([\d\.,]+)\s+e\s+([\d\.,]+)",
            mensagem,
            re.IGNORECASE | re.DOTALL
        )

        if faixa_entre:
            return converter(faixa_entre.group(1)), converter(faixa_entre.group(2))

        return None, None

    except Exception:
        return None, None


def tratativa_palavra(texto: str, padrao: str) -> bool:
    """Simula o comportamento do LIKE '%padrao%' do SQL, ignorando maiusculas/minusculas e espacos extras."""
    texto_normalizado = ' '.join(texto.lower().split())
    padrao_normalizado = padrao.lower().strip('%').strip()
    return padrao_normalizado in texto_normalizado


def ajusta_xml(xml_divida:str):
    idDivida = int(extrair_tag(xml_divida, "<IdDivida>"))
    IdContrato = int(extrair_tag(xml_divida, "<IdContrato>"))
    return IdContrato, idDivida


def valor_tag_xml(xml: str, tag: str, padrao: str = "") -> str:
    valor = extrair_tag(xml, f"<{tag}>", f"</{tag}>")
    return valor if valor not in (None, "") else padrao


def valor_decimal_xml(xml: str, tag: str, fallback: str = "0") -> str:
    valor = valor_tag_xml(xml, tag, fallback)
    try:
        if float(valor) == 0 and fallback != "0":
            return fallback
    except ValueError:
        return fallback
    return valor


def calcular_atraso_xml(data_vencimento: str, data_pagamento: str) -> int:
    try:
        data_vencimento = re.sub(r"T.*", "", data_vencimento or "")
        data_pagamento = re.sub(r"T.*", "", data_pagamento or "")
        vencimento = datetime.strptime(data_vencimento, "%Y-%m-%d")
        pagamento = datetime.strptime(data_pagamento, "%Y-%m-%d")
        return max((pagamento - vencimento).days, 0)
    except Exception:
        return 0


def chave_divida_tabular(xml: str) -> tuple[str, str, str]:
    return (
        valor_tag_xml(xml, "IdContrato"),
        valor_tag_xml(xml, "IdDivida"),
        valor_tag_xml(xml, "DividaCedente"),
    )


def divida_original_valida_tabular(xml: str) -> bool:
    tipo_divida = valor_tag_xml(xml, "TipoDivida").strip().lower()
    id_contrato = valor_tag_xml(xml, "IdContrato").strip()
    id_divida = valor_tag_xml(xml, "IdDivida").strip()
    divida_cedente = valor_tag_xml(xml, "DividaCedente").strip()
    return (
        tipo_divida == "original"
        and id_contrato not in ("", "0")
        and id_divida not in ("", "0")
        and divida_cedente != ""
    )


def adicionar_divida_unica_tabular(dividas: list[str], chaves: set[tuple[str, str, str]], divida: str):
    chave = chave_divida_tabular(divida)
    if chave in chaves:
        return

    chaves.add(chave)
    dividas.append(divida.replace("<Marcado>false</Marcado>", "<Marcado>true</Marcado>"))


def montar_divida_original_acordo_tabular(
    original: str,
    acordo: str,
    divida_contexto: str,
    id_cliente: int,
    servidor: str,
) -> str:
    data_pagamento = (
        valor_tag_xml(acordo, "DataCalculo")
        or valor_tag_xml(divida_contexto, "DataPagamento")
        or valor_tag_xml(original, "DataVencimento")
    )
    data_vencimento = valor_tag_xml(original, "DataVencimento")
    valor_calculo = valor_tag_xml(original, "ValorDividaCalculo", "0")
    valor_integral = valor_decimal_xml(original, "ValorDividaIntegral", valor_calculo)
    atraso = calcular_atraso_xml(data_vencimento, data_pagamento)

    return f"""<DividaAtiva>
    <Marcado>true</Marcado>
    <TipoDivida>Original</TipoDivida>
    <Identificador>{valor_tag_xml(original, "ContratoCedente", valor_tag_xml(original, "DividaCedente"))}</Identificador>
    <NumeroPrestacao>{valor_tag_xml(original, "NumeroPrestacao", "0")}</NumeroPrestacao>
    <DataVencimento>{data_vencimento}</DataVencimento>
    <ValorDividaIntegral>{valor_integral}</ValorDividaIntegral>
    <ValorDividaCalculo>{valor_calculo}</ValorDividaCalculo>
    <DataCorrecao>{valor_tag_xml(original, "DataCorrecao", "0001-01-01T00:00:00")}</DataCorrecao>
    <ValorCorrecao>{valor_tag_xml(original, "ValorCorrecao", "0")}</ValorCorrecao>
    <ValorMinimo>{valor_tag_xml(original, "ValorMinimo", "0")}</ValorMinimo>
    <DataPagamento>{data_pagamento}</DataPagamento>
    <ValorAtualizado>{valor_tag_xml(divida_contexto, "ValorAtualizado", "0")}</ValorAtualizado>
    <ValorJuros>{valor_tag_xml(original, "ValorJuros", "0")}</ValorJuros>
    <ValorDescontoPrincipal>{valor_tag_xml(original, "ValorDescontoPrincipal", "0")}</ValorDescontoPrincipal>
    <ValorDescontoJuros>{valor_tag_xml(original, "ValorDescontoJuros", "0")}</ValorDescontoJuros>
    <ValorMulta>{valor_tag_xml(original, "ValorMulta", "0")}</ValorMulta>
    <ValorTaxaAdministrativa>{valor_tag_xml(original, "ValorTaxaAdministrativa", "0")}</ValorTaxaAdministrativa>
    <ValorEncargos>{valor_tag_xml(original, "ValorEncargos", "0")}</ValorEncargos>
    <ValorReceita>{valor_tag_xml(divida_contexto, "ValorReceita", "0")}</ValorReceita>
    <ValorRepasse>{valor_tag_xml(original, "ValorRepasse", "0")}</ValorRepasse>
    <Atraso>{atraso}</Atraso>
    <TipoFatura>Nenhum</TipoFatura>
    <IdCliente>{valor_tag_xml(original, "IdCliente", str(id_cliente))}</IdCliente>
    <IdContrato>{valor_tag_xml(original, "IdContrato", "0")}</IdContrato>
    <IdDivida>{valor_tag_xml(original, "IdDivida", "0")}</IdDivida>
    <IdAcordo>0</IdAcordo>
    <IdFatura>0</IdFatura>
    <DividaCedente>{valor_tag_xml(original, "DividaCedente")}</DividaCedente>
    <HashCalculo>0</HashCalculo>
    <IdCedente>{valor_tag_xml(divida_contexto, "IdCedente", str(servidor))}</IdCedente>
    <IdDividaBloqueio>0</IdDividaBloqueio>
    <IdUsuario>0</IdUsuario>
    <TipoOrigemBaixa>{valor_tag_xml(divida_contexto, "TipoOrigemBaixa", "Carga")}</TipoOrigemBaixa>
    <TipoLigacaoContrato>Titular</TipoLigacaoContrato>
    <DivBloqueadaPorAcao>false</DivBloqueadaPorAcao>
    <PercentualDescontoPrincipal>{valor_tag_xml(original, "PercentualDescontoPrincipal", "0")}</PercentualDescontoPrincipal>
    <PercentualDescontoJuros>{valor_tag_xml(original, "PercentualDescontoJuros", "0")}</PercentualDescontoJuros>
    <NmCedente>{valor_tag_xml(divida_contexto, "NmCedente")}</NmCedente>
    <idProduto>{valor_tag_xml(divida_contexto, "idProduto", "0")}</idProduto>
    <NmProduto>{valor_tag_xml(divida_contexto, "NmProduto")}</NmProduto>
    <NmCedenteProduto>{valor_tag_xml(divida_contexto, "NmCedenteProduto")}</NmCedenteProduto>
    <DataInclusao>{valor_tag_xml(original, "DataInclusao", "0001-01-01T00:00:00")}</DataInclusao>
    <idAssessoria>{valor_tag_xml(divida_contexto, "idAssessoria", "0")}</idAssessoria>
    <nmAssessoria>{valor_tag_xml(divida_contexto, "nmAssessoria")}</nmAssessoria>
    <ValorDividaOriginalNovacao>{valor_tag_xml(original, "ValorDividaOriginalNovacao", "0")}</ValorDividaOriginalNovacao>
</DividaAtiva>"""


def adicionar_originais_do_acordo_tabular(
    dividas_tabular: list[str],
    chaves: set[tuple[str, str, str]],
    divida_contexto: str,
    id_cliente: int,
    servidor: str,
    consultar_acordo,
):
    id_acordo = valor_tag_xml(divida_contexto, "IdAcordo")
    if not id_acordo or id_acordo == "0":
        return

    acordo = consultar_acordo(int(id_acordo))
    if not acordo or "<RetornoErro>" in acordo:
        return

    originais = extrair_tag(acordo, "<OriginaisAcordo>", "</OriginaisAcordo>") or acordo
    while "<OriginalAcordo>" in originais:
        original = extrair_array(originais, "<OriginalAcordo>", "</OriginalAcordo>")
        if not original:
            break

        divida = montar_divida_original_acordo_tabular(
            original=original,
            acordo=acordo,
            divida_contexto=divida_contexto,
            id_cliente=id_cliente,
            servidor=servidor,
        )
        if divida_original_valida_tabular(divida):
            adicionar_divida_unica_tabular(dividas_tabular, chaves, divida)

        originais = originais.replace(original, "", 1)


def montar_xml_dividas_para_tabular(
    dividas: str,
    id_cliente: int,
    servidor: str,
    consultar_acordo,
) -> str:
    xml_dividas = extrair_tag(dividas, "<ArrayOfDividaAtiva>", "</ArrayOfDividaAtiva>") or dividas or ""
    dividas_tabular = []
    chaves = set()

    while "<DividaAtiva>" in xml_dividas:
        divida = extrair_array(xml_dividas, "<DividaAtiva>", "</DividaAtiva>")
        if not divida:
            break

        tipo_divida = valor_tag_xml(divida, "TipoDivida").strip().lower()
        if divida_original_valida_tabular(divida):
            adicionar_divida_unica_tabular(dividas_tabular, chaves, divida)
        elif tipo_divida == "parcelaacordo":
            adicionar_originais_do_acordo_tabular(
                dividas_tabular=dividas_tabular,
                chaves=chaves,
                divida_contexto=divida,
                id_cliente=id_cliente,
                servidor=servidor,
                consultar_acordo=consultar_acordo,
            )

        xml_dividas = xml_dividas.replace(divida, "", 1)

    if not dividas_tabular:
        raise ValueError("No momento, nao constam dividas ativas do cliente em nossa assessoria.")

    return f"<ArrayOfDividaAtiva>{''.join(dividas_tabular)}</ArrayOfDividaAtiva>"


def xml_invalido_cedente_77(id_cedente: int, resultado: str) -> bool:
    if id_cedente not in (77, 103):
        return False

    if not resultado or "<Acordo>" not in resultado:
        return True

    plano = extrair_tag(resultado, "<Plano>")
    parcelas = extrair_tag(resultado, "<ParcelasAcordo>") or ""
    possui_parcela = "<ParcelaAcordo>" in parcelas
    valor_primeira_parcela = extrair_tag(resultado, "<ValorParcela>")
    data_primeira_parcela = extrair_tag(resultado, "<DataParcela>")

    return (
        not plano
        or int(plano) <= 0
        or not possui_parcela
        or not valor_primeira_parcela
        or not data_primeira_parcela
    )


def normalizar_nome(nome: str) -> str:
        nome = (nome or "").strip().upper()
        nome = "".join(
            c for c in unicodedata.normalize("NFD", nome)
            if unicodedata.category(c) != "Mn"
        )
        nome = " ".join(nome.split())
        return nome


def eh_erro_contrato_nao_encontrado(mensagem: str | None) -> bool:
    mensagem_normalizada = normalizar_nome(mensagem or "")
    return "NAO FOI ENCONTR" in mensagem_normalizada and "CONTRATO" in mensagem_normalizada


def eh_erro_teta_nao_negociavel(mensagem: str | None) -> bool:
    mensagem_normalizada = normalizar_nome(mensagem or "")
    return (
        "NECESSARIO MARCAR TODAS AS DIVIDAS DO CONTRATO" in mensagem_normalizada
        or (
            "POLICY" in mensagem_normalizada
            and "NENHUMA POLITICA FOI ENCONTRADA" in mensagem_normalizada
        )
    )


def eh_erro_divida_nao_selecionada(mensagem: str | None) -> bool:
    mensagem_normalizada = normalizar_nome(mensagem or "")
    return (
        "NENHUMA DIVIDA" in mensagem_normalizada
        and (
            "SELECIONADA" in mensagem_normalizada
            or "ORIGINAL FOI MARCADA" in mensagem_normalizada
        )
    )


def extrair_nm_produto(xml: str) -> str | None:
    produto = extrair_tag(xml, "<NmProduto>")
    if produto:
        return produto

    detalhes_xml = extrair_tag(xml, "<ArrayOfContratoDetalhe>")
    if not detalhes_xml:
        detalhes_xml = xml

    candidatos_por_nome = {
        "CODIGO PRODUTO BETA": None,
        "PRODUTO BETA": None,
        "PRODUTO EVEREST": None,
        "CORE BETA": None,
    }

    while "<ContratoDetalhe>" in detalhes_xml:
        detalhe = extrair_array(detalhes_xml, "<ContratoDetalhe>")
        if not detalhe:
            break

        nome_detalhe = normalizar_nome(extrair_tag(detalhe, "<NomeDetalhe>") or "")
        valor = extrair_tag(detalhe, "<Valor>")

        if nome_detalhe in candidatos_por_nome and valor:
            candidatos_por_nome[nome_detalhe] = valor

        detalhes_xml = detalhes_xml.replace(detalhe, "", 1)

    for chave in ("CODIGO PRODUTO BETA", "PRODUTO BETA", "PRODUTO EVEREST", "CORE BETA"):
        valor = candidatos_por_nome.get(chave)
        if valor:
            return valor

    return extrair_tag(xml, "<Identificador>")


def forcar_detalhe_vazio(cedente_id: int, detalhes) -> bool:
    return cedente_id in (81, 104) and not detalhes


def gerar_xml_detalhe_calculo(detalhes, force_empty: bool = False) -> str:
    if force_empty:
        return "<ArrayOfAcordoDetalhe><AcordoDetalhe> </AcordoDetalhe></ArrayOfAcordoDetalhe>"

    acordo_detalhe = ""
    for detalhe in detalhes:
        if hasattr(detalhe, "nome"):
            nome_detalhe = detalhe.nome
            valor = detalhe.valor
            id_detalhe = detalhe.id_detalhe
            tipo_detalhe = detalhe.tipo_detalhe
            origem = detalhe.origem
        else:
            nome_detalhe, valor, id_detalhe, tipo_detalhe, origem = detalhe

        acordo_detalhe += f"""<AcordoDetalhe>
                                            <Nome>{nome_detalhe}</Nome>
                                            <Valor>{valor}</Valor>
                                            <IdDetalhe>{id_detalhe}</IdDetalhe>
                                            <TipoDetalhe>{tipo_detalhe}</TipoDetalhe>
                                            <TipoOrigemDetalhe>{origem}</TipoOrigemDetalhe>
                                        </AcordoDetalhe>
                                    """

    return f"<ArrayOfAcordoDetalhe>{acordo_detalhe}</ArrayOfAcordoDetalhe>"
