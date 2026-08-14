from uuid import uuid4
from datetime import datetime
from database.conexao import conectar
from repositories.tribunal_repository import TribunalRepository


# Ordem explicita - valor_causa foi adicionado via ALTER TABLE e fica
# fisicamente no final da tabela, nao antes de criado_em como "faria sentido".
COLUNAS_PROCESSO = """
    id, escritorio_id, tribunal_id, numero_cnj, classe, assunto, vara,
    comarca, status, advogado_responsavel_id, criado_em, atualizado_em, valor_causa
"""


class ProcessoRepository:

    def __init__(self):
        self.tribunal_repo = TribunalRepository()

    def _obter_ou_criar_tribunal_padrao(self):
        """
        Fallback para quando nenhuma sigla de tribunal foi informada
        no cadastro do processo (a sincronizacao automatica nao vai
        funcionar pra esse processo ate a sigla ser preenchida).
        """
        return self.tribunal_repo.obter_ou_criar("nd", nome="Nao informado")

    def cadastrar(self, processo, clientes_ids=None, papel="cliente", sigla_tribunal=None):
        """
        Cadastra o processo e vincula aos clientes informados
        (clientes_ids: lista de UUIDs/str) na tabela cliente_processo.
        sigla_tribunal: alias do DataJud (ex: 'tjsp', 'trf1') - se informado,
        habilita esse processo para a sincronizacao automatica.
        """

        conexao = conectar()
        cursor = conexao.cursor()

        if processo.id is None:
            processo.id = uuid4()

        if sigla_tribunal:
            processo.tribunal_id = self.tribunal_repo.obter_ou_criar(sigla_tribunal)
        elif processo.tribunal_id is None:
            processo.tribunal_id = self._obter_ou_criar_tribunal_padrao()

        if processo.criado_em is None:
            processo.criado_em = datetime.now()

        sql = """
            INSERT INTO processo (
                id,
                escritorio_id,
                tribunal_id,
                numero_cnj,
                classe,
                assunto,
                vara,
                comarca,
                status,
                advogado_responsavel_id,
                valor_causa,
                criado_em
            )
            VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            RETURNING id;
        """

        cursor.execute(sql, (
            str(processo.id),
            str(processo.escritorio_id) if processo.escritorio_id else None,
            str(processo.tribunal_id),
            processo.numero_cnj,
            processo.classe,
            processo.assunto,
            processo.vara,
            processo.comarca,
            processo.status,
            str(processo.advogado_responsavel_id) if processo.advogado_responsavel_id else None,
            processo.valor_causa,
            processo.criado_em
        ))

        id = cursor.fetchone()[0]

        for cliente_id in (clientes_ids or []):
            cursor.execute(
                """
                INSERT INTO cliente_processo (id, cliente_id, processo_id, papel)
                VALUES (%s, %s, %s, %s);
                """,
                (str(uuid4()), str(cliente_id), str(id), papel)
            )

        conexao.commit()

        cursor.close()
        conexao.close()

        return id

    def atualizar(self, processo_id, classe, assunto, vara, comarca, status, valor_causa):

        conexao = conectar()
        cursor = conexao.cursor()

        cursor.execute(
            """
            UPDATE processo
            SET classe = %s, assunto = %s, vara = %s, comarca = %s,
                status = %s, valor_causa = %s, atualizado_em = %s
            WHERE id = %s;
            """,
            (classe, assunto, vara, comarca, status, valor_causa, datetime.now(), str(processo_id))
        )

        conexao.commit()

        cursor.close()
        conexao.close()

    def obter_por_id(self, processo_id):

        conexao = conectar()
        cursor = conexao.cursor()

        cursor.execute(f"SELECT {COLUNAS_PROCESSO} FROM processo WHERE id = %s;", (str(processo_id),))
        processo = cursor.fetchone()

        cursor.close()
        conexao.close()

        return processo

    def listar_com_responsavel(self, escritorio_id):
        """
        Todos os processos do escritorio, com o nome do advogado
        responsavel (ou NULL se ninguem foi designado ainda).
        Usado no painel do lider.
        """

        conexao = conectar()
        cursor = conexao.cursor()

        sql = """
            SELECT
                p.id, p.numero_cnj, p.classe, p.assunto, p.status,
                u.id AS advogado_id, u.nome AS advogado_nome
            FROM processo p
            LEFT JOIN usuario u ON u.id = p.advogado_responsavel_id
            WHERE p.escritorio_id = %s
            ORDER BY p.numero_cnj;
        """

        cursor.execute(sql, (str(escritorio_id),))
        processos = cursor.fetchall()

        cursor.close()
        conexao.close()

        return processos

    def listar_por_advogado(self, usuario_id):
        """
        Processos designados a um advogado especifico
        (o "meu sistema unico" de cada advogado).
        """

        conexao = conectar()
        cursor = conexao.cursor()

        sql = f"""
            SELECT {COLUNAS_PROCESSO}
            FROM processo
            WHERE advogado_responsavel_id = %s
            ORDER BY numero_cnj;
        """

        cursor.execute(sql, (str(usuario_id),))
        processos = cursor.fetchall()

        cursor.close()
        conexao.close()

        return processos

    def listar_nao_atribuidos(self, escritorio_id):
        """
        Processos do escritorio que ainda nao tem advogado responsavel -
        um advogado pode "pegar pra si" a partir dessa lista.
        """

        conexao = conectar()
        cursor = conexao.cursor()

        sql = f"""
            SELECT {COLUNAS_PROCESSO}
            FROM processo
            WHERE escritorio_id = %s
              AND advogado_responsavel_id IS NULL
            ORDER BY numero_cnj;
        """

        cursor.execute(sql, (str(escritorio_id),))
        processos = cursor.fetchall()

        cursor.close()
        conexao.close()

        return processos

    def designar_advogado(self, processo_id, usuario_id):
        """
        usuario_id = None para desatribuir (deixar o processo livre de novo).
        """

        conexao = conectar()
        cursor = conexao.cursor()

        cursor.execute(
            """
            UPDATE processo
            SET advogado_responsavel_id = %s, atualizado_em = %s
            WHERE id = %s;
            """,
            (str(usuario_id) if usuario_id else None, datetime.now(), str(processo_id))
        )

        conexao.commit()

        cursor.close()
        conexao.close()

    def buscar(self, escritorio_id, termo):
        """
        Busca por numero do processo, classe/assunto, ou pelo nome/CPF-CNPJ
        de algum cliente vinculado.
        """

        conexao = conectar()
        cursor = conexao.cursor()

        sql = """
            SELECT DISTINCT p.*
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
            ORDER BY p.numero_cnj;
        """

        termo_busca = f"%{termo}%"
        cursor.execute(sql, (
            str(escritorio_id),
            termo_busca, termo_busca, termo_busca, termo_busca, termo_busca
        ))

        processos = cursor.fetchall()

        cursor.close()
        conexao.close()

        return processos

    def listar_por_cliente(self, cliente_id):

        conexao = conectar()
        cursor = conexao.cursor()

        sql = """
            SELECT p.id, p.numero_cnj, p.classe, p.status
            FROM processo p
            JOIN cliente_processo cp ON cp.processo_id = p.id
            WHERE cp.cliente_id = %s
            ORDER BY p.numero_cnj;
        """

        cursor.execute(sql, (str(cliente_id),))
        processos = cursor.fetchall()

        cursor.close()
        conexao.close()

        return processos

    def listar_clientes_do_processo(self, processo_id):

        conexao = conectar()
        cursor = conexao.cursor()

        sql = """
            SELECT c.id, c.nome, c.cpf_cnpj, cp.papel
            FROM cliente c
            JOIN cliente_processo cp ON cp.cliente_id = c.id
            WHERE cp.processo_id = %s;
        """

        cursor.execute(sql, (str(processo_id),))
        clientes = cursor.fetchall()

        cursor.close()
        conexao.close()

        return clientes

    def listar_todos(self):

        conexao = conectar()
        cursor = conexao.cursor()

        sql = f"""
            SELECT {COLUNAS_PROCESSO}
            FROM processo
            ORDER BY criado_em DESC;
        """

        cursor.execute(sql)

        processos = cursor.fetchall()

        cursor.close()
        conexao.close()

        return processos

    def listar_ativos_com_tribunal(self):
        """
        Processos ativos que tem uma sigla de tribunal real cadastrada
        (ou seja, elegiveis para a sincronizacao automatica via DataJud).
        """

        conexao = conectar()
        cursor = conexao.cursor()

        sql = """
            SELECT p.id, p.numero_cnj, t.sigla
            FROM processo p
            JOIN tribunal t ON t.id = p.tribunal_id
            WHERE p.status = 'ativo'
              AND t.sigla <> 'nd';
        """

        cursor.execute(sql)
        processos = cursor.fetchall()

        cursor.close()
        conexao.close()

        return processos

    def listar_clientes_com_processos(self, escritorio_id=None, advogado_id=None):
        """
        Retorna uma linha por (cliente, processo) ja unidos via
        cliente_processo, pronta pra alimentar a tela de visao geral.
        """

        conexao = conectar()
        cursor = conexao.cursor()

        condicoes = []
        parametros = []

        if escritorio_id:
            condicoes.append("c.escritorio_id = %s")
            parametros.append(str(escritorio_id))

        if advogado_id:
            condicoes.append("p.advogado_responsavel_id = %s")
            parametros.append(str(advogado_id))

        filtro = ("WHERE " + " AND ".join(condicoes)) if condicoes else ""

        sql = f"""
            SELECT
                c.id            AS cliente_id,
                c.nome          AS cliente_nome,
                c.cpf_cnpj      AS cliente_cpf_cnpj,
                p.id            AS processo_id,
                p.numero_cnj,
                p.classe,
                p.assunto,
                p.vara,
                p.comarca,
                p.status
            FROM cliente c
            JOIN cliente_processo cp ON cp.cliente_id = c.id
            JOIN processo p ON p.id = cp.processo_id
            {filtro}
            ORDER BY c.nome, p.numero_cnj;
        """

        cursor.execute(sql, tuple(parametros))
        linhas = cursor.fetchall()

        cursor.close()
        conexao.close()

        return linhas
