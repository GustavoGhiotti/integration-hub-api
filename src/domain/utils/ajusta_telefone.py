import re

def ajusta_telefone(numero: str) -> tuple[str, str]:
    if not numero:
        raise ValueError("numero vazio")

    if numero.startswith("55"):
        numero = numero[2:]

    if numero.startswith("0"):
        numero = numero[1:]

    if len(numero) < 10:
        raise ValueError(f"Numero: {numero} invalido, quantidade de numeros insuficiente")

    ddd = int(numero[:2])
    telefone = int(numero[2:])

    return ddd, telefone

def validar_numero_whatsapp(numero: str):
    numero = (
        str(numero)
        .strip()
        .replace("+", "")
        .replace(" ", "")
        .replace("-", "")
        .replace("(", "")
        .replace(")", "")
    )

    if not numero.isdigit():
        raise Exception(f"Número de origem inválido (caracteres inválidos): {numero}")

    if not numero.startswith("55"):
        numero = "55" + numero

    if len(numero) not in (12, 13):
        raise Exception(
            f"Número inválido. Esperado DDI+DDD+Número comercial/celular. Recebido: {numero}"
        )

    return numero

