import time
import logging
from functools import wraps

log = logging.getLogger("db_utils")

def safe_db_exec(context: str):
    """
    Decorator para padronizar execução de queries SQL.
    - Loga sucesso e erros com contexto (ex: 'registrar_disparo')
    - Mede tempo de execução
    - Evita repetição de try/except em cada função
    """
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            start = time.time()
            try:
                result = func(self, *args, **kwargs)
                duration = time.time() - start
                log.info(f"[{context}] Execução OK em {duration:.3f}s")
                return result
            except Exception as e:
                duration = time.time() - start
                log.error(f"[{context}] Erro: {e} (tempo={duration:.3f}s)", exc_info=True)
                raise
        return wrapper
    return decorator