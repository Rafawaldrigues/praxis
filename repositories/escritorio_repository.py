from uuid import uuid4
from psycopg.types.json import Json
from database.conexao import conectar


class EscritorioRepository:

    def cadastrar(self, escritorio):

        conexao = conectar()
        cursor = conexao.cursor()

        # a tabela escritorio nao tem DEFAULT no id, entao geramos aqui
        if getattr(escritorio, "id", None) is None:
            escritorio.id = uuid4()

        sql = """
            INSERT INTO escritorio (
                id,
                nome,
                telefone,
                email,
                cnpj,
                configuracoes
            )
            VALUES (
                %s,
                %s,
                %s,
                %s,
                %s,
                %s
            )
            RETURNING id;
        """

        cursor.execute(sql, (
            str(escritorio.id),
            escritorio.nome,
            escritorio.telefone,
            escritorio.email,
            escritorio.cnpj,
            Json(escritorio.configuracoes)
        ))

        id = cursor.fetchone()[0]

        conexao.commit()

        cursor.close()
        conexao.close()

        return id


    
        # READ
    def listar_todos(self):

        conexao = conectar()
        cursor = conexao.cursor()

        sql = """
            SELECT *
            FROM escritorio;
        """

        cursor.execute(sql)

        escritorios = cursor.fetchall()

        cursor.close()
        conexao.close()

        return escritorios

    def Buscar_por_id(self, id):

        conexao = conectar()
        cursor = conexao.cursor()

        sql = """ 
        SELECT *
        FROM escritorio
        WHERE  ID  =  %s"""

        cursor.execute(sql,id)

        id = cursor.fetchone()[0]
        
        conexao.commit()
        
        cursor.close()
        conexao.close()
        
        return id
