import asyncio
import base64
import os
import shutil

from flask import Blueprint, jsonify, request

from src.application.services.easycollector_service import ExecutarJobUseCase
from src.domain.entities.job_easycollector import Job
from src.domain.enums.job_type_easycollector import JobType
from src.shared.utils.env_load import Settings


bp = Blueprint("easycollector", __name__, url_prefix="/easycollector")


@bp.post("/status")
def executar_easycollector():
    payload = request.get_json(silent=True) or {}
    tarefa = payload.get("tarefa")
    status = payload.get("status")

    if not tarefa and not status:
        return jsonify({"erro": "Informe 'tarefa' ou 'status'"}), 400

    usuario = os.getenv("EASYCOLLECTOR_USER")
    senha = os.getenv("EASYCOLLECTOR_PASSWORD")
    if not usuario or not senha:
        return jsonify({"erro": "EASYCOLLECTOR_USER/EASYCOLLECTOR_PASSWORD nao definidos"}), 500

    job = Job(
        chat_id=None,
        tipo=JobType.CONSULTAR_SITE,
        parametros={
            "usuario": usuario,
            "senha": senha,
            "tarefa": tarefa,
            "status": status
        }
    )

    try:
        resultado = asyncio.run(ExecutarJobUseCase().executar(job))
        screenshot_paths = resultado.get("screenshots") or []
        screenshot_path = resultado.get("screenshot")
        if not screenshot_paths and screenshot_path:
            screenshot_paths = [screenshot_path]
        imagem_base64 = None
        imagens_base64 = []
        for path in screenshot_paths:
            if path and os.path.isfile(path):
                with open(path, "rb") as arquivo:
                    encoded = base64.b64encode(arquivo.read()).decode("ascii")
                    imagens_base64.append(encoded)
        if imagens_base64:
            imagem_base64 = imagens_base64[0]

        return jsonify({
            "job_id": resultado.get("job_id"),
            "tarefa": resultado.get("tarefa"),
            "status": resultado.get("status"),
            "imagem_base64": imagem_base64,
            "imagens_base64": imagens_base64,
        }), 200
    except Exception as exc:
        return jsonify({"erro": str(exc)}), 500
    finally:
        pasta_data = os.path.join(Settings.BASE_DIR, "data")
        if os.path.isdir(pasta_data):
            shutil.rmtree(pasta_data)


@bp.get("/health")
def health():
    return jsonify({"status": "ok"}), 200
