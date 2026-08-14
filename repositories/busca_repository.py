from database.conexao import conectar


class BuscaRepository:

    def buscar_geral(self, escritorio_id, termo):
        """
        Busca combinada: clientes (nome/CPF-CNPJ) e processos (numero,
        classe, assunto, ou nome/CPF-CNPJ de cliente vinculado).
        Retorna um dict com as duas listas separadas.
        """

        conexao = conectar()
        cursor = conexao.cursor()

        termo_busca = f"%{termo}%"

        cursor.execute(
            """
            SELECT id, nome, cpf_cnpj, telefone, whatsapp
            FROM cliente
            WHERE escritorio_id = %s
              AND (nome ILIKE %s OR cpf_cnpj ILIKE %s)
            ORDER BY nome
            LIMIT 20;
            """,
            (str(escritorio_id), termo_busca, termo_busca)
        )
        clientes = cursor.fetchall()

        cursor.execute(
            """
            SELECT DISTINCT p.id, p.numero_cnj, p.classe, p.assunto, p.status
            FROM processo p
            LEFT JOIN cliente_processo cp ON cp.processo_id = p.id
            LEFT JOIN cliente c ON c.id = cp.cliente_id
            WHERE p.escritorio_id = %s
              AND (
                    p.numero_cnj ILIKE %s
                 OR p.classe ILIKE %s
                 OR p.assunto ILIKE %s
                 OR c.nome ILIKE %s
                 OR c.cpf_cnpj ILIKE %s
              )
            ORDER BY p.numero_cnj
            LIMIT 20;
            """,
            (str(escritorio_id), termo_busca, termo_busca, termo_busca, termo_busca, termo_busca)
        )
        processos = cursor.fetchall()

        cursor.close()
        conexao.close()

        return {"clientes": clientes, "processos": processos}
