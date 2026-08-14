from uuid import uuid4
from datetime import datetime
from database.conexao import conectar


class FinanceiroRepository:

    def cadastrar(self, lancamento):

        conexao = conectar()
        cursor = conexao.cursor()

        if lancamento.id is None:
            lancamento.id = uuid4()

        sql = """
            INSERT INTO financeiro (
                id, escritorio_id, processo_id, cliente_id, tipo,
                descricao, valor, status, vencimento
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id;
        """

        cursor.execute(sql, (
            str(lancamento.id),
            str(lancamento.escritorio_id),
            str(lancamento.processo_id) if lancamento.processo_id else None,
            str(lancamento.cliente_id) if lancamento.cliente_id else None,
            lancamento.tipo,
            lancamento.descricao,
            lancamento.valor,
            lancamento.status,
            lancamento.vencimento
        ))

        id = cursor.fetchone()[0]

        conexao.commit()

        cursor.close()
        conexao.close()

        return id

    def listar_por_escritorio(self, escritorio_id, status=None):

        conexao = conectar()
        cursor = conexao.cursor()

        condicoes = ["f.escritorio_id = %s"]
        parametros = [str(escritorio_id)]

        if status:
            condicoes.append("f.status = %s")
            parametros.append(status)

        sql = f"""
            SELECT f.id, f.tipo, f.descricao, f.valor, f.status, f.vencimento,
                   p.numero_cnj, c.nome AS cliente_nome
            FROM financeiro f
            LEFT JOIN processo p ON p.id = f.processo_id
            LEFT JOIN cliente c ON c.id = f.cliente_id
            WHERE {" AND ".join(condicoes)}
            ORDER BY f.vencimento NULLS LAST, f.criado_em DESC;
        """

        cursor.execute(sql, tuple(parametros))
        lancamentos = cursor.fetchall()

        cursor.close()
        conexao.close()

        return lancamentos

    def listar_por_processo(self, processo_id):

        conexao = conectar()
        cursor = conexao.cursor()

        cursor.execute(
            "SELECT * FROM financeiro WHERE processo_id = %s ORDER BY vencimento NULLS LAST;",
            (str(processo_id),)
        )
        lancamentos = cursor.fetchall()

        cursor.close()
        conexao.close()

        return lancamentos

    def marcar_pago(self, lancamento_id):

        conexao = conectar()
        cursor = conexao.cursor()

        cursor.execute(
            "UPDATE financeiro SET status = 'pago', pago_em = %s WHERE id = %s;",
            (datetime.now(), str(lancamento_id))
        )

        conexao.commit()

        cursor.close()
        conexao.close()

    def resumo(self, escritorio_id):
        """
        Totais rapidos pro painel: a receber (receita pendente),
        recebido (receita paga), a pagar (despesa pendente).
        """

        conexao = conectar()
        cursor = conexao.cursor()

        cursor.execute(
            """
            SELECT tipo, status, COALESCE(SUM(valor), 0)
            FROM financeiro
            WHERE escritorio_id = %s
            GROUP BY tipo, status;
            """,
            (str(escritorio_id),)
        )
        linhas = cursor.fetchall()

        cursor.close()
        conexao.close()

        resumo = {"a_receber": 0, "recebido": 0, "a_pagar": 0, "pago": 0}
        for tipo, status, total in linhas:
            total = float(total)
            if tipo == "receita" and status == "pendente":
                resumo["a_receber"] = total
            elif tipo == "receita" and status == "pago":
                resumo["recebido"] = total
            elif tipo == "despesa" and status == "pendente":
                resumo["a_pagar"] = total
            elif tipo == "despesa" and status == "pago":
                resumo["pago"] = total

        return resumo
