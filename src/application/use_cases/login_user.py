



from xml.dom import NotFoundErr

from jsonschema import ValidationError
from src.infrastructure.repositories.users_repository import Users_Repository


class LoginUser:
    def __init__(
        self,
        repo: Users_Repository,
    ):
        self.repo = repo

    def execute(self, username: str, password: str) -> dict:
        user = self.repo.pesquisar(username, password)

        if not user:
            raise NotFoundErr("Usuário ou senha inválidos.")

        return user