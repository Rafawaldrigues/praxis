from uuid import uuid4
from datetime import datetime
from psycopg.types.json import Json
from database.conexao import conectar


class MovimentacaoRepository:

    def cadastrar(self, movimentacao):

        conexao = conectar()
        cursor = conexao.cursor()

        if movimentacao.id is None:
            movimentacao.id = uuid4()

        if movimentacao.data_consulta is None:
            movimentacao.data_consulta = datetime.now()

        sql = """
            INSERT INTO movimentacao (
                id,
                processo_id,
                descricao_original,
                descricao_resumida,
                importancia,
                data_movimentacao,
                data_consulta,
                metadados
            )
            VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s
            )
            RETURNING id;
        """

        cursor.execute(sql, (
            str(movimentacao.id),
            str(movimentacao.processo_id),
            movimentacao.descricao_original,
            movimentacao.descricao_resumida,
            movimentacao.importancia,
            movimentacao.data_movimentacao,
            movimentacao.data_consulta,
            Json(movimentacao.metadados or {})
        ))

        id = cursor.fetchone()[0]

        conexao.commit()

        cursor.close()
        conexao.close()

        return id

    def obter_data_ultima_movimentacao(self, processo_id):
        """
        Retorna a data/hora da movimentacao mais recente ja salva pra esse
        processo, ou None se ainda nao tem nenhuma (processo novo).
        """

        conexao = conectar()
        cursor = conexao.cursor()

        cursor.execute(
            """
            SELECT MAX(data_movimentacao)
            FROM movimentacao
            WHERE processo_id = %s;
            """,
            (str(processo_id),)
        )

        resultado = cursor.fetchone()

        cursor.close()
        conexao.close()

        return resultado[0] if resultado else None

    def listar_por_processo(self, processo_id):

        conexao = conectar()
        cursor = conexao.cursor()

        sql = """
            SELECT *
            FROM movimentacao
            WHERE processo_id = %s
            ORDER BY data_movimentacao DESC;
        """

        cursor.execute(sql, (str(processo_id),))

        movimentacoes = cursor.fetchall()

        cursor.close()
        conexao.close()

        return movimentacoes
