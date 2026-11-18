from flask import jsonify
from werkzeug.exceptions import HTTPException

def register_http_error_handlers(app):

    @app.errorhandler(HTTPException)
    def handle_http_error(e: HTTPException):
        response = {
            "error": e.name,
            "code": e.code,
            "description": e.description,
        }
        app.logger.warning("Erro HTTP %s: %s", e.code, e.description)
        return jsonify(response), e.code

    @app.errorhandler(Exception)
    def handle_generic_error(e):
        print(e)
        app.logger.exception("Erro não tratado: %s", e)
        return jsonify({
            "error": "Erro interno no servidor",
            "code": 500
        }), 500