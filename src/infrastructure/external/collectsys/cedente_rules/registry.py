from .zeta_rule import ZetaCedenteRule
from .arc4_rule import Arc4CedenteRule
from .arc4_omega_rule import Arc4OmegaCedenteRule
from .gama_rule import GamaCedenteRule
from .teta_special_rule import TetaSpecialCedenteRule
from .teta_rule import TetaCedenteRule
from .teta_swat_rule import TetaSwatCedenteRule
from .mu_rule import MuCedenteRule
from .default_rule import DefaultCedenteRule
from .delta_bigger_rule import DeltaBiggerCedenteRule
from .delta_rule import DeltaCedenteRule
from .rho_rule import RhoCedenteRule
from .beta_rule import BetaCedenteRule
from .pi_rule import PiCedenteRule
from .phipf_rule import PhipfCedenteRule
from .bancoalfa_rule import BancoalfaCedenteRule
from .nu_rule import NuCedenteRule


DEFAULT_RULE = DefaultCedenteRule()

RULES_BY_CEDENTE = {
    3: MuCedenteRule(),
    4: GamaCedenteRule(),
    14: NuCedenteRule(),
    43: RhoCedenteRule(),
    51: BancoalfaCedenteRule(),
    60: PiCedenteRule(),
    65: DeltaCedenteRule(),
    71: ZetaCedenteRule(),
    73: DeltaBiggerCedenteRule(),
    77: TetaCedenteRule(),
    81: BetaCedenteRule(),
    84: TetaSwatCedenteRule(),
    83: PhipfCedenteRule(),
    90: Arc4CedenteRule(),
    96: Arc4OmegaCedenteRule(),
    99: TetaSpecialCedenteRule(),
    103: TetaCedenteRule(),
    104: BetaCedenteRule(),
}


def get_cedente_rule(cedente_id: int):
    return RULES_BY_CEDENTE.get(cedente_id, DEFAULT_RULE)
