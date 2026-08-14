"""
Interpreta a numeracao unica de processos do CNJ (Resolucao 65/2008):

    NNNNNNN-DD.AAAA.J.TR.OOOO

J  = segmento do Poder Judiciario (1 digito)
TR = tribunal daquele segmento (2 digitos)

Fonte da tabela de segmentos (J): Resolucao CNJ 65/2008 / Portal CNJ -
Perguntas Frequentes sobre Numeracao Unica.
Fonte da tabela de TJs (J=8): compilacao publica dos codigos de tribunal
estadual (numeracao unica), confirmada via busca em 2026.

IMPORTANTE: essa tabela cobre Justica Estadual (J=8, todas as siglas),
Justica Federal (J=4, TRF1-TRF6) e Justica do Trabalho (J=5, TRT1-TRT24)
com confianca alta. Justica Eleitoral (J=6) e Justica Militar (J=7, J=9)
NAO tem mapeamento automatico aqui porque nao foi possivel confirmar a
tabela de codigos com segurança - nesses casos, a sigla precisa ser
preenchida manualmente no cadastro do processo.
"""

import re

SEGMENTO_TJ = {
    "01": "tjac", "02": "tjal", "03": "tjap", "04": "tjam", "05": "tjba",
    "06": "tjce", "07": "tjdft", "08": "tjes", "09": "tjgo", "10": "tjma",
    "11": "tjmt", "12": "tjms", "13": "tjmg", "14": "tjpa", "15": "tjpb",
    "16": "tjpr", "17": "tjpe", "18": "tjpi", "19": "tjrj", "20": "tjrn",
    "21": "tjrs", "22": "tjro", "23": "tjrr", "24": "tjsc", "25": "tjse",
    "26": "tjsp", "27": "tjto",
}


def limpar_numero(numero_cnj: str) -> str:
    return re.sub(r"\D", "", numero_cnj or "")


def interpretar(numero_cnj: str) -> dict | None:
    """
    Retorna um dict com os campos decompostos, ou None se o numero nao
    tiver os 20 digitos esperados.
    """
    numero = limpar_numero(numero_cnj)

    if len(numero) != 20:
        return None

    return {
        "sequencial": numero[0:7],
        "digito_verificador": numero[7:9],
        "ano": numero[9:13],
        "segmento": numero[13:14],
        "tribunal": numero[14:16],
        "origem": numero[16:20],
    }


def detectar_sigla_tribunal(numero_cnj: str) -> str | None:
    """
    Tenta descobrir a sigla do tribunal (formato usado pelo DataJud, ex:
    'tjsp', 'trf3', 'trt2') so a partir do numero do processo.
    Retorna None se nao for possivel detectar com confiança.
    """
    partes = interpretar(numero_cnj)
    if partes is None:
        return None

    segmento = partes["segmento"]
    tribunal = partes["tribunal"]

    if segmento == "8":  # Justica Estadual
        return SEGMENTO_TJ.get(tribunal)

    if segmento == "4":  # Justica Federal (TRF1 a TRF6)
        try:
            numero_regiao = int(tribunal)
            if 1 <= numero_regiao <= 6:
                return f"trf{numero_regiao}"
        except ValueError:
            pass
        return None

    if segmento == "5":  # Justica do Trabalho (TRT1 a TRT24)
        try:
            numero_regiao = int(tribunal)
            if 1 <= numero_regiao <= 24:
                return f"trt{numero_regiao}"
        except ValueError:
            pass
        return None

    if segmento == "1":
        return "stf"

    if segmento == "3":
        return "stj"

    # segmento 6 (eleitoral), 7 e 9 (militar): sem tabela confirmada
    return None
