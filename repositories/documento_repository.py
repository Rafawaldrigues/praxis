from uuid import uuid4
from datetime import datetime
from database.conexao import conectar


class DocumentoRepository:

    def cadastrar(self, documento):

        conexao = conectar()
        cursor = conexao.cursor()

        if documento.id is None:
            documento.id = uuid4()

        if documento.criado_em is None:
            documento.criado_em = datetime.now()

        sql = """
            INSERT INTO documento_processo (
                id, processo_id, usuario_id, nome_arquivo, tipo,
                conteudo, tamanho_bytes, criado_em
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id;
        """

        cursor.execute(sql, (
            str(documento.id),
            str(documento.processo_id),
            str(documento.usuario_id) if documento.usuario_id else None,
            documento.nome_arquivo,
            documento.tipo,
            documento.conteudo,
            documento.tamanho_bytes,
            documento.criado_em
        ))

        id = cursor.fetchone()[0]

        conexao.commit()

        cursor.close()
        conexao.close()

        return id

    def listar_por_processo(self, processo_id):
        """
        Lista sem o conteudo binario (pra nao pesar a tela) - so os metadados.
        Use obter_conteudo() pra baixar um documento especifico.
        """

        conexao = conectar()
        cursor = conexao.cursor()

        sql = """
            SELECT id, processo_id, usuario_id, nome_arquivo, tipo, tamanho_bytes, criado_em
            FROM documento_processo
            WHERE processo_id = %s
            ORDER BY criado_em DESC;
        """

        cursor.execute(sql, (str(processo_id),))
        documentos = cursor.fetchall()

        cursor.close()
        conexao.close()

        return documentos

    def obter_conteudo(self, documento_id):

        conexao = conectar()
        cursor = conexao.cursor()

        cursor.execute(
            "SELECT nome_arquivo, conteudo FROM documento_processo WHERE id = %s;",
            (str(documento_id),)
        )
        resultado = cursor.fetchone()

        cursor.close()
        conexao.close()

        return resultado  # (nome_arquivo, conteudo) ou None
