from database.conexao import conectar


class RelatorioAvancadoRepository:

    # -----------------------------------------------------------------
    # Produtividade por advogado
    # -----------------------------------------------------------------

    def produtividade_por_advogado(self, escritorio_id, data_inicio=None, data_fim=None):
        conexao = conectar()
        cursor = conexao.cursor()

        cursor.execute(
            "SELECT id, nome FROM usuario WHERE escritorio_id = %s AND ativo = TRUE ORDER BY nome;",
            (str(escritorio_id),)
        )
        equipe = {str(u[0]): {"usuario_id": str(u[0]), "nome": u[1],
                               "processos_ativos": 0, "movimentacoes_periodo": 0,
                               "horas_medias_ate_avisar": None}
                  for u in cursor.fetchall()}

        cursor.execute(
            """
            SELECT advogado_responsavel_id, COUNT(*)
            FROM processo
            WHERE escritorio_id = %s AND status = 'ativo' AND advogado_responsavel_id IS NOT NULL
            GROUP BY advogado_responsavel_id;
            """,
            (str(escritorio_id),)
        )
        for adv_id, total in cursor.fetchall():
            if str(adv_id) in equipe:
                equipe[str(adv_id)]["processos_ativos"] = total

        condicoes_periodo = []
        params_periodo = [str(escritorio_id)]
        if data_inicio:
            condicoes_periodo.append("m.data_movimentacao >= %s")
            params_periodo.append(data_inicio)
        if data_fim:
            condicoes_periodo.append("m.data_movimentacao <= %s")
            params_periodo.append(data_fim)
        filtro_periodo = (" AND " + " AND ".join(condicoes_periodo)) if condicoes_periodo else ""

        cursor.execute(
            f"""
            SELECT p.advogado_responsavel_id, COUNT(m.id)
            FROM movimentacao m
            JOIN processo p ON p.id = m.processo_id
            WHERE p.escritorio_id = %s AND p.advogado_responsavel_id IS NOT NULL {filtro_periodo}
            GROUP BY p.advogado_responsavel_id;
            """,
            tuple(params_periodo)
        )
        for adv_id, total in cursor.fetchall():
            if str(adv_id) in equipe:
                equipe[str(adv_id)]["movimentacoes_periodo"] = total

        cursor.execute(
            """
            SELECT p.advogado_responsavel_id, AVG(EXTRACT(EPOCH FROM (r.enviado_em - m.data_movimentacao)) / 3600.0)
            FROM relatorio r
            JOIN movimentacao m ON m.id = r.movimentacao_id
            JOIN processo p ON p.id = r.processo_id
            WHERE p.escritorio_id = %s AND r.status_envio = 'enviado' AND p.advogado_responsavel_id IS NOT NULL
            GROUP BY p.advogado_responsavel_id;
            """,
            (str(escritorio_id),)
        )
        for adv_id, horas in cursor.fetchall():
            if str(adv_id) in equipe:
                equipe[str(adv_id)]["horas_medias_ate_avisar"] = float(horas) if horas is not None else None

        cursor.close()
        conexao.close()

        return list(equipe.values())

    # -----------------------------------------------------------------
    # Saúde da carteira (distribuição)
    # -----------------------------------------------------------------

    def distribuicao_carteira(self, escritorio_id):
        conexao = conectar()
        cursor = conexao.cursor()

        cursor.execute(
            "SELECT status, COUNT(*) FROM processo WHERE escritorio_id = %s GROUP BY status ORDER BY COUNT(*) DESC;",
            (str(escritorio_id),)
        )
        por_status = [{"chave": s, "total": t} for s, t in cursor.fetchall()]

        cursor.execute(
            "SELECT classe, COUNT(*) FROM processo WHERE escritorio_id = %s GROUP BY classe ORDER BY COUNT(*) DESC LIMIT 15;",
            (str(escritorio_id),)
        )
        por_classe = [{"chave": c, "total": t} for c, t in cursor.fetchall()]

        cursor.execute(
            """
            SELECT comarca, COUNT(*)
            FROM processo
            WHERE escritorio_id = %s AND comarca IS NOT NULL AND comarca <> ''
            GROUP BY comarca ORDER BY COUNT(*) DESC LIMIT 15;
            """,
            (str(escritorio_id),)
        )
        por_comarca = [{"chave": c, "total": t} for c, t in cursor.fetchall()]

        cursor.execute(
            """
            SELECT CASE WHEN t.sigla = 'nd' THEN 'manual' ELSE 'sincronizado' END, COUNT(*)
            FROM processo p
            JOIN tribunal t ON t.id = p.tribunal_id
            WHERE p.escritorio_id = %s
            GROUP BY 1;
            """,
            (str(escritorio_id),)
        )
        sincronizacao = [{"chave": k, "total": t} for k, t in cursor.fetchall()]

        cursor.close()
        conexao.close()

        return {
            "por_status": por_status, "por_classe": por_classe,
            "por_comarca": por_comarca, "sincronizacao": sincronizacao,
        }

    # -----------------------------------------------------------------
    # Histórico por cliente
    # -----------------------------------------------------------------

    def historico_cliente(self, cliente_id):
        conexao = conectar()
        cursor = conexao.cursor()

        cursor.execute(
            """
            SELECT p.id, p.numero_cnj, p.classe, p.status
            FROM processo p
            JOIN cliente_processo cp ON cp.processo_id = p.id
            WHERE cp.cliente_id = %s
            ORDER BY p.numero_cnj;
            """,
            (str(cliente_id),)
        )
        processos = [{"id": str(p[0]), "numero_cnj": p[1], "classe": p[2], "status": p[3]} for p in cursor.fetchall()]

        cursor.execute(
            """
            SELECT p.numero_cnj, m.descricao_resumida, m.descricao_original, m.importancia, m.data_movimentacao
            FROM movimentacao m
            JOIN processo p ON p.id = m.processo_id
            JOIN cliente_processo cp ON cp.processo_id = p.id
            WHERE cp.cliente_id = %s
            ORDER BY m.data_movimentacao DESC;
            """,
            (str(cliente_id),)
        )
        movimentacoes = [
            {
                "processo_numero": m[0], "descricao": m[1] or m[2],
                "importancia": m[3], "data": m[4].isoformat() if m[4] else None,
            }
            for m in cursor.fetchall()
        ]

        cursor.close()
        conexao.close()

        return {"processos": processos, "movimentacoes": movimentacoes}

    # -----------------------------------------------------------------
    # Cumprimento de prazos (agenda)
    # -----------------------------------------------------------------

    def cumprimento_prazos(self, escritorio_id, advogado_id=None):
        conexao = conectar()
        cursor = conexao.cursor()

        condicoes = ["p.escritorio_id = %s"]
        parametros = [str(escritorio_id)]
        if advogado_id:
            condicoes.append("p.advogado_responsavel_id = %s")
            parametros.append(str(advogado_id))
        filtro = " AND ".join(condicoes)

        cursor.execute(
            f"""
            SELECT
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE c.concluido) AS concluidos,
                COUNT(*) FILTER (WHERE NOT c.concluido AND c.data_hora < CURRENT_TIMESTAMP) AS atrasados
            FROM compromisso c
            JOIN processo p ON p.id = c.processo_id
            WHERE {filtro};
            """,
            tuple(parametros)
        )
        total, concluidos, atrasados = cursor.fetchone()

        cursor.execute(
            f"""
            SELECT c.tipo,
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE c.concluido) AS concluidos
            FROM compromisso c
            JOIN processo p ON p.id = c.processo_id
            WHERE {filtro}
            GROUP BY c.tipo
            ORDER BY total DESC;
            """,
            tuple(parametros)
        )
        por_tipo = [{"tipo": t, "total": tot, "concluidos": conc} for t, tot, conc in cursor.fetchall()]

        por_advogado = []
        if advogado_id is None:
            cursor.execute(
                """
                SELECT u.nome,
                    COUNT(*) AS total,
                    COUNT(*) FILTER (WHERE NOT c.concluido AND c.data_hora < CURRENT_TIMESTAMP) AS atrasados
                FROM compromisso c
                JOIN processo p ON p.id = c.processo_id
                LEFT JOIN usuario u ON u.id = p.advogado_responsavel_id
                WHERE p.escritorio_id = %s
                GROUP BY u.nome
                ORDER BY atrasados DESC;
                """,
                (str(escritorio_id),)
            )
            por_advogado = [
                {"advogado_nome": n or "Não atribuído", "total": tot, "atrasados": atr}
                for n, tot, atr in cursor.fetchall()
            ]

        cursor.close()
        conexao.close()

        return {
            "total": total, "concluidos": concluidos, "atrasados": atrasados,
            "por_tipo": por_tipo, "por_advogado": por_advogado,
        }

    # -----------------------------------------------------------------
    # Qualidade de dados / governança
    # -----------------------------------------------------------------

    def qualidade_dados(self, escritorio_id):
        conexao = conectar()
        cursor = conexao.cursor()

        cursor.execute(
            """
            SELECT p.numero_cnj
            FROM processo p
            JOIN tribunal t ON t.id = p.tribunal_id
            WHERE p.escritorio_id = %s AND t.sigla = 'nd'
            ORDER BY p.numero_cnj;
            """,
            (str(escritorio_id),)
        )
        sem_tribunal = [r[0] for r in cursor.fetchall()]

        cursor.execute(
            """
            SELECT numero_cnj FROM processo
            WHERE escritorio_id = %s AND advogado_responsavel_id IS NULL
            ORDER BY numero_cnj;
            """,
            (str(escritorio_id),)
        )
        sem_advogado = [r[0] for r in cursor.fetchall()]

        cursor.execute(
            """
            SELECT p.numero_cnj
            FROM processo p
            LEFT JOIN movimentacao m ON m.processo_id = p.id
            WHERE p.escritorio_id = %s
            GROUP BY p.id, p.numero_cnj
            HAVING COUNT(m.id) = 0
            ORDER BY p.numero_cnj;
            """,
            (str(escritorio_id),)
        )
        sem_movimentacao = [r[0] for r in cursor.fetchall()]

        cursor.close()
        conexao.close()

        return {
            "sem_tribunal": sem_tribunal, "sem_advogado": sem_advogado,
            "sem_movimentacao": sem_movimentacao,
        }
