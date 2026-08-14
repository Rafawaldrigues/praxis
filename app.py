from datetime import datetime, date, timedelta

import streamlit as st

from models.escritorio import Escritorio
from models.cliente import Cliente
from models.processo import Processo
from models.movimentacao import Movimentacao
from models.relatorio import Relatorio
from models.usuario import Usuario
from models.documento import Documento
from models.comentario import Comentario
from models.compromisso import Compromisso
from models.financeiro import Financeiro

from repositories.escritorio_repository import EscritorioRepository
from repositories.cliente_repository import ClienteRepository
from repositories.processo_repository import ProcessoRepository
from repositories.movimentacao_repository import MovimentacaoRepository
from repositories.relatorio_repository import RelatorioRepository
from repositories.usuario_repository import UsuarioRepository
from repositories.documento_repository import DocumentoRepository
from repositories.comentario_repository import ComentarioRepository
from repositories.busca_repository import BuscaRepository
from repositories.relatorio_gerencial_repository import RelatorioGerencialRepository
from repositories.log_repository import LogRepository
from repositories.compromisso_repository import CompromissoRepository
from repositories.financeiro_repository import FinanceiroRepository

from servicos.cnj_parser import detectar_sigla_tribunal


st.set_page_config(page_title="PRAXIS", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,600&family=IBM+Plex+Mono:wght@500&display=swap');

h1, h2, h3 { font-family: 'Fraunces', serif !important; }
[data-testid="stMetricValue"] { font-family: 'IBM Plex Mono', monospace; color: #c9a24b; }
[data-testid="stMetricLabel"] { color: #8a93a6; }
.stTabs [data-baseweb="tab"] { font-weight: 500; }
div[data-testid="stForm"] {
    border: 1px solid rgba(201,162,75,0.25);
    border-radius: 4px;
    padding: 20px;
}
.stButton > button[kind="primary"], .stFormSubmitButton > button {
    background-color: #c9a24b;
    color: #0b1220;
    border: none;
    font-weight: 600;
}
.stButton > button[kind="primary"]:hover, .stFormSubmitButton > button:hover {
    background-color: #e8d9ae;
}
</style>
""", unsafe_allow_html=True)

col_logo, col_titulo = st.columns([1, 8])
with col_logo:
    st.markdown(
        "<div style='width:44px;height:44px;border-radius:50%;border:1.5px solid #c9a24b;"
        "display:flex;align-items:center;justify-content:center;font-family:Fraunces,serif;"
        "color:#c9a24b;font-size:20px;margin-top:6px;'>&sect;</div>",
        unsafe_allow_html=True
    )

escritorio_repo = EscritorioRepository()
cliente_repo = ClienteRepository()
processo_repo = ProcessoRepository()
movimentacao_repo = MovimentacaoRepository()
relatorio_repo = RelatorioRepository()
usuario_repo = UsuarioRepository()
documento_repo = DocumentoRepository()
comentario_repo = ComentarioRepository()
busca_repo = BuscaRepository()
relatorio_gerencial_repo = RelatorioGerencialRepository()
log_repo = LogRepository()
compromisso_repo = CompromissoRepository()
financeiro_repo = FinanceiroRepository()

TEMPLATE_MENSAGEM = (
    "Ola {cliente_nome}, tudo bem?\n\n"
    "Seu processo no {numero_cnj} teve uma nova movimentacao:\n\n"
    "{resumo}\n\n"
    "Qualquer duvida, estamos a disposicao."
)


# ---------------------------------------------------------------------------
# Autenticação
# ---------------------------------------------------------------------------

def usuario_logado():
    return st.session_state.get("usuario_id") is not None


def eh_lider():
    return st.session_state.get("perfil") == "lider"


def fazer_logout():
    for chave in ["usuario_id", "escritorio_id", "usuario_nome", "escritorio_nome", "perfil"]:
        st.session_state.pop(chave, None)
    st.rerun()


def tela_login():
    st.title("PRAXIS")

    aba_entrar, aba_criar = st.tabs(["Entrar", "Criar escritorio"])

    with aba_entrar:
        with st.form("form_login"):
            email = st.text_input("E-mail")
            senha = st.text_input("Senha", type="password")
            enviado = st.form_submit_button("Entrar")

            if enviado:
                usuario = usuario_repo.autenticar(email, senha)

                if usuario is None:
                    st.error("E-mail ou senha invalidos.")
                else:
                    (usuario_id, escritorio_id, nome, _email, _hash, perfil, _ativo, _criado) = usuario
                    escritorios = escritorio_repo.listar_todos()
                    nome_escritorio = next((e[1] for e in escritorios if str(e[0]) == str(escritorio_id)), "")

                    st.session_state["usuario_id"] = usuario_id
                    st.session_state["escritorio_id"] = escritorio_id
                    st.session_state["usuario_nome"] = nome
                    st.session_state["escritorio_nome"] = nome_escritorio
                    st.session_state["perfil"] = perfil
                    st.rerun()

    with aba_criar:
        st.caption("Cria um novo escritorio e o primeiro usuario (lider) dele.")

        with st.form("form_criar_escritorio"):
            nome_escritorio = st.text_input("Nome do escritorio")
            nome_usuario = st.text_input("Seu nome")
            email_usuario = st.text_input("Seu e-mail")
            senha_usuario = st.text_input("Senha", type="password")
            senha_confirmacao = st.text_input("Confirmar senha", type="password")

            enviado = st.form_submit_button("Criar escritorio")

            if enviado:
                if not nome_escritorio or not nome_usuario or not email_usuario or not senha_usuario:
                    st.error("Preencha todos os campos.")
                elif senha_usuario != senha_confirmacao:
                    st.error("As senhas nao conferem.")
                elif usuario_repo.email_ja_existe(email_usuario):
                    st.error("Ja existe um usuario com esse e-mail.")
                else:
                    escritorio = Escritorio(
                        nome=nome_escritorio, telefone="", email=email_usuario, cnpj="", configuracoes={}
                    )
                    escritorio_id = escritorio_repo.cadastrar(escritorio)

                    usuario = Usuario(
                        escritorio_id=escritorio_id, nome=nome_usuario, email=email_usuario,
                        perfil="lider", ativo=True
                    )
                    usuario_repo.cadastrar(usuario, senha_usuario)

                    st.success("Escritorio criado! Va para a aba 'Entrar'.")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def formatar_moeda(valor):
    if valor is None:
        return "-"
    return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def processos_visiveis(escritorio_id, usuario_id, lider):
    if lider:
        processos = processo_repo.listar_com_responsavel(escritorio_id)
        return [(p[0], p[1], p[6]) for p in processos]

    meus = processo_repo.listar_por_advogado(usuario_id)
    livres = processo_repo.listar_nao_atribuidos(escritorio_id)
    combinados = {p[0]: p[3] for p in meus}
    combinados.update({p[0]: p[3] for p in livres})
    return [(pid, ncj, None) for pid, ncj in combinados.items()]


def renderizar_painel_cliente(cliente_id):
    cliente = cliente_repo.obter_por_id(cliente_id)
    # id, escritorio_id, nome, cpf_cnpj, email, telefone, whatsapp, idade,
    # tipo_pessoa, preferencias_notificacao, criado_em, ativo
    (_id, _esc, nome, cpf_cnpj, email, telefone, whatsapp, idade,
     tipo_pessoa, _pref, _criado, ativo) = cliente

    st.markdown(f"### {nome}")
    if not ativo:
        st.warning("Este cliente esta desativado.")

    with st.form(f"form_editar_cliente_{cliente_id}"):
        novo_nome = st.text_input("Nome", value=nome)
        novo_cpf_cnpj = st.text_input("CPF/CNPJ", value=cpf_cnpj)
        nova_idade = st.number_input("Idade", min_value=0, max_value=120, step=1, value=idade or 0)
        novo_email = st.text_input("E-mail", value=email or "")
        novo_telefone = st.text_input("Telefone", value=telefone or "")
        novo_whatsapp = st.text_input("WhatsApp", value=whatsapp or "")
        novo_tipo = st.selectbox(
            "Tipo de pessoa", ["fisica", "juridica"],
            index=0 if tipo_pessoa == "fisica" else 1
        )

        salvar = st.form_submit_button("Salvar alteracoes")
        if salvar:
            cliente_repo.atualizar(
                cliente_id, novo_nome, novo_cpf_cnpj, nova_idade or None,
                novo_email, novo_telefone, novo_whatsapp, novo_tipo
            )
            log_repo.registrar(st.session_state["usuario_id"], "atualizar", "cliente", cliente_id)
            st.success("Cliente atualizado.")
            st.rerun()

    col_a, col_b = st.columns(2)
    if ativo:
        if col_a.button("Desativar cliente", key=f"desativar_{cliente_id}"):
            cliente_repo.definir_ativo(cliente_id, False)
            log_repo.registrar(st.session_state["usuario_id"], "desativar", "cliente", cliente_id)
            st.rerun()
    else:
        if col_a.button("Reativar cliente", key=f"reativar_{cliente_id}"):
            cliente_repo.definir_ativo(cliente_id, True)
            log_repo.registrar(st.session_state["usuario_id"], "reativar", "cliente", cliente_id)
            st.rerun()

    st.write("---")
    st.write("**Processos vinculados**")
    processos_vinculados = processo_repo.listar_por_cliente(cliente_id)
    if processos_vinculados:
        st.table([
            {"numero_cnj": p[1], "classe": p[2], "status": p[3]}
            for p in processos_vinculados
        ])
    else:
        st.caption("Nenhum processo vinculado a este cliente ainda.")


def renderizar_painel_processo(processo_id, numero_cnj, lider, usuario_id, escritorio_id):
    processo = processo_repo.obter_por_id(processo_id)
    # id, escritorio_id, tribunal_id, numero_cnj, classe, assunto, vara,
    # comarca, status, advogado_responsavel_id, criado_em, atualizado_em, valor_causa
    (_id, _esc, _trib, _numero, classe, assunto, vara, comarca, status,
     advogado_id, _criado, _atualizado, valor_causa) = processo

    st.markdown(f"### Processo {numero_cnj}")

    col_a, col_b, col_c, col_d = st.columns(4)
    col_a.metric("Status", status)
    col_b.metric("Vara", vara or "-")
    col_c.metric("Comarca", comarca or "-")
    col_d.metric("Valor da causa", formatar_moeda(valor_causa))

    clientes_do_processo = processo_repo.listar_clientes_do_processo(processo_id)
    if clientes_do_processo:
        st.write("Cliente(s) vinculado(s): " + ", ".join(c[1] for c in clientes_do_processo))

    # --- Editar dados ---
    with st.expander("Editar dados do processo"):
        with st.form(f"form_editar_processo_{processo_id}"):
            nova_classe = st.text_input("Classe", value=classe)
            novo_assunto = st.text_input("Assunto", value=assunto or "")
            nova_vara = st.text_input("Vara", value=vara or "")
            nova_comarca = st.text_input("Comarca", value=comarca or "")
            novo_status = st.selectbox(
                "Status", ["ativo", "arquivado", "suspenso", "baixado"],
                index=["ativo", "arquivado", "suspenso", "baixado"].index(status)
            )
            novo_valor_causa = st.number_input(
                "Valor da causa (R$)", min_value=0.0, step=100.0,
                value=float(valor_causa) if valor_causa else 0.0
            )

            salvar = st.form_submit_button("Salvar alteracoes")
            if salvar:
                processo_repo.atualizar(
                    processo_id, nova_classe, novo_assunto, nova_vara, nova_comarca,
                    novo_status, novo_valor_causa or None
                )
                log_repo.registrar(usuario_id, "atualizar", "processo", processo_id)
                st.success("Processo atualizado.")
                st.rerun()

    # --- Atribuição ---
    st.write("---")
    if lider:
        equipe = usuario_repo.listar_por_escritorio(escritorio_id)
        opcoes = {"Ninguem": None}
        opcoes.update({u[2]: u[0] for u in equipe})

        nome_atual = next((n for n, i in opcoes.items() if str(i) == str(advogado_id)), "Ninguem")
        escolhido = st.selectbox(
            "Advogado responsavel", list(opcoes.keys()),
            index=list(opcoes.keys()).index(nome_atual),
            key=f"atribuir_{processo_id}"
        )
        if st.button("Salvar atribuicao", key=f"salvar_atrib_{processo_id}"):
            processo_repo.designar_advogado(processo_id, opcoes[escolhido])
            log_repo.registrar(usuario_id, "atribuir", "processo", processo_id)
            st.success("Atribuicao atualizada.")
            st.rerun()
    else:
        if advogado_id is None:
            if st.button("Pegar este processo pra mim", key=f"pegar_{processo_id}"):
                processo_repo.designar_advogado(processo_id, usuario_id)
                log_repo.registrar(usuario_id, "atribuir", "processo", processo_id)
                st.success("Processo atribuido a voce.")
                st.rerun()
        elif str(advogado_id) == str(usuario_id):
            st.caption("Este processo esta atribuido a voce.")
        else:
            st.caption("Este processo esta atribuido a outro advogado da equipe.")

    # --- Registrar atualização ---
    st.write("---")
    with st.expander("Registrar atualizacao (movimentacao)"):
        with st.form(f"form_atualizacao_{processo_id}"):
            tipo_evento = st.selectbox(
                "Tipo de evento",
                ["Nova movimentacao", "Audiencia marcada", "Prazo", "Decisao/Sentenca", "Documento juntado", "Outro"],
                key=f"tipo_evento_{processo_id}"
            )
            descricao = st.text_area("O que mudou?", key=f"descricao_{processo_id}")
            importancia = st.selectbox("Importancia", ["alta", "media", "baixa"], index=1, key=f"import_{processo_id}")
            data_evento = st.date_input("Data do evento", value=date.today(), key=f"data_evento_{processo_id}")

            registrar = st.form_submit_button("Registrar e gerar aviso")
            if registrar:
                if not descricao:
                    st.error("Descreva o que mudou.")
                else:
                    resumo = f"[{tipo_evento}] {descricao}"

                    movimentacao = Movimentacao(
                        processo_id=processo_id, descricao_original=descricao, descricao_resumida=resumo,
                        importancia=importancia, data_movimentacao=datetime.combine(data_evento, datetime.min.time())
                    )
                    movimentacao_id = movimentacao_repo.cadastrar(movimentacao)

                    relatorio = Relatorio(
                        processo_id=processo_id, movimentacao_id=movimentacao_id,
                        conteudo=resumo, canal_envio="whatsapp", status_envio="pendente"
                    )
                    relatorio_repo.cadastrar(relatorio)
                    log_repo.registrar(usuario_id, "registrar_movimentacao", "processo", processo_id)

                    st.success("Atualizacao registrada. Aviso gerado na aba Avisos.")
                    st.rerun()

    # --- Histórico ---
    st.write("---")
    st.write("**Historico de movimentacoes**")
    historico = movimentacao_repo.listar_por_processo(processo_id)
    if not historico:
        st.caption("Nenhuma movimentacao registrada ainda.")
    else:
        st.table([
            {"data": mov[5], "importancia": (mov[4] or "-").upper(), "descricao": mov[3] or mov[2]}
            for mov in historico
        ])

    # --- Agenda do processo ---
    st.write("---")
    st.write("**Agenda deste processo**")
    with st.form(f"form_compromisso_{processo_id}"):
        tipo_compromisso = st.selectbox("Tipo", ["audiencia", "prazo", "reuniao", "outro"], key=f"tipo_comp_{processo_id}")
        descricao_compromisso = st.text_input("Descricao", key=f"desc_comp_{processo_id}")
        data_compromisso = st.date_input("Data", value=date.today(), key=f"data_comp_{processo_id}")
        hora_compromisso = st.time_input("Hora", key=f"hora_comp_{processo_id}")

        adicionar = st.form_submit_button("Adicionar a agenda")
        if adicionar:
            compromisso = Compromisso(
                processo_id=processo_id, tipo=tipo_compromisso, descricao=descricao_compromisso,
                data_hora=datetime.combine(data_compromisso, hora_compromisso)
            )
            compromisso_repo.cadastrar(compromisso)
            log_repo.registrar(usuario_id, "criar", "compromisso", processo_id)
            st.success("Adicionado a agenda.")
            st.rerun()

    compromissos_processo = compromisso_repo.listar_por_processo(processo_id)
    if compromissos_processo:
        st.table([
            {
                "tipo": c[2], "descricao": c[3], "data": c[4],
                "status": "concluido" if c[5] else "pendente"
            }
            for c in compromissos_processo
        ])

    # --- Financeiro do processo ---
    st.write("---")
    st.write("**Financeiro deste processo**")
    lancamentos_processo = financeiro_repo.listar_por_processo(processo_id)
    if lancamentos_processo:
        st.table([
            {
                "tipo": f[4], "descricao": f[5], "valor": formatar_moeda(f[6]),
                "status": f[7], "vencimento": f[8]
            }
            for f in lancamentos_processo
        ])
    else:
        st.caption("Nenhum lancamento financeiro para este processo. Adicione pela aba Financeiro.")

    # --- Documentos ---
    st.write("---")
    st.write("**Documentos**")
    arquivo = st.file_uploader(
        "Anexar PDF ou foto", type=["pdf", "png", "jpg", "jpeg"], key=f"upload_{processo_id}"
    )
    if arquivo is not None:
        if st.button("Salvar documento", key=f"salvar_doc_{processo_id}"):
            extensao = arquivo.name.split(".")[-1].lower()
            tipo = "pdf" if extensao == "pdf" else "foto"
            conteudo_bytes = arquivo.read()

            documento = Documento(
                processo_id=processo_id, usuario_id=usuario_id, nome_arquivo=arquivo.name,
                tipo=tipo, conteudo=conteudo_bytes, tamanho_bytes=len(conteudo_bytes)
            )
            documento_repo.cadastrar(documento)
            log_repo.registrar(usuario_id, "anexar_documento", "processo", processo_id)
            st.success(f"'{arquivo.name}' anexado.")
            st.rerun()

    documentos = documento_repo.listar_por_processo(processo_id)
    for doc in documentos:
        doc_id, _proc_id, _usuario_id, nome_arquivo, tipo, tamanho, criado_em = doc
        col_nome, col_baixar = st.columns([4, 1])
        col_nome.write(f"{nome_arquivo} ({tamanho or 0} bytes, {criado_em})")
        with col_baixar:
            resultado = documento_repo.obter_conteudo(doc_id)
            if resultado:
                _nome, conteudo = resultado
                st.download_button("Baixar", data=conteudo, file_name=nome_arquivo, key=f"baixar_{doc_id}")

    # --- Comentários ---
    st.write("---")
    st.write("**Comentarios da equipe**")
    novo_comentario = st.text_area("Adicionar comentario", key=f"comentario_{processo_id}")
    if st.button("Comentar", key=f"btn_comentar_{processo_id}"):
        if novo_comentario.strip():
            comentario = Comentario(processo_id=processo_id, usuario_id=usuario_id, texto=novo_comentario.strip())
            comentario_repo.cadastrar(comentario)
            log_repo.registrar(usuario_id, "comentar", "processo", processo_id)
            st.rerun()

    for com in comentario_repo.listar_por_processo(processo_id):
        _com_id, texto, criado_em, autor = com
        st.markdown(f"**{autor or 'Equipe'}** - {criado_em}")
        st.write(texto)


# ---------------------------------------------------------------------------
# App principal
# ---------------------------------------------------------------------------

def app_principal():
    escritorio_id = st.session_state["escritorio_id"]
    usuario_id = st.session_state["usuario_id"]
    lider = eh_lider()

    st.sidebar.markdown(f"**{st.session_state['escritorio_nome']}**")
    st.sidebar.caption(f"{st.session_state['usuario_nome']} ({st.session_state['perfil']})")
    if st.sidebar.button("Sair"):
        fazer_logout()

    st.title("PRAXIS")

    if lider:
        avisos_pendentes = relatorio_repo.listar_pendentes(escritorio_id=escritorio_id)
    else:
        meus_ids = {p[0] for p in processo_repo.listar_por_advogado(usuario_id)}
        avisos_pendentes = [a for a in relatorio_repo.listar_pendentes(escritorio_id=escritorio_id) if a[6] in meus_ids]

    st.sidebar.write(f"Avisos pendentes: {len(avisos_pendentes)}")

    nomes_abas = ["Painel", "Clientes", "Processos", "Agenda", "Financeiro", "Avisos", "Buscar"]
    if lider:
        nomes_abas += ["Equipe", "Relatorio"]

    abas = dict(zip(nomes_abas, st.tabs(nomes_abas)))

    # --- Painel ---
    with abas["Painel"]:
        st.subheader("Visao geral")

        advogado_filtro = None if lider else usuario_id
        clientes_ativos = cliente_repo.listar_por_escritorio(escritorio_id)
        lista_processos = processos_visiveis(escritorio_id, usuario_id, lider)
        proximos_compromissos = compromisso_repo.listar_proximos(escritorio_id, advogado_id=advogado_filtro)
        resumo_financeiro = financeiro_repo.resumo(escritorio_id)

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Clientes ativos", len(clientes_ativos))
        col2.metric("Processos visiveis", len(lista_processos))
        col3.metric("Avisos pendentes", len(avisos_pendentes))
        col4.metric("Compromissos futuros", len(proximos_compromissos))

        col5, col6 = st.columns(2)
        col5.metric("A receber", formatar_moeda(resumo_financeiro["a_receber"]))
        col6.metric("A pagar", formatar_moeda(resumo_financeiro["a_pagar"]))

        st.write("---")
        st.write("**Proximos compromissos**")
        if proximos_compromissos:
            st.table([
                {
                    "data": c[3], "tipo": c[1], "descricao": c[2],
                    "processo": c[6], "advogado": c[7] or "-"
                }
                for c in proximos_compromissos[:10]
            ])
        else:
            st.caption("Nenhum compromisso futuro cadastrado.")

        st.write("---")
        st.write("**Processos parados ha mais tempo**")
        if lider:
            parados = relatorio_gerencial_repo.listar_processos_por_tempo_sem_atualizacao(escritorio_id, ordem="mais_tempo")[:5]
            linhas_parados = []
            for p in parados:
                _pid, ncj, status_p, adv_nome, ultima = p
                dias = (datetime.now() - ultima).days if ultima else None
                linhas_parados.append({
                    "processo": ncj, "status": status_p, "advogado": adv_nome or "-",
                    "sem atualizacao ha": f"{dias} dia(s)" if dias is not None else "nunca atualizado"
                })
            st.table(linhas_parados)
        else:
            st.caption("Disponivel apenas para o perfil lider (aba Relatorio).")

    # --- Clientes ---
    with abas["Clientes"]:
        st.subheader("Clientes")

        with st.expander("Novo cliente"):
            with st.form("form_cliente"):
                nome = st.text_input("Nome")
                cpf_cnpj = st.text_input("CPF/CNPJ")
                idade = st.number_input("Idade", min_value=0, max_value=120, step=1, value=0)
                email = st.text_input("E-mail")
                telefone = st.text_input("Telefone")
                whatsapp = st.text_input("WhatsApp")
                tipo_pessoa = st.selectbox("Tipo de Pessoa", ["fisica", "juridica"])

                enviado = st.form_submit_button("Cadastrar")

                if enviado:
                    if not nome or not cpf_cnpj:
                        st.error("Nome e CPF/CNPJ sao obrigatorios.")
                    else:
                        cliente = Cliente(
                            escritorio_id=escritorio_id, nome=nome, cpf_cnpj=cpf_cnpj,
                            idade=idade or None, email=email, telefone=telefone, whatsapp=whatsapp,
                            tipo_pessoa=tipo_pessoa, preferencias_notificacao={}
                        )
                        cliente_id = cliente_repo.cadastrar(cliente)
                        log_repo.registrar(usuario_id, "criar", "cliente", cliente_id)
                        st.success(f"Cliente '{nome}' cadastrado.")
                        st.rerun()

        clientes = cliente_repo.listar_por_escritorio(escritorio_id)
        if not clientes:
            st.info("Nenhum cliente cadastrado ainda.")
        else:
            opcoes_clientes = {f"{c[2]} ({c[3]})": c[0] for c in clientes}
            escolhido = st.selectbox("Selecione um cliente", list(opcoes_clientes.keys()))
            st.write("")
            renderizar_painel_cliente(opcoes_clientes[escolhido])

    # --- Processos ---
    with abas["Processos"]:
        st.subheader("Processos do escritorio" if lider else "Meus processos")

        with st.expander("Novo processo"):
            todos_clientes = cliente_repo.listar_por_escritorio(escritorio_id)
            opcoes_clientes_cad = {c[2]: c[0] for c in todos_clientes}

            if not opcoes_clientes_cad:
                st.info("Cadastre pelo menos um cliente antes de criar um processo.")
            else:
                equipe = usuario_repo.listar_por_escritorio(escritorio_id)
                if lider:
                    opcoes_atribuicao = {"Nao atribuir": None}
                    opcoes_atribuicao.update({u[2]: u[0] for u in equipe})
                else:
                    opcoes_atribuicao = {"Nao atribuir": None, "Atribuir a mim": usuario_id}

                with st.form("form_processo"):
                    numero_cnj = st.text_input("Numero CNJ")
                    classe = st.text_input("Classe processual")
                    assunto = st.text_input("Assunto")
                    vara = st.text_input("Vara")
                    comarca = st.text_input("Comarca")
                    status = st.selectbox("Status", ["ativo", "arquivado", "suspenso", "baixado"])
                    valor_causa = st.number_input("Valor da causa (R$)", min_value=0.0, step=100.0)
                    sigla_tribunal = st.text_input(
                        "Sigla do tribunal no DataJud (deixe em branco para detectar automaticamente)",
                        placeholder="ex: tjsp, trf1, tjpr"
                    )
                    atribuir_para = st.selectbox("Atribuir a", list(opcoes_atribuicao.keys()))
                    clientes_selecionados = st.multiselect("Cliente(s) vinculado(s)", list(opcoes_clientes_cad.keys()))

                    enviado = st.form_submit_button("Cadastrar")

                    if enviado:
                        if not numero_cnj or not classe or not clientes_selecionados:
                            st.error("Numero CNJ, classe e ao menos um cliente sao obrigatorios.")
                        else:
                            sigla_final = sigla_tribunal.strip() if sigla_tribunal.strip() else detectar_sigla_tribunal(numero_cnj)

                            processo = Processo(
                                escritorio_id=escritorio_id, numero_cnj=numero_cnj, classe=classe,
                                assunto=assunto, vara=vara, comarca=comarca, status=status,
                                valor_causa=valor_causa or None
                            )
                            clientes_ids = [opcoes_clientes_cad[nome] for nome in clientes_selecionados]
                            processo_id = processo_repo.cadastrar(
                                processo, clientes_ids=clientes_ids, sigla_tribunal=sigla_final
                            )

                            advogado_escolhido = opcoes_atribuicao[atribuir_para]
                            if advogado_escolhido:
                                processo_repo.designar_advogado(processo_id, advogado_escolhido)

                            log_repo.registrar(usuario_id, "criar", "processo", processo_id)

                            if not sigla_tribunal.strip() and sigla_final:
                                st.success(f"Processo '{numero_cnj}' cadastrado. Tribunal detectado automaticamente: {sigla_final}.")
                            elif not sigla_final:
                                st.success(f"Processo '{numero_cnj}' cadastrado. Nao foi possivel detectar o tribunal automaticamente - preencha manualmente se quiser sincronizacao com o DataJud.")
                            else:
                                st.success(f"Processo '{numero_cnj}' cadastrado.")
                            st.rerun()

        lista = processos_visiveis(escritorio_id, usuario_id, lider)
        if not lista:
            st.info("Nenhum processo disponivel ainda.")
        else:
            opcoes = {}
            for pid, ncj, adv_nome in lista:
                rotulo = ncj if not lider else f"{ncj}" + (f" - {adv_nome}" if adv_nome else " - (nao atribuido)")
                opcoes[rotulo] = pid

            escolhido = st.selectbox("Selecione um processo", list(opcoes.keys()))
            st.write("")
            renderizar_painel_processo(opcoes[escolhido], escolhido.split(" - ")[0], lider, usuario_id, escritorio_id)

    # --- Agenda ---
    with abas["Agenda"]:
        st.subheader("Agenda" if lider else "Minha agenda")

        advogado_filtro = None if lider else usuario_id
        incluir_concluidos = st.checkbox("Mostrar concluidos")
        agenda = compromisso_repo.listar_proximos(escritorio_id, advogado_id=advogado_filtro, incluir_concluidos=incluir_concluidos)

        if not agenda:
            st.info("Nada na agenda ainda.")
        else:
            agora = datetime.now()
            for item in agenda:
                comp_id, tipo, descricao, data_hora, concluido, _pid, numero_cnj, advogado_nome = item
                atrasado = (not concluido) and data_hora < agora

                with st.container(border=True):
                    col_info, col_acao = st.columns([4, 1])
                    with col_info:
                        etiqueta = "ATRASADO - " if atrasado else ""
                        st.markdown(f"**{etiqueta}{tipo.upper()}** - {numero_cnj} - {data_hora}")
                        st.write(descricao)
                        if lider:
                            st.caption(f"Responsavel: {advogado_nome or '-'}")
                    with col_acao:
                        if not concluido:
                            if st.button("Concluir", key=f"concluir_{comp_id}"):
                                compromisso_repo.marcar_concluido(comp_id)
                                st.rerun()

    # --- Financeiro ---
    with abas["Financeiro"]:
        st.subheader("Financeiro")

        resumo = financeiro_repo.resumo(escritorio_id)
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("A receber", formatar_moeda(resumo["a_receber"]))
        col2.metric("Recebido", formatar_moeda(resumo["recebido"]))
        col3.metric("A pagar", formatar_moeda(resumo["a_pagar"]))
        col4.metric("Pago", formatar_moeda(resumo["pago"]))

        with st.expander("Novo lancamento"):
            clientes_fin = cliente_repo.listar_por_escritorio(escritorio_id)
            processos_fin = processos_visiveis(escritorio_id, usuario_id, lider)

            opcoes_clientes_fin = {"Nenhum": None}
            opcoes_clientes_fin.update({c[2]: c[0] for c in clientes_fin})

            opcoes_processos_fin = {"Nenhum": None}
            opcoes_processos_fin.update({ncj: pid for pid, ncj, _adv in processos_fin})

            with st.form("form_financeiro"):
                tipo_lancamento = st.selectbox("Tipo", ["receita", "despesa"])
                descricao_lancamento = st.text_input("Descricao")
                valor_lancamento = st.number_input("Valor (R$)", min_value=0.0, step=50.0)
                vencimento_lancamento = st.date_input("Vencimento", value=date.today())
                cliente_lancamento = st.selectbox("Cliente (opcional)", list(opcoes_clientes_fin.keys()))
                processo_lancamento = st.selectbox("Processo (opcional)", list(opcoes_processos_fin.keys()))

                enviado = st.form_submit_button("Lancar")

                if enviado:
                    if not descricao_lancamento or not valor_lancamento:
                        st.error("Descricao e valor sao obrigatorios.")
                    else:
                        lancamento = Financeiro(
                            escritorio_id=escritorio_id,
                            processo_id=opcoes_processos_fin[processo_lancamento],
                            cliente_id=opcoes_clientes_fin[cliente_lancamento],
                            tipo=tipo_lancamento, descricao=descricao_lancamento,
                            valor=valor_lancamento, status="pendente", vencimento=vencimento_lancamento
                        )
                        financeiro_repo.cadastrar(lancamento)
                        log_repo.registrar(usuario_id, "criar", "financeiro", None)
                        st.success("Lancamento adicionado.")
                        st.rerun()

        filtro_status = st.selectbox("Filtrar por status", ["todos", "pendente", "pago"])
        lancamentos = financeiro_repo.listar_por_escritorio(
            escritorio_id, status=None if filtro_status == "todos" else filtro_status
        )

        if not lancamentos:
            st.info("Nenhum lancamento cadastrado ainda.")
        else:
            for lanc in lancamentos:
                lanc_id, tipo, descricao, valor, status_l, vencimento, numero_cnj, cliente_nome = lanc
                with st.container(border=True):
                    col_info, col_acao = st.columns([4, 1])
                    with col_info:
                        st.markdown(f"**{tipo.upper()}** - {descricao} - {formatar_moeda(valor)}")
                        st.caption(f"Vencimento: {vencimento or '-'} | Processo: {numero_cnj or '-'} | Cliente: {cliente_nome or '-'} | Status: {status_l}")
                    with col_acao:
                        if status_l == "pendente":
                            if st.button("Marcar pago", key=f"pagar_{lanc_id}"):
                                financeiro_repo.marcar_pago(lanc_id)
                                st.rerun()

    # --- Avisos ---
    with abas["Avisos"]:
        st.subheader("Avisos pendentes de envio ao cliente")

        if not avisos_pendentes:
            st.info("Nenhum aviso pendente no momento.")
        else:
            for aviso in avisos_pendentes:
                (relatorio_id, conteudo, canal_envio, descricao_resumida, importancia,
                 data_movimentacao, processo_id, numero_cnj, cliente_id, cliente_nome) = aviso

                with st.container(border=True):
                    col_info, col_acao = st.columns([4, 1])
                    with col_info:
                        st.markdown(f"**{(importancia or '-').upper()}** - {cliente_nome} - processo {numero_cnj}")
                        st.text(TEMPLATE_MENSAGEM.format(
                            cliente_nome=cliente_nome, numero_cnj=numero_cnj,
                            resumo=descricao_resumida or conteudo
                        ))
                        if data_movimentacao:
                            st.caption(f"Evento em {data_movimentacao}")
                    with col_acao:
                        chave = f"enviar_{relatorio_id}_{cliente_id}"
                        if st.button("Marcar como avisado", key=chave):
                            relatorio_repo.marcar_como_enviado(relatorio_id)
                            st.rerun()

    # --- Buscar ---
    with abas["Buscar"]:
        st.subheader("Buscar por nome, CPF/CNPJ ou numero de processo")
        termo = st.text_input("O que voce esta procurando?")

        if termo:
            resultado = busca_repo.buscar_geral(escritorio_id, termo)

            st.write(f"Clientes ({len(resultado['clientes'])})")
            if resultado["clientes"]:
                st.table([
                    {"nome": c[1], "cpf_cnpj": c[2], "telefone": c[3], "whatsapp": c[4]}
                    for c in resultado["clientes"]
                ])
            else:
                st.caption("Nenhum cliente encontrado.")

            st.write(f"Processos ({len(resultado['processos'])})")
            if resultado["processos"]:
                st.table([
                    {"numero_cnj": p[1], "classe": p[2], "assunto": p[3], "status": p[4]}
                    for p in resultado["processos"]
                ])
            else:
                st.caption("Nenhum processo encontrado.")

    # --- Equipe (lider) ---
    if lider:
        with abas["Equipe"]:
            st.subheader("Equipe do escritorio")

            with st.form("form_novo_membro"):
                nome_membro = st.text_input("Nome")
                email_membro = st.text_input("E-mail")
                senha_membro = st.text_input("Senha provisoria", type="password")
                perfil_membro = st.selectbox("Perfil", ["advogado", "lider"])

                enviado = st.form_submit_button("Adicionar a equipe")

                if enviado:
                    if not nome_membro or not email_membro or not senha_membro:
                        st.error("Preencha todos os campos.")
                    elif usuario_repo.email_ja_existe(email_membro):
                        st.error("Ja existe um usuario com esse e-mail.")
                    else:
                        novo = Usuario(
                            escritorio_id=escritorio_id, nome=nome_membro, email=email_membro,
                            perfil=perfil_membro, ativo=True
                        )
                        usuario_repo.cadastrar(novo, senha_membro)
                        st.success(f"{nome_membro} adicionado a equipe como {perfil_membro}.")
                        st.rerun()

            st.write("---")
            equipe = usuario_repo.listar_por_escritorio(escritorio_id)
            st.table([
                {"nome": u[2], "email": u[3], "perfil": u[4], "ativo": u[5]}
                for u in equipe
            ])

    # --- Relatório (lider) ---
    if lider:
        with abas["Relatorio"]:
            st.subheader("Relatorio de atualizacoes")

            col1, col2, col3 = st.columns(3)
            usar_periodo = col1.checkbox("Filtrar por periodo")
            data_inicio = col2.date_input("De", value=date.today(), disabled=not usar_periodo)
            data_fim = col3.date_input("Ate", value=date.today(), disabled=not usar_periodo)

            ordenar_por = st.selectbox(
                "Ordenar por", ["recente", "antigo", "urgente"],
                format_func=lambda o: {"recente": "Mais recentes", "antigo": "Mais antigos", "urgente": "Mais urgentes"}[o]
            )

            movimentacoes = relatorio_gerencial_repo.listar_movimentacoes(
                escritorio_id,
                data_inicio=datetime.combine(data_inicio, datetime.min.time()) if usar_periodo else None,
                data_fim=datetime.combine(data_fim, datetime.max.time()) if usar_periodo else None,
                ordenar_por=ordenar_por
            )

            if not movimentacoes:
                st.info("Nenhuma movimentacao encontrada nesse filtro.")
            else:
                st.table([
                    {
                        "data": m[3], "importancia": (m[2] or "-").upper(),
                        "processo": m[5], "advogado": m[6] or "-", "descricao": m[1]
                    }
                    for m in movimentacoes
                ])

            st.write("---")
            st.write("**Processos por tempo sem atualizacao**")
            ordem_tempo = st.selectbox(
                "Ordenar", ["mais_tempo", "menos_tempo"],
                format_func=lambda o: "Mais tempo sem atualizacao" if o == "mais_tempo" else "Menos tempo sem atualizacao"
            )
            processos_parados = relatorio_gerencial_repo.listar_processos_por_tempo_sem_atualizacao(
                escritorio_id, ordem=ordem_tempo
            )

            linhas_tempo = []
            for p in processos_parados:
                _pid, numero_cnj, status_p, advogado_nome, ultima = p
                if ultima:
                    dias = (datetime.now() - ultima).days
                    dias_texto = f"{dias} dia(s)"
                else:
                    dias_texto = "nunca atualizado"
                linhas_tempo.append({
                    "processo": numero_cnj, "status": status_p, "advogado": advogado_nome or "-",
                    "ultima atualizacao": ultima or "-", "tempo parado": dias_texto
                })
            st.table(linhas_tempo)


# ---------------------------------------------------------------------------
# Ponto de entrada
# ---------------------------------------------------------------------------

if usuario_logado():
    app_principal()
else:
    tela_login()
