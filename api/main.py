"""
API do PRAXIS.

Roda a partir da RAIZ do projeto (a pasta que tem app.py, main.py, models/,
repositories/, database/):

    uvicorn api.main:app --reload --port 8000

Reaproveita os mesmos repositories que o app Streamlit usa - a regra de
negocio nao foi duplicada, so exposta como HTTP.

SEGURANCA (importante, leia): a autenticacao aqui e' por token opaco
guardado em memoria (dict SESSOES). Isso significa:
  - Reiniciar o servidor derruba todas as sessoes (usuarios precisam logar
    de novo). Aceitavel pra demo, NAO pra producao.
  - Nao ha expiracao de token, nao ha HTTPS configurado aqui (fica por
    conta de onde for hospedado), e nao ha rate limiting.
  - O escritorio_id/usuario_id/perfil de cada requisicao vem do token
    validado no servidor (nao do que o cliente manda) - isso pelo menos
    evita que alguem finja ser de outro escritorio so trocando um campo
    no request.
Antes de qualquer uso real (fora de demo), trocar por JWT com expiracao
e sessao persistida (Redis ou tabela no proprio Postgres).
"""

import io
import csv
import secrets
from datetime import datetime, date
from decimal import Decimal
from typing import Optional
from uuid import UUID

from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, FileResponse
from pydantic import BaseModel

from models.escritorio import Escritorio
from models.cliente import Cliente
from models.processo import Processo
from models.movimentacao import Movimentacao
from models.relatorio import Relatorio
from models.usuario import Usuario
from models.comentario import Comentario
from models.compromisso import Compromisso

from repositories.escritorio_repository import EscritorioRepository
from repositories.cliente_repository import ClienteRepository
from repositories.processo_repository import ProcessoRepository
from repositories.movimentacao_repository import MovimentacaoRepository
from repositories.relatorio_repository import RelatorioRepository
from repositories.usuario_repository import UsuarioRepository
from repositories.comentario_repository import ComentarioRepository
from repositories.busca_repository import BuscaRepository
from repositories.relatorio_gerencial_repository import RelatorioGerencialRepository
from repositories.log_repository import LogRepository
from repositories.compromisso_repository import CompromissoRepository
from repositories.relatorio_avancado_repository import RelatorioAvancadoRepository

from servicos.cnj_parser import detectar_sigla_tribunal


app = FastAPI(title="PRAXIS API")

# Demo: libera geral. Restrinja allow_origins ao dominio real antes de producao.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

escritorio_repo = EscritorioRepository()
cliente_repo = ClienteRepository()
processo_repo = ProcessoRepository()
movimentacao_repo = MovimentacaoRepository()
relatorio_repo = RelatorioRepository()
usuario_repo = UsuarioRepository()
comentario_repo = ComentarioRepository()
busca_repo = BuscaRepository()
relatorio_gerencial_repo = RelatorioGerencialRepository()
log_repo = LogRepository()
compromisso_repo = CompromissoRepository()
relatorio_avancado_repo = RelatorioAvancadoRepository()

# Serve o front-end (arquivo unico) na raiz do mesmo dominio/porta da API -
# assim nao precisa de um segundo container so pra isso, nem de path
# prefix/stripprefix no Traefik. Ver instrucoes de deploy.
@app.get("/")
def servir_frontend():
    return FileResponse("frontend/praxis_app.html")

# token -> {usuario_id, escritorio_id, nome, perfil, escritorio_nome}
SESSOES = {}


# ---------------------------------------------------------------------------
# Helpers de serializacao (tupla do banco -> dict JSON)
# ---------------------------------------------------------------------------

def _num(v):
    """Converte Decimal/None pra float/None (JSON nao entende Decimal)."""
    if v is None:
        return None
    return float(v)


def serializar_cliente(c):
    # COLUNAS_CLIENTE: id, escritorio_id, nome, cpf_cnpj, email, telefone,
    # whatsapp, idade, tipo_pessoa, preferencias_notificacao, criado_em, ativo
    return {
        "id": str(c[0]), "nome": c[2], "cpf_cnpj": c[3], "email": c[4],
        "telefone": c[5], "whatsapp": c[6], "idade": c[7], "tipo_pessoa": c[8],
        "ativo": c[11],
    }


def serializar_processo_lista(p):
    # id, numero_cnj, classe, assunto, status, advogado_id, advogado_nome
    return {
        "id": str(p[0]), "numero_cnj": p[1], "classe": p[2], "assunto": p[3],
        "status": p[4], "advogado_id": str(p[5]) if p[5] else None, "advogado_nome": p[6],
    }


def serializar_movimentacao(m):
    # id, processo_id, descricao_original, descricao_resumida, importancia,
    # data_movimentacao, data_consulta, metadados
    return {
        "id": str(m[0]), "descricao": m[3] or m[2], "importancia": m[4],
        "data": m[5].isoformat() if m[5] else None,
    }


def serializar_compromisso(c):
    # id, processo_id, tipo, descricao, data_hora, concluido, criado_em
    return {
        "id": str(c[0]), "tipo": c[2], "descricao": c[3],
        "data_hora": c[4].isoformat() if c[4] else None, "concluido": c[5],
    }


def serializar_comentario(c):
    # id, texto, criado_em, autor
    return {
        "id": str(c[0]), "texto": c[1],
        "criado_em": c[2].isoformat() if c[2] else None, "autor": c[3] or "Equipe",
    }


def serializar_aviso(a):
    # relatorio_id, conteudo, canal_envio, descricao_resumida, importancia,
    # data_movimentacao, processo_id, numero_cnj, cliente_id, cliente_nome
    resumo = a[3] or a[1]
    mensagem = (
        f"Ola {a[9]}, tudo bem?\n\n"
        f"Seu processo no {a[7]} teve uma nova movimentacao:\n\n"
        f"{resumo}\n\nQualquer duvida, estamos a disposicao."
    )
    return {
        "id": str(a[0]), "importancia": a[4], "cliente_nome": a[9],
        "processo_numero": a[7], "mensagem": mensagem,
        "data_movimentacao": a[5].isoformat() if a[5] else None,
    }


# ---------------------------------------------------------------------------
# Autenticacao
# ---------------------------------------------------------------------------

class LoginBody(BaseModel):
    email: str
    senha: str


class CriarEscritorioBody(BaseModel):
    nome_escritorio: str
    nome_usuario: str
    email: str
    senha: str


def _sessao_para_resposta(token, sessao):
    return {
        "token": token,
        "usuario": {"id": str(sessao["usuario_id"]), "nome": sessao["nome"], "perfil": sessao["perfil"]},
        "escritorio": {"id": str(sessao["escritorio_id"]), "nome": sessao["escritorio_nome"]},
    }


@app.post("/auth/login")
def login(body: LoginBody):
    usuario = usuario_repo.autenticar(body.email, body.senha)
    if usuario is None:
        raise HTTPException(401, "E-mail ou senha invalidos.")

    usuario_id, escritorio_id, nome, _email, _hash, perfil, _ativo, _criado = usuario
    escritorios = escritorio_repo.listar_todos()
    escritorio_nome = next((e[1] for e in escritorios if str(e[0]) == str(escritorio_id)), "")

    token = secrets.token_hex(24)
    SESSOES[token] = {
        "usuario_id": usuario_id, "escritorio_id": escritorio_id,
        "nome": nome, "perfil": perfil, "escritorio_nome": escritorio_nome,
    }
    return _sessao_para_resposta(token, SESSOES[token])


@app.post("/auth/criar-escritorio")
def criar_escritorio(body: CriarEscritorioBody):
    if usuario_repo.email_ja_existe(body.email):
        raise HTTPException(400, "Ja existe um usuario com esse e-mail.")

    escritorio = Escritorio(nome=body.nome_escritorio, telefone="", email=body.email, cnpj="", configuracoes={})
    escritorio_id = escritorio_repo.cadastrar(escritorio)

    usuario = Usuario(escritorio_id=escritorio_id, nome=body.nome_usuario, email=body.email, perfil="lider", ativo=True)
    usuario_id = usuario_repo.cadastrar(usuario, body.senha)

    token = secrets.token_hex(24)
    SESSOES[token] = {
        "usuario_id": usuario_id, "escritorio_id": escritorio_id,
        "nome": body.nome_usuario, "perfil": "lider", "escritorio_nome": body.nome_escritorio,
    }
    return _sessao_para_resposta(token, SESSOES[token])


def usuario_atual(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Nao autenticado.")
    token = authorization.removeprefix("Bearer ").strip()
    sessao = SESSOES.get(token)
    if sessao is None:
        raise HTTPException(401, "Sessao invalida ou expirada.")
    return sessao


def exigir_lider(sessao):
    if sessao["perfil"] != "lider":
        raise HTTPException(403, "Acao permitida apenas para o perfil lider.")


# ---------------------------------------------------------------------------
# Painel
# ---------------------------------------------------------------------------

@app.get("/painel")
def painel(authorization: Optional[str] = Header(None)):
    sessao = usuario_atual(authorization)
    escritorio_id = sessao["escritorio_id"]
    lider = sessao["perfil"] == "lider"
    advogado_filtro = None if lider else sessao["usuario_id"]

    clientes_ativos = cliente_repo.listar_por_escritorio(escritorio_id)
    lista_processos = _processos_visiveis(escritorio_id, sessao["usuario_id"], lider)
    proximos = compromisso_repo.listar_proximos(escritorio_id, advogado_id=advogado_filtro)
    avisos = _avisos_visiveis(sessao)

    parados = None
    if lider:
        brutos = relatorio_gerencial_repo.listar_processos_por_tempo_sem_atualizacao(escritorio_id, ordem="mais_tempo")[:5]
        parados = [
            {
                "numero_cnj": p[1], "status": p[2], "advogado_nome": p[3] or None,
                "ultima_movimentacao": p[4].isoformat() if p[4] else None,
            }
            for p in brutos
        ]

    return {
        "metrics": {
            "clientes_ativos": len(clientes_ativos), "processos_visiveis": len(lista_processos),
            "avisos_pendentes": len(avisos), "compromissos_futuros": len(proximos),
        },
        "proximos_compromissos": [
            {**serializar_compromisso((c[0], None, c[1], c[2], c[3], c[4], None)), "processo_numero": c[6]}
            for c in proximos
        ],
        "processos_parados": parados,
    }


# ---------------------------------------------------------------------------
# Clientes
# ---------------------------------------------------------------------------

class ClienteBody(BaseModel):
    nome: str
    cpf_cnpj: str
    idade: Optional[int] = None
    email: Optional[str] = ""
    telefone: Optional[str] = ""
    whatsapp: Optional[str] = ""
    tipo_pessoa: str = "fisica"


@app.get("/clientes")
def listar_clientes(authorization: Optional[str] = Header(None)):
    sessao = usuario_atual(authorization)
    return [serializar_cliente(c) for c in cliente_repo.listar_por_escritorio(sessao["escritorio_id"])]


@app.post("/clientes")
def criar_cliente(body: ClienteBody, authorization: Optional[str] = Header(None)):
    sessao = usuario_atual(authorization)
    cliente = Cliente(
        escritorio_id=sessao["escritorio_id"], nome=body.nome, cpf_cnpj=body.cpf_cnpj,
        idade=body.idade, email=body.email, telefone=body.telefone, whatsapp=body.whatsapp,
        tipo_pessoa=body.tipo_pessoa, preferencias_notificacao={}
    )
    cliente_id = cliente_repo.cadastrar(cliente)
    log_repo.registrar(sessao["usuario_id"], "criar", "cliente", cliente_id)
    return {"id": str(cliente_id)}


@app.get("/clientes/{cliente_id}")
def obter_cliente(cliente_id: UUID, authorization: Optional[str] = Header(None)):
    usuario_atual(authorization)
    c = cliente_repo.obter_por_id(cliente_id)
    if c is None:
        raise HTTPException(404, "Cliente nao encontrado.")
    dados = serializar_cliente(c)
    dados["processos_vinculados"] = [
        {"id": str(p[0]), "numero_cnj": p[1], "classe": p[2], "status": p[3]}
        for p in processo_repo.listar_por_cliente(cliente_id)
    ]
    return dados


@app.put("/clientes/{cliente_id}")
def atualizar_cliente(cliente_id: UUID, body: ClienteBody, authorization: Optional[str] = Header(None)):
    sessao = usuario_atual(authorization)
    cliente_repo.atualizar(
        cliente_id, body.nome, body.cpf_cnpj, body.idade, body.email, body.telefone, body.whatsapp, body.tipo_pessoa
    )
    log_repo.registrar(sessao["usuario_id"], "atualizar", "cliente", cliente_id)
    return {"ok": True}


@app.post("/clientes/{cliente_id}/desativar")
def desativar_cliente(cliente_id: UUID, authorization: Optional[str] = Header(None)):
    sessao = usuario_atual(authorization)
    cliente_repo.definir_ativo(cliente_id, False)
    log_repo.registrar(sessao["usuario_id"], "desativar", "cliente", cliente_id)
    return {"ok": True}


@app.post("/clientes/{cliente_id}/reativar")
def reativar_cliente(cliente_id: UUID, authorization: Optional[str] = Header(None)):
    sessao = usuario_atual(authorization)
    cliente_repo.definir_ativo(cliente_id, True)
    log_repo.registrar(sessao["usuario_id"], "reativar", "cliente", cliente_id)
    return {"ok": True}


# ---------------------------------------------------------------------------
# Processos
# ---------------------------------------------------------------------------

def _processos_visiveis(escritorio_id, usuario_id, lider):
    if lider:
        return processo_repo.listar_com_responsavel(escritorio_id)
    meus = processo_repo.listar_por_advogado(usuario_id)
    livres = processo_repo.listar_nao_atribuidos(escritorio_id)
    combinados = {p[0]: p for p in meus}
    combinados.update({p[0]: p for p in livres})
    # normaliza pro mesmo formato de listar_com_responsavel (id, numero_cnj, classe, assunto, status, adv_id, adv_nome)
    return [(p[0], p[3], p[4], p[5], p[8], p[9], None) for p in combinados.values()]


class ProcessoBody(BaseModel):
    numero_cnj: str
    classe: str
    assunto: Optional[str] = ""
    vara: Optional[str] = ""
    comarca: Optional[str] = ""
    status: str = "ativo"
    valor_causa: Optional[float] = None
    sigla_tribunal: Optional[str] = None
    atribuir_usuario_id: Optional[UUID] = None
    clientes_ids: list[UUID] = []


@app.get("/processos")
def listar_processos(authorization: Optional[str] = Header(None)):
    sessao = usuario_atual(authorization)
    lider = sessao["perfil"] == "lider"
    brutos = _processos_visiveis(sessao["escritorio_id"], sessao["usuario_id"], lider)
    return [serializar_processo_lista(p) for p in brutos]


@app.post("/processos")
def criar_processo(body: ProcessoBody, authorization: Optional[str] = Header(None)):
    sessao = usuario_atual(authorization)

    sigla_final = body.sigla_tribunal.strip() if body.sigla_tribunal and body.sigla_tribunal.strip() else detectar_sigla_tribunal(body.numero_cnj)

    processo = Processo(
        escritorio_id=sessao["escritorio_id"], numero_cnj=body.numero_cnj, classe=body.classe,
        assunto=body.assunto, vara=body.vara, comarca=body.comarca, status=body.status,
        valor_causa=body.valor_causa
    )
    processo_id = processo_repo.cadastrar(processo, clientes_ids=body.clientes_ids, sigla_tribunal=sigla_final)

    atribuir_para = body.atribuir_usuario_id
    if sessao["perfil"] != "lider":
        # advogado so pode atribuir a si mesmo
        atribuir_para = sessao["usuario_id"] if body.atribuir_usuario_id else None
    if atribuir_para:
        processo_repo.designar_advogado(processo_id, atribuir_para)

    log_repo.registrar(sessao["usuario_id"], "criar", "processo", processo_id)
    return {"id": str(processo_id), "tribunal_detectado": sigla_final}


def _checar_acesso_processo(sessao, processo_id):
    """Advogado so acessa processo que e' dele ou que esta livre; lider acessa tudo."""
    if sessao["perfil"] == "lider":
        return
    processo = processo_repo.obter_por_id(processo_id)
    if processo is None:
        raise HTTPException(404, "Processo nao encontrado.")
    advogado_id = processo[9]
    if advogado_id is not None and str(advogado_id) != str(sessao["usuario_id"]):
        raise HTTPException(403, "Este processo esta atribuido a outro advogado.")


@app.get("/processos/{processo_id}")
def obter_processo(processo_id: UUID, authorization: Optional[str] = Header(None)):
    sessao = usuario_atual(authorization)
    _checar_acesso_processo(sessao, processo_id)

    p = processo_repo.obter_por_id(processo_id)
    if p is None:
        raise HTTPException(404, "Processo nao encontrado.")
    # COLUNAS_PROCESSO: id, escritorio_id, tribunal_id, numero_cnj, classe, assunto,
    # vara, comarca, status, advogado_responsavel_id, criado_em, atualizado_em, valor_causa
    advogado_nome = None
    if p[9]:
        equipe = usuario_repo.listar_por_escritorio(sessao["escritorio_id"])
        advogado_nome = next((u[2] for u in equipe if str(u[0]) == str(p[9])), None)

    return {
        "id": str(p[0]), "numero_cnj": p[3], "classe": p[4], "assunto": p[5], "vara": p[6],
        "comarca": p[7], "status": p[8], "advogado_id": str(p[9]) if p[9] else None,
        "advogado_nome": advogado_nome, "valor_causa": _num(p[12]),
        "clientes_vinculados": [
            {"id": str(c[0]), "nome": c[1]} for c in processo_repo.listar_clientes_do_processo(processo_id)
        ],
        "movimentacoes": [serializar_movimentacao(m) for m in movimentacao_repo.listar_por_processo(processo_id)],
        "agenda": [serializar_compromisso(c) for c in compromisso_repo.listar_por_processo(processo_id)],
        "comentarios": [serializar_comentario(c) for c in comentario_repo.listar_por_processo(processo_id)],
    }


class ProcessoUpdateBody(BaseModel):
    classe: str
    assunto: Optional[str] = ""
    vara: Optional[str] = ""
    comarca: Optional[str] = ""
    status: str
    valor_causa: Optional[float] = None


@app.put("/processos/{processo_id}")
def atualizar_processo(processo_id: UUID, body: ProcessoUpdateBody, authorization: Optional[str] = Header(None)):
    sessao = usuario_atual(authorization)
    _checar_acesso_processo(sessao, processo_id)
    processo_repo.atualizar(processo_id, body.classe, body.assunto, body.vara, body.comarca, body.status, body.valor_causa)
    log_repo.registrar(sessao["usuario_id"], "atualizar", "processo", processo_id)
    return {"ok": True}


class AtribuirBody(BaseModel):
    usuario_id: Optional[UUID] = None


@app.post("/processos/{processo_id}/atribuir")
def atribuir_processo(processo_id: UUID, body: AtribuirBody, authorization: Optional[str] = Header(None)):
    sessao = usuario_atual(authorization)

    if sessao["perfil"] != "lider":
        # advogado so pode pegar pra si um processo livre - nao pode reatribuir a terceiros nem tomar de outro
        processo = processo_repo.obter_por_id(processo_id)
        if processo is None:
            raise HTTPException(404, "Processo nao encontrado.")
        if processo[9] is not None:
            raise HTTPException(403, "Este processo ja tem um responsavel.")
        if str(body.usuario_id) != str(sessao["usuario_id"]):
            raise HTTPException(403, "Voce so pode atribuir processos livres a si mesmo.")

    processo_repo.designar_advogado(processo_id, body.usuario_id)
    log_repo.registrar(sessao["usuario_id"], "atribuir", "processo", processo_id)
    return {"ok": True}


class MovimentacaoBody(BaseModel):
    tipo_evento: str
    descricao: str
    importancia: str = "media"
    data: date


@app.post("/processos/{processo_id}/movimentacoes")
def registrar_movimentacao(processo_id: UUID, body: MovimentacaoBody, authorization: Optional[str] = Header(None)):
    sessao = usuario_atual(authorization)
    _checar_acesso_processo(sessao, processo_id)

    resumo = f"[{body.tipo_evento}] {body.descricao}"
    movimentacao = Movimentacao(
        processo_id=processo_id, descricao_original=body.descricao, descricao_resumida=resumo,
        importancia=body.importancia, data_movimentacao=datetime.combine(body.data, datetime.min.time())
    )
    movimentacao_id = movimentacao_repo.cadastrar(movimentacao)

    relatorio = Relatorio(
        processo_id=processo_id, movimentacao_id=movimentacao_id,
        conteudo=resumo, canal_envio="whatsapp", status_envio="pendente"
    )
    relatorio_repo.cadastrar(relatorio)
    log_repo.registrar(sessao["usuario_id"], "registrar_movimentacao", "processo", processo_id)
    return {"ok": True}


class CompromissoBody(BaseModel):
    tipo: str
    descricao: str
    data_hora: datetime


@app.post("/processos/{processo_id}/compromissos")
def criar_compromisso(processo_id: UUID, body: CompromissoBody, authorization: Optional[str] = Header(None)):
    sessao = usuario_atual(authorization)
    _checar_acesso_processo(sessao, processo_id)
    compromisso = Compromisso(processo_id=processo_id, tipo=body.tipo, descricao=body.descricao, data_hora=body.data_hora)
    compromisso_repo.cadastrar(compromisso)
    log_repo.registrar(sessao["usuario_id"], "criar", "compromisso", processo_id)
    return {"ok": True}


class ComentarioBody(BaseModel):
    texto: str


@app.post("/processos/{processo_id}/comentarios")
def criar_comentario(processo_id: UUID, body: ComentarioBody, authorization: Optional[str] = Header(None)):
    sessao = usuario_atual(authorization)
    _checar_acesso_processo(sessao, processo_id)
    comentario = Comentario(processo_id=processo_id, usuario_id=sessao["usuario_id"], texto=body.texto)
    comentario_repo.cadastrar(comentario)
    log_repo.registrar(sessao["usuario_id"], "comentar", "processo", processo_id)
    return {"ok": True}


# ---------------------------------------------------------------------------
# Agenda
# ---------------------------------------------------------------------------

@app.get("/agenda")
def listar_agenda(incluir_concluidos: bool = False, authorization: Optional[str] = Header(None)):
    sessao = usuario_atual(authorization)
    lider = sessao["perfil"] == "lider"
    advogado_filtro = None if lider else sessao["usuario_id"]

    brutos = compromisso_repo.listar_proximos(sessao["escritorio_id"], advogado_id=advogado_filtro, incluir_concluidos=incluir_concluidos)
    return [
        {
            "id": str(c[0]), "tipo": c[1], "descricao": c[2],
            "data_hora": c[3].isoformat() if c[3] else None, "concluido": c[4],
            "processo_numero": c[6], "advogado_nome": c[7],
        }
        for c in brutos
    ]


@app.post("/compromissos/{compromisso_id}/concluir")
def concluir_compromisso(compromisso_id: UUID, authorization: Optional[str] = Header(None)):
    usuario_atual(authorization)
    compromisso_repo.marcar_concluido(compromisso_id)
    return {"ok": True}


# ---------------------------------------------------------------------------
# Avisos
# ---------------------------------------------------------------------------

def _avisos_visiveis(sessao):
    todos = relatorio_repo.listar_pendentes(escritorio_id=sessao["escritorio_id"])
    if sessao["perfil"] == "lider":
        return todos
    meus_ids = {p[0] for p in processo_repo.listar_por_advogado(sessao["usuario_id"])}
    return [a for a in todos if a[6] in meus_ids]


@app.get("/avisos")
def listar_avisos(authorization: Optional[str] = Header(None)):
    sessao = usuario_atual(authorization)
    return [serializar_aviso(a) for a in _avisos_visiveis(sessao)]


@app.post("/avisos/{relatorio_id}/marcar-enviado")
def marcar_aviso_enviado(relatorio_id: UUID, authorization: Optional[str] = Header(None)):
    usuario_atual(authorization)
    relatorio_repo.marcar_como_enviado(relatorio_id)
    return {"ok": True}


# ---------------------------------------------------------------------------
# Busca
# ---------------------------------------------------------------------------

@app.get("/buscar")
def buscar(termo: str, authorization: Optional[str] = Header(None)):
    sessao = usuario_atual(authorization)
    resultado = busca_repo.buscar_geral(sessao["escritorio_id"], termo)
    return {
        "clientes": [
            {"id": str(c[0]), "nome": c[1], "cpf_cnpj": c[2], "telefone": c[3], "whatsapp": c[4]}
            for c in resultado["clientes"]
        ],
        "processos": [
            {"id": str(p[0]), "numero_cnj": p[1], "classe": p[2], "assunto": p[3], "status": p[4]}
            for p in resultado["processos"]
        ],
    }


# ---------------------------------------------------------------------------
# Equipe (lider)
# ---------------------------------------------------------------------------

class MembroBody(BaseModel):
    nome: str
    email: str
    senha: str
    perfil: str = "advogado"


@app.get("/equipe")
def listar_equipe(authorization: Optional[str] = Header(None)):
    sessao = usuario_atual(authorization)
    exigir_lider(sessao)
    brutos = usuario_repo.listar_por_escritorio(sessao["escritorio_id"])
    return [{"id": str(u[0]), "nome": u[2], "email": u[3], "perfil": u[4], "ativo": u[5]} for u in brutos]


@app.post("/equipe")
def criar_membro(body: MembroBody, authorization: Optional[str] = Header(None)):
    sessao = usuario_atual(authorization)
    exigir_lider(sessao)
    if usuario_repo.email_ja_existe(body.email):
        raise HTTPException(400, "Ja existe um usuario com esse e-mail.")
    novo = Usuario(escritorio_id=sessao["escritorio_id"], nome=body.nome, email=body.email, perfil=body.perfil, ativo=True)
    usuario_id = usuario_repo.cadastrar(novo, body.senha)
    return {"id": str(usuario_id)}


# ---------------------------------------------------------------------------
# Relatorio (lider)
# ---------------------------------------------------------------------------

@app.get("/relatorio/movimentacoes")
def relatorio_movimentacoes(
    data_inicio: Optional[datetime] = None, data_fim: Optional[datetime] = None,
    ordenar_por: str = "recente", formato: str = "json", authorization: Optional[str] = Header(None)
):
    sessao = usuario_atual(authorization)
    exigir_lider(sessao)
    brutos = relatorio_gerencial_repo.listar_movimentacoes(
        sessao["escritorio_id"], data_inicio=data_inicio, data_fim=data_fim, ordenar_por=ordenar_por
    )
    linhas = [
        {
            "id": str(m[0]), "descricao": m[1], "importancia": m[2],
            "data": m[3].isoformat() if m[3] else None, "processo_numero": m[5], "advogado_nome": m[6],
        }
        for m in brutos
    ]
    if formato == "csv":
        return _csv_response(linhas, ["data", "importancia", "processo_numero", "advogado_nome", "descricao"], "movimentacoes.csv")
    return linhas


@app.get("/relatorio/parados")
def relatorio_parados(ordem: str = "mais_tempo", formato: str = "json", authorization: Optional[str] = Header(None)):
    sessao = usuario_atual(authorization)
    exigir_lider(sessao)
    brutos = relatorio_gerencial_repo.listar_processos_por_tempo_sem_atualizacao(sessao["escritorio_id"], ordem=ordem)
    linhas = [
        {
            "numero_cnj": p[1], "status": p[2], "advogado_nome": p[3],
            "ultima_movimentacao": p[4].isoformat() if p[4] else None,
        }
        for p in brutos
    ]
    if formato == "csv":
        return _csv_response(linhas, ["numero_cnj", "status", "advogado_nome", "ultima_movimentacao"], "processos_parados.csv")
    return linhas


# ---------------------------------------------------------------------------
# Relatórios avançados
# ---------------------------------------------------------------------------

def _csv_response(linhas, colunas, nome_arquivo):
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=colunas, extrasaction="ignore")
    writer.writeheader()
    for linha in linhas:
        writer.writerow(linha)
    return Response(
        content=buffer.getvalue(), media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{nome_arquivo}"'}
    )


@app.get("/relatorio/produtividade")
def relatorio_produtividade(
    data_inicio: Optional[datetime] = None, data_fim: Optional[datetime] = None,
    formato: str = "json", authorization: Optional[str] = Header(None)
):
    sessao = usuario_atual(authorization)
    exigir_lider(sessao)
    dados = relatorio_avancado_repo.produtividade_por_advogado(
        sessao["escritorio_id"], data_inicio=data_inicio, data_fim=data_fim
    )
    if formato == "csv":
        return _csv_response(
            dados, ["nome", "processos_ativos", "movimentacoes_periodo", "horas_medias_ate_avisar"],
            "produtividade.csv"
        )
    return dados


@app.get("/relatorio/distribuicao")
def relatorio_distribuicao(
    secao: Optional[str] = None, formato: str = "json", authorization: Optional[str] = Header(None)
):
    sessao = usuario_atual(authorization)
    exigir_lider(sessao)
    dados = relatorio_avancado_repo.distribuicao_carteira(sessao["escritorio_id"])

    if formato == "csv":
        chave_secao = {
            "status": "por_status", "classe": "por_classe",
            "comarca": "por_comarca", "sincronizacao": "sincronizacao",
        }.get(secao, "por_status")
        return _csv_response(dados[chave_secao], ["chave", "total"], f"distribuicao_{chave_secao}.csv")
    return dados


@app.get("/relatorio/cliente/{cliente_id}")
def relatorio_cliente(cliente_id: UUID, formato: str = "json", authorization: Optional[str] = Header(None)):
    usuario_atual(authorization)
    dados = relatorio_avancado_repo.historico_cliente(cliente_id)

    if formato == "csv":
        return _csv_response(
            dados["movimentacoes"], ["processo_numero", "data", "importancia", "descricao"],
            "historico_cliente.csv"
        )
    return dados


@app.get("/relatorio/prazos")
def relatorio_prazos(formato: str = "json", authorization: Optional[str] = Header(None)):
    sessao = usuario_atual(authorization)
    advogado_id = None if sessao["perfil"] == "lider" else sessao["usuario_id"]
    dados = relatorio_avancado_repo.cumprimento_prazos(sessao["escritorio_id"], advogado_id=advogado_id)

    if formato == "csv":
        return _csv_response(dados["por_tipo"], ["tipo", "total", "concluidos"], "prazos_por_tipo.csv")
    return dados


@app.get("/relatorio/qualidade")
def relatorio_qualidade(formato: str = "json", authorization: Optional[str] = Header(None)):
    sessao = usuario_atual(authorization)
    exigir_lider(sessao)
    dados = relatorio_avancado_repo.qualidade_dados(sessao["escritorio_id"])

    if formato == "csv":
        linhas = (
            [{"categoria": "sem_tribunal", "numero_cnj": n} for n in dados["sem_tribunal"]]
            + [{"categoria": "sem_advogado", "numero_cnj": n} for n in dados["sem_advogado"]]
            + [{"categoria": "sem_movimentacao", "numero_cnj": n} for n in dados["sem_movimentacao"]]
        )
        return _csv_response(linhas, ["categoria", "numero_cnj"], "qualidade_dados.csv")
    return dados
