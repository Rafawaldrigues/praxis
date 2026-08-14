from uuid import UUID
from datetime import datetime


class Processo:

    def __init__(
        self,
        id: UUID = None,
        escritorio_id: UUID = None,
        tribunal_id: UUID = None,
        numero_cnj: str = "",
        classe: str = "",
        assunto: str = "",
        vara: str = "",
        comarca: str = "",
        status: str = "ativo",
        advogado_responsavel_id: UUID = None,
        valor_causa: float = None,
        criado_em: datetime = None,
        atualizado_em: datetime = None
    ):

        self.id = id
        self.escritorio_id = escritorio_id
        self.tribunal_id = tribunal_id
        self.numero_cnj = numero_cnj
        self.classe = classe
        self.assunto = assunto
        self.vara = vara
        self.comarca = comarca
        self.status = status
        self.advogado_responsavel_id = advogado_responsavel_id
        self.valor_causa = valor_causa
        self.criado_em = criado_em
        self.atualizado_em = atualizado_em
