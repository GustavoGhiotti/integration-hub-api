from flask_smorest import Blueprint
from flask import request
from flask import jsonify
from src.infrastructure.security.auth_decorator import token_require
from src.application.services.upload_arquivo_service import FileUploadService
from src.presentation.schemas import UploadArquivoResponseSchema, Erro401Schema

bp = Blueprint("arquivo", __name__, url_prefix="/upload")


@bp.post("/upload-arquivo")
@token_require("/upload")
@bp.response(200, UploadArquivoResponseSchema)
@bp.response(401, Erro401Schema)
def upload_boleto():
    try:
        file = request.files.get("file")

        service = FileUploadService()
        result = service.upload_boleto(file)

        return jsonify({
            "status": True,
            "boleto": result
        }), 200

    except ValueError as e:
        return {"erro": str(e)}, 400

    except Exception as e:
        print("ERRO UPLOAD >>>", e)
        return {"erro": "Erro interno ao processar upload"}, 500
