from src.infrastructure.external.collectsys import DadosAcordo, EmitirBoleto
from src.infrastructure.external.collectsys import ObterDivida, DadosAcordo, Calcular, ConsultarCliente
from src.infrastructure.repositories.sql_email_collectsys import *
from src.domain.entities.contrato import Contrato
from src.domain.exceptions.collectsys_exception import *
from src.domain.exceptions.beta_boleto_exception import BetaBoletoException
from src.shared.utils.xml_tratamentos import *
from src.infrastructure.servers import conexao
from src.application.services.collectsys.beta_boleto_email_service import BetaBoletoEmailService
from io import BytesIO
from datetime import date, datetime
import base64
import os
import hashlib
import hmac
import qrcode
import random
import smbclient


_SECRET_KEY = os.getenv("BOLETO_FILENAME_KEY")


class Boleto:
    @staticmethod
    def _somente_digitos(valor) -> str:
        return "".join(char for char in str(valor or "") if char.isdigit())

    @staticmethod
    def _cpf_cliente_collectsys(id_cliente: int, servidor: str = "Cobrancas") -> str | None:
        cliente = ConsultarCliente(servidor, id_cliente).consultar()
        if not cliente:
            return None

        cpf_cnpj = Boleto._somente_digitos(extrair_tag(cliente, "<CpfCnpj>", "</CpfCnpj>"))
        if len(cpf_cnpj) == 10:
            return cpf_cnpj.zfill(11)
        if len(cpf_cnpj) == 13:
            return cpf_cnpj.zfill(14)
        return cpf_cnpj or None

    @staticmethod
    def _extrair_boleto_base64(xml: str) -> str | None:
        if "<BOLETOEMBASE64>" in xml and "</BOLETOEMBASE64>" in xml:
            boleto64 = extrair_tag(xml, "<BOLETOEMBASE64>", "</BOLETOEMBASE64>")
            if boleto64 and boleto64.strip():
                return boleto64.strip()
        return None

    @staticmethod
    def _extrair_codigo_barras_base64(xml: str) -> str | None:
        if "<CODIGO_BARRAS>" in xml and "</CODIGO_BARRAS>" in xml:
            codigo_barras = extrair_tag(xml, "<CODIGO_BARRAS>", "</CODIGO_BARRAS>")
            if codigo_barras and codigo_barras.strip():
                return codigo_barras.strip()
        return None

    @staticmethod
    def _nome_ofuscado(id_cliente: int, id_acordo: int, parcela: int) -> str:
        msg = f"{id_cliente}:{id_acordo}:{parcela}".encode("utf-8")
        key = _SECRET_KEY.encode("utf-8")
        mac = hmac.new(key, msg, hashlib.sha256).hexdigest()
        short = mac[:24]
        return f"boleto_{short}.pdf"

    @staticmethod
    def _nome_ofuscado_original(id_cliente: int, id_contrato: int) -> str:
        msg = f"{id_cliente}:original:{id_contrato}".encode("utf-8")
        key = _SECRET_KEY.encode("utf-8")
        mac = hmac.new(key, msg, hashlib.sha256).hexdigest()
        short = mac[:24]
        return f"boleto_{short}.pdf"

    @staticmethod
    def _registrar_arquivo_boleto(
        nome_boleto: str,
        conteudo64: str,
        extensao: str,
        linha_digitavel: str | None = None,
        sobrescrever: bool = False,
    ) -> dict:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        raiz_projeto = os.path.abspath(os.path.join(base_dir, "../../../../"))
        caminho_registro = os.path.join(raiz_projeto, "arquivos", "boletos")
        os.makedirs(caminho_registro, exist_ok=True)

        nome_arquivo = nome_boleto.replace(".pdf", extensao)
        registro_boleto = os.path.join(caminho_registro, nome_arquivo)
        url_boleto = fr"https://api.empresa.example/boletos/{nome_arquivo}"

        if not sobrescrever and os.path.exists(registro_boleto) and os.path.getsize(registro_boleto) > 0:
            return {
                "nomeBoleto": nome_arquivo,
                "urlBoleto": url_boleto,
                "linhaDigitavel": linha_digitavel,
                "mensagem": "Boleto emitido anteriormente."
            }

        arquivo = base64.b64decode(conteudo64, validate=True)

        with open(registro_boleto, "wb") as f:
            f.write(arquivo)

        if os.path.exists(registro_boleto) and os.path.getsize(registro_boleto) > 0:
            return {
                "nomeBoleto": nome_arquivo,
                "urlBoleto": url_boleto,
                "linhaDigitavel": linha_digitavel,
                "mensagem": "Boleto emitido com sucesso."
            }

        return {
            "erro": "Falha ao salvar boleto",
            "mensagem": "O arquivo nao foi criado corretamente."
        }

    # HOMOLOGACAO:
    # Use esta versao do metodo no ambiente HML quando a pasta local de
    # homologacao nao estiver publicada para acesso externo. Ela salva o
    # boleto direto no servidor da API de producao (.91) e mantem o link
    # publico de producao, preservando o historico em
    # C:\inetpub\wwwroot\APISistemaAcme.
    #
    # @staticmethod
    # def _registrar_arquivo_boleto(
    #     nome_boleto: str,
    #     conteudo64: str,
    #     extensao: str,
    #     linha_digitavel: str | None = None,
    #     sobrescrever: bool = False,
    # ) -> dict:
    #     caminho_registro = (
    #         r"\\10.0.0.91\c\inetpub\wwwroot\APISistemaAcme"
    #         r"\arquivos\boletos"
    #     )
    #     os.makedirs(caminho_registro, exist_ok=True)
    #
    #     nome_arquivo = nome_boleto.replace(".pdf", extensao)
    #     registro_boleto = os.path.join(caminho_registro, nome_arquivo)
    #     url_boleto = fr"https://api.empresa.example/boletos/{nome_arquivo}"
    #
    #     if not sobrescrever and os.path.exists(registro_boleto) and os.path.getsize(registro_boleto) > 0:
    #         return {
    #             "nomeBoleto": nome_arquivo,
    #             "urlBoleto": url_boleto,
    #             "linhaDigitavel": linha_digitavel,
    #             "mensagem": "Boleto emitido anteriormente."
    #         }
    #
    #     arquivo = base64.b64decode(conteudo64, validate=True)
    #
    #     with open(registro_boleto, "wb") as f:
    #         f.write(arquivo)
    #
    #     if os.path.exists(registro_boleto) and os.path.getsize(registro_boleto) > 0:
    #         return {
    #             "nomeBoleto": nome_arquivo,
    #             "urlBoleto": url_boleto,
    #             "linhaDigitavel": linha_digitavel,
    #             "mensagem": "Boleto emitido com sucesso."
    #         }
    #
    #     return {
    #         "erro": "Falha ao salvar boleto",
    #         "mensagem": "O arquivo nao foi criado corretamente."
    #     }

    @staticmethod
    def _registrar_boleto(
        nome_boleto: str,
        boleto64: str,
        linha_digitavel: str | None = None,
        sobrescrever: bool = False,
    ) -> dict:
        arquivo = base64.b64decode(boleto64, validate=True)
        if not arquivo.startswith(b"%PDF"):
            raise ValueError("Arquivo nao e um PDF valido (cabecalhos invalidos)")
        return Boleto._registrar_arquivo_boleto(nome_boleto, boleto64, ".pdf", linha_digitavel, sobrescrever)

    @staticmethod
    def _registrar_pdf_bytes(
        nome_boleto: str,
        arquivo: bytes,
        linha_digitavel: str | None = None,
        sobrescrever: bool = False,
    ) -> dict:
        if not arquivo.startswith(b"%PDF"):
            raise ValueError("Arquivo nao e um PDF valido (cabecalhos invalidos)")
        conteudo64 = base64.b64encode(arquivo).decode("utf-8")
        return Boleto._registrar_arquivo_boleto(nome_boleto, conteudo64, ".pdf", linha_digitavel, sobrescrever)

    @staticmethod
    def _registrar_imagem_boleto(
        nome_boleto: str,
        imagem64: str,
        linha_digitavel: str | None = None,
        sobrescrever: bool = False,
    ) -> dict:
        arquivo = base64.b64decode(imagem64, validate=True)
        if not arquivo.startswith(b"\xff\xd8\xff"):
            raise ValueError("Erro ao gerar Boleto.")
        retorno = Boleto._registrar_arquivo_boleto(nome_boleto, imagem64, ".jpg", linha_digitavel, sobrescrever)
        retorno["mensagem"] = "Boleto pagamento a vista."
        return retorno

    def obter(id_cliente: int, id_acordo: int, id_cedente: int, parcela: int = 1) -> dict:
        nome_boleto = Boleto._nome_ofuscado(id_cliente, id_acordo, parcela)

        emitir_boleto = EmitirBoleto(
            servidor="Cobranca",
            id_cliente=id_cliente,
            id_acordo=id_acordo,
            parcela=parcela,
            id_cedente=id_cedente
        ).emitir()

        linha_digitavel = extrair_tag(emitir_boleto, "<LINHA_DIGITAVEL>", "</LINHA_DIGITAVEL>")
        boleto64 = Boleto._extrair_boleto_base64(emitir_boleto)
        if not boleto64:
            raise ValueError("BOLETOEMBASE64 nao retornado para emissao do boleto.")
        return Boleto._registrar_boleto(nome_boleto, boleto64, linha_digitavel, sobrescrever=parcela > 1)

    @staticmethod
    def obter_original_por_divida(id_cliente: int, id_contrato: int, id_cedente: int, xml_divida: str) -> dict | None:
        emitir_boleto = EmitirBoleto(
            servidor="Cobranca",
            id_cliente=id_cliente,
            id_acordo=0,
            parcela=1,
            id_cedente=id_cedente
        ).emitir_original(xml_divida)

        nome_boleto = Boleto._nome_ofuscado_original(id_cliente, id_contrato)
        linha_digitavel = extrair_tag(emitir_boleto, "<LINHA_DIGITAVEL>", "</LINHA_DIGITAVEL>")

        boleto64 = Boleto._extrair_boleto_base64(emitir_boleto)
        if not boleto64:
            return None
        return Boleto._registrar_boleto(nome_boleto, boleto64, linha_digitavel)

    @staticmethod
    def obter_original_por_divida_parcelado(id_cliente: int, id_contrato: int, id_cedente: int, xml_divida: str) -> dict | None:
        emitir_boleto = EmitirBoleto(
            servidor="Cobranca",
            id_cliente=id_cliente,
            id_acordo=0,
            parcela=1,
            id_cedente=id_cedente
        ).emitir_original(xml_divida)

        nome_boleto = Boleto._nome_ofuscado_original(id_cliente, id_contrato)
        linha_digitavel = extrair_tag(emitir_boleto, "<LINHA_DIGITAVEL>", "</LINHA_DIGITAVEL>")

        boleto64 = Boleto._extrair_boleto_base64(emitir_boleto)
        if boleto64:
            return Boleto._registrar_boleto(nome_boleto, boleto64, linha_digitavel)

        codigo_barras64 = Boleto._extrair_codigo_barras_base64(emitir_boleto)
        if codigo_barras64:
            return Boleto._registrar_imagem_boleto(nome_boleto, codigo_barras64, linha_digitavel)

        return None

    def obter_boleto_beta(
        id_cliente: int,
        id_acordo: int,
        id_cedente: int,
        email: str | None = None,
        parcela: int = 1,
        cpf_cnpj: str | None = None,
    ):
        email_base = email or os.getenv("BETA_BOLETO_EMAIL")
        if not email_base:
            raise RuntimeError("Configure BETA_BOLETO_EMAIL ou envie o campo email para emitir boleto BETA.")
        email_destino = email_base

        email_cliente_repository = EmailCliente()
        emails_cliente = email_cliente_repository.busca_cliente_email(id_cliente) or []
        cpf_cliente = Boleto._somente_digitos(cpf_cnpj or Boleto._cpf_cliente_collectsys(id_cliente))
        if cpf_cliente:
            cpf_cliente = cpf_cliente.zfill(11)
        else:
            raise RuntimeError("CPF do cliente nao encontrado para validar boleto BETA.")

        email_boleto_service = BetaBoletoEmailService()
        email_boleto_service.validar_autenticacao()

        email_cliente = next(
            (
                email_registro
                for email_registro in emails_cliente
                if str(email_registro.get("TP_PREFERENCIAL", "")).strip() == "1"
            ),
            None
        )

        if email_cliente:
            email_cliente_repository.troca_preferencia(
                preferencial=0,
                id_cliente=id_cliente,
                id_email=email_cliente["ID_EMAIL"],
            )

        email_cliente_repository.email_envio_boleto(
            id_cliente=id_cliente,
            nm_email=email_destino,
        )

        try:
            emissao_iniciada_em = datetime.now()
            dividas = ObterDivida("CobranÃ§a").consultar_por_id(id_cliente)
            nome_cedente = extrair_tag(dividas, "<NmCedente>", "</NmCedente>")
            resultado_acordo = DadosAcordo(nome_cedente, id_cliente, id_acordo).obter_faturas()

            if "<RetornoErro>" in resultado_acordo:
                return {"mensagem": "Acordo nÃo encontrado."}

            contrato = Contrato(resultado_acordo, nome_cedente, id_cedente, id_cliente).acordo(parcela)
            xml_divida = extrair_tag(dividas, "<ArrayOfDividaAtiva>", "</ArrayOfDividaAtiva>")
            vencimento = (
                contrato.vencimento_boleto.date()
                if isinstance(contrato.vencimento_boleto, datetime)
                else contrato.vencimento_boleto
                if isinstance(contrato.vencimento_boleto, date)
                else date.fromisoformat(contrato.vencimento_boleto)
            )
            hoje = date.today()

            if vencimento < hoje:
                return {"mensagem": "Boleto com vencimento anterior a hoje."}

            boleto_original = EmitirBoleto(
                servidor="Cobranca",
                id_cliente=id_cliente,
                id_acordo=id_acordo,
                parcela=parcela,
                id_cedente=id_cedente,
            ).emitir_original(xml_divida)
            linha_digitavel_original = extrair_tag(boleto_original, "<LINHA_DIGITAVEL>", "</LINHA_DIGITAVEL>")

            emitir_boleto = EmitirBoleto(
                servidor="Cobranca",
                id_cliente=id_cliente,
                id_acordo=id_acordo,
                parcela=parcela,
                id_cedente=id_cedente,
            ).emitir()

            if "<RetornoErro>" not in emitir_boleto:
                nome_boleto = Boleto._nome_ofuscado(id_cliente, id_acordo, parcela)
                linha_digitavel = extrair_tag(emitir_boleto, "<LINHA_DIGITAVEL>", "</LINHA_DIGITAVEL>")
                boleto64 = Boleto._extrair_boleto_base64(emitir_boleto)
                if not boleto64:
                    return {"mensagem": "Boleto sem arquivo PDF no retorno."}
                return Boleto._registrar_boleto(nome_boleto, boleto64, linha_digitavel, sobrescrever=parcela > 1)

            mensagem = extrair_tag(emitir_boleto, "<Mensagem>", "</Mensagem>") or ""
            mensagens_sucesso_beta = (
                "Erro ao emitir boleto [passo: 37 ]: Exception has been thrown by the target of an invocation.",
                "Erro ao emitir boleto [passo: 37 ]: Value cannot be null.\r\nParameter name: text",
            )
            if not any(mensagem_sucesso in mensagem for mensagem_sucesso in mensagens_sucesso_beta):
                raise BetaBoletoException(mensagem=f"<Mensagem>{mensagem or 'mensagem nao retornada'}</Mensagem>")

            boleto_email = email_boleto_service.aguardar_boleto(
                cpf_cliente,
                emissao_iniciada_em,
                valor_esperado=contrato.valor,
            )
            if not boleto_email:
                return {"mensagem": "Boleto BETA emitido, mas o anexo ainda nao foi encontrado no email central."}

            nome_boleto = Boleto._nome_ofuscado(id_cliente, id_acordo, parcela)
            boleto = Boleto._registrar_pdf_bytes(
                nome_boleto,
                boleto_email.conteudo_pdf,
                linha_digitavel_original,
                sobrescrever=parcela > 1,
            )
            return boleto
        finally:
            try:
                email_cliente_repository.remover_email(id_cliente=id_cliente, nm_email=email_destino)
            except Exception as cleanup_error:
                print(f"Erro ao remover email temporario do BETA: {cleanup_error}")

            if email_cliente:
                try:
                    email_cliente_repository.troca_preferencia(
                        preferencial=1,
                        id_cliente=id_cliente,
                        id_email=email_cliente["ID_EMAIL"],
                    )
                except Exception as cleanup_error:
                    print(f"Erro ao restaurar preferencia de email do BETA: {cleanup_error}")


class CodigoPix:
    @staticmethod
    def _extrair_valor_pix(dados_acordo: str) -> str | None:
        detalhes = extrair_tag(dados_acordo, "<DetalhesAcordo>", "</DetalhesAcordo>")
        if not detalhes:
            return None

        while "<AcordoDetalhe>" in detalhes:
            detalhe = extrair_array(detalhes, "<AcordoDetalhe>", "</AcordoDetalhe>")
            if not detalhe:
                break

            nome = (extrair_tag(detalhe, "<Nome>", "</Nome>") or "").strip().upper()
            valor = (extrair_tag(detalhe, "<Valor>", "</Valor>") or "").strip()
            if nome == "PIX COPIA COLA" and CodigoPix._parece_codigo_pix(valor):
                return valor

            detalhes = detalhes.replace(detalhe, "", 1)

        return None

    @staticmethod
    def _parece_codigo_pix(valor: str | None) -> bool:
        valor = (valor or "").strip()
        return valor.startswith("000201") and "br.gov.bcb.pix" in valor

    def obter(nome_cedente: str, id_cliente: int, id_acordo: int, id_cedente: int):
        if id_cedente != 3:
            raise CodigoPixException("Codigo PIX indisponivel")

        dados_acordo = DadosAcordo(nome_cedente, id_cliente, id_acordo).obter_acordo()
        codigo_pix = CodigoPix._extrair_valor_pix(dados_acordo)
        if not codigo_pix:
            raise CodigoPixException("Codigo PIX indisponivel")

        return codigo_pix


class QrCode:
    @staticmethod
    def _nome_ofuscado(id_cliente: int, id_acordo: int) -> str:
        msg = f"{id_cliente}:{id_acordo}".encode("utf-8")
        key = _SECRET_KEY.encode("utf-8")
        mac = hmac.new(key, msg, hashlib.sha256).hexdigest()
        short = mac[:20]
        return f"qrcode_{short}.png"

    @staticmethod
    def gerar(id_cliente: int, id_acordo: int, conteudo: str) -> dict:
        if not conteudo:
            raise ValueError("Conteudo do QR Code esta vazio ou invalido.")

        try:
            qr = qrcode.make(conteudo)
            buffer = BytesIO()
            qr.save(buffer, format="PNG")
            img_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

            base_dir = os.path.dirname(os.path.abspath(__file__))
            raiz_projeto = os.path.abspath(os.path.join(base_dir, "../../../../"))
            caminho_registro = os.path.join(raiz_projeto, "arquivos", "qrcode")
            os.makedirs(caminho_registro, exist_ok=True)

            nome_qrcode = QrCode._nome_ofuscado(id_cliente, id_acordo)
            registro_qrcode = os.path.join(caminho_registro, nome_qrcode)
            url_qrcode = fr"https://api.empresa.example/qrcode/{nome_qrcode}"

            if os.path.exists(registro_qrcode) and os.path.getsize(registro_qrcode) > 0:
                return {
                    "nomeArquivo": nome_qrcode,
                    "urlArquivo": url_qrcode,
                    "mensagem": "QR Code ja existente."
                }

            with open(registro_qrcode, "wb") as f:
                f.write(buffer.getvalue())

            if os.path.exists(registro_qrcode) and os.path.getsize(registro_qrcode) > 0:
                return {
                    "nomeArquivo": nome_qrcode,
                    "urlArquivo": url_qrcode,
                    "mensagem": "QR Code gerado e salvo com sucesso."
                }
            else:
                return {
                    "erro": "Falha ao salvar QR Code.",
                    "mensagem": "O arquivo nao foi criado corretamente."
                }

        except Exception as e:
            raise Exception(f"Erro ao gerar QR Code: {e}")


class LinhaDigitavel:
    def obter(id_cliente: int, id_acordo: int) -> str:
        dados_acordo = DadosAcordo("Acme", id_cliente, id_acordo).obter_faturas()
        linha_digitavel = extrair_tag(dados_acordo, "<LinhaDigitavel>", "</LinhaDigitavel>")
        if linha_digitavel is None:
            linha_digitavel = "Ã‰ necessario a emissao do boleto, utilizar o metodo emitir-boleto"
        return linha_digitavel
