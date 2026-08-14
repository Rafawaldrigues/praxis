from uuid import UUID
from datetime import datetime


class Escritorio:

    def __init__(
        self,
        id: UUID = None,
        nome: str = "",
        telefone: str = "",
        email: str = "",
        cnpj: str = "",
        configuracoes: dict = None,
        criado_em: datetime = None
    ):

        self.id = id
        self.nome = nome
        self.telefone = telefone
        self.email = email
        self.cnpj = cnpj
        self.configuracoes = configuracoes
        self.criado_em = criado_em