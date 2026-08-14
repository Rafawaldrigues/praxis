import re
import requests

# Chave publica atual, divulgada pelo CNJ para uso livre da API Publica do
# DataJud. O CNJ pode trocar essa chave a qualquer momento - se parar de
# funcionar, pega a chave atualizada em:
# https://datajud-wiki.cnj.jus.br/api-publica/acesso
CHAVE_PUBLICA_DATAJUD = "cDZHYzlZa0JadVREZDJCendQbXY6SkJlTzNjLV9TRENyQk1RdnFKZGRQdw=="

URL_BASE = "https://api-publica.datajud.cnj.jus.br"


def _numero_sem_formatacao(numero_cnj: str) -> str:
    return re.sub(r"\D", "", numero_cnj)


def consultar_processo(numero_cnj: str, sigla_tribunal: str) -> dict | None:
    """
    Consulta um processo pelo numero CNJ no tribunal informado.

    sigla_tribunal: alias do DataJud em minusculo, ex: 'tjsp', 'trf1', 'tre-sp'.
    Lista completa: https://datajud-wiki.cnj.jus.br/api-publica/endpoints

    Retorna o dict "_source" do primeiro resultado (dados do processo +
    lista de movimentos) ou None se nao encontrar nada.

    OBS: nao foi possivel testar contra a API real neste ambiente (sem
    acesso a internet externa aqui) - testa isso rodando local antes de
    colocar pra rodar automatico.
    """

    sigla_tribunal = sigla_tribunal.lower().strip()
    url = f"{URL_BASE}/api_publica_{sigla_tribunal}/_search"

    headers = {
        "Authorization": f"APIKey {CHAVE_PUBLICA_DATAJUD}",
        "Content-Type": "application/json",
    }

    body = {
        "query": {
            "match": {
                "numeroProcesso": _numero_sem_formatacao(numero_cnj)
            }
        }
    }

    resposta = requests.get(url, headers=headers, json=body, timeout=30)
    resposta.raise_for_status()

    dados = resposta.json()
    hits = dados.get("hits", {}).get("hits", [])

    if not hits:
        return None

    return hits[0]["_source"]
