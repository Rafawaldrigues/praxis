from uuid import uuid4
from datetime import datetime
from psycopg.types.json import Json
from database.conexao import conectar


# Lista explicita e na ORDEM que o resto do codigo espera. Importante usar
# isso em vez de "SELECT *": colunas adicionadas via ALTER TABLE (whatsapp,
# idade, ativo) ficam fisicamente no FINAL da tabela, nao onde "fariam
# sentido" - SELECT * te dá a ordem fisica, nao a logica.
COLUNAS_CLIENTE = """
    id, escritorio_id, nome, cpf_cnpj, email, telefone,
    whatsapp, idade, tipo_pessoa, preferencias_notificacao, criado_em, ativo
"""


class ClienteRepository:

    def cadastrar(self, cliente):

        conexao = conectar()
        cursor = conexao.cursor()

        if cliente.id is None:
            cliente.id = uuid4()

        if cliente.criado_em is None:
            cliente.criado_em = datetime.now()

        sql = """
            INSERT INTO cliente (
                id,
                escritorio_id,
                nome,
                cpf_cnpj,
                email,
                telefone,
                whatsapp,
                idade,
                tipo_pessoa,
                preferencias_notificacao,
                criado_em
            )
            VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            RETURNING id;
        """

        cursor.execute(sql, (
            str(cliente.id),
            str(cliente.escritorio_id) if cliente.escritorio_id else None,
            cliente.nome,
            cliente.cpf_cnpj,
            cliente.email,
            cliente.telefone,
            cliente.whatsapp,
            cliente.idade,
            cliente.tipo_pessoa,
            Json(cliente.preferencias_notificacao or {}),
            cliente.criado_em
        ))

        id = cursor.fetchone()[0]

        conexao.commit()

        cursor.close()
        conexao.close()

        return id

    def listar_todos(self):

        conexao = conectar()
        cursor = conexao.cursor()

        cursor.execute(f"SELECT {COLUNAS_CLIENTE} FROM cliente ORDER BY nome;")

        clientes = cursor.fetchall()

        cursor.close()
        conexao.close()

        return clientes

    def listar_por_escritorio(self, escritorio_id, incluir_inativos=False):

        conexao = conectar()
        cursor = conexao.cursor()

        sql = f"""
            SELECT {COLUNAS_CLIENTE}
            FROM cliente
            WHERE escritorio_id = %s
        """ + ("" if incluir_inativos else " AND ativo = TRUE ") + """
            ORDER BY nome;
        """

        cursor.execute(sql, (str(escritorio_id),))

        clientes = cursor.fetchall()

        cursor.close()
        conexao.close()

        return clientes

    def obter_por_id(self, cliente_id):

        conexao = conectar()
        cursor = conexao.cursor()

        cursor.execute(f"SELECT {COLUNAS_CLIENTE} FROM cliente WHERE id = %s;", (str(cliente_id),))
        cliente = cursor.fetchone()

        cursor.close()
        conexao.close()

        return cliente

    def atualizar(self, cliente_id, nome, cpf_cnpj, idade, email, telefone, whatsapp, tipo_pessoa):

        conexao = conectar()
        cursor = conexao.cursor()

        cursor.execute(
            """
            UPDATE cliente
            SET nome = %s, cpf_cnpj = %s, idade = %s, email = %s,
                telefone = %s, whatsapp = %s, tipo_pessoa = %s
            WHERE id = %s;
            """,
            (nome, cpf_cnpj, idade, email, telefone, whatsapp, tipo_pessoa, str(cliente_id))
        )

        conexao.commit()

        cursor.close()
        conexao.close()

    def definir_ativo(self, cliente_id, ativo):

        conexao = conectar()
        cursor = conexao.cursor()

        cursor.execute(
            "UPDATE cliente SET ativo = %s WHERE id = %s;",
            (ativo, str(cliente_id))
        )

        conexao.commit()

        cursor.close()
        conexao.close()

    def buscar(self, escritorio_id, termo):
        """
        Busca por nome ou CPF/CNPJ (contendo o termo, case-insensitive).
        """

        conexao = conectar()
        cursor = conexao.cursor()

        sql = f"""
            SELECT {COLUNAS_CLIENTE}
            FROM cliente
            WHERE escritorio_id = %s
              AND ativo = TRUE
              AND (nome ILIKE %s OR cpf_cnpj ILIKE %s)
            ORDER BY nome;
        """

        termo_busca = f"%{termo}%"
        cursor.execute(sql, (str(escritorio_id), termo_busca, termo_busca))

        clientes = cursor.fetchall()

        cursor.close()
        conexao.close()

        return clientes
