from uuid import uuid4
from database.conexao import conectar


class LogRepository:

    def registrar(self, usuario_id, acao, entidade, entidade_id, dados_novos=None):
        """
        acao: ex: 'criar', 'atualizar', 'atribuir', 'anexar_documento', 'comentar'
        entidade: ex: 'cliente', 'processo', 'documento', 'comentario'
        """

        conexao = conectar()
        cursor = conexao.cursor()

        cursor.execute(
            """
            INSERT INTO log (id, usuario_id, acao, entidade, entidade_id, dados_novos)
            VALUES (%s, %s, %s, %s, %s, %s);
            """,
            (
                str(uuid4()),
                str(usuario_id) if usuario_id else None,
                acao,
                entidade,
                str(entidade_id) if entidade_id else None,
                None
            )
        )

        conexao.commit()

        cursor.close()
        conexao.close()

    def listar_por_escritorio(self, escritorio_id, limite=100):
        """
        Log de atividade recente da equipe (util pro lider acompanhar).
        """

        conexao = conectar()
        cursor = conexao.cursor()

        sql = """
            SELECT l.acao, l.entidade, l.entidade_id, l.criado_em, u.nome AS usuario_nome
            FROM log l
            LEFT JOIN usuario u ON u.id = l.usuario_id
            WHERE u.escritorio_id = %s
            ORDER BY l.criado_em DESC
            LIMIT %s;
        """

        cursor.execute(sql, (str(escritorio_id), limite))
        logs = cursor.fetchall()

        cursor.close()
        conexao.close()

        return logs
