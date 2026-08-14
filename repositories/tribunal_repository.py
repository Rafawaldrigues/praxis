from uuid import uuid4
from database.conexao import conectar


class TribunalRepository:

    def obter_ou_criar(self, sigla, nome=None):
        """
        sigla: alias oficial do DataJud, em minusculo (ex: 'tjsp', 'trf1', 'tre-sp').
        Ver lista completa em https://datajud-wiki.cnj.jus.br/api-publica/endpoints
        """

        sigla = sigla.lower().strip()

        conexao = conectar()
        cursor = conexao.cursor()

        cursor.execute("SELECT id FROM tribunal WHERE sigla = %s;", (sigla,))
        row = cursor.fetchone()

        if row:
            cursor.close()
            conexao.close()
            return row[0]

        tribunal_id = uuid4()
        url_api = f"https://api-publica.datajud.cnj.jus.br/api_publica_{sigla}/_search"

        cursor.execute(
            """
            INSERT INTO tribunal (id, nome, sigla, url_api, ativo)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id;
            """,
            (str(tribunal_id), nome or sigla.upper(), sigla, url_api, True)
        )
        id = cursor.fetchone()[0]

        conexao.commit()

        cursor.close()
        conexao.close()

        return id

    def listar_todos(self):

        conexao = conectar()
        cursor = conexao.cursor()

        cursor.execute("SELECT * FROM tribunal ORDER BY sigla;")
        tribunais = cursor.fetchall()

        cursor.close()
        conexao.close()

        return tribunais
