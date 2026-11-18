from src.infrastructure.database.sql_server_connection import SQLServerConnection
from src.shared.utils.env_load import DB_66


class CarteiraRepository:
    def __init__(self):
        self.db = SQLServerConnection(server=DB_66, database="DB_CHATBOT")

    def buscar_por_id_cedente(self, id_cedente: int):
        query = """
            SELECT 
                ID,
                ID_CEDENTE,
                NM_CEDENTE,
                NM_CEDENTE_FORMATADO
            FROM msg.TB_CARTEIRA WITH (NOLOCK)
            WHERE ID_CEDENTE = ?
        """

        rows = self.db.execute(query=query, parametros=(id_cedente,), fetch=True)

        if not rows:
            return None

        row = rows[0]

        return {
            "id": row["ID"],
            "idCedente": row["ID_CEDENTE"],
            "nomeCedente": row["NM_CEDENTE"],
            "nomeCedenteFormatado": row["NM_CEDENTE_FORMATADO"],
        }
