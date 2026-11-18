import requests
from src.shared.utils.env_load import (
    INFOBIP_BASE_URL,
    INFOBIP_API_KEY,
    INFOBIP_AUTH_TYPE,
    INFOBIP_WHATSAPP_ENDPOINT,
)


class InfobipClient:
    def __init__(
        self,
        base_url: str | None = INFOBIP_BASE_URL,
        api_key: str | None = INFOBIP_API_KEY,
        auth_type: str = INFOBIP_AUTH_TYPE,
        endpoint: str = INFOBIP_WHATSAPP_ENDPOINT,
    ):
        self.base_url = base_url
        self.api_key = api_key
        self.auth_type = auth_type
        self.endpoint = endpoint

    def get(self, path: str, params: dict | None = None) -> dict:
        if not self.base_url:
            raise Exception("INFOBIP_BASE_URL nao configurado")
        if not self.api_key:
            raise Exception("INFOBIP_API_KEY nao configurado")

        normalized_base_url = self.base_url.strip()
        if not normalized_base_url.startswith(("http://", "https://")):
            normalized_base_url = f"https://{normalized_base_url}"

        url = f"{normalized_base_url.rstrip('/')}/{path.lstrip('/')}"
        headers = {
            "Authorization": f"{self.auth_type} {self.api_key}",
            "Accept": "application/json",
        }

        response = requests.get(url, headers=headers, params=params, timeout=15)

        try:
            data = response.json()
        except Exception:
            data = {"raw": response.text}

        if response.status_code >= 400:
            raise Exception(f"Infobip erro {response.status_code}: {data}")

        return data

    def send_whatsapp_template(self, payload: dict) -> dict:
        if not self.base_url:
            raise Exception("INFOBIP_BASE_URL nao configurado")
        if not self.api_key:
            raise Exception("INFOBIP_API_KEY nao configurado")

        normalized_base_url = self.base_url.strip()
        if not normalized_base_url.startswith(("http://", "https://")):
            normalized_base_url = f"https://{normalized_base_url}"

        url = f"{normalized_base_url.rstrip('/')}/{self.endpoint.lstrip('/')}"
        headers = {
            "Authorization": f"{self.auth_type} {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        response = requests.post(url, json=payload, headers=headers, timeout=15)

        try:
            data = response.json()
        except Exception:
            data = {"raw": response.text}

        if response.status_code >= 400:
            raise Exception(f"Infobip erro {response.status_code}: {data}")

        return data
