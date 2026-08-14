from uuid import uuid4
from datetime import datetime
from database.conexao import conectar


class ComentarioRepository:

    def cadastrar(self, comentario):

        conexao = conectar()
        cursor = conexao.cursor()

        if comentario.id is None:
            comentario.id = uuid4()

        if comentario.criado_em is None:
            comentario.criado_em = datetime.now()

        sql = """
            INSERT INTO comentario_processo (id, processo_id, usuario_id, texto, criado_em)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id;
        """

        cursor.execute(sql, (
            str(comentario.id),
            str(comentario.processo_id),
            str(comentario.usuario_id) if comentario.usuario_id else None,
            comentario.texto,
            comentario.criado_em
        ))

        id = cursor.fetchone()[0]

        conexao.commit()

        cursor.close()
        conexao.close()

        return id

    def listar_por_processo(self, processo_id):

        conexao = conectar()
        cursor = conexao.cursor()

        sql = """
            SELECT cp.id, cp.texto, cp.criado_em, u.nome AS autor
            FROM comentario_processo cp
            LEFT JOIN usuario u ON u.id = cp.usuario_id
            WHERE cp.processo_id = %s
            ORDER BY cp.criado_em DESC;
        """

        cursor.execute(sql, (str(processo_id),))
        comentarios = cursor.fetchall()

        cursor.close()
        conexao.close()

        return comentarios
