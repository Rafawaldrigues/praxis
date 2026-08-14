from uuid import uuid4
from datetime import datetime
from database.conexao import conectar


class RelatorioRepository:

    def cadastrar(self, relatorio):

        conexao = conectar()
        cursor = conexao.cursor()

        if relatorio.id is None:
            relatorio.id = uuid4()

        sql = """
            INSERT INTO relatorio (
                id,
                processo_id,
                movimentacao_id,
                conteudo,
                canal_envio,
                status_envio,
                enviado_em
            )
            VALUES (
                %s, %s, %s, %s, %s, %s, %s
            )
            RETURNING id;
        """

        cursor.execute(sql, (
            str(relatorio.id),
            str(relatorio.processo_id),
            str(relatorio.movimentacao_id) if relatorio.movimentacao_id else None,
            relatorio.conteudo,
            relatorio.canal_envio,
            relatorio.status_envio,
            relatorio.enviado_em
        ))

        id = cursor.fetchone()[0]

        conexao.commit()

        cursor.close()
        conexao.close()

        return id

    def listar_pendentes(self, escritorio_id=None):
        """
        Um "aviso pendente" = um relatorio com status_envio = 'pendente',
        expandido por cliente (um processo pode ter mais de um cliente vinculado).
        """

        conexao = conectar()
        cursor = conexao.cursor()

        sql = """
            SELECT
                r.id                AS relatorio_id,
                r.conteudo,
                r.canal_envio,
                m.descricao_resumida,
                m.importancia,
                m.data_movimentacao,
                p.id                AS processo_id,
                p.numero_cnj,
                c.id                AS cliente_id,
                c.nome              AS cliente_nome
            FROM relatorio r
            JOIN processo p ON p.id = r.processo_id
            LEFT JOIN movimentacao m ON m.id = r.movimentacao_id
            JOIN cliente_processo cp ON cp.processo_id = p.id
            JOIN cliente c ON c.id = cp.cliente_id
            WHERE r.status_envio = 'pendente'
            {filtro}
            ORDER BY m.data_movimentacao DESC NULLS LAST;
        """.format(filtro="AND p.escritorio_id = %s" if escritorio_id else "")

        if escritorio_id:
            cursor.execute(sql, (str(escritorio_id),))
        else:
            cursor.execute(sql)

        avisos = cursor.fetchall()

        cursor.close()
        conexao.close()

        return avisos

    def marcar_como_enviado(self, relatorio_id):

        conexao = conectar()
        cursor = conexao.cursor()

        sql = """
            UPDATE relatorio
            SET status_envio = 'enviado',
                enviado_em = %s
            WHERE id = %s;
        """

        cursor.execute(sql, (datetime.now(), str(relatorio_id)))

        conexao.commit()

        cursor.close()
        conexao.close()
