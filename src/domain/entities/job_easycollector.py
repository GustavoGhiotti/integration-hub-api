from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Any
from uuid import uuid4

from src.domain.enums.job_type_easycollector import JobType


class JobStatus:
    PENDENTE = "PENDENTE"
    EM_EXECUCAO = "EM_EXECUCAO"
    FINALIZADO = "FINALIZADO"
    ERRO = "ERRO"


@dataclass
class Job:

    id: str = field(default_factory=lambda: str(uuid4()))
    chat_id: int | None = None
    tipo: JobType = JobType.CONSULTAR_SITE
    parametros: dict = field(default_factory=dict)

    status: str = JobStatus.PENDENTE
    criado_em: datetime = field(default_factory=datetime.utcnow)
    iniciado_em: Optional[datetime] = None
    finalizado_em: Optional[datetime] = None

    resultado: Optional[Any] = None
    erro: Optional[str] = None


    def iniciar(self) -> None:
        if self.status != JobStatus.PENDENTE:
            raise RuntimeError("Job não pode ser iniciado neste estado")

        self.status = JobStatus.EM_EXECUCAO
        self.iniciado_em = datetime.utcnow()


    def finalizar(self, resultado: Any = None) -> None:
        if self.status != JobStatus.EM_EXECUCAO:
            raise RuntimeError("Job não pode ser finalizado neste estado")

        self.status = JobStatus.FINALIZADO
        self.finalizado_em = datetime.utcnow()
        self.resultado = resultado


    def falhar(self, erro: str) -> None:
        self.status = JobStatus.ERRO
        self.finalizado_em = datetime.utcnow()
        self.erro = erro
