from copy import deepcopy

from src.domain.entities.cedentes import CEDENTES_TETA_COMUM


class NegociacaoResponseLegacyDTO:
    """Contrato temporario que reverte para a saida publica da branch main."""

    INCLUI_INFORMACOES_ACORDO = False

    @classmethod
    def ordenar(cls, valor):
        if isinstance(valor, list):
            return [cls.ordenar(item) for item in valor]
        if isinstance(valor, dict):
            return {chave: cls.ordenar(valor[chave]) for chave in sorted(valor, key=str)}
        return valor

    @staticmethod
    def _parcelas_legadas(valor_original):
        if not isinstance(valor_original, dict):
            return
        parcelas = valor_original.get("parcelasEmAtraso")
        if not isinstance(parcelas, list) or not any(isinstance(item, dict) for item in parcelas):
            return

        numeros = []
        for item in parcelas:
            if not isinstance(item, dict):
                numeros.append(item)
                continue
            if isinstance(item.get("parcelas"), list):
                numeros.extend(
                    parcela.get("parcela") if isinstance(parcela, dict) else parcela
                    for parcela in item["parcelas"]
                )
            elif "parcela" in item:
                numeros.append(item["parcela"])
        numeros = [numero for numero in numeros if numero is not None]
        try:
            valor_original["parcelasEmAtraso"] = sorted(numeros, key=int)
        except (TypeError, ValueError):
            valor_original["parcelasEmAtraso"] = sorted(numeros, key=str)

    @classmethod
    def _remover_campos_v2(cls, item):
        if not isinstance(item, dict):
            return item
        eh_vcom = cls._eh_vcom(item)
        item.pop("metodoNegociacao", None)
        item.pop("valorAtualizado", None)
        cls._parcelas_legadas(item.get("valorOriginal"))
        for contrato in item.get("contratosUtilizados") or []:
            if isinstance(contrato, dict):
                contrato.pop("valorAtualizado", None)
                parcelas = contrato.get("parcelasEmAtraso")
                if not eh_vcom and isinstance(parcelas, list):
                    contrato["parcelasEmAtraso"] = [
                        parcela.get("parcela") if isinstance(parcela, dict) else parcela
                        for parcela in parcelas
                    ]
        return item

    @staticmethod
    def _eh_vcom(item):
        return str(item.get("origem") or "").upper() == "VCOM"

    @classmethod
    def _reverter_agrupamento_collectsys(cls, item, chave_contrato=None, id_cedente=None):
        if not isinstance(item, dict) or cls._eh_vcom(item):
            return item

        if isinstance(item.get("parcelas"), list):
            # A main nao adicionava o IdContrato nos itens de acordo ativo.
            item.pop("contrato", None)
            return item

        contratos = item.pop("contratosUtilizados", None)
        identificacao = str(item.get("grupo") or item.get("nomeCedente") or "").upper()
        eh_teta = "TETA" in identificacao or id_cedente in CEDENTES_TETA_COMUM
        if not contratos and "TETA" not in identificacao and "BETA" not in identificacao:
            item.pop("produto", None)
        if contratos:
            if "PI" in identificacao:
                item["contratosPi"] = contratos
            elif int(item.get("quantidadeContratos") or len(contratos)) > 1 or eh_teta:
                item["contratosTeta"] = contratos
            else:
                item.pop("quantidadeContratos", None)

        agrupado = isinstance(contratos, list) and len(contratos) > 1
        if agrupado:
            item.pop("produto", None)
            item.pop("NumeroContratoBanco", None)
            ids = [
                contrato.get("contrato")
                for contrato in contratos
                if isinstance(contrato, dict) and contrato.get("contrato") is not None
            ]
            if ids:
                item["contrato"] = ids

            # TETA e PI agrupados nao expunham detalhes de parcelas na main.
            valor_original = item.get("valorOriginal")
            if isinstance(valor_original, dict):
                valor_original.pop("parcelasEmAtraso", None)
                valor_original.pop("quantidadeParcelasEmAtraso", None)
                valor_original.pop("quantidadeParcelas", None)
            if "PI" in identificacao:
                for contrato in contratos:
                    if isinstance(contrato, dict):
                        contrato.pop("produto", None)
        elif item.get("contrato") is None and chave_contrato is not None:
            try:
                item["contrato"] = int(chave_contrato)
            except (TypeError, ValueError):
                item["contrato"] = chave_contrato
        elif item.get("contrato") is None and contratos:
            ids = [
                contrato.get("contrato")
                for contrato in contratos
                if isinstance(contrato, dict) and contrato.get("contrato") is not None
            ]
            if ids:
                item["contrato"] = ids if len(ids) > 1 else ids[0]
        return item

    @classmethod
    def remover_origem(cls, retorno):
        # Apesar do nome historico do helper, a main preservava `origem`.
        return cls.ordenar(retorno)

    @classmethod
    def normalizar_verifica(cls, contratos):
        if isinstance(contratos, dict):
            retorno = deepcopy(contratos)
            for chave, item in retorno.items():
                cls._remover_campos_v2(item)
                cls._reverter_agrupamento_collectsys(item, chave)
            return cls.ordenar(retorno)
        if isinstance(contratos, list):
            retorno = deepcopy(contratos)
            for item in retorno:
                cls._remover_campos_v2(item)
                cls._reverter_agrupamento_collectsys(item)
            return cls.ordenar(retorno)
        return contratos

    @classmethod
    def normalizar_parcelamento(cls, retorno):
        retorno = deepcopy(retorno)
        cls._remover_campos_v2(retorno)
        cls._reverter_agrupamento_collectsys(retorno)
        return cls.ordenar(retorno)

    @classmethod
    def normalizar_proposta(cls, retorno, id_cedente=None):
        retorno = deepcopy(retorno)
        cls._remover_campos_v2(retorno)
        cls._reverter_agrupamento_collectsys(retorno, id_cedente=id_cedente)
        return cls.ordenar(retorno)

    @staticmethod
    def normalizar_informacoes_acordo(id_cliente, proposta):
        return None
