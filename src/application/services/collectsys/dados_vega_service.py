from datetime import datetime, timedelta
import holidays
from src.infrastructure.repositories.sql_vega_repository import VegaRepository


class DadosDividaVega:
    def __init__(self):
        self.repo = VegaRepository()

    def obter_divida_vega(self, id_cliente: int):

        cpf_row = self.repo.buscar_cpf_por_id_cliente(id_cliente)

        if not cpf_row:
            return {"statusCliente": "clienteForaAssessoria"}

        cpf = cpf_row[0]["NR_CPF"]
        cpf_limpo = "".join(filter(str.isdigit, str(cpf)))

        dados_cliente = self.repo.buscar_dados_cliente(cpf_limpo)

        if not dados_cliente:
            return {"statusCliente": "clienteForaAssessoria"}

        primeiro = dados_cliente[0]

        email_rows = self.repo.buscar_email_cliente(primeiro["ID_CLIENTE"])
        email = email_rows[0]["NM_EMAIL"] if email_rows else ""

        dia_venc = datetime.strptime(primeiro["DIA_VENCIMENTO"], "%d-%m-%Y")
        feriados = holidays.BR()

        while dia_venc.weekday() in (5, 6) or dia_venc in feriados:
            dia_venc -= timedelta(days=1)

        dia_venc_fmt = dia_venc.strftime("%d-%m-%Y")

        nome = primeiro["NM_CLIENTE"].split(" ")[0]

        retorno = {
            "statusCliente": "clienteEmAssessoria",
            "cpf": str(primeiro["NR_CPF"]),
            "idCliente": str(primeiro["ID_CLIENTE"]),
            "nome": nome,
            "email": email,
            "contratosEmAtraso": len(dados_cliente),
            "contratos": []
        }

        for c in dados_cliente:
            retorno["contratos"].append({
                "tpContrato": str(c["TP_CONTRATO"]),
                "nmProduto": str(c["NM_PRODUTO"]),
                "vlPrestacao": "{:.2f}".format(float(c["VL_PRESTACAO"])),
                "DiasAtraso": str(int(c["DIAS_ATRASO"])),
                "parcelasAtraso": str(int(c["PARCELA_ATRASO"])),
                "nmGrupoProduto": str(c["NM_GRUPO_PRODUTO"]),
                "fase": str(c["FASE"]),
                "nrContrato": str(c["NR_CONTRATO"]),
                "diaVencimento": dia_venc_fmt,
            })

        return retorno
