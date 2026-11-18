from src.domain.strategies.carteiras.default_strategy import CarteiraDefault

class NuStrategy(CarteiraDefault):
    def contratos_negociar(self) -> list:
        
        return super().contratos_negociar()
    
