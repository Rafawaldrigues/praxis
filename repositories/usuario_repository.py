from uuid import uuid4
from datetime import datetime
import bcrypt
from database.conexao import conectar


class UsuarioRepository:

    def cadastrar(self, usuario, senha_plana):
        """
        Recebe a senha em texto puro (senha_plana) separadamente do model
        pra deixar claro que ela nunca é guardada como veio - só o hash.
        """

        conexao = conectar()
        cursor = conexao.cursor()

        if usuario.id is None:
            usuario.id = uuid4()

        if usuario.criado_em is None:
            usuario.criado_em = datetime.now()

        senha_hash = bcrypt.hashpw(senha_plana.encode("utf-8"), bcrypt.gensalt())

        sql = """
            INSERT INTO usuario (
                id,
                escritorio_id,
                nome,
                email,
                senha_hash,
                perfil,
                ativo,
                criado_em
            )
            VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s
            )
            RETURNING id;
        """

        cursor.execute(sql, (
            str(usuario.id),
            str(usuario.escritorio_id) if usuario.escritorio_id else None,
            usuario.nome,
            usuario.email.lower().strip(),
            senha_hash.decode("utf-8"),
            usuario.perfil,
            usuario.ativo,
            usuario.criado_em
        ))

        id = cursor.fetchone()[0]

        conexao.commit()

        cursor.close()
        conexao.close()

        return id

    def listar_por_escritorio(self, escritorio_id):

        conexao = conectar()
        cursor = conexao.cursor()

        sql = """
            SELECT id, escritorio_id, nome, email, perfil, ativo, criado_em
            FROM usuario
            WHERE escritorio_id = %s
            ORDER BY nome;
        """

        cursor.execute(sql, (str(escritorio_id),))

        usuarios = cursor.fetchall()

        cursor.close()
        conexao.close()

        return usuarios

    def buscar_por_email(self, email):

        conexao = conectar()
        cursor = conexao.cursor()

        sql = """
            SELECT id, escritorio_id, nome, email, senha_hash, perfil, ativo, criado_em
            FROM usuario
            WHERE email = %s;
        """

        cursor.execute(sql, (email.lower().strip(),))

        usuario = cursor.fetchone()

        cursor.close()
        conexao.close()

        return usuario

    def autenticar(self, email, senha_plana):
        """
        Retorna a linha do usuario se email/senha baterem e o usuario
        estiver ativo, ou None caso contrário.
        """

        usuario = self.buscar_por_email(email)

        if usuario is None:
            return None

        _, _, _, _, senha_hash, _, ativo, _ = usuario

        if not ativo:
            return None

        senha_confere = bcrypt.checkpw(
            senha_plana.encode("utf-8"),
            senha_hash.encode("utf-8")
        )

        if not senha_confere:
            return None

        return usuario

    def email_ja_existe(self, email):
        return self.buscar_por_email(email) is not None
