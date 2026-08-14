from uuid import UUID
from datetime import datetime


class Documento:

    def __init__(
        self,
        id: UUID = None,
        processo_id: UUID = None,
        usuario_id: UUID = None,
        nome_arquivo: str = "",
        tipo: str = "outro",
        conteudo: bytes = None,
        tamanho_bytes: int = None,
        criado_em: datetime = None
    ):

        self.id = id
        self.processo_id = processo_id
        self.usuario_id = usuario_id
        self.nome_arquivo = nome_arquivo
        self.tipo = tipo
        self.conteudo = conteudo
        self.tamanho_bytes = tamanho_bytes
        self.criado_em = criado_em
