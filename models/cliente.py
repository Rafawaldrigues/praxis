from uuid import UUID
from datetime import datetime


class Cliente:

    def __init__(
        self,
        id: UUID = None,
        escritorio_id: UUID = None,
        nome: str = "",
        cpf_cnpj: str = "",
        email: str = "",
        telefone: str = "",
        whatsapp: str = "",
        idade: int = None,
        tipo_pessoa: str = "",
        preferencias_notificacao: dict = None,
        criado_em: datetime = None
    ):

        self.id = id
        self.escritorio_id = escritorio_id
        self.nome = nome
        self.cpf_cnpj = cpf_cnpj
        self.email = email
        self.telefone = telefone
        self.whatsapp = whatsapp
        self.idade = idade
        self.tipo_pessoa = tipo_pessoa
        self.preferencias_notificacao = preferencias_notificacao
        self.criado_em = criado_em