from uuid import UUID
from datetime import datetime


class Compromisso:

    def __init__(
        self,
        id: UUID = None,
        processo_id: UUID = None,
        tipo: str = "outro",
        descricao: str = "",
        data_hora: datetime = None,
        concluido: bool = False,
        criado_em: datetime = None
    ):
        self.id = id
        self.processo_id = processo_id
        self.tipo = tipo
        self.descricao = descricao
        self.data_hora = data_hora
        self.concluido = concluido
        self.criado_em = criado_em
