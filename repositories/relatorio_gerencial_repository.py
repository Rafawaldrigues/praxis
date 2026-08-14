from database.conexao import conectar


ORDENS_MOVIMENTACAO = {
    "recente": "m.data_movimentacao DESC",
    "antigo": "m.data_movimentacao ASC",
    "urgente": """
        CASE m.importancia
            WHEN 'alta' THEN 1
            WHEN 'media' THEN 2
            WHEN 'baixa' THEN 3
            ELSE 4
        END ASC, m.data_movimentacao DESC
    """,
}


class RelatorioGerencialRepository:

    def listar_movimentacoes(self, escritorio_id, data_inicio=None, data_fim=None, ordenar_por="recente"):
        """
        Relatorio de todas as movimentacoes (atualizacoes) do escritorio
        num periodo, com filtro e ordenacao (recente/antigo/urgente).
        """

        conexao = conectar()
        cursor = conexao.cursor()

        condicoes = ["p.escritorio_id = %s"]
        parametros = [str(escritorio_id)]

        if data_inicio:
            condicoes.append("m.data_movimentacao >= %s")
            parametros.append(data_inicio)

        if data_fim:
            condicoes.append("m.data_movimentacao <= %s")
            parametros.append(data_fim)

        ordem_sql = ORDENS_MOVIMENTACAO.get(ordenar_por, ORDENS_MOVIMENTACAO["recente"])

        sql = f"""
            SELECT
                m.id, m.descricao_resumida, m.importancia, m.data_movimentacao,
                p.id AS processo_id, p.numero_cnj,
                u.nome AS advogado_nome
            FROM movimentacao m
            JOIN processo p ON p.id = m.processo_id
            LEFT JOIN usuario u ON u.id = p.advogado_responsavel_id
            WHERE {" AND ".join(condicoes)}
            ORDER BY {ordem_sql};
        """

        cursor.execute(sql, tuple(parametros))
        movimentacoes = cursor.fetchall()

        cursor.close()
        conexao.close()

        return movimentacoes

    def listar_processos_por_tempo_sem_atualizacao(self, escritorio_id, ordem="mais_tempo"):
        """
        Um processo por linha, com a data da ultima movimentacao (ou NULL
        se nunca teve nenhuma) - pra identificar processos "esquecidos".
        ordem: 'mais_tempo' (mais tempo parado primeiro) ou 'menos_tempo'.
        """

        conexao = conectar()
        cursor = conexao.cursor()

        direcao = "ASC" if ordem == "mais_tempo" else "DESC"
        # NULLS FIRST quando "mais_tempo" (processo sem nenhuma movimentacao = o mais parado de todos)
        nulls = "NULLS FIRST" if ordem == "mais_tempo" else "NULLS LAST"

        sql = f"""
            SELECT
                p.id, p.numero_cnj, p.status,
                u.nome AS advogado_nome,
                MAX(m.data_movimentacao) AS ultima_movimentacao
            FROM processo p
            LEFT JOIN usuario u ON u.id = p.advogado_responsavel_id
            LEFT JOIN movimentacao m ON m.processo_id = p.id
            WHERE p.escritorio_id = %s
            GROUP BY p.id, p.numero_cnj, p.status, u.nome
            ORDER BY ultima_movimentacao {direcao} {nulls};
        """

        cursor.execute(sql, (str(escritorio_id),))
        processos = cursor.fetchall()

        cursor.close()
        conexao.close()

        return processos
