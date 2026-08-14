from uuid import UUID
from datetime import datetime


class Usuario:

    def __init__(
        self,
        id: UUID = None,
        escritorio_id: UUID = None,
        nome: str = "",
        email: str = "",
        senha_hash: str = "",
        perfil: str = "admin",
        ativo: bool = True,
        criado_em: datetime = None
    ):

        self.id = id
        self.escritorio_id = escritorio_id
        self.nome = nome
        self.email = email
        self.senha_hash = senha_hash
        self.perfil = perfil
        self.ativo = ativo
        self.criado_em = criado_em
