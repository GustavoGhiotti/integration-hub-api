
from jsonschema import ValidationError


def parse_login(data: dict):
    if not isinstance(data, dict):
        raise ValidationError("JSON inválido.")

    username = (data.get("username") or "").strip()
    password = (data.get("password") or "").strip()

    if not username or not password:
        raise ValidationError("Usuário e senha são obrigatórios.")

    return username, password
