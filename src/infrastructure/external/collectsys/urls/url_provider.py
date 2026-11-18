from dataclasses import dataclass
import unicodedata


@dataclass(frozen=True, slots=True)
class CollectSysUrlProvider:
    cobranca_url: str = "http://10.0.0.64/easycollectorws/easycollectorWs.asmx?op="
    vega_url: str = "http://10.0.0.18/easycollectorws/easycollectorWs.asmx?op="

    def base_url(self, servidor: str | None = None) -> str:
        servidor_normalizado = self._normalizar(servidor)

        if servidor_normalizado in {"vega", "vega financeira"}:
            return self.vega_url

        return self.cobranca_url

    def _normalizar(self, valor: str | None) -> str:
        texto = valor or ""
        texto = unicodedata.normalize("NFKD", texto)
        texto = "".join(char for char in texto if not unicodedata.combining(char))
        return texto.strip().lower()