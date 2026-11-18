from src.domain.strategies.parcelamento.definir_strategy import get_cedente_rule
from src.application.services.collectsys.divida_ativa import DividaAtiva

class ParcelamentoMaximo:

    def execute(self,id_cliente:int, contratos_selecionados:tuple):
        #obter_divida_ativa
        contrato = DividaAtiva.obter(id_cliente)

        #pegar o fluxo do cedente
        carteira_strategia = get_cedente_rule(contrato.id_cedente) 
        
        carteira_strategia.gerar_propostas(contrato, contratos_selecionados)

        #retorno no método  retorno_carteira(self) -> RetornoCarteiraBase
        return carteira_strategia.retorno_carteira

