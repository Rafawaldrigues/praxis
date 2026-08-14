from uuid import UUID
from datetime import datetime


class Movimentacao:

    def __init__(
        self,
        id: UUID = None,
        processo_id: UUID = None,
        descricao_original: str = "",
        descricao_resumida: str = "",
        importancia: str = "media",
        data_movimentacao: datetime = None,
        data_consulta: datetime = None,
        metadados: dict = None
    ):

        self.id = id
        self.processo_id = processo_id
        self.descricao_original = descricao_original
        self.descricao_resumida = descricao_resumida
        self.importancia = importancia
        self.data_movimentacao = data_movimentacao
        self.data_consulta = data_consulta
        self.metadados = metadados
