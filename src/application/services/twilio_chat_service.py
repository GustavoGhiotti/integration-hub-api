import os
from datetime import datetime, timezone
from typing import Optional
from twilio.rest import Client


class TwilioChatService:
    def __init__(self, identity: Optional[str] = None) -> None:
        self.twilio_client = Client(
            os.getenv("ACCOUNT_SID"),
            os.getenv("AUTH_TOKEN"),
        )
        self.service_sid = os.getenv("TWILIO_CONVERSATIONS_SERVICE_SID")
        self.flow_sid = os.getenv("TWILIO_FLOW_SID")
        self.conversation_sid: Optional[str] = None
        self.identity = identity

    def _require_service_sid(self) -> None:
        if not self.service_sid:
            raise RuntimeError("TWILIO_CONVERSATIONS_SERVICE_SID não configurado.")

    def _resolve_identity(self, identity: Optional[str]) -> str:
        resolved = identity or self.identity
        if not resolved:
            raise RuntimeError("identity não informado.")
        return resolved

    @staticmethod
    def _unique_name(identity: str) -> str:
        return f"chat-web-{identity}"

    def get_or_create_conversation(self, identity: Optional[str] = None) -> str:
        self._require_service_sid()

        resolved_identity = self._resolve_identity(identity)
        unique_name = self._unique_name(resolved_identity)

        if self.conversation_sid:
            conversation_sid = self.conversation_sid
        else:
            conversations = self.twilio_client.conversations.v1.services(
                self.service_sid
            ).conversations
            existing = conversations.list(limit=200)
            conversation = next(
                (c for c in existing if c.unique_name == unique_name),
                None,
            )

            if not conversation:
                conversation = conversations.create(
                    unique_name=unique_name,
                    friendly_name="Chat Web",
                )
            self.conversation_sid = conversation.sid
            conversation_sid = conversation.sid

        self.ensure_participant(conversation_sid, resolved_identity)
        self.ensure_studio_webhook(conversation_sid)
        return conversation_sid

    def ensure_studio_webhook(self, conversation_sid: str) -> None:
        if not self.flow_sid:
            return

        webhooks = self.twilio_client.conversations.v1.services(self.service_sid) \
            .conversations(conversation_sid) \
            .webhooks

        existing = webhooks.list(limit=20)
        for webhook in existing:
            config = webhook.configuration or {}
            if webhook.target == "studio" and config.get("flow_sid") == self.flow_sid:
                return

        try:
            webhooks.create(
                target="studio",
                configuration_flow_sid=self.flow_sid,
                configuration_filters=["onMessageAdded"],
            )
        except Exception as exc:
            print(f"[TWILIO] failed creating studio webhook: {exc}")

    def ensure_participant(self, conversation_sid: str, identity: str) -> None:
        try:
            self.twilio_client.conversations.v1.services(self.service_sid) \
                .conversations(conversation_sid) \
                .participants.create(identity=identity)
        except Exception:
            pass

    def send_message(
        self,
        conversation_sid: str,
        identity: Optional[str],
        message: str,
    ) -> None:
        resolved_identity = self._resolve_identity(identity)
        self.twilio_client.conversations.v1.services(self.service_sid) \
            .conversations(conversation_sid) \
            .messages.create(
                author=resolved_identity,
                body=message,
                x_twilio_webhook_enabled="true",
            )

    def list_messages(self, conversation_sid: str, limit: int = 200) -> list[dict]:
        items = self.twilio_client.conversations.v1.services(self.service_sid) \
            .conversations(conversation_sid) \
            .messages.list(limit=limit)

        return [
            {
                "sid": msg.sid,
                "author": msg.author,
                "body": msg.body,
                "date_created": msg.date_created.isoformat() if msg.date_created else None,
                "client_id": None,
            }
            for msg in reversed(items)
        ]

    @staticmethod
    def now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()
