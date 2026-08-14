from uuid import uuid4
from datetime import datetime
from database.conexao import conectar


class CompromissoRepository:

    def cadastrar(self, compromisso):

        conexao = conectar()
        cursor = conexao.cursor()

        if compromisso.id is None:
            compromisso.id = uuid4()

        sql = """
            INSERT INTO compromisso (id, processo_id, tipo, descricao, data_hora, concluido)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id;
        """

        cursor.execute(sql, (
            str(compromisso.id), str(compromisso.processo_id), compromisso.tipo,
            compromisso.descricao, compromisso.data_hora, compromisso.concluido
        ))

        id = cursor.fetchone()[0]

        conexao.commit()

        cursor.close()
        conexao.close()

        return id

    def listar_por_processo(self, processo_id):

        conexao = conectar()
        cursor = conexao.cursor()

        cursor.execute(
            """
            SELECT * FROM compromisso
            WHERE processo_id = %s
            ORDER BY data_hora;
            """,
            (str(processo_id),)
        )
        compromissos = cursor.fetchall()

        cursor.close()
        conexao.close()

        return compromissos

    def listar_proximos(self, escritorio_id, advogado_id=None, incluir_concluidos=False):
        """
        Agenda do escritorio (ou de um advogado especifico), ordenada por
        data - usada na aba Agenda e no Painel.
        """

        conexao = conectar()
        cursor = conexao.cursor()

        condicoes = ["p.escritorio_id = %s"]
        parametros = [str(escritorio_id)]

        if advogado_id:
            condicoes.append("p.advogado_responsavel_id = %s")
            parametros.append(str(advogado_id))

        if not incluir_concluidos:
            condicoes.append("c.concluido = FALSE")

        sql = f"""
            SELECT c.id, c.tipo, c.descricao, c.data_hora, c.concluido,
                   p.id AS processo_id, p.numero_cnj, u.nome AS advogado_nome
            FROM compromisso c
            JOIN processo p ON p.id = c.processo_id
            LEFT JOIN usuario u ON u.id = p.advogado_responsavel_id
            WHERE {" AND ".join(condicoes)}
            ORDER BY c.data_hora;
        """

        cursor.execute(sql, tuple(parametros))
        compromissos = cursor.fetchall()

        cursor.close()
        conexao.close()

        return compromissos

    def marcar_concluido(self, compromisso_id):

        conexao = conectar()
        cursor = conexao.cursor()

        cursor.execute(
            "UPDATE compromisso SET concluido = TRUE WHERE id = %s;",
            (str(compromisso_id),)
        )

        conexao.commit()

        cursor.close()
        conexao.close()
