import os
from flask import jsonify, request
from flask_smorest import Blueprint
import requests
from src.infrastructure.repositories.sql_acionamento_repository import AcionamentoRepository
from src.presentation.schemas.auth import *
from src.application.services.twilio_chat_service import TwilioChatService
from twilio.request_validator import RequestValidator
from threading import Thread


bp = Blueprint("chat portalacordo", __name__, url_prefix="/chat")

TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
INTERNAL_WEBHOOK_URL = os.getenv("INTERNAL_WEBHOOK_URL") 
INTERNAL_WEBHOOK_TOKEN = os.getenv("INTERNAL_WEBHOOK_TOKEN")  

validator = RequestValidator(TWILIO_AUTH_TOKEN)


@bp.post("/twilio/conversations/webhook")
def twilio_conversations_webhook():
    signature = request.headers.get("X-Twilio-Signature", "")
    url = request.url
    form = request.form.to_dict()

    if not validator.validate(str(url), form, signature):
        return jsonify({"error": "invalid signature"}), 403

    def _forward():
        try:
            requests.post(
                INTERNAL_WEBHOOK_URL,
                json=form,
                headers={"X-Internal-Token": INTERNAL_WEBHOOK_TOKEN},
                timeout=(1, 2),
            )
        except Exception:
            pass

    Thread(target=_forward, daemon=True).start()
    return jsonify({}), 200


