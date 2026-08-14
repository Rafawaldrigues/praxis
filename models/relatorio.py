from uuid import UUID
from datetime import datetime


class Relatorio:

    def __init__(
        self,
        id: UUID = None,
        processo_id: UUID = None,
        movimentacao_id: UUID = None,
        conteudo: str = "",
        canal_envio: str = "whatsapp",
        status_envio: str = "pendente",
        enviado_em: datetime = None
    ):

        self.id = id
        self.processo_id = processo_id
        self.movimentacao_id = movimentacao_id
        self.conteudo = conteudo
        self.canal_envio = canal_envio
        self.status_envio = status_envio
        self.enviado_em = enviado_em
