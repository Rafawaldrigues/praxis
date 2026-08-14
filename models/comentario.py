from uuid import UUID
from datetime import datetime


class Comentario:

    def __init__(
        self,
        id: UUID = None,
        processo_id: UUID = None,
        usuario_id: UUID = None,
        texto: str = "",
        criado_em: datetime = None
    ):

        self.id = id
        self.processo_id = processo_id
        self.usuario_id = usuario_id
        self.texto = texto
        self.criado_em = criado_em
