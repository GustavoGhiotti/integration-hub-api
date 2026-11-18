def parse_twilio_template(tpl, approval=None): #meta=none
    parsed = {
        "sid_template": tpl.sid,
        "nome_template": tpl.friendly_name,
        "lingua": tpl.language,
        "criado_em": tpl.date_created.isoformat() if tpl.date_created else None,

        "variaveis": [],
        "tipos": [],
        "corpos": {},
        "acoes": {},
        "media": {},
        "titulos": {},
        "subtitulos": {},

        "status_aprovacao": None,
        "motivo_rejeicao": None,
        "data_aprovacao": None
    }

    if getattr(tpl, "variables", None):
        parsed["variaveis"] = dict(tpl.variables)

    tipos = tpl.types or {}
    parsed["tipos"] = list(tipos.keys())

    for tipo, conteudo in tipos.items():
        if conteudo.get("body"):
            parsed["corpos"][tipo] = conteudo["body"]

        if conteudo.get("title"):
            parsed["titulos"][tipo] = conteudo["title"]

        if conteudo.get("subtitle"):
            parsed["subtitulos"][tipo] = conteudo["subtitle"]

        if conteudo.get("media"):
            parsed["media"][tipo] = conteudo["media"]

        if conteudo.get("actions"):
            parsed["acoes"][tipo] = [
                a.get("title") or a.get("id") for a in conteudo["actions"]
            ]

    if approval:
        parsed["status_aprovacao"] = approval.get("status")
        parsed["motivo_rejeicao"] = approval.get("motivo_rejeicao")
        parsed["data_aprovacao"] = approval.get("data")

    # if meta and not meta.get("erro"):
    #     parsed["status_aprovacao"] = meta.get("status")
    #     parsed["motivo_rejeicao"] = meta.get("motivo_rejeicao")
    #     parsed["data_aprovacao"] = meta.get("ultima_atualizacao")

    return parsed
