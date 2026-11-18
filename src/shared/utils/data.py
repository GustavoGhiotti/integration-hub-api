from datetime import datetime, date, timedelta
from typing import Optional
import holidays
import re

def formatar_data(data_str: str) -> date:
    formatos = ["%Y-%m-%d", "%d/%m/%Y"]
    for fmt in formatos:
        try:
            return datetime.strptime(data_str, fmt).date()
        except ValueError:
            continue

    raise ValueError(f"Formato de data inválido: {data_str}")



def validacao_dia_util(dia:date) -> date:
    feriados = holidays.BR()

    while (dia.weekday() in [5, 6]) or (dia in feriados):
    # Ajusta o vencimento para o dia anterior
        dia = dia - timedelta(days=1)

    return dia


def proximo_dia_util(dia: date) -> date:
    """Ajusta a data para frente ate cair em um dia util (nao fim de semana/feriado nacional).

    Diferente de `validacao_dia_util` (que retrocede), esta avanca a data. Usada para
    datas de pagamento/formalizacao, que nao podem cair em data passada."""
    feriados = holidays.BR()

    while (dia.weekday() in [5, 6]) or (dia in feriados):
        dia = dia + timedelta(days=1)

    return dia


def capturar_data(resultado: str) -> Optional[str]:
    # Expressão regular para capturar datas no formato DD/MM/AAAA ou AAAA-MM-DD
    regex_datas = r'\b\d{2}/\d{2}/\d{4}\b|\b\d{4}-\d{2}-\d{2}\b'
    # Encontrar todas as datas no texto
    data_encontrada = re.findall(regex_datas, resultado)
    if not data_encontrada:
        return None

    data = data_encontrada[0]
    if "/" in data:  # Formato DD/MM/AAAA
        data_dt = datetime.strptime(data, '%d/%m/%Y')
    else:
        data_dt = datetime.strptime(data, '%Y-%m-%d')

    data_vencimento = validacao_dia_util(data_dt.date())
    return data_vencimento.strftime('%Y-%m-%d')


def capturar_desconto(resultado: str) -> Optional[float]:
    """
    Captura o percentual de desconto informado no texto de erro.
    Exemplos esperados:
    - "O desconto máximo permitido é de 0%."
    - "Desconto maximo permitido: 12,5%"
    """
    if not resultado:
        return None

    padroes = [
        r"desconto\s+m[áa]ximo(?:\s+permitido)?(?:\s+é|\s+e)?(?:\s+de)?\s*(\d+(?:[.,]\d+)?)\s*%",
        r"(\d+(?:[.,]\d+)?)\s*%"
    ]

    for padrao in padroes:
        match = re.search(padrao, resultado, flags=re.IGNORECASE)
        if not match:
            continue

        valor_str = match.group(1).replace(",", ".")
        try:
            valor = float(valor_str)
        except ValueError:
            continue

        if valor.is_integer():
            return int(valor)
        return valor

    return None


def validar_data_ymd(valor: str) -> str:
    try:
        datetime.strptime(valor, "%Y-%m-%d")
        return valor
    except ValueError:
        raise ValueError("A data deve seguir o padrão YYYY-MM-DD")