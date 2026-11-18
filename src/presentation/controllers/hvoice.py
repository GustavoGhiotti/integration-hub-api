from flask import jsonify, send_from_directory
from flask_smorest import Blueprint
from src.infrastructure.security.auth_decorator import token_require
from src.application.services.hvoice_service import (
    HVOICE_DOWNLOAD_BASE_URL,
    Hvoice,
    apagar_zip_apos_24h,
    diretorio_hvoice_publicado,
)
from src.presentation.schemas import HvoiceSchema

import os 
from datetime import datetime

bp = Blueprint("Hvoice", __name__, url_prefix = "/hvoice")

@bp.get("/obter-metadados")
@bp.doc(description="Método para obter dívidas dos clientes")
@bp.arguments(HvoiceSchema, location="headers")
@token_require("/hvoice")
def obter_metadados(body: HvoiceSchema):
     
    service = Hvoice(
        cedente = body.carteira,
        data = body.data.strftime("%Y-%m-%d"),
        data_final = body.data_final.strftime("%Y-%m-%d") if getattr(body, "data_final", None) else None,
        faixa = body.produto,
        tabulacao = body.tabulacao,
        min_minuto = body.minsegundos,
        max_minuto = body.maxsegundos,
        min_total_max = body.mintotalmax,
        qtd_operador = body.qtdoperador
    )
    
    if service.cedente.upper() == "VEGA":
        resultado_metadados = service.metadados_vega()
    else:
        resultado_metadados = service.metadados_cobranca()

    if not resultado_metadados:
        return jsonify({"status": False, "msg": "Nenhum arquivo gerado (zip_path None)"}), 404

    zip_path = resultado_metadados["zip_path"]

    if not os.path.exists(zip_path):
        return jsonify({"status": False, "msg": "Arquivo ZIP não encontrado no diretório temporário"}), 404
    
    apagar_zip_apos_24h(zip_path)

    filename = os.path.basename(zip_path)
    download_link = f"{HVOICE_DOWNLOAD_BASE_URL}/{filename}"
    gerado_em = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


    return jsonify({
        "status": True,
        "download_link": download_link,
        "gerado_em": gerado_em,
        "carteira": body.carteira,
        "data_processada": body.data,
        "data_final": getattr(body, "data_final", None),
        "faixa": body.produto,
        "total_segundos_audios": resultado_metadados["total_segundos_audios"],
        "total_minutos_audios": resultado_metadados["total_minutos_audios"],
        "tempo_validade": "24 hora"
    }), 200


@bp.get("/download/<filename>")
@token_require("/hvoice")
def download_file(filename):
    dir_hvoice = diretorio_hvoice_publicado()
    file_path = os.path.join(dir_hvoice, filename)
    
    if not os.path.exists(file_path):
        return jsonify({"status": False, "msg": "Arquivo não encontrado"}), 404
    
    return send_from_directory(dir_hvoice, filename, as_attachment=True)
