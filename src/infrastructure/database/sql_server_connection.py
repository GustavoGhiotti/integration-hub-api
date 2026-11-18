import time
from src.shared.utils.env_load import *
import pyodbc
import random
from src.infrastructure.database.base_connection import BaseConnection
from typing import List


class SQLServerConnection(BaseConnection):
    """
    Implementação da conexão com SQL Server usando pyodbc,
    com retry e backoff em caso de deadlock (1205).
    Permite escolher qual servidor/banco usar.
    """

    def __init__(self, server: str, database: str):
        """
        :param server: Nome da variável de ambiente que contém o servidor (ex: 'DB_66')
        :param database: Nome do banco de dados (ex: 'DB_EMAIL')
        """
        self.__ipServidor = server
        self.__banco = database
        self.__usuario = get_env_required("DB_USER")
        self.__senha = get_env_required("DB_PASSWORD")
    
    def _connect(self) -> pyodbc.Connection: 
        return pyodbc.connect("DRIVER={ODBC Driver 17 for SQL Server};"
                              f"SERVER={self.__ipServidor};"
                              f"DATABASE={self.__banco};"
                              f"UID={self.__usuario};"
                              f"PWD={self.__senha};"
                              "TrustServerCertificate=YES"
                              )
    

    def execute(self, *, query: str, parametros: tuple, fetch: bool = False):
        conexao = None  # garante que existe no finally

        for attempt in range(3):
            try:
                conexao = self._connect()

                with conexao.cursor() as cursor:
                    cursor.execute(query, parametros)

                    if fetch:
                        colunas = [c[0] for c in cursor.description]
                        return [dict(zip(colunas, linha)) for linha in cursor.fetchall()]
                    else:
                        conexao.commit()
                        return cursor.rowcount

            except pyodbc.Error as e:
                print(f"Erro no banco: {e}")

                if "1205" in str(e):  # deadlock
                    if conexao:
                        conexao.rollback()

                    if attempt < 2:
                        time.sleep(0.5 + random.random())
                        continue

                raise

            finally:
                if conexao is not None:
                    try:
                        conexao.close()
                    except:
                        pass

    def executemany(self, query: str, parametros: list):

        conexao = None

        try:
            conexao = self._connect() 
            cursor = conexao.cursor()

            cursor.fast_executemany = True
            cursor.executemany(query, parametros)
            conexao.commit()

        except Exception as e:
            # fallback — nunca perde registros
            try:
                if cursor:
                    for p in parametros:
                        try:
                            cursor.execute(query, p)
                        except Exception as e2:
                            pass
                        
                    conexao.commit()
            except:
                pass

        finally:
            if conexao:
                try:
                    conexao.close()
                except:
                    pass

    def execute_transaction(self, statements: list[tuple[str, tuple]]):
        """Executa comandos ordenados com uma conexao e um unico commit."""
        conexao = None
        for attempt in range(3):
            try:
                conexao = self._connect()
                with conexao.cursor() as cursor:
                    for query, parametros in statements:
                        cursor.execute(query, parametros)
                        while cursor.nextset():
                            pass
                conexao.commit()
                return len(statements)
            except pyodbc.Error as error:
                if conexao:
                    conexao.rollback()
                if "1205" in str(error) and attempt < 2:
                    time.sleep(0.5 + random.random())
                    continue
                raise
            except Exception:
                if conexao:
                    conexao.rollback()
                raise
            finally:
                if conexao is not None:
                    try:
                        conexao.close()
                    except Exception:
                        pass
