from flask import jsonify
from src.domain.exceptions import *
from pydantic import ValidationError


def register_domain_error_handlers(app):
    @app.errorhandler(CpfCnpjInvalidoException)
    def handle_cpf_invalido(e):
        return jsonify({"status": False, "erro": str(e)}), 401

    @app.errorhandler(NenhumaDividaException)
    def handle_sem_divida(e):
        return jsonify({"status": True, "msg": str(e)}), 200

    @app.errorhandler(InfobipNumeroIndisponivelException)
    def handle_infobip_numero_indisponivel(e):
        return jsonify({"status": False, "msg": str(e)}), 200
    
    @app.errorhandler(RetornoTratadoBeta)
    def handle_sem_divida(e):
        return jsonify({"status": True, "msg": str(e)}), 200

    @app.errorhandler(TokenInvalido)
    def handle_token_invalido(e):
        return jsonify({"status": False, "erro": str(e)}), 401

    @app.errorhandler(ValidationError)
    def handle_arg_invalido(e):
        detalhes = []

        for err in e.errors():
            campo = ".".join(str(p) for p in err.get("loc", []))
            msg = err.get("msg", "Erro de validação")
            tipo = err.get("type", "")

            # Tenta extrair apenas o valor relacionado ao campo específico
            valor_invalido = None
            input_data = err.get("input", None)

            if isinstance(input_data, dict) and campo in input_data:
                valor_invalido = input_data[campo]
            elif not isinstance(input_data, dict):
                valor_invalido = input_data

            detalhes.append({
                "campo": campo,
                "mensagem": msg,
                "tipo_erro": tipo,
                "valor_invalido": valor_invalido
            })

        return jsonify({
            "status": False,
            "erro": "Erro de validação nos campos enviados",
            "detalhes": detalhes
        }), 400

