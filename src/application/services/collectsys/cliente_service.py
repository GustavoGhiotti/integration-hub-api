from src.infrastructure.external.collectsys import ConsultarCliente
from src.domain.exceptions import ClienteNaoEncontrado
from src.shared.utils.xml_tratamentos import *
import asyncio
from datetime import date, datetime

class ClienteService:
    async def dados_cliente(dividas) -> dict:
        ids_vega = {
            divida.get("idCliente")
            for divida in dividas
            if "VEGA" in (divida.get("cedente") or "").upper()
            and divida.get("idCliente") is not None
        }

        ids_cobranca = {
            divida.get("idCliente")
            for divida in dividas
            if "VEGA" not in (divida.get("cedente") or "").upper()
            and divida.get("idCliente") is not None
        }

        id_cliente_vega = next(iter(ids_vega), None)
        id_cliente_cobranca = next(iter(ids_cobranca), None)


        dados_cliente = {}
        
        cliente_cobranca, cliente_vega = await asyncio.gather(
                    asyncio.to_thread(lambda:ConsultarCliente("Cobrancas", id_cliente_cobranca).consultar()),
                    asyncio.to_thread(lambda:ConsultarCliente("Vega", id_cliente_vega).consultar())
                )

        dados = cliente_cobranca if id_cliente_cobranca else cliente_vega
        if not dados: 
            raise ClienteNaoEncontrado(mensagem="Cliente não localizado.")
        
        if id_cliente_cobranca and id_cliente_vega:
            nome_cobranca = extrair_tag(cliente_cobranca, "<Nome>", "</Nome>").split()[0]
            nome_vega = extrair_tag(cliente_vega, "<Nome>", "</Nome>").split()[0]

            if normalizar_nome(nome_cobranca) != normalizar_nome(nome_vega):
                raise ClienteNaoEncontrado(mensagem="Divergência de dados")
        
        nome = extrair_tag(dados, "<Nome>", "</Nome>").split()[0]

        data_nascimento = extrair_tag(dados, "<DataNascimento>", "</DataNascimento>").replace("T00:00:00","")
        data_nascimento = datetime.strptime(data_nascimento, "%Y-%m-%d").strftime("%d/%m/%Y")

        dados_cliente.update({"nome":nome,"dataNascimento":data_nascimento})
        
        return dados_cliente