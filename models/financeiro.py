from uuid import UUID
from datetime import date, datetime


class Financeiro:

    def __init__(
        self,
        id: UUID = None,
        escritorio_id: UUID = None,
        processo_id: UUID = None,
        cliente_id: UUID = None,
        tipo: str = "receita",
        descricao: str = "",
        valor: float = 0.0,
        status: str = "pendente",
        vencimento: date = None,
        pago_em: datetime = None,
        criado_em: datetime = None
    ):
        self.id = id
        self.escritorio_id = escritorio_id
        self.processo_id = processo_id
        self.cliente_id = cliente_id
        self.tipo = tipo
        self.descricao = descricao
        self.valor = valor
        self.status = status
        self.vencimento = vencimento
        self.pago_em = pago_em
        self.criado_em = criado_em
