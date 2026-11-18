import json

from flask import jsonify, has_request_context, request
from werkzeug.exceptions import HTTPException


def _request_payload_for_log():
    if not has_request_context():
        return "-"

    try:
        payload = request.get_json(silent=True)
        if payload is not None:
            return json.dumps(payload, ensure_ascii=False, default=str)
    except Exception:
        pass

    try:
        raw_body = request.get_data(cache=True, as_text=True)
        if raw_body:
            return raw_body[:5000]
    except Exception:
        pass

    return "-"


def register_http_error_handlers(app):

    @app.errorhandler(HTTPException)
    def handle_http_error(e: HTTPException):
        response = {
            "error": e.name,
            "code": e.code,
            "description": e.description,
        }
        app.logger.warning(
            "Erro HTTP %s method=%s path=%s descricao=%s",
            e.code,
            request.method if has_request_context() else "-",
            request.path if has_request_context() else "-",
            e.description,
        )
        return jsonify(response), e.code

    @app.errorhandler(Exception)
    def handle_generic_error(e):
        app.logger.exception(
            "Erro nao tratado method=%s path=%s query=%s payload=%s erro=%s",
            request.method if has_request_context() else "-",
            request.path if has_request_context() else "-",
            dict(request.args) if has_request_context() else "-",
            _request_payload_for_log(),
            e,
        )
        return jsonify({
            "error": "Erro interno no servidor",
            "code": 500
        }), 500
