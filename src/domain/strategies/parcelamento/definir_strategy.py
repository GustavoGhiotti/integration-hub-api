from .banco_beta_strategy import BancoBetaParcelamentoStrategy
from .mu_strategy import MuStrategy
from .base_strategy import ParcelamentoStrategy
from .nu_strategy import NuStrategy


DEFAULT_RULE = CarteiraDefault()

RULES_BY_CEDENTE = {
    3: MuStrategy(),
    14: NuStrategy(),
    81: BancoBetaParcelamentoStrategy(),
    104: BancoBetaParcelamentoStrategy(),
}


def get_cedente_rule(cedente_id: int) -> ParcelamentoStrategy:
    return RULES_BY_CEDENTE.get(cedente_id, DEFAULT_RULE)
