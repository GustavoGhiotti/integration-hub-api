import re

class Documento:
    def __init__(self, documento: str):
        self.documento = documento

    def remove_caracteres(self) -> str:
        """Remove caracteres não numéricos de um documento (CPF ou CNPJ)"""
        return re.sub(r'\D', '', self.documento)


class ValidacaoDocumento(Documento):
    def __init__(self, documento: str):
        super().__init__(documento)

    def _calcular_digito_cpf(self, base: str, peso_inicial: int) -> str:
        soma = sum(int(digito) * peso for digito, peso in zip(base, range(peso_inicial, 1, -1)))
        resto = soma % 11
        return '0' if resto < 2 else str(11 - resto)

    def validacao_cpf(self) -> bool:
        cpf = self.remove_caracteres().zfill(11)

        if len(cpf) != 11 or cpf == cpf[0] * 11:
            return False

        digito1 = self._calcular_digito_cpf(cpf[:9], 10)
        digito2 = self._calcular_digito_cpf(cpf[:9] + digito1, 11)

        return cpf[-2:] == digito1 + digito2

    def _calcular_digito_cnpj(self, base: str, pesos: list[int]) -> str:
        soma = sum(int(digito) * peso for digito, peso in zip(base, pesos))
        resto = soma % 11
        return '0' if resto < 2 else str(11 - resto)

    def validacao_cnpj(self) -> bool:
        cnpj = self.remove_caracteres().zfill(14)

        if len(cnpj) != 14 or cnpj == cnpj[0] * 14:
            return False

        pesos_1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
        pesos_2 = [6] + pesos_1

        digito1 = self._calcular_digito_cnpj(cnpj[:12], pesos_1)
        digito2 = self._calcular_digito_cnpj(cnpj[:12] + digito1, pesos_2)

        return cnpj[-2:] == digito1 + digito2

    def validar_documento(self) -> bool:
        return self.validacao_cpf() or self.validacao_cnpj()
