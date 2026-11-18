import os
import hmac
import hashlib
import uuid
from werkzeug.utils import secure_filename


_SECRET_KEY = os.getenv("BOLETO_FILENAME_KEY")


class FileUploadService:

    @staticmethod
    def _nome_ofuscado() -> str:
        random_uuid = uuid.uuid4().hex.encode("utf-8")
        key = _SECRET_KEY.encode("utf-8")

        mac = hmac.new(key, random_uuid, hashlib.sha256).hexdigest()
        short = mac[:24]

        return f"boleto_{short}.pdf"

    def upload_boleto(self, file) -> dict:

        base_dir = os.path.dirname(os.path.abspath(__file__))
        raiz_projeto = os.path.abspath(os.path.join(base_dir, "../../../"))
        caminho_registro = os.path.join(raiz_projeto, "arquivos", "boletos")
        os.makedirs(caminho_registro, exist_ok=True)

        nome_boleto = self._nome_ofuscado()
        registro_boleto = os.path.join(caminho_registro, nome_boleto)
        url_boleto = f"https://api.empresa.example/boletos/{nome_boleto}"

        if os.path.exists(registro_boleto) and os.path.getsize(registro_boleto) > 0:
            return {
                "nomeBoleto": nome_boleto,
                "urlBoleto": url_boleto,
                "mensagem": "Boleto já registrado."
            }

        if not file or file.filename == "":
            raise ValueError("Arquivo inválido")

        filename = secure_filename(file.filename)
        if not filename.lower().endswith(".pdf"):
            raise ValueError("Somente arquivos PDF são permitidos")

        header = file.stream.read(4)
        file.stream.seek(0)
        if not header.startswith(b"%PDF"):
            raise ValueError("Arquivo não é um PDF válido")

        file.save(registro_boleto)

        if os.path.exists(registro_boleto) and os.path.getsize(registro_boleto) > 0:
            return {
                "nomeBoleto": nome_boleto,
                "urlBoleto": url_boleto,
                "mensagem": "Boleto registrado com sucesso."
            }

        return {
            "erro": "Falha ao salvar boleto",
            "mensagem": "O arquivo não foi criado corretamente."
        }
    # HOMOLOGACAO:
    # Use esta versao no ambiente HML quando a pasta local de homologacao
    # nao estiver publicada para acesso externo. Ela salva o PDF direto no
    # servidor da API de producao (.91) e mantem o link publico de producao,
    # preservando o historico em C:\inetpub\wwwroot\APISistemaAcme.
    #
    # def upload_boleto(self, file) -> dict:
    #
    #     caminho_registro = (
    #         r"\\10.0.0.91\c\inetpub\wwwroot\APISistemaAcme"
    #         r"\arquivos\boletos"
    #     )
    #     os.makedirs(caminho_registro, exist_ok=True)
    #
    #     nome_boleto = self._nome_ofuscado()
    #     registro_boleto = os.path.join(caminho_registro, nome_boleto)
    #     url_boleto = f"https://api.empresa.example/boletos/{nome_boleto}"
    #
    #     if os.path.exists(registro_boleto) and os.path.getsize(registro_boleto) > 0:
    #         return {
    #             "nomeBoleto": nome_boleto,
    #             "urlBoleto": url_boleto,
    #             "mensagem": "Boleto ja registrado."
    #         }
    #
    #     if not file or file.filename == "":
    #         raise ValueError("Arquivo invalido")
    #
    #     filename = secure_filename(file.filename)
    #     if not filename.lower().endswith(".pdf"):
    #         raise ValueError("Somente arquivos PDF sao permitidos")
    #
    #     header = file.stream.read(4)
    #     file.stream.seek(0)
    #     if not header.startswith(b"%PDF"):
    #         raise ValueError("Arquivo nao e um PDF valido")
    #
    #     file.save(registro_boleto)
    #
    #     if os.path.exists(registro_boleto) and os.path.getsize(registro_boleto) > 0:
    #         return {
    #             "nomeBoleto": nome_boleto,
    #             "urlBoleto": url_boleto,
    #             "mensagem": "Boleto registrado com sucesso."
    #         }
    #
    #     return {
    #         "erro": "Falha ao salvar boleto",
    #         "mensagem": "O arquivo nao foi criado corretamente."
    #     }
