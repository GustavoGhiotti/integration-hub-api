from typing import cast
from flask import g

from src.infrastructure.external.collectsys.credentials.credentials import CollectSysCredentials
from src.infrastructure.repositories.sql_collectsys_repository import SqlCollectSysRepository
from src.domain.entities.usuario_collectsys import UsuarioCollectSys
from src.shared.utils.env_load import get_env_required


class CollectSysCredentialsProvider:
    def __init__(self):
        self.repository = SqlCollectSysRepository(
            server=get_env_required("DB_66"),
            database="DB_DESENVOLVIMENTO"
        )

    def obter(self, id_cedente: int | None = None) -> CollectSysCredentials:
        if id_cedente in (73, 65, 71, 70):
            id_usuario = self._mapear_usuario_por_cedente(id_cedente)

            result = self.repository.obter_usuario_cedente(id_usuario)

            return CollectSysCredentials(
                usuario=result["USUARIO"],
                senha=result["SENHA"]
            )

        collectsys = cast(UsuarioCollectSys, g.collectsys)

        return CollectSysCredentials(
            usuario=collectsys.login,
            senha=collectsys.senha
        )

    def _mapear_usuario_por_cedente(self, id_cedente: int) -> int:
        mapa = {
            73: 8,
            65: 9,
            71: 7,
            70: 10,
        }

        return mapa[id_cedente]
    
    