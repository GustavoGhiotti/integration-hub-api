from src.domain.strategies.carteiras.base_strategy import CarteiraBaseStrategy, RetornoCarteiraBase
from datetime import date, timedelta


class CarteiraDefault(CarteiraBaseStrategy):
    def valor_entrada(self) -> float:
        return 0.0
    
    def data_limite(self) -> date:
        return date.today() + timedelta(days=7)

    def parcela_max(self) -> int:
        return 48 #arrumar depois
    
    def desconto_max(self) -> int:
        return 100

    def contratos_negociar(self) -> list:
        return super().contratos_negociar()

    def parcelas_negociar(self) -> int:
        return super().parcelas_negociar()

    def retorno_carteira(self) -> RetornoCarteiraBase: 
        return RetornoCarteiraBase(
                valor_entrada=self.valor_entrada(),
                data_limite=self.data_limite(),
                parcela_max=self.parcela_max(),
                desconto_max=self.desconto_max(),                
                mensagem=None,
                permite_negociacao=True,
            )