"""Ranqueamento linear supervisionado exclusivamente por alvos numéricos de treino.

Cada questão contribui com a média da perda logística dos seus pares positivo /
negativo. Selecionamos, na ordem recebida, até cinco positivos e vinte negativos;
o chamador ordena os candidatos por recuperação antes de fornecer os dados.
Os atributos são padronizados sobre todos os candidatos de treino, sem consultar
os alvos. Não há intercepto: ele se anularia na diferença entre candidatos.
O escore retornado é um valor de ordenação, não probabilidade de acerto.
"""

from __future__ import annotations

import math


SCHEMA = "ranking_linear_pares_m7_v1"
PASSOS = 300
PASSO = 0.1
REGULARIZACAO = 1.0
MAX_POSITIVOS = 5
MAX_NEGATIVOS = 20


def _numero(valor: object) -> float:
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        raise ValueError("Atributos e parâmetros devem ser números finitos.")
    try:
        resultado = float(valor)
    except (ValueError, OverflowError):
        raise ValueError("Atributo fora do intervalo numérico.") from None
    if not math.isfinite(resultado):
        raise ValueError("Atributos e parâmetros devem ser números finitos.")
    return resultado


def _vetor(valores: object, dimensoes: int) -> list[float]:
    if not isinstance(valores, list) or len(valores) != dimensoes:
        raise ValueError("Dimensão de atributos incompatível.")
    return [_numero(valor) for valor in valores]


def _produto(a: list[float], b: list[float]) -> float:
    try:
        resultado = math.fsum(x * y for x, y in zip(a, b))
    except (ValueError, OverflowError):
        raise ValueError("Produto escalar fora do intervalo numérico.") from None
    return _numero(resultado)


def _padronizar(linha: list[float], centros: list[float], escalas: list[float]) -> list[float]:
    return [_numero((valor - centro) / escala)
            for valor, centro, escala in zip(linha, centros, escalas)]


def _erro(margem: float) -> float:
    """Sigmoide de -margem, sem overflow na exponencial."""
    if margem >= 0:
        e = math.exp(-margem)
        return e / (1.0 + e)
    return 1.0 / (1.0 + math.exp(margem))


def _objetivo(pesos: list[float], grupos: list[list[list[float]]]) -> float:
    perdas = []
    for pares in grupos:
        margens = [_produto(pesos, par) for par in pares]
        perdas.append(math.fsum(
            max(-m, 0.0) + math.log1p(math.exp(-abs(m))) for m in margens
        ) / len(pares))
    return _numero(math.fsum(perdas) / len(grupos)
                   + 0.5 * REGULARIZACAO * math.fsum(p * p for p in pesos))


def _gradiente(pesos: list[float], grupos: list[list[list[float]]]) -> list[float]:
    gradiente = [REGULARIZACAO * peso for peso in pesos]
    for pares in grupos:
        fator = 1.0 / (len(grupos) * len(pares))
        erros = [-_erro(_produto(pesos, par)) * fator for par in pares]
        for j in range(len(pesos)):
            gradiente[j] += math.fsum(erro * par[j] for erro, par in zip(erros, pares))
    return [_numero(g) for g in gradiente]


def ajustar(pares_por_questao: list[list[dict]], dimensoes: int) -> dict:
    """Ajusta 300 passos determinísticos de gradiente, sem consultar dados externos."""
    if type(dimensoes) is not int or dimensoes <= 0:
        raise ValueError("A dimensão deve ser um inteiro positivo.")
    if not isinstance(pares_por_questao, list) or not pares_por_questao:
        raise ValueError("O treino deve conter questões e candidatos.")
    questoes, todas = [], []
    for questao in pares_por_questao:
        if not isinstance(questao, list) or not questao:
            raise ValueError("Cada questão deve conter candidatos de treino.")
        candidatos = []
        for candidato in questao:
            if (not isinstance(candidato, dict)
                    or type(candidato.get("positivo")) is not bool):
                raise ValueError("Cada candidato deve ter alvo positivo booleano.")
            linha = _vetor(candidato.get("atributos"), dimensoes)
            candidatos.append((linha, candidato["positivo"]))
            todas.append(linha)
        questoes.append(candidatos)

    centros, escalas = [], []
    try:
        for j in range(dimensoes):
            centro = _numero(math.fsum(linha[j] for linha in todas) / len(todas))
            escala = _numero(math.hypot(*(linha[j] - centro for linha in todas))
                              / math.sqrt(len(todas)))
            centros.append(centro)
            escalas.append(escala or 1.0)
    except (ValueError, OverflowError):
        raise ValueError("Escala de atributos fora do intervalo numérico.") from None

    grupos = []
    for candidatos in questoes:
        positivos = [linha for linha, alvo in candidatos if alvo][:MAX_POSITIVOS]
        negativos = [linha for linha, alvo in candidatos if not alvo][:MAX_NEGATIVOS]
        if not positivos or not negativos:
            continue
        positivos = [_padronizar(linha, centros, escalas) for linha in positivos]
        negativos = [_padronizar(linha, centros, escalas) for linha in negativos]
        grupos.append([[_numero(p - n) for p, n in zip(pos, neg)]
                       for pos in positivos for neg in negativos])
    if not grupos:
        raise ValueError("O treino precisa de ao menos uma questão com pares positivos e negativos.")

    pesos = [0.0] * dimensoes
    inicial = _objetivo(pesos, grupos)
    for _ in range(PASSOS):
        gradiente = _gradiente(pesos, grupos)
        pesos = [_numero(p - PASSO * g) for p, g in zip(pesos, gradiente)]
    final = _objetivo(pesos, grupos)
    return {
        "schema": SCHEMA,
        "dimensoes": dimensoes,
        "pesos": pesos,
        "centros": centros,
        "escalas": escalas,
        "diagnostico": {
            "questoes": len(questoes),
            "candidatos": len(todas),
            "questoes_com_pares": len(grupos),
            "questoes_sem_pares": len(questoes) - len(grupos),
            "pares": sum(len(grupo) for grupo in grupos),
            "max_positivos_por_questao": MAX_POSITIVOS,
            "max_negativos_por_questao": MAX_NEGATIVOS,
            "regularizacao": REGULARIZACAO,
            "passos": PASSOS,
            "passo": PASSO,
            "objetivo_inicial": inicial,
            "objetivo_final": final,
            "norma_gradiente_final": math.hypot(*_gradiente(pesos, grupos)),
        },
    }


def pontuar(modelo: dict, atributos: list[float]) -> float:
    """Aplica as estatísticas salvas; a consulta nunca ajusta a representação."""
    if not isinstance(modelo, dict) or modelo.get("schema") != SCHEMA:
        raise ValueError("Esquema de ranker incompatível.")
    dimensoes = modelo.get("dimensoes")
    if type(dimensoes) is not int or dimensoes <= 0:
        raise ValueError("Dimensão do ranker inválida.")
    pesos = _vetor(modelo.get("pesos"), dimensoes)
    centros = _vetor(modelo.get("centros"), dimensoes)
    escalas = _vetor(modelo.get("escalas"), dimensoes)
    if any(escala <= 0 for escala in escalas):
        raise ValueError("Escalas do ranker devem ser positivas.")
    linha = _vetor(atributos, dimensoes)
    return _produto(pesos, _padronizar(linha, centros, escalas))
