"""
Sincroniza os processos ativos com a API Publica do DataJud (CNJ).

Pra cada processo que tenha uma sigla de tribunal real cadastrada:
  1. Consulta o DataJud pelo numero CNJ
  2. Compara os movimentos retornados com a ultima movimentacao ja salva
  3. Pra cada movimento novo: salva em `movimentacao` e cria um
     `relatorio` pendente (mesmo fluxo que a aba "Registrar Atualizacao"
     do app ja faz manualmente)

Como rodar manualmente:
    python -m servicos.sincronizar_processos

Como automatizar (exemplos):
  - cron (Linux/Mac), rodando 1x por dia as 7h:
        0 7 * * * cd /caminho/do/projeto && /caminho/do/venv/bin/python -m servicos.sincronizar_processos
  - Agendador de Tarefas do Windows, apontando pro mesmo comando.

IMPORTANTE: nao foi possivel testar este script contra a API real do
DataJud neste ambiente (sandbox sem acesso a internet externa). Roda
local com 1-2 processos reais antes de confiar/automatizar - os nomes
dos campos retornados pelo DataJud podem variar entre tribunais.
"""

import time
from datetime import datetime

from models.movimentacao import Movimentacao
from models.relatorio import Relatorio
from repositories.processo_repository import ProcessoRepository
from repositories.movimentacao_repository import MovimentacaoRepository
from repositories.relatorio_repository import RelatorioRepository
from servicos.datajud_client import consultar_processo


processo_repo = ProcessoRepository()
movimentacao_repo = MovimentacaoRepository()
relatorio_repo = RelatorioRepository()


def _classificar_importancia(nome_movimento: str) -> str:
    """
    Classificacao simples por palavra-chave, so pra nao deixar tudo como
    'media'. Isso e o que a IA (ainda nao integrada) faria de forma
    mais inteligente no futuro.
    """
    nome = (nome_movimento or "").lower()

    palavras_alta = ["sentença", "sentenca", "audiência", "audiencia", "decisão", "decisao", "citação", "citacao"]
    palavras_baixa = ["conclusão", "conclusao", "certidão", "certidao", "remessa", "distribuição", "distribuicao"]

    if any(p in nome for p in palavras_alta):
        return "alta"
    if any(p in nome for p in palavras_baixa):
        return "baixa"
    return "media"


def _parse_data_hora(valor):
    """
    O DataJud costuma retornar dataHora em formato ISO (ex:
    '2023-08-01T10:15:00.000Z'). Converte pra datetime "ingenuo"
    (sem timezone) pra poder comparar direto com o que ja esta no banco.
    """
    if not valor:
        return None

    texto = str(valor).replace("Z", "+00:00")

    try:
        convertido = datetime.fromisoformat(texto)
    except ValueError:
        try:
            convertido = datetime.fromisoformat(texto.split(".")[0])
        except ValueError:
            return None

    return convertido.replace(tzinfo=None)


def sincronizar_processo(processo_id, numero_cnj, sigla_tribunal):
    fonte = consultar_processo(numero_cnj, sigla_tribunal)

    if fonte is None:
        print(f"  [{numero_cnj}] não encontrado no DataJud ({sigla_tribunal}).")
        return 0

    movimentos = fonte.get("movimentos", [])
    if not movimentos:
        print(f"  [{numero_cnj}] sem movimentos retornados.")
        return 0

    ultima_data_salva = movimentacao_repo.obter_data_ultima_movimentacao(processo_id)

    novos = 0
    for movimento in movimentos:
        data_hora = _parse_data_hora(movimento.get("dataHora"))
        nome = movimento.get("nome", "")

        if not data_hora:
            continue

        # so importa o que e mais novo do que a ultima movimentacao ja salva
        if ultima_data_salva and data_hora <= ultima_data_salva:
            continue

        movimentacao = Movimentacao(
            processo_id=processo_id,
            descricao_original=nome,
            descricao_resumida=nome,  # aqui entraria a IA resumindo, no futuro
            importancia=_classificar_importancia(nome),
            data_movimentacao=data_hora
        )
        movimentacao_id = movimentacao_repo.cadastrar(movimentacao)

        relatorio = Relatorio(
            processo_id=processo_id,
            movimentacao_id=movimentacao_id,
            conteudo=nome,
            canal_envio="whatsapp",
            status_envio="pendente"
        )
        relatorio_repo.cadastrar(relatorio)

        novos += 1

    print(f"  [{numero_cnj}] {novos} movimento(s) novo(s) importado(s).")
    return novos


def main():
    processos = processo_repo.listar_ativos_com_tribunal()

    if not processos:
        print("Nenhum processo elegível (com sigla de tribunal cadastrada) para sincronizar.")
        return

    print(f"Sincronizando {len(processos)} processo(s)...")

    total_novos = 0
    for processo_id, numero_cnj, sigla_tribunal in processos:
        try:
            total_novos += sincronizar_processo(processo_id, numero_cnj, sigla_tribunal)
        except Exception as erro:
            print(f"  [{numero_cnj}] erro ao consultar: {erro}")

        time.sleep(1)  # evita martelar a API muito rápido

    print(f"Concluído. {total_novos} movimentação(ões) nova(s) no total.")


if __name__ == "__main__":
    main()
