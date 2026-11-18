VCOM_ID_CREDOR_OFFSET = 1000


def id_credor_externo(id_credor: int | str | None) -> int | None:
    if id_credor is None:
        return None
    return int(id_credor) + VCOM_ID_CREDOR_OFFSET


def id_credor_vcom(id_credor: int | str | None) -> int | None:
    if id_credor is None:
        return None

    valor = int(id_credor)
    if valor >= VCOM_ID_CREDOR_OFFSET:
        return valor - VCOM_ID_CREDOR_OFFSET
    return valor

