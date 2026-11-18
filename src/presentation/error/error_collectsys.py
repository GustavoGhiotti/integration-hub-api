from flask import jsonify
from src.domain.exceptions import * 

def register_collectsys_error_handlers(app):
    @app.errorhandler(TabularException)
    def handle_tabulacao_invalido(e):
        return jsonify({"status": False, "erro": str(e)}), 401
    @app.errorhandler(ErroFormalizarAcordo)
    def handle_formalizar_invalido(e):
        return jsonify({"status": False, "erro": str(e)}), 401
    @app.errorhandler(CodigoPixException)
    def handle_formalizar_invalido(e):
        return jsonify({"status": False, "erro": str(e)}), 401
    @app.errorhandler(BetaBoletoException)
    def beta_boleto_exception(e:BetaBoletoException):
        return jsonify({"status": False, "erro": str(e.erro())}), 401
    @app.errorhandler(CollectSysException)
    def collectsys_exception(e:CollectSysException):
        return jsonify({"status": False, "erro": str(e.erro())}), 401
