from .banco_beta_strategy import BetaStrategy
from .mu_strategy import MuStrategy
from .default_strategy import CarteiraDefault
from .nu_strategy import NuStrategy


DEFAULT_RULE = CarteiraDefault()

RULES_BY_CEDENTE = {
    3: MuStrategy(),
    14: NuStrategy(),
    81: BetaStrategy(),
    104: BetaStrategy(),
}


def get_cedente_rule(cedente_id: int):
    return RULES_BY_CEDENTE.get(cedente_id, DEFAULT_RULE)
